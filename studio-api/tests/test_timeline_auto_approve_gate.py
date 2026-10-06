"""Timeline generate-complete must stop at CandidateReady (no auto-approve)."""

from __future__ import annotations

import inspect
import threading
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import continuity as continuity_mod
from app.director_timeline_w46 import orchestrator, service
from app.director_timeline_w46.generation import watcher as timeline_watcher
from app.director_timeline_w46.generation.completion import apply_shared_completion
from app.director_timeline_w46.generation.contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
    TimelineGenerationResult,
)
from app.director_timeline_w46.contracts import SceneTimelineMaster


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Timeline Auto-Approve Gate", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="cinematic bottle push-in",
            duration_sec=5.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _two_ltx_batches(db, pid, sid):
    ws = service.workspace(db, pid, sid)
    b1 = ws["master"]["batchBlocks"][0]["id"]
    added = service.add_batch(
        db, pid, sid, label="Batch 2", planned_duration=5.0, generator_id="ltx-local"
    )
    b2 = added["batch"]["id"]
    service.patch_batch(db, pid, sid, b1, {"generatorId": "ltx-local", "label": "Batch 1"})
    return b1, b2


def _snapshot(db, pid, sid, batch_id, continuity=None):
    from app.director_timeline_w46 import store

    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == batch_id)
    snap = orchestrator.create_execution_snapshot(batch, continuity=continuity)
    master.executionSnapshots[snap.id] = snap
    store.save_master(db, pid, sid, master)
    return snap


def _result(asset_id: str, *, draft: bool = False) -> TimelineGenerationResult:
    return TimelineGenerationResult(
        internalJobId=f"job-{asset_id}",
        providerJobId=f"prov-{asset_id}",
        queueJobId=f"q-{asset_id}",
        generatorId="ltx-local",
        status="completed",
        outputAssetIds=[asset_id],
        duration=5.0,
        apiUsed=False,
        providerMetadata={"draftMode": True} if draft else {},
    )


def test_watcher_source_gates_timeline_auto_approve_false():
    src = inspect.getsource(timeline_watcher.start_completion_watcher)
    assert "auto_approve=False" in src
    assert "auto_approve=not draft" not in src
    assert "auto_approve=True" not in src


def test_completion_default_auto_approve_unchanged_for_non_timeline_callers():
    """Shared completion default stays True so Character/ERS callers are not flipped."""
    sig = inspect.signature(apply_shared_completion)
    assert sig.parameters["auto_approve"].default is True


def test_timeline_watcher_passes_auto_approve_false_for_final_render():
    captured: dict = {}
    done = threading.Event()

    def _capture(*_args, **kwargs):
        captured.update(kwargs)
        done.set()
        return {"ok": True}

    class _DoneAdapter:
        def get_status(self, submission):
            return NormalizedJobStatus(
                internalJobId=submission.internalJobId,
                generatorId=submission.generatorId,
                status="completed",
            )

        def collect_result(self, submission):
            return _result("asset-final")

    class _Registry:
        def get(self, generator_id):
            return _DoneAdapter()

    submission = NormalizedJobSubmission(
        generatorId="ltx-local",
        providerMetadata={},
    )
    with (
        patch.object(timeline_watcher, "get_registry", return_value=_Registry()),
        patch.object(timeline_watcher, "apply_shared_completion", side_effect=_capture),
    ):
        timeline_watcher.start_completion_watcher(
            project_id="proj",
            scene_id="scene",
            batch_id="batch",
            execution_snapshot_id="snap",
            submission=submission,
            poll_interval_sec=0.05,
            timeout_sec=5.0,
        )
        assert done.wait(timeout=5.0), "watcher never called apply_shared_completion"
    assert captured.get("auto_approve") is False


