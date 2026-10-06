from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Job, Project, Scene
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import SceneTimelineMaster
from app.director_timeline_w46.scene_publish import (
    magi_upscale_full_stitch,
    persist_scene_upscaled_asset,
    publish_scene,
    publish_status,
)
from app.generation_tools.lineage import register_derived_asset
from app.magi.upscale_targets import TARGET_NOT_ABOVE, UpscaleTargetError
from app.magi.upscaling import enqueue_upscale, run_upscale_job


def _seed_ready_scene(db: Session, tmp_path: Path):
    pid = f"p_{uuid.uuid4().hex[:8]}"
    sid = f"s_{uuid.uuid4().hex[:8]}"
    db.add(Project(id=pid, name="MAGI Upscale Convergence"))
    db.add(Scene(id=sid, project_id=pid, name="Scene", duration_sec=30.0, prompt=""))
    db.commit()
    media = tmp_path / "projects" / pid / "assets"
    media.mkdir(parents=True, exist_ok=True)
    stitch_file = media / "stitch_src.mp4"
    stitch_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    stitch_id = f"ast_{uuid.uuid4().hex[:8]}"
    db.add(
        Asset(
            id=stitch_id,
            project_id=pid,
            tag="scene_stitch",
            kind="video",
            filename=stitch_file.name,
            path=str(stitch_file),
        )
    )
    db.commit()
    master = SceneTimelineMaster.model_validate(
        {
            "migratedFromDirectorJson": False,
            "batchBlocks": [
                {
                    "id": "bb1",
                    "sceneId": sid,
                    "order": 0,
                    "status": "Approved",
                    "approvedClip": {"assetId": "batch-a1", "executionSnapshotId": "snap1"},
                }
            ],
            "sceneStitch": {
                "assetId": stitch_id,
                "sourceBatchIds": ["bb1"],
                "sourceAssetIds": ["batch-a1"],
            },
            "sceneFinalCheck": {
                "lifecycleStatus": "SCENE_FINISHED",
                "creatorVerdict": "FINAL CHECK PASSED / SCENE FINISHED",
                "categories": [],
            },
        }
    )
    store.save_master(db, pid, sid, master, touch_batches=False)
    return pid, sid, stitch_id


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    from app import config
    from app.db import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    db = SessionLocal()
    yield db
    db.close()


def test_enqueue_refuses_1080_to_1080(db_session, tmp_path, monkeypatch):
    pid, sid, stitch_id = _seed_ready_scene(db_session, tmp_path)
    monkeypatch.setattr("app.magi.upscaling.probe_media", lambda _p: {"width": 1920, "height": 1080})
    with pytest.raises(UpscaleTargetError) as exc:
        enqueue_upscale(
            db_session,
            project_id=pid,
            asset_id=stitch_id,
            engine="ffmpeg-scale",
            model="lanczos",
            target_resolution="1920x1080",
            preview=False,
            scene_id=sid,
            persist_scene_publish=True,
        )
    assert exc.value.code == TARGET_NOT_ABOVE


def test_preview_cannot_set_persist_scene_publish(db_session, tmp_path, monkeypatch):
    pid, sid, stitch_id = _seed_ready_scene(db_session, tmp_path)
    captured: dict = {}

    def fake_enqueue(db, **kwargs):
        captured.update(kwargs)
        return Job(
            id="job-preview",
            project_id=pid,
            kind="magi_upscale",
            status="running",
            params_json=json.dumps(kwargs.get("params") or {}),
        )

    monkeypatch.setattr("app.magi.jobs.enqueue_job", fake_enqueue)
    monkeypatch.setattr("app.magi.jobs.find_active_duplicate", lambda *_a, **_k: None)
    monkeypatch.setattr("app.magi.upscaling.probe_media", lambda _p: {"width": 1280, "height": 720})
    enqueue_upscale(
        db_session,
        project_id=pid,
        asset_id=stitch_id,
        engine="ffmpeg-scale",
        model="lanczos",
        target_resolution="1080p",
        preview=True,
        scene_id=sid,
        persist_scene_publish=True,
    )
    assert captured["params"]["preview"] is True
    assert captured["params"]["persistScenePublish"] is False


