"""Queue hardening regressions (Timeline Full Audit DEFECT-Q1/Q2/Q3).

Q1: _mark_job_failed must never clobber an already-terminal (Approved /
    CandidateReady) batch when a late/stale provider failure arrives.
Q2: an exception in the watcher's terminal-status handling must not kill the
    watcher thread silently — the error is surfaced and the sequential chain
    advance is still attempted.
Q3: editing a Queued batch's config must invalidate the staged
    pendingSnapshotId (stale provenance) and return the batch to Ready.
"""

from __future__ import annotations

import threading
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import SceneTimelineMaster
from app.director_timeline_w46.generation import registry as registry_mod
from app.director_timeline_w46.generation import watcher as watcher_mod
from app.director_timeline_w46.generation.adapters import stub_cert
from app.director_timeline_w46.generation.contracts import (
    NormalizedJobStatus,
    NormalizedJobSubmission,
)


@pytest.fixture()
def stub_env(tmp_path, monkeypatch):
    monkeypatch.setenv(stub_cert.ENV_FLAG, "1")
    monkeypatch.setattr(stub_cert, "_cert_dir", lambda: tmp_path)
    registry_mod._REGISTRY = None
    yield tmp_path
    registry_mod._REGISTRY = None


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Queue Hardening Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="queue hardening",
            duration_sec=15.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _master(db, pid, sid) -> SceneTimelineMaster:
    payload = store.load_master(db, pid, sid)
    return SceneTimelineMaster.model_validate(payload["master"])


def _two_stub_batches(db, pid, sid):
    service.workspace(db, pid, sid)
    ws = service.workspace(db, pid, sid)
    b1 = ws["master"]["batchBlocks"][0]["id"]
    res = service.add_batch(db, pid, sid, label="Batch 2", planned_duration=5.0)
    b2 = res["batch"]["id"] if "batch" in res else res["batchBlockId"]
    for i, bid in enumerate((b1, b2)):
        service.patch_batch(
            db,
            pid,
            sid,
            bid,
            {
                "generatorId": stub_cert.GENERATOR_ID,
                "plannedDuration": 5.0,
                "promptSegments": [
                    {
                        "id": f"ps{i}",
                        "start": 0,
                        "length": 5,
                        "text": f"prompt {i}",
                        "role": "primary",
                        "strength": 1,
                        "anchorIds": [],
                        "executionStrategy": "compiled",
                        "versionId": f"psv{i}",
                    }
                ],
            },
        )
    return b1, b2


def test_q1_late_failure_never_clobbers_approved_batch(db_scene, stub_env):
    db, pid, sid = db_scene
    (b1,) = _two_stub_batches(db, pid, sid)[:1]

    # Drive the batch to Approved via the real completion path.
    orchestrator.submit_batch_generation(db, pid, sid, b1)
    master = _master(db, pid, sid)
    batch = next(b for b in master.batchBlocks if b.id == b1)
    job = batch.generationJobs[-1]
    from app.director_timeline_w46.generation.completion import apply_shared_completion
    from app.director_timeline_w46.generation.contracts import TimelineGenerationResult

    apply_shared_completion(
        db,
        project_id=pid,
        scene_id=sid,
        batch_id=b1,
        execution_snapshot_id=job.executionSnapshotId,
        result=TimelineGenerationResult(
            internalJobId=job.id,
            generatorId=stub_cert.GENERATOR_ID,
            status="completed",
            outputAssetIds=["asset-approved-1"],
            duration=5.0,
        ),
        job=NormalizedJobSubmission(
            internalJobId=job.id,
            generatorId=stub_cert.GENERATOR_ID,
            providerMetadata={"projectId": pid},
        ),
        auto_approve=True,
    )
    master = _master(db, pid, sid)
    assert next(b for b in master.batchBlocks if b.id == b1).status == "Approved"

    # Late stale failure from the provider must be ignored.
    watcher_mod._mark_job_failed(db, pid, sid, b1, job.executionSnapshotId, "LATE_FAILURE", "stale")

    master = _master(db, pid, sid)
    batch = next(b for b in master.batchBlocks if b.id == b1)
    assert batch.status == "Approved"
    assert batch.approvedClip is not None
    assert all(j.status != "failed" for j in batch.generationJobs)


