"""Additive scene stitch planning and persistence."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import Asset, Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import service, store
from app.director_timeline_w46.contracts import ApprovedClip, SceneTimelineMaster
from app.director_timeline_w46.scene_stitch import (
    collect_completed_sources,
    plan_stitch,
    stitch_scene,
)


def test_plan_stitch_already_current():
    plan = plan_stitch(["a", "b", "c"], ["a", "b", "c"])
    assert plan["mode"] == "already_current"
    assert plan["appendAssetIds"] == []
    assert plan["rebuildAll"] is False


def test_plan_stitch_incremental_append():
    plan = plan_stitch(["a", "b", "c"], ["a", "b", "c", "d"])
    assert plan["mode"] == "incremental"
    assert plan["appendAssetIds"] == ["d"]
    assert plan["rebuildAll"] is False


def test_plan_stitch_full_when_middle_take_changes():
    plan = plan_stitch(["a", "b", "c"], ["a", "b2", "c"])
    assert plan["mode"] == "full"
    assert plan["rebuildAll"] is True
    assert plan["appendAssetIds"] == ["a", "b2", "c"]


def test_plan_stitch_full_when_no_prior():
    plan = plan_stitch(None, ["a", "b"])
    assert plan["mode"] == "full"
    assert plan["appendAssetIds"] == ["a", "b"]


def test_collect_skips_unreviewed_and_keeps_order():
    master = SceneTimelineMaster.model_validate(
        {
            "migratedFromDirectorJson": False,
            "batchBlocks": [
                {
                    "id": "bb2",
                    "sceneId": "s1",
                    "order": 1,
                    "status": "Approved",
                    "approvedClip": {"assetId": "asset-2", "executionSnapshotId": "snap2"},
                },
                {
                    "id": "bb1",
                    "sceneId": "s1",
                    "order": 0,
                    "status": "Approved",
                    "approvedClip": {"assetId": "asset-1", "executionSnapshotId": "snap1"},
                },
                {
                    "id": "bb3",
                    "sceneId": "s1",
                    "order": 2,
                    "status": "CandidateReady",
                    "approvedClip": {"assetId": "asset-3", "executionSnapshotId": "snap3"},
                },
            ],
        }
    )
    assert collect_completed_sources(master) == [("bb1", "asset-1"), ("bb2", "asset-2")]


def test_collect_sources_follow_current_take_membership():
    """REBUILD LAW fence (Take/asset ownership): the scene result is the
    stitched continuity of the CURRENT take. After a pointer heal, approvedClip
    can lag the current take — the stitch source must resolve through the
    current Take's membership, never the stale approved asset (Take O silent
    gate bypass shape)."""
    master = SceneTimelineMaster.model_validate(
        {
            "migratedFromDirectorJson": False,
            "currentSceneTakeId": "stk_b",
            "sceneTakes": [
                {
                    "id": "stk_a",
                    "status": "incomplete",
                    "createdAt": "2026-09-18T10:00:00Z",
                    "batches": [
                        {"batchId": "bb1", "order": 0, "assetId": "stale-asset-1"},
                    ],
                },
                {
                    "id": "stk_b",
                    "status": "rendering",
                    "createdAt": "2026-09-18T11:00:00Z",
                    "batches": [
                        {"batchId": "bb1", "order": 0, "assetId": "current-asset-1"},
                        {"batchId": "bb2", "order": 1, "assetId": "current-asset-2"},
                    ],
                },
            ],
            "batchBlocks": [
                {
                    "id": "bb1",
                    "sceneId": "s1",
                    "order": 0,
                    "status": "Approved",
                    "approvedClip": {"assetId": "stale-asset-1", "executionSnapshotId": "snap1"},
                },
                {
                    "id": "bb2",
                    "sceneId": "s1",
                    "order": 1,
                    "status": "Approved",
                    "approvedClip": {"assetId": "stale-asset-2", "executionSnapshotId": "snap2"},
                },
            ],
        }
    )
    assert collect_completed_sources(master) == [
        ("bb1", "current-asset-1"),
        ("bb2", "current-asset-2"),
    ]


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Scene Stitch Gate", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="corridor walk",
            duration_sec=10.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _tiny_mp4(path: Path, seconds: float = 0.4, color: str = "red") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=64x64:d={seconds}",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-800:])


def _approve_two(db: Session, pid: str, sid: str, paths: list[Path]) -> tuple[list[str], list[str]]:
    ws = service.workspace(db, pid, sid)
    b1 = ws["master"]["batchBlocks"][0]["id"]
    added = service.add_batch(db, pid, sid, label="Batch 2", planned_duration=5.0, generator_id="ltx-local")
    b2 = added["batch"]["id"]
    batch_ids = [b1, b2]
    asset_ids: list[str] = []
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    for batch, path, label in zip(master.batchBlocks, paths, ["b1", "b2"], strict=False):
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=pid,
            tag=label,
            kind="video",
            filename=path.name,
            path=str(path),
            comfy_name="",
        )
        db.add(asset)
        db.flush()
        batch.status = "Approved"
        batch.approvedClip = ApprovedClip(assetId=asset.id, executionSnapshotId="snap")
        asset_ids.append(asset.id)
    store.save_master(db, pid, sid, master, touch_batches=False)
    db.commit()
    return batch_ids, asset_ids


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required for live stitch")
def test_stitch_is_additive_and_incremental(db_scene, tmp_path):
    db, pid, sid = db_scene
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    c = tmp_path / "c.mp4"
    _tiny_mp4(a, 0.3, "red")
    _tiny_mp4(b, 0.3, "green")
    _tiny_mp4(c, 0.3, "blue")
    batch_ids, asset_ids = _approve_two(db, pid, sid, [a, b])

    first = stitch_scene(db, pid, sid)
    assert first["ok"] is True
    assert first["alreadyCurrent"] is False
    assert first["incremental"] is False
    assert first["mock"] is False
    stitch_id = first["sceneStitch"]["assetId"]
    assert first["sourceBatchIds"] == batch_ids
    assert first["sourceAssetIds"] == asset_ids

    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert [batch.id for batch in master.batchBlocks] == batch_ids
    assert all(batch.status == "Approved" for batch in master.batchBlocks)
    assert master.sceneStitch and master.sceneStitch.assetId == stitch_id

    again = stitch_scene(db, pid, sid)
    assert again["ok"] is True
    assert again["alreadyCurrent"] is True
    assert again["sceneStitch"]["assetId"] == stitch_id

    added = service.add_batch(db, pid, sid, label="Batch 3", planned_duration=5.0, generator_id="ltx-local")
    b3 = added["batch"]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    asset3 = Asset(
        id=str(uuid.uuid4()),
        project_id=pid,
        tag="b3",
        kind="video",
        filename=c.name,
        path=str(c),
        comfy_name="",
    )
    db.add(asset3)
    db.flush()
    for batch in master.batchBlocks:
        if batch.id == b3:
            batch.status = "Approved"
            batch.approvedClip = ApprovedClip(assetId=asset3.id, executionSnapshotId="snap3")
    store.save_master(db, pid, sid, master, touch_batches=False)
    db.commit()

    second = stitch_scene(db, pid, sid)
    assert second["ok"] is True
    assert second["alreadyCurrent"] is False
    assert second["incremental"] is True
    assert second["sceneStitch"]["assetId"] != stitch_id
    assert second["sourceBatchIds"] == batch_ids + [b3]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    assert [batch.id for batch in master.batchBlocks] == batch_ids + [b3]
    assert all(batch.approvedClip and batch.approvedClip.assetId for batch in master.batchBlocks)
