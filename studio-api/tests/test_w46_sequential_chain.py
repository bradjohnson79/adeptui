"""Sequential submission chain + cert stub adapter (provider-boundary cert).

Proves REQUEST SNAPSHOT CREATED is distinct from PROVIDER JOB SUBMITTED and
that local sequential orchestration keeps provider submission concurrency = 1
— without executing any provider code.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import CancelRequest, SceneTimelineMaster
from app.director_timeline_w46.generation import registry as registry_mod
from app.director_timeline_w46.generation.adapters import stub_cert


@pytest.fixture()
def stub_env(tmp_path, monkeypatch):
    monkeypatch.setenv(stub_cert.ENV_FLAG, "1")
    monkeypatch.setattr(stub_cert, "_cert_dir", lambda: tmp_path)
    registry_mod._REGISTRY = None

    # Wiring cert: Production Control marks cert-stub executable=False (Gen).
    # Force Ready only inside this suite so sequential queue proofs can run.
    import app.director_timeline_w46.capabilities as caps

    real_list = caps.list_generators

    def _list_ready():
        out = []
        for gen in real_list():
            if gen.id == stub_cert.GENERATOR_ID:
                out.append(
                    gen.model_copy(
                        update={
                            "executable": True,
                            "readiness": "Ready",
                            "disabledReason": "",
                            "capabilityLabel": "Available",
                        }
                    )
                )
            else:
                out.append(gen)
        return out

    monkeypatch.setattr(caps, "list_generators", _list_ready)
    yield tmp_path
    registry_mod._REGISTRY = None


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="Seq Chain Cert", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="seq chain",
            duration_sec=15.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


def _make_batches(db, pid, sid, count=3):
    service.workspace(db, pid, sid)  # ensures master exists
    ids = []
    for i in range(count):
        if i == 0:
            ws = service.workspace(db, pid, sid)
            bid = ws["master"]["batchBlocks"][0]["id"]
        else:
            res = service.add_batch(db, pid, sid, label=f"Batch {i + 1}", planned_duration=5.0)
            bid = res["batch"]["id"] if "batch" in res else res["batchBlockId"]
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
                        "text": f"prompt for batch {i + 1}",
                        "role": "primary",
                        "strength": 1,
                        "anchorIds": [],
                        "executionStrategy": "compiled",
                        "versionId": f"psv{i}",
                    }
                ],
            },
        )
        ids.append(bid)
    # Queue-chain proofs use fake asset ids (no video files). Disable Auto
    # Continuity so bridge extract failure cannot strand B2..Bn.
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    master.continuityPolicy.autoContinuity = False
    master.continuityPolicy.configuredTailDuration = 0.0
    master.coDirectorContinuityPolicy.enabled = False
    store.save_master(db, pid, sid, master, touch_batches=False)
    return ids


def _master(db, pid, sid) -> SceneTimelineMaster:
    payload = store.load_master(db, pid, sid)
    return SceneTimelineMaster.model_validate(payload["master"])


def test_stub_registered_only_when_env_gated(stub_env):
    registry = registry_mod.get_registry()
    adapter = registry.get("cert-stub-local")
    assert adapter.id == stub_cert.GENERATOR_ID
    ids = list(registry.known_ids())
    assert "cert-stub-local" in ids


def test_stub_not_registered_without_env(monkeypatch):
    monkeypatch.delenv(stub_cert.ENV_FLAG, raising=False)
    registry_mod._REGISTRY = None
    try:
        registry = registry_mod.get_registry()
        with pytest.raises(registry_mod.GeneratorNotFoundError):
            registry.get("cert-stub-local")
    finally:
        registry_mod._REGISTRY = None


def test_sequential_generate_stages_then_chains(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2, b3 = _make_batches(db, pid, sid)

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        result = orchestrator.generate_scene(db, pid, sid, scope="full")
    assert result["ok"] is True

    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}

    # Submission concurrency = 1: only Batch 1 Generating; Batches 2/3 Queued
    # with pre-created immutable snapshots (REQUEST SNAPSHOT CREATED).
    assert by_id[b1].status == "Generating"
    assert by_id[b2].status == "Queued"
    assert by_id[b3].status == "Queued"
    assert by_id[b2].pendingSnapshotId
    assert by_id[b3].pendingSnapshotId
    snap2 = by_id[b2].pendingSnapshotId
    assert master.executionSnapshots[snap2].immutable is True

    # Exactly one provider submission happened (sink has 1 record, batch 1).
    sink = stub_cert.read_request_sink()
    assert len(sink) == 1
    assert sink[0]["request"]["batchBlockId"] == b1

        # SUCCESS (CandidateReady) - not Approve - advances the queue to Batch 2.
    # Fake cert assets have no files on disk; mock last-frame analyze so the
    # continuity gate cannot strand the ordered queue (live gens have real paths).
    def _ready_bridge(db, project_id, master, bridge):
        bridge.status = "Ready"
        bridge.error = None
        state = dict(bridge.continuityState or {})
        state["sourceAssetId"] = "asset-b1"
        bridge.continuityState = state
        return bridge

    def _green_handoff(db, *, project_id, scene_id, asset_id, batch, master, owner=False):
        from app.codirector.video_intelligence.gpu_lease import handoff_key, note_handoff
        from app.director_timeline_w46.generation.window_handoff import _take_id

        note_handoff(handoff_key(scene_id, _take_id(master), batch.id), state="ready")
        return {"ok": True, "readyForNext": True, "continuityQc": None, "equipmentQc": None}

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ), patch(
        "app.director_timeline_w46.continuity.analyze_bridge",
        side_effect=_ready_bridge,
    ), patch(
        "app.director_timeline_w46.generation.window_handoff.run_completion_reviews",
        side_effect=_green_handoff,
    ), patch(
        "app.codirector.video_intelligence.service.packet_blocks_submit",
        lambda *_a, **_k: False,
    ):
        done = orchestrator.complete_batch_candidate(
            db, pid, sid, b1,
            asset_id="asset-b1",
            generated_duration=5.0,
            execution_snapshot_id=by_id[b1].generationJobs[0].executionSnapshotId,
        )
    assert done["ok"] is True
    assert done.get("sequentialChain", {}).get("submitted") is True
    assert done["sequentialChain"]["batchBlockId"] == b2

    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}
    assert by_id[b1].status == "CandidateReady"
    assert by_id[b1].activeTakeId
    assert by_id[b2].status == "Generating"
    assert by_id[b2].pendingSnapshotId is None
    assert by_id[b3].status == "Queued"

    sink = stub_cert.read_request_sink()
    assert len(sink) == 2
    assert sink[1]["request"]["batchBlockId"] == b2
    # The chained submission reused the staged snapshot identity.
    assert sink[1]["request"]["executionSnapshotId"] == snap2


def test_failure_halts_queue_preserves_prior_complete(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2, b3 = _make_batches(db, pid, sid)

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        orchestrator.generate_scene(db, pid, sid, scope="full")

    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}
    snap1 = by_id[b1].generationJobs[0].executionSnapshotId

    from app.director_timeline_w46.generation.watcher import _mark_job_failed

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        _mark_job_failed(db, pid, sid, b1, snap1, "STUB_FAIL", "simulated failure")

    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}
    assert by_id[b1].status == "Failed"
    # Remaining Queued cancelled — do not skip to B2/B3.
    assert by_id[b2].status == "Cancelled"
    assert by_id[b3].status == "Cancelled"
    sink = stub_cert.read_request_sink()
    assert [r["request"]["batchBlockId"] for r in sink] == [b1]



def test_stop_remaining_kills_chain_and_preserves_authoring(db_scene, stub_env):
    db, pid, sid = db_scene
    b1, b2, b3 = _make_batches(db, pid, sid)

    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        orchestrator.generate_scene(db, pid, sid, scope="full")

    result = orchestrator.cancel_scene(
        db, pid, sid, CancelRequest(action="stop_remaining_scene_jobs")
    )
    assert result.ok is True

    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}
    # STOP != DELETE: prompts/config preserved; all batches Cancelled; no chain.
    for bid in (b1, b2, b3):
        assert by_id[bid].status == "Cancelled"
        assert by_id[bid].pendingSnapshotId is None
        assert by_id[bid].promptSegments[0].text.startswith("prompt for batch")
    sink = stub_cert.read_request_sink()
    assert len(sink) == 1  # only the original Batch 1 submission

    # Resume: Generate again re-submits Batch 1 and re-stages 2/3.
    with patch(
        "app.director_timeline_w46.generation.watcher.start_completion_watcher",
        MagicMock(),
    ):
        orchestrator.generate_scene(db, pid, sid, scope="full")
    master = _master(db, pid, sid)
    by_id = {b.id: b for b in master.batchBlocks}
    assert by_id[b1].status == "Generating"
    assert by_id[b2].status == "Queued"
    assert by_id[b3].status == "Queued"
    sink = stub_cert.read_request_sink()
    assert len(sink) == 2
    assert sink[1]["request"]["batchBlockId"] == b1


def test_stub_state_store_deterministic_transitions(stub_env):
    adapter = stub_cert.StubCertAdapter()
    from app.director_timeline_w46.generation.contracts import TimelineGenerationRequest

    req = TimelineGenerationRequest(
        projectId="p",
        sceneId="s",
        batchBlockId="b",
        executionSnapshotId="snap",
        generatorId=stub_cert.GENERATOR_ID,
        prompt="hello",
        duration=5.0,
    )
    sub = adapter.submit(req)
    assert sub.status == "queued"
    job_id = sub.queueJobId

    assert adapter.get_status(sub).status == "queued"
    stub_cert.set_stub_job_state(job_id, "running")
    assert adapter.get_status(sub).status == "running"
    stub_cert.set_stub_job_state(job_id, "succeeded", output_asset_ids=["asset-x"])
    status = adapter.get_status(sub)
    assert status.status == "completed"
    result = adapter.collect_result(sub)
    assert result.outputAssetIds == ["asset-x"]
    stub_cert.set_stub_job_state(job_id, "failed", error_code="E", error_message="boom")
    failed = adapter.get_status(sub)
    assert failed.status == "failed"
    assert failed.errorMessage == "boom"
    with pytest.raises(ValueError):
        stub_cert.set_stub_job_state(job_id, "bogus")
