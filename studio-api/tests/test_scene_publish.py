"""Timeline Publish readiness, refuse-before-pass, provenance, dirty/update, MAGI full-stitch gate."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import store
from app.director_timeline_w46.contracts import (
    SceneFinalCheck,
    ScenePublishState,
    SceneStitch,
    SceneTimelineMaster,
)
from app.director_timeline_w46.scene_publish import (
    PUBLISH_READY_LIFECYCLES,
    _allowed_magi_asset_ids,
    _choose_magi_source,
    changes_pending,
    content_fingerprint,
    is_publish_ready,
    magi_upscale_full_stitch,
    persist_scene_upscaled_asset,
    publish_scene,
    publish_status,
)


def _master(**kwargs) -> SceneTimelineMaster:
    base = {
        "migratedFromDirectorJson": False,
        "batchBlocks": [],
    }
    base.update(kwargs)
    return SceneTimelineMaster.model_validate(base)


def test_publish_ready_lifecycles():
    assert "SCENE_FINISHED" in PUBLISH_READY_LIFECYCLES
    assert "SCENE_FINISHED_WITH_ACCEPTED_ISSUES" in PUBLISH_READY_LIFECYCLES
    assert "FINAL_CHECK" not in PUBLISH_READY_LIFECYCLES


def test_is_publish_ready_requires_finished_and_stitch():
    assert is_publish_ready(None) is False
    m = _master(
        sceneFinalCheck={"lifecycleStatus": "FINAL_CHECK", "categories": []},
        sceneStitch={"assetId": "s1", "sourceBatchIds": ["b1"], "sourceAssetIds": ["a1"]},
    )
    assert is_publish_ready(m) is False
    m2 = _master(
        sceneFinalCheck={"lifecycleStatus": "SCENE_FINISHED", "categories": []},
    )
    assert is_publish_ready(m2) is False
    m3 = _master(
        sceneFinalCheck={
            "lifecycleStatus": "SCENE_FINISHED",
            "categories": [],
            "creatorVerdict": "FINAL CHECK PASSED / SCENE FINISHED",
        },
        sceneStitch={"assetId": "s1", "sourceBatchIds": ["b1", "b2"], "sourceAssetIds": ["a1", "a2"]},
    )
    assert is_publish_ready(m3) is True


def test_accepted_issues_ready_and_honest_status():
    m = _master(
        sceneFinalCheck={
            "lifecycleStatus": "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
            "categories": [],
            "creatorVerdict": "SCENE FINISHED ISSUES ACCEPTED BY CREATOR",
        },
        sceneStitch={"assetId": "s1", "sourceBatchIds": ["b1"], "sourceAssetIds": ["a1"]},
    )
    assert is_publish_ready(m) is True
    st = publish_status(m)
    assert st["showPublish"] is True
    assert st["showUpscaleWithMagi"] is True


def test_changes_pending_when_stitch_asset_moves():
    m = _master(
        sceneStitch={"assetId": "stitch-2", "sourceBatchIds": ["b1"], "sourceAssetIds": ["a1"]},
        sceneFinalCheck={"lifecycleStatus": "SCENE_FINISHED", "categories": []},
        scenePublish={
            "publishedAssetId": "pub-1",
            "publishedAt": "2026-09-14T00:00:00Z",
            "sourceSceneStitchAssetId": "stitch-1",
            "lifecycleStatusSnapshot": "SCENE_FINISHED",
            "acceptedIssues": False,
            "contentFingerprint": "oldfp",
            "version": 1,
        },
    )
    assert changes_pending(m) is True
    st = publish_status(m)
    assert st["showUpdatePublished"] is True
    assert st["showPublish"] is False


def test_fingerprint_stable():
    m = _master(
        sceneStitch={
            "assetId": "s1",
            "sourceBatchIds": ["b1", "b2"],
            "sourceAssetIds": ["a1", "a2"],
        }
    )
    a = content_fingerprint(m)
    b = content_fingerprint(m)
    assert a == b
    assert len(a) == 32


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Point data_dir at tmp so register_derived_asset writes safely.
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    yield db
    db.close()


def _seed_scene_with_stitch(db: Session, tmp_path: Path, *, lifecycle: str, verdict: str):
    pid = f"p_{uuid.uuid4().hex[:8]}"
    sid = f"s_{uuid.uuid4().hex[:8]}"
    proj = Project(id=pid, name="Publish Test")
    db.add(proj)
    scene = Scene(id=sid, project_id=pid, name="Scene Pub", duration_sec=10.0, prompt="")
    db.add(scene)
    db.commit()

    media = tmp_path / "projects" / pid / "assets"
    media.mkdir(parents=True, exist_ok=True)
    stitch_file = media / "stitch_src.mp4"
    stitch_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    stitch_id = f"ast_{uuid.uuid4().hex[:8]}"
    asset = Asset(
        id=stitch_id,
        project_id=pid,
        tag="scene_stitch",
        kind="video",
        filename=stitch_file.name,
        path=str(stitch_file),
    )
    db.add(asset)
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
                },
                {
                    "id": "bb2",
                    "sceneId": sid,
                    "order": 1,
                    "status": "Approved",
                    "approvedClip": {"assetId": "batch-a2", "executionSnapshotId": "snap2"},
                },
            ],
            "sceneStitch": {
                "assetId": stitch_id,
                "sourceBatchIds": ["bb1", "bb2"],
                "sourceAssetIds": ["batch-a1", "batch-a2"],
            },
            "sceneFinalCheck": {
                "lifecycleStatus": lifecycle,
                "creatorVerdict": verdict,
                "categories": [],
            },
        }
    )
    store.save_master(db, pid, sid, master, touch_batches=False)
    return pid, sid, stitch_id


def test_publish_refuses_before_pass(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, _ = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="FINAL_CHECK",
        verdict="",
    )
    result = publish_scene(db_session, pid, sid)
    assert result["ok"] is False
    assert result["error"] == "NOT_PUBLISH_READY"


def test_publish_atomic_register_with_pass_provenance(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED",
        verdict="FINAL CHECK PASSED / SCENE FINISHED",
    )
    result = publish_scene(db_session, pid, sid)
    assert result["ok"] is True, result
    pub = result["scenePublish"]
    assert pub["publishedAssetId"]
    assert pub["sourceSceneStitchAssetId"] == stitch_id
    assert pub["lifecycleStatusSnapshot"] == "SCENE_FINISHED"
    assert pub["acceptedIssues"] is False
    assert "FINAL CHECK PASSED" in (pub.get("creatorVerdictSnapshot") or "")
    asset = db_session.get(Asset, pub["publishedAssetId"])
    assert asset is not None
    assert asset.tag == "video_published_master"
    # Batches preserved
    assert len(result["master"]["batchBlocks"]) == 2


def test_publish_accepted_issues_honest_provenance(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
        verdict="SCENE FINISHED ISSUES ACCEPTED BY CREATOR",
    )
    result = publish_scene(db_session, pid, sid)
    assert result["ok"] is True, result
    pub = result["scenePublish"]
    assert pub["acceptedIssues"] is True
    assert pub["lifecycleStatusSnapshot"] == "SCENE_FINISHED_WITH_ACCEPTED_ISSUES"
    assert "ISSUES ACCEPTED" in (pub.get("creatorVerdictSnapshot") or "")
    # Must NOT pretend clean PASS
    assert pub["lifecycleStatusSnapshot"] != "SCENE_FINISHED" or pub["acceptedIssues"] is True


def test_update_published_version_safety(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED",
        verdict="FINAL CHECK PASSED / SCENE FINISHED",
    )
    first = publish_scene(db_session, pid, sid)
    assert first["ok"] is True
    # No changes → refuse update
    again = publish_scene(db_session, pid, sid, update=True, expected_version=1)
    assert again["ok"] is False
    assert again["error"] == "NO_CHANGES_PENDING"

    # Simulate re-stitch: new stitch asset file + id
    media = tmp_path / "projects" / pid / "assets"
    new_file = media / "stitch_v2.mp4"
    new_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 64)
    new_id = f"ast_{uuid.uuid4().hex[:8]}"
    db_session.add(
        Asset(
            id=new_id,
            project_id=pid,
            tag="scene_stitch",
            kind="video",
            filename=new_file.name,
            path=str(new_file),
        )
    )
    db_session.commit()
    payload = store.load_master(db_session, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    master.sceneStitch = SceneStitch(
        assetId=new_id,
        sourceBatchIds=["bb1", "bb2"],
        sourceAssetIds=["batch-a1", "batch-a2"],
    )
    store.save_master(db_session, pid, sid, master, touch_batches=False)

    conflict = publish_scene(db_session, pid, sid, update=True, expected_version=99)
    assert conflict["ok"] is False
    assert conflict["error"] == "VERSION_CONFLICT"

    updated = publish_scene(db_session, pid, sid, update=True, expected_version=1)
    assert updated["ok"] is True, updated
    assert updated["scenePublish"]["version"] == 2
    assert updated["scenePublish"]["sourceSceneStitchAssetId"] == new_id


def test_magi_uses_published_master_not_other_take_stitch():
    m = _master(
        sceneStitch={"assetId": "take-c-stitch", "sourceBatchIds": ["b1"], "sourceAssetIds": ["c1"]},
        sceneFinalCheck={"lifecycleStatus": "SCENE_FINISHED", "categories": []},
        scenePublish={
            "publishedAssetId": "pub-b",
            "publishedAt": "2026-09-15T00:00:00Z",
            "sourceSceneStitchAssetId": "take-b-stitch",
            "lifecycleStatusSnapshot": "SCENE_FINISHED",
            "acceptedIssues": False,
            "version": 1,
        },
    )
    allowed = _allowed_magi_asset_ids(m)
    assert "pub-b" in allowed
    assert "take-b-stitch" in allowed
    assert "take-c-stitch" not in allowed
    chosen, err = _choose_magi_source(m, None)
    assert err is None
    assert chosen == "pub-b"
    blocked, err2 = _choose_magi_source(m, "take-c-stitch")
    assert blocked is None
    assert err2 and err2["error"] == "MAGI_FULL_STITCH_ONLY"


def test_magi_blocks_batch_asset(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED",
        verdict="FINAL CHECK PASSED / SCENE FINISHED",
    )
    result = magi_upscale_full_stitch(
        db_session,
        pid,
        sid,
        asset_id="batch-a1",
        engine="ffmpeg-scale",
        model="lanczos",
        target_resolution="1280x720",
    )
    assert result["ok"] is False
    assert result["error"] == "MAGI_FULL_STITCH_ONLY"


def test_persist_upscaled_asset_before_first_publish(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, _stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED",
        verdict="FINAL CHECK PASSED / SCENE FINISHED",
    )
    result = persist_scene_upscaled_asset(db_session, pid, sid, "up-before-pub")
    assert result["ok"] is True
    payload = store.load_master(db_session, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert master.scenePublish is not None
    assert master.scenePublish.publishedAssetId == ""
    assert master.scenePublish.upscaledAssetId == "up-before-pub"
    chrome = publish_status(master)
    assert chrome["hasPublished"] is False
    assert chrome["showPublish"] is True


def test_magi_enqueue_response_has_no_upscaled_asset_id(db_session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "data_dir", str(tmp_path))
    pid, sid, _stitch_id = _seed_scene_with_stitch(
        db_session,
        tmp_path,
        lifecycle="SCENE_FINISHED",
        verdict="FINAL CHECK PASSED / SCENE FINISHED",
    )
    monkeypatch.setattr(
        "app.magi.upscaling.apply_upscale",
        lambda *_a, **_k: {"ok": True, "queued": True, "jobId": "queued-only"},
    )
    result = magi_upscale_full_stitch(db_session, pid, sid)
    assert result["ok"] is True
    assert result["jobId"] == "queued-only"
    assert result["upscaledAssetId"] is None