def test_q3_config_edit_on_queued_batch_invalidates_staged_snapshot(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2 = _two_stub_batches(db, pid, sid)

    # Sequential scene generate: b1 submits, b2 is staged Queued with a snapshot.
    out = orchestrator.generate_scene(db, pid, sid, scope="full")
    assert out["ok"] is True
    master = _master(db, pid, sid)
    batch2 = next(b for b in master.batchBlocks if b.id == b2)
    assert batch2.status == "Queued"
    staged_id = batch2.pendingSnapshotId
    assert staged_id
    assert staged_id in master.executionSnapshots

    # Creator edits the Queued batch's prompt — fingerprint changes.
    res = orchestrator.touch_batch_config(
        db,
        pid,
        sid,
        b2,
        {
            "promptSegments": [
                {
                    "id": "ps1b",
                    "start": 0,
                    "length": 5,
                    "text": "EDITED prompt for batch 2",
                    "role": "primary",
                    "strength": 1,
                    "anchorIds": [],
                    "executionStrategy": "compiled",
                    "versionId": "psv1b",
                }
            ]
        },
    )
    assert res["ok"] is True
    assert res["stagedSnapshotStaled"] is True
    assert res["status"] == "Ready"

    master = _master(db, pid, sid)
    batch2 = next(b for b in master.batchBlocks if b.id == b2)
    assert batch2.pendingSnapshotId is None
    assert batch2.status == "Ready"
    # Immutable audit record retained — never rewritten or deleted.
    assert staged_id in master.executionSnapshots


def test_q3_label_only_edit_keeps_staged_snapshot(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2 = _two_stub_batches(db, pid, sid)
    orchestrator.generate_scene(db, pid, sid, scope="full")
    master = _master(db, pid, sid)
    batch2 = next(b for b in master.batchBlocks if b.id == b2)
    assert batch2.status == "Queued"

    # Label is presentation-only; it must not change the config fingerprint.
    res = orchestrator.touch_batch_config(db, pid, sid, b2, {"label": "Hero shot"})
    assert res["ok"] is True
    assert res["stagedSnapshotStaled"] is False
    master = _master(db, pid, sid)
    batch2 = next(b for b in master.batchBlocks if b.id == b2)
    assert batch2.status == "Queued"
    assert batch2.pendingSnapshotId


def test_q2_watcher_terminal_exception_still_advances_chain(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2 = _two_stub_batches(db, pid, sid)

    class _ExplodingCompletionAdapter:
        def get_status(self, submission):
            return NormalizedJobStatus(
                internalJobId=submission.internalJobId,
                generatorId=submission.generatorId,
                status="completed",
            )

        def collect_result(self, submission):
            return None  # apply_shared_completion is patched to raise anyway

    class _Registry:
        def get(self, generator_id):
            return _ExplodingCompletionAdapter()

    chain_advanced = threading.Event()

    real_submit_next = orchestrator.submit_next_queued_batch

    def _record_chain(*args, **kwargs):
        chain_advanced.set()
        return real_submit_next(*args, **kwargs)

    submission = NormalizedJobSubmission(
        generatorId=stub_cert.GENERATOR_ID,
        providerMetadata={},
    )
    with (
        patch.object(watcher_mod, "get_registry", return_value=_Registry()),
        patch.object(
            watcher_mod,
            "apply_shared_completion",
            side_effect=RuntimeError("simulated placement failure"),
        ),
        patch.object(orchestrator, "submit_next_queued_batch", side_effect=_record_chain),
    ):
        watcher_mod.start_completion_watcher(
            project_id=pid,
            scene_id=sid,
            batch_id=b1,
            execution_snapshot_id="snap-x",
            submission=submission,
            poll_interval_sec=0.05,
            timeout_sec=5.0,
        )
        assert chain_advanced.wait(timeout=5.0), (
            "watcher died on terminal-handling exception without advancing the chain"
        )
