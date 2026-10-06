"""P6 hygiene: Timeline Generation Reconciler + master collapse guard."""
from __future__ import annotations

from types import SimpleNamespace

from app.director_timeline_w46.generation import timeline_reconciler
from app.director_timeline_w46.generation.timeline_reconciler import (
    queue_job_id_for_reconcile,
    reconcile_batch_from_job,
    refuse_master_structure_collapse,
)
from app.director_timeline_w46.contracts import (
    BatchBlock,
    DurationState,
    GenerationJobRef,
    SceneTimelineMaster,
)


def test_refuse_collapse_multi_to_foreign_draft():
    prev = {
        "batchBlocks": [
            {"id": "bb_a", "status": "Approved", "order": 0},
            {"id": "bb_b", "status": "Generating", "order": 1},
        ]
    }
    incoming = {
        "batchBlocks": [
            {"id": "bb_new", "status": "Draft", "order": 0},
        ]
    }
    err = refuse_master_structure_collapse(previous=prev, incoming=incoming)
    assert err is not None
    assert err["error"] == "MASTER_STRUCTURE_COLLAPSE_REFUSED"


def test_refuse_collapse_drop_sibling():
    prev = {
        "batchBlocks": [
            {"id": "bb_a", "status": "Approved", "order": 0},
            {"id": "bb_b", "status": "NeedsDialogueRetake", "order": 1},
        ]
    }
    incoming = {"batchBlocks": [{"id": "bb_a", "status": "Approved", "order": 0}]}
    err = refuse_master_structure_collapse(previous=prev, incoming=incoming)
    assert err is not None


def test_allow_same_multi_batch_update():
    prev = {
        "batchBlocks": [
            {"id": "bb_a", "status": "Approved", "order": 0},
            {"id": "bb_b", "status": "Generating", "order": 1},
        ]
    }
    incoming = {
        "batchBlocks": [
            {"id": "bb_a", "status": "Approved", "order": 0},
            {"id": "bb_b", "status": "QC_Pending", "order": 1},
        ]
    }
    assert refuse_master_structure_collapse(previous=prev, incoming=incoming) is None


def test_batch_status_accepts_qc_pending():
    b = BatchBlock(
        id="bb_x",
        sceneId="sc_x",
        order=0,
        label="W1",
        status="QC_Pending",
        duration=DurationState(plannedDuration=15.0),
    )
    assert b.status == "QC_Pending"
    b2 = BatchBlock(
        id="bb_y",
        sceneId="sc_x",
        order=1,
        label="W2",
        status="QC_RetryRequired",
        duration=DurationState(plannedDuration=15.0),
    )
    assert b2.status == "QC_RetryRequired"


def test_done_job_without_library_asset_does_not_close_the_take(monkeypatch):
    batch = BatchBlock(
        id="bb_w1",
        sceneId="sc_x",
        order=0,
        label="W1",
        status="Generating",
        duration=DurationState(plannedDuration=15.0),
        generationJobs=[
            GenerationJobRef(
                executionSnapshotId="snap_1",
                queueJobId="job-1",
                status="running",
            )
        ],
    )
    master = SceneTimelineMaster(batchBlocks=[batch])
    job = SimpleNamespace(status="done", output_path=r"C:\renders\scene.mp4", params_json="{}")
    monkeypatch.setattr(timeline_reconciler, "_job_row", lambda _db, _qid: job)
    monkeypatch.setattr(
        "app.director_timeline_w46.store.load_master",
        lambda *_a, **_k: {"ok": True, "master": master.model_dump()},
    )
    saved: list[bool] = []
    monkeypatch.setattr(
        "app.director_timeline_w46.store.save_master",
        lambda *_a, **_k: saved.append(True),
    )
    result = reconcile_batch_from_job(
        None,
        project_id="p",
        scene_id="s",
        batch_id="bb_w1",
        queue_job_id="job-1",
    )
    assert result["reason"] == "awaiting_library_asset"
    assert batch.status == "Generating"
    assert saved == []


def test_queued_window_is_not_closed_by_a_previous_takes_job():
    batch = BatchBlock(
        id="bb_w2",
        sceneId="s",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=15.0),
        pendingSnapshotId="snap_new",
        generationJobs=[
            GenerationJobRef(
                executionSnapshotId="snap_old",
                queueJobId="job-previous-take",
                status="completed",
            )
        ],
    )
    assert queue_job_id_for_reconcile(batch) is None


def test_queued_window_reconciles_only_its_own_snapshot_job():
    batch = BatchBlock(
        id="bb_w2",
        sceneId="s",
        order=1,
        status="Queued",
        duration=DurationState(plannedDuration=15.0),
        pendingSnapshotId="snap_new",
        generationJobs=[
            GenerationJobRef(
                executionSnapshotId="snap_old",
                queueJobId="job-previous-take",
                status="completed",
            ),
            GenerationJobRef(
                executionSnapshotId="snap_new",
                queueJobId="job-this-window",
                status="running",
            ),
        ],
    )
    assert queue_job_id_for_reconcile(batch) == "job-this-window"