def test_timeline_enqueue_does_not_persist_asset_id(db_session, tmp_path, monkeypatch):
    pid, sid, stitch_id = _seed_ready_scene(db_session, tmp_path)

    def fake_apply(*_a, **_k):
        return {"ok": True, "queued": True, "jobId": "job-queued"}

    monkeypatch.setattr("app.magi.upscaling.apply_upscale", fake_apply)
    result = magi_upscale_full_stitch(
        db_session,
        pid,
        sid,
        engine="ffmpeg-scale",
        model="lanczos",
        target_resolution="1440p",
    )
    assert result["ok"] is True
    assert result["jobId"] == "job-queued"
    assert result["upscaledAssetId"] is None
    payload = store.load_master(db_session, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert master.scenePublish is None or not master.scenePublish.upscaledAssetId


def test_job_completion_persists_upscaled_asset_before_publish(db_session, tmp_path, monkeypatch):
    pid, sid, _stitch_id = _seed_ready_scene(db_session, tmp_path)
    monkeypatch.setattr(
        "app.magi.upscaling.upscale_asset",
        lambda *_a, **_k: {"ok": True, "assetId": "up-derived-1"},
    )
    job = Job(
        id=f"job_{uuid.uuid4().hex[:8]}",
        project_id=pid,
        kind="magi_upscale",
        status="running",
        params_json=json.dumps(
            {
                "preview": False,
                "persistScenePublish": True,
                "sceneId": sid,
                "assetId": "src",
            }
        ),
    )
    db_session.add(job)
    db_session.commit()
    result = run_upscale_job(db_session, job)
    assert result["ok"] is True
    assert result["upscaledAssetId"] == "up-derived-1"
    payload = store.load_master(db_session, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert master.scenePublish is not None
    assert master.scenePublish.publishedAssetId == ""
    assert master.scenePublish.upscaledAssetId == "up-derived-1"
    assert master.scenePublish.upscalePendingPublish is True
    chrome = publish_status(master)
    assert chrome["showPublish"] is True
    assert chrome["hasPublished"] is False


def test_persist_helper_writes_draft_publish_state(db_session, tmp_path):
    pid, sid, _stitch_id = _seed_ready_scene(db_session, tmp_path)
    result = persist_scene_upscaled_asset(db_session, pid, sid, "up-draft-1")
    assert result["ok"] is True
    payload = store.load_master(db_session, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert master.scenePublish.publishedAssetId == ""
    assert master.scenePublish.upscaledAssetId == "up-draft-1"


def test_first_publish_can_use_upscaled_source(db_session, tmp_path):
    pid, sid, stitch_id = _seed_ready_scene(db_session, tmp_path)
    media = tmp_path / "projects" / pid / "assets"
    up_file = media / "upscaled.mp4"
    up_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x33" * 64)
    up_id = f"up_{uuid.uuid4().hex[:8]}"
    db_session.add(
        Asset(
            id=up_id,
            project_id=pid,
            tag="magi_upscale",
            kind="video",
            filename=up_file.name,
            path=str(up_file),
            parent_asset_id=stitch_id,
        )
    )
    db_session.commit()
    persist_scene_upscaled_asset(db_session, pid, sid, up_id)
    result = publish_scene(db_session, pid, sid, source="upscaled")
    assert result["ok"] is True, result
    assert result["scenePublish"]["publishSource"] == "upscaled"
    assert result["scenePublish"]["upscaledAssetId"] == up_id
    assert result["scenePublish"]["upscalePendingPublish"] is False
    assert result["scenePublish"]["publishedAssetId"]
    assert result["scenePublish"]["publishedAssetId"] != stitch_id


def test_library_assign_failure_fails_magi_upscale(db_session, tmp_path, monkeypatch):
    pid, _sid, _stitch_id = _seed_ready_scene(db_session, tmp_path)
    src = tmp_path / "projects" / pid / "assets" / "derived.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x11" * 64)

    def boom(*_a, **_k):
        raise RuntimeError("assign exploded")

    monkeypatch.setattr("app.project_library.service.assign_asset", boom)
    with pytest.raises(RuntimeError, match="Library registration failed"):
        register_derived_asset(
            db_session,
            project_id=pid,
            source_path=src,
            kind="video",
            tag="magi_upscale",
            parent_asset_id="parent-1",
            op="upscale",
            model="lanczos",
            library_key="video.generated",
        )


def test_library_assign_failure_still_swallowed_for_other_ops(db_session, tmp_path, monkeypatch):
    pid, _sid, _stitch_id = _seed_ready_scene(db_session, tmp_path)
    src = tmp_path / "projects" / pid / "assets" / "grade.mp4"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x22" * 64)

    def boom(*_a, **_k):
        raise RuntimeError("assign exploded")

    monkeypatch.setattr("app.project_library.service.assign_asset", boom)
    asset = register_derived_asset(
        db_session,
        project_id=pid,
        source_path=src,
        kind="video",
        tag="magi_grade",
        parent_asset_id="parent-1",
        op="color",
        model="grade",
        library_key="video.generated",
    )
    assert asset.id
