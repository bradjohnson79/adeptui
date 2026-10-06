"""Multi-batch retake source + generationProgress + sequential N dispatch."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db import Base, Project, Scene, SessionLocal, engine
from app.director_timeline_w46 import orchestrator, service, store
from app.director_timeline_w46.contracts import (
    ApprovedClip,
    CandidateVersion,
    SceneTimelineMaster,
)
from app.director_timeline_w46.current_take import (
    compute_generation_progress,
    resolve_current_take,
)
from app.director_timeline_w46.generation import registry as registry_mod
from app.director_timeline_w46.generation.adapters import stub_cert


@pytest.fixture()
def db_scene():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    pid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    db.add(Project(id=pid, name="MultiBatch Retake", description=""))
    db.add(
        Scene(
            id=sid,
            project_id=pid,
            index=0,
            name="Scene 1",
            prompt="multi batch",
            duration_sec=20.0,
            director_json="",
        )
    )
    db.commit()
    try:
        yield db, pid, sid
    finally:
        db.close()


@pytest.fixture()
def stub_env(tmp_path, monkeypatch):
    monkeypatch.setenv(stub_cert.ENV_FLAG, "1")
    monkeypatch.setattr(stub_cert, "_cert_dir", lambda: tmp_path)
    registry_mod._REGISTRY = None
    yield tmp_path
    registry_mod._REGISTRY = None


def _make_batches(db, pid, sid, count=3):
    service.workspace(db, pid, sid)
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
    return ids


def test_resolve_current_take_prefers_latest_candidate_not_approved():
    batch = SceneTimelineMaster(
        batchBlocks=[
            __import__("app.director_timeline_w46.contracts", fromlist=["BatchBlock"]).BatchBlock(
                id="bb1",
                sceneId="s",
                status="CandidateReady",
                approvedClip=ApprovedClip(assetId="asset-approved", executionSnapshotId="snap-old"),
                candidateVersions=[
                    CandidateVersion(
                        id="cand-old",
                        executionSnapshotId="snap-old",
                        assetId="asset-approved",
                        takeId="take_old",
                        createdAt="2026-01-01T00:00:00+00:00",
                    ),
                    CandidateVersion(
                        id="cand-new",
                        executionSnapshotId="snap-new",
                        assetId="asset-generated",
                        takeId="take_new",
                        createdAt="2026-01-02T00:00:00+00:00",
                    ),
                ],
            )
        ]
    ).batchBlocks[0]
    resolved = resolve_current_take(batch)
    assert resolved is not None
    assert resolved["assetId"] == "asset-generated"
    assert resolved["source"] == "latest_candidate"
    assert resolved["takeId"] == "take_new"


def test_retake_range_uses_unapproved_generated_take(db_scene):
    db, pid, sid = db_scene
    ws = service.workspace(db, pid, sid)
    batch_id = ws["master"]["batchBlocks"][0]["id"]
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    batch = master.batchBlocks[0]
    batch.generatorId = "ltx-local"
    batch.status = "CandidateReady"
    batch.approvedClip = None
    batch.candidateVersions = [
        CandidateVersion(
            id="cand-gen",
            executionSnapshotId="snap-gen",
            assetId="asset-generated",
            takeId="take_gen",
        )
    ]
    batch.currentTakeId = "take_gen"
    batch.currentTakeAssetId = "asset-generated"
    store.save_master(db, pid, sid, master)

    captured = {}

    def fake_submit(db, project_id, scene_id, bid, **kwargs):
        captured.update(kwargs)
        captured["batch_id"] = bid
        return {"ok": True, "generatorId": "ltx-local", "mock": False}

    class _Gen:
        label = "LTX"
        locality = "local"
        executable = True
        inPaintStrategies = ["range_replacement"]
        supportsImageToVideo = True
        disabledReason = ""
        readiness = "Ready"

    with patch.object(orchestrator, "get_generator", return_value=_Gen()):
        with patch.object(orchestrator, "submit_batch_generation", side_effect=fake_submit):
            with patch.object(orchestrator, "add_repair_range", return_value={"ok": True, "ranges": [{"id": "rr_1"}]}):
                out = orchestrator.retake_range(
                    db, pid, sid, batch_id, start=0.0, length=2.0, prompt="fix the stumble"
                )
    assert out["ok"] is True, out
    assert out.get("error") != "APPROVED_TAKE_REQUIRED"
    rr = captured["continuity"]["rangeReplacement"]
    assert rr["sourceAssetId"] == "asset-generated"



def test_generation_progress_shape_on_master_get(db_scene):
    from app.director_timeline_w46.contracts import GenerationJobRef

    db, pid, sid = db_scene
    ids = _make_batches(db, pid, sid, count=3)
    payload = store.load_master(db, pid, sid)
    master = SceneTimelineMaster.model_validate(payload["master"])
    by_id = {b.id: b for b in master.batchBlocks}
    by_id[ids[0]].status = "Generating"
    by_id[ids[0]].generationJobs = [
        GenerationJobRef(executionSnapshotId="snap-g", status="running", progress=0.4)
    ]
    by_id[ids[1]].status = "Queued"
    by_id[ids[2]].status = "Queued"
    store.save_master(db, pid, sid, master)

    ws = service.workspace(db, pid, sid)
    assert ws["ok"] is True
    gp = ws["generationProgress"]
    for key in (
        "currentBatchIndex",
        "totalBatches",
        "batchStatus",
        "batchProgress",
        "sceneStatus",
        "message",
        "currentBatchId",
    ):
        assert key in gp, key
    assert gp["totalBatches"] == 3
    assert gp["currentBatchIndex"] == 1
    assert gp["batchStatus"] == "Generating"
    assert gp["sceneStatus"] == "generating"
    assert gp["currentBatchId"] == ids[0]
    assert abs(float(gp["batchProgress"]) - 0.4) < 1e-6
    assert isinstance(gp["message"], str)
    assert ws["master"]["generationProgress"]["totalBatches"] == 3

    derived = compute_generation_progress(master)
    assert derived["totalBatches"] == 3
    assert derived["batchStatus"] == "Generating"


def test_deposited_qc_windows_count_as_batches_complete():
    master = SceneTimelineMaster.model_validate(
        {
            "sceneId": "s1",
            "batchBlocks": [
                {
                    "id": "b1",
                    "sceneId": "s1",
                    "order": 0,
                    "status": "QC_RetryRequired",
                    "generatorId": "minimax-h3",
                    "duration": {"plannedDuration": 15},
                    "promptSegments": [{"text": "Opening.", "start": 0, "length": 15}],
                },
                {
                    "id": "b2",
                    "sceneId": "s1",
                    "order": 1,
                    "status": "QC_Pending",
                    "generatorId": "minimax-h3",
                    "duration": {"plannedDuration": 15},
                    "promptSegments": [{"text": "Next.", "start": 15, "length": 15}],
                },
                {
                    "id": "b3",
                    "sceneId": "s1",
                    "order": 2,
                    "status": "Queued",
                    "generatorId": "minimax-h3",
                    "duration": {"plannedDuration": 15},
                    "promptSegments": [{"text": "Later.", "start": 30, "length": 15}],
                },
                {
                    "id": "b4",
                    "sceneId": "s1",
                    "order": 3,
                    "status": "Queued",
                    "generatorId": "minimax-h3",
                    "duration": {"plannedDuration": 15},
                    "promptSegments": [{"text": "Ending.", "start": 45, "length": 15}],
                },
            ],
        }
    )
    progress = compute_generation_progress(master)
    assert progress["renderCompletedBatches"] == 2
    assert progress["overallBatchesLabel"] == "2/4 batches complete"
    assert "2/4 batches complete" in progress["statusLines"]


def test_sequential_n_dispatch_stages_all_later_batches(db_scene):
    db, pid, sid = db_scene
    ids = _make_batches(db, pid, sid, count=4)
    submitted: list[str] = []
    staged: list[str] = []

    def fake_submit(db, project_id, scene_id, batch_id, **kwargs):
        submitted.append(batch_id)
        return {"ok": True, "batchBlockId": batch_id, "mock": False}

    def fake_stage(db, project_id, scene_id, batch_id):
        staged.append(batch_id)
        payload = store.load_master(db, project_id, scene_id)
        master = SceneTimelineMaster.model_validate(payload["master"])
        batch = next(b for b in master.batchBlocks if b.id == batch_id)
        batch.status = "Queued"
        batch.pendingSnapshotId = f"snap-staged-{batch_id[-6:]}"
        store.save_master(db, project_id, scene_id, master)
        return {"ok": True, "staged": True, "batchBlockId": batch_id, "mock": False}

    with patch.object(orchestrator, "submit_batch_generation", side_effect=fake_submit):
        with patch.object(orchestrator, "stage_batch_snapshot", side_effect=fake_stage):
            result = orchestrator.generate_scene(db, pid, sid, scope="full")
    assert result["ok"] is True, result
    assert submitted == [ids[0]]
    assert staged == ids[1:]
    gp = compute_generation_progress(
        SceneTimelineMaster.model_validate(store.load_master(db, pid, sid)["master"])
    )
    assert gp["totalBatches"] == 4