def test_timeline_final_completion_stops_at_candidate_ready(db_scene):
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap = _snapshot(db, pid, sid, b1)
    from app.director_timeline_w46 import store

    before = SceneTimelineMaster.model_validate(store.load_master(db, pid, sid)["master"])
    bridges_before = [b.bridgeId for b in before.continuityBridges]

    with patch(
        "app.director_timeline_w46.generation.completion.orchestrator.approve_candidate"
    ) as mock_approve, patch.object(
        continuity_mod, "prepare_outgoing_bridge", wraps=continuity_mod.prepare_outgoing_bridge
    ) as spy:
        done = apply_shared_completion(
            db,
            project_id=pid,
            scene_id=sid,
            batch_id=b1,
            execution_snapshot_id=snap.id,
            result=_result("asset-final"),
            auto_approve=False,
        )
    assert done["ok"] is True
    mock_approve.assert_not_called()
    assert spy.call_count == 0

    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)
    assert batch_rel["status"] == "CandidateReady"
    assert batch_rel["approvedClip"] is None
    assert batch_rel["candidateVersions"]
    assert batch_rel["candidateVersions"][0]["approved"] is False
    after = SceneTimelineMaster.model_validate(reloaded["master"])
    assert [b.bridgeId for b in after.continuityBridges] == bridges_before


def test_approve_candidate_writes_approved_clip_and_outgoing_bridge(db_scene):
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap = _snapshot(db, pid, sid, b1)
    apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=b1,
        execution_snapshot_id=snap.id,
        result=_result("asset-final"),
        auto_approve=False,
    )
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)
    cand_id = batch_rel["candidateVersions"][0]["id"]
    bridges_before = [
        b["bridgeId"] if isinstance(b, dict) else b.bridgeId
        for b in reloaded["master"].get("continuityBridges") or []
    ]

    with patch.object(
        continuity_mod, "prepare_outgoing_bridge", wraps=continuity_mod.prepare_outgoing_bridge
    ) as spy:
        out = orchestrator.approve_candidate(db, pid, sid, b1, cand_id)
    assert out["ok"] is True
    assert spy.call_count == 1

    after = service.workspace(db, pid, sid)
    batch3 = next(b for b in after["master"]["batchBlocks"] if b["id"] == b1)
    assert batch3["approvedClip"] is not None
    assert batch3["approvedClip"]["assetId"] == "asset-final"
    assert batch3["status"] == "Approved"
    assert batch3["candidateVersions"][0]["approved"] is True
    bridges_after = [b["bridgeId"] for b in after["master"].get("continuityBridges") or []]
    assert len(bridges_after) == len(bridges_before) + 1


def test_approve_post_writes_approved_clip_and_outgoing_bridge(db_scene, client):
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap = _snapshot(db, pid, sid, b1)
    apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=b1,
        execution_snapshot_id=snap.id,
        result=_result("asset-final"),
        auto_approve=False,
    )
    reloaded = service.workspace(db, pid, sid)
    cand_id = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)[
        "candidateVersions"
    ][0]["id"]
    bridges_before = [b["bridgeId"] for b in reloaded["master"].get("continuityBridges") or []]

    with patch.object(
        continuity_mod, "prepare_outgoing_bridge", wraps=continuity_mod.prepare_outgoing_bridge
    ) as spy:
        resp = client.post(
            f"/api/director-timeline/projects/{pid}/scenes/{sid}/batches/{b1}/approve",
            json={"candidateId": cand_id},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("ok") is True
    assert spy.call_count == 1

    after = service.workspace(db, pid, sid)
    batch3 = next(b for b in after["master"]["batchBlocks"] if b["id"] == b1)
    assert batch3["approvedClip"] is not None
    assert batch3["approvedClip"]["assetId"] == "asset-final"
    assert batch3["status"] == "Approved"
    bridges_after = [b["bridgeId"] for b in after["master"].get("continuityBridges") or []]
    assert len(bridges_after) == len(bridges_before) + 1


def test_draft_completion_still_auto_approve_false(db_scene):
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap = _snapshot(
        db,
        pid,
        sid,
        b1,
        continuity={"takeState": {"quality": "draft", "draftPathway": "local_live"}},
    )
    with patch.object(
        continuity_mod, "prepare_outgoing_bridge", wraps=continuity_mod.prepare_outgoing_bridge
    ) as spy:
        done = apply_shared_completion(
            db,
            project_id=pid,
            scene_id=sid,
            batch_id=b1,
            execution_snapshot_id=snap.id,
            result=_result("asset-draft", draft=True),
            auto_approve=True,
        )
    assert done["ok"] is True
    assert spy.call_count == 0
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)
    assert batch_rel["approvedClip"] is None
    assert batch_rel["status"] == "CandidateReady"
    assert batch_rel["candidateVersions"][0]["takeState"]["quality"] == "draft"


