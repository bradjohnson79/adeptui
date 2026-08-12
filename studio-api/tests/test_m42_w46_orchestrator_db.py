"""W46 orchestrator persistence against SQLite scene.director_json."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline import CameraClip
from app.director_timeline_w46 import orchestrator, service
from app.director_timeline_w46.contracts import CancelRequest
from app.director_timeline_w46 import store


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="W46 Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="wide establishing",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def test_full_batch_lifecycle(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    assert ws["ok"] is True
    batch_id = ws["master"]["batchBlocks"][0]["id"]

    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "ltx-local",
            "label": "Hero",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "wide establishing",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
        },
    )
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    assert gen.get("queueJobId")
    snap_id = gen["executionSnapshotId"]

    # Snapshot immutable via GET path
    snap = service.snapshot_get(db, pid, sid, snap_id)
    assert snap["immutable"] is True

    done = orchestrator.complete_batch_candidate(
        db,
        pid,
        sid,
        batch_id,
        asset_id="asset-demo",
        generated_duration=4.5,
        execution_snapshot_id=snap_id,
    )
    assert done["ok"] is True
    assert done["duration"]["plannedDuration"] == 5.0
    assert done["duration"]["generatedDuration"] == 4.5
    assert done["duration"]["timelineVisibleDuration"] == 4.5

    cand_id = done["candidate"]["id"]
    approved = orchestrator.approve_candidate(db, pid, sid, batch_id, cand_id)
    assert approved["batchStatus"] == "Approved"

    # Config change after approval → invalidation
    touched = orchestrator.touch_batch_config(
        db, pid, sid, batch_id, {"plannedDuration": 6.0}
    )
    assert touched["invalidated"] is True
    assert touched["status"] == "ApprovedConfigurationChanged"

    # Overlap blocked
    r1 = orchestrator.add_repair_range(
        db, pid, sid, batch_id, {"start": 0.0, "length": 2.0, "label": "A"}
    )
    assert r1["ok"] is True
    r2 = orchestrator.add_repair_range(
        db, pid, sid, batch_id, {"start": 1.0, "length": 2.0, "label": "B"}
    )
    assert r2["ok"] is False and r2["blocked"] is True

    # Hosted cancel honesty
    cancel = orchestrator.cancel_scene(
        db,
        pid,
        sid,
        CancelRequest(action="request_hosted_cancellation", batchBlockIds=[batch_id]),
    )
    assert cancel.hostedCancelSupport in ("unsupported", "unknown", "supported")

    # Mode switch preserves batches
    mode = service.set_mode(db, pid, sid, "video_finishing")
    assert mode["batchCount"] >= 1


def test_camera_strategy_snapshot_and_preflight(db_scene):
    db, pid, sid = db_scene
    bundle = service.load_timeline_bundle(db, pid, sid)
    master = bundle["master"]
    director_timeline = bundle["directorTimeline"]
    director_timeline.camera_clips = [
        CameraClip(
            id="cam-lockoff",
            start=0.0,
            length=5.0,
            motion_type="static",
            motion_id="locked_off",
            rig="handheld",
            rig_id="handheld",
            subject_lock=0.95,
        )
    ]
    store.save_master(db, pid, sid, master, director_tl=director_timeline)

    findings = orchestrator.run_preflight(master, director_timeline=director_timeline)
    contradiction_codes = {f["code"] for f in findings}
    assert "camera_contradiction:locked_off_with_handheld_family" in contradiction_codes

    batch_id = master.batchBlocks[0].id
    service.patch_batch(
        db,
        pid,
        sid,
        batch_id,
        {
            "generatorId": "ltx-local",
            "promptSegments": [
                {
                    "id": "ps1",
                    "start": 0,
                    "length": 5,
                    "text": "wide establishing",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1",
                }
            ],
        },
    )
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        gen = orchestrator.submit_batch_generation(db, pid, sid, batch_id)
    assert gen["ok"] is True
    snap = service.snapshot_get(db, pid, sid, gen["executionSnapshotId"])
    camera_strategy = snap["snapshot"]["settings"]["cameraStrategy"]
    assert camera_strategy["capability"] == "Workflow-Mapped"
    assert camera_strategy["hasContradictions"] is True