def test_retake_still_does_not_auto_approve_over_active_take(db_scene):
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap_a = _snapshot(db, pid, sid, b1)
    first = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=b1,
        execution_snapshot_id=snap_a.id,
        result=_result("asset-take-a"),
        auto_approve=True,
    )
    assert first["ok"] is True
    from app.director_timeline_w46 import store

    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = next(b for b in master.batchBlocks if b.id == b1)
    snap_b = orchestrator.create_execution_snapshot(
        batch,
        continuity={"reTakeReason": "creator_retake", "userCorrection": {"delta": "walk behind"}},
    )
    master.executionSnapshots[snap_b.id] = snap_b
    store.save_master(db, pid, sid, master)
    with patch.object(
        continuity_mod, "prepare_outgoing_bridge", wraps=continuity_mod.prepare_outgoing_bridge
    ) as spy:
        second = apply_shared_completion(
            db,
            project_id=pid,
            scene_id=sid,
            batch_id=b1,
            execution_snapshot_id=snap_b.id,
            result=_result("asset-take-b"),
            auto_approve=True,
        )
    assert second["ok"] is True
    assert spy.call_count == 0
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)
    assert batch_rel["approvedClip"]["assetId"] == "asset-take-a"
    take_b = next(c for c in batch_rel["candidateVersions"] if c["assetId"] == "asset-take-b")
    assert take_b["approved"] is False


def test_missing_measured_duration_uses_planned_not_silent_five(db_scene):
    db, pid, sid = db_scene
    added = service.add_batch(
        db, pid, sid, label="H3 8s", planned_duration=8.0, generator_id="minimax-h3"
    )
    bid = added["batch"]["id"]
    snap = _snapshot(db, pid, sid, bid)
    result = TimelineGenerationResult(
        internalJobId="job-h3-8",
        providerJobId="prov-h3-8",
        queueJobId="q-h3-8",
        generatorId="minimax-h3",
        status="completed",
        outputAssetIds=["asset-h3-8"],
        duration=None,
        apiUsed=False,
    )
    done = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=bid,
        execution_snapshot_id=snap.id,
        result=result,
        auto_approve=False,
    )
    assert done["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == bid)
    assert batch_rel["duration"]["generatedDuration"] == 8.0
    assert batch_rel["duration"]["sourceMediaDuration"] == 8.0
    assert batch_rel["duration"]["timelineVisibleDuration"] == 8.0


def test_non_timeline_default_still_can_auto_approve(db_scene):
    """Direct apply_shared_completion default (prior behavior) still auto-approves."""
    db, pid, sid = db_scene
    b1, _b2 = _two_ltx_batches(db, pid, sid)
    snap = _snapshot(db, pid, sid, b1)
    done = apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=b1,
        execution_snapshot_id=snap.id,
        result=_result("asset-default"),
    )
    assert done["ok"] is True
    reloaded = service.workspace(db, pid, sid)
    batch_rel = next(b for b in reloaded["master"]["batchBlocks"] if b["id"] == b1)
    assert batch_rel["status"] == "Approved"
    assert batch_rel["approvedClip"]["assetId"] == "asset-default"
