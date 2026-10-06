"""Render status is a copy of the progress a sync already read."""

from app.director_timeline_w46.generation.contracts import NormalizedJobStatus
from app.film_timeline.contracts import Segment, Shot
from app.film_timeline import orchestrator
from app.film_timeline.render_status import (
    begin_api_generation,
    creator_render_status,
    hold_api_preparation,
    note_api_render_progress,
)


def test_creator_render_status_keeps_grounded_progress_and_drops_internals():
    stamped = creator_render_status(
        progress=0.42,
        telemetry={
            "progress": 0.42,
            "progressGrounded": True,
            "phase": "sampling",
            "phaseLabel": "Sampling",
            "elapsedActiveTime": 48,
            "message": "Sampling step 13/25",
            "currentNode": "10",
        },
        segment_status="generating",
    )
    assert stamped == {
        "progressGrounded": True,
        "status": "generating",
        "phaseLabel": "Generating",
        "progress": 0.42,
        "elapsedSec": 48.0,
    }


def test_ungrounded_status_does_not_invent_a_percent():
    stamped = creator_render_status(
        progress=0.2,
        telemetry={"progressGrounded": False, "phase": "preparing_model", "message": "Preparing model"},
        segment_status="generating",
    )
    assert "progress" not in stamped
    assert stamped["progressGrounded"] is False
    assert stamped["phaseLabel"] == "Preparing model"


def test_api_provider_progress_moves_through_queue_generate_and_finalize():
    rec: dict = {}
    note_api_render_progress(rec, message="preparing", elapsed_sec=1)
    assert rec["progressTelemetry"]["phaseLabel"] == "Preparing model"
    assert rec["progressTelemetry"]["apiPhase"] == "preparing"
    assert rec["progress"] == 0.05

    note_api_render_progress(rec, message="fal queued", elapsed_sec=2)
    assert rec["progressTelemetry"]["phaseLabel"] == "Queued"
    assert rec["progressTelemetry"]["apiPhase"] == "generating"
    assert rec["progress"] == 0.12

    note_api_render_progress(rec, message="fal in progress", elapsed_sec=0)
    assert rec["progressTelemetry"]["phaseLabel"] == "Generating"
    assert 0.18 <= rec["progress"] < 0.3

    note_api_render_progress(rec, message="fal in progress", elapsed_sec=600)
    assert 0.89 < rec["progress"] <= 0.90

    note_api_render_progress(rec, message="fal completed — downloading", elapsed_sec=610)
    assert rec["progressTelemetry"]["phaseLabel"] == "Finalizing"
    assert rec["progress"] == 0.92
    assert rec["progressTelemetry"]["progressGrounded"] is False

    stamped = creator_render_status(
        progress=0.0,
        telemetry=rec["progressTelemetry"],
        segment_status="generating",
    )
    assert stamped["progress"] == 0.92
    assert stamped["phaseLabel"] == "Finalizing"
    assert stamped["elapsedSec"] == 610.0
    assert stamped["apiPhase"] == "generating"


def test_api_preparation_hold_can_be_cancelled_before_the_provider():
    rec: dict = {"status": "running"}
    clock = {"t": 0.0}

    def monotonic() -> float:
        return clock["t"]

    def sleep(dt: float) -> None:
        clock["t"] += dt
        if clock["t"] >= 0.8:
            rec["status"] = "cancelled"

    assert hold_api_preparation(rec, seconds=10, monotonic=monotonic, sleep=sleep) is False
    assert rec["apiPhase"] == "preparing"
    assert rec["status"] == "cancelled"


def test_api_preparation_hold_then_generation_starts():
    rec: dict = {"status": "running"}
    clock = {"t": 0.0}

    def monotonic() -> float:
        return clock["t"]

    def sleep(dt: float) -> None:
        clock["t"] += dt

    assert hold_api_preparation(rec, seconds=1, monotonic=monotonic, sleep=sleep) is True
    assert rec["progressTelemetry"]["apiPhase"] == "preparing"
    begin_api_generation(rec)
    assert rec["apiPhase"] == "generating"
    assert rec["progressTelemetry"]["apiPhase"] == "generating"


def test_ungrounded_status_holds_the_last_stored_percent():
    stamped = creator_render_status(
        progress=0.0,
        telemetry={"progress": 0.4, "progressGrounded": False, "phase": "preparing_model"},
        segment_status="generating",
    )
    assert stamped["progress"] == 0.4
    assert stamped["progressGrounded"] is False


def test_refresh_shot_copies_the_status_it_already_received(monkeypatch):
    segment = Segment(
        id="seg_status",
        status="generating",
        generatorId="minimax-h3-i2v-local",
        generationMetadata={
            "submission": {
                "generatorId": "minimax-h3-i2v-local",
                "internalJobId": "job-secret-id",
            }
        },
    )
    shot = Shot(id="shot_status", segments=[segment], status="generating")

    def _status(job):
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            generatorId=job.generatorId,
            status="running",
            progress=0.42,
            providerMetadata={
                "progressTelemetry": {
                    "progress": 0.42,
                    "progressGrounded": True,
                    "phase": "sampling",
                    "elapsedActiveTime": 48,
                    "message": "Sampling step 13/25",
                    "currentNode": "10",
                }
            },
        )

    monkeypatch.setattr(orchestrator, "_adapter", lambda _gid: type("Adapter", (), {"get_status": staticmethod(_status)})())
    orchestrator._refresh_shot(None, shot)
    stamped = shot.segments[0].generationMetadata["renderStatus"]
    blob = str(stamped)
    assert stamped["progress"] == 0.42
    assert stamped["phaseLabel"] == "Generating"
    assert stamped["status"] == "generating"
    assert "13/25" not in blob
    assert "currentNode" not in blob
    assert "job-secret-id" not in blob
    assert "fps_mode" not in blob


def test_refresh_shot_failure_does_not_keep_a_raw_node_error(monkeypatch):
    segment = Segment(
        id="seg_fail",
        status="generating",
        generatorId="minimax-h3-i2v-local",
        generationMetadata={"submission": {"generatorId": "minimax-h3-i2v-local", "internalJobId": "job-1"}},
    )
    shot = Shot(id="shot_fail", segments=[segment], status="generating")

    def _status(job):
        return NormalizedJobStatus(
            internalJobId=job.internalJobId,
            generatorId=job.generatorId,
            status="failed",
            progress=0.9,
            errorMessage="Traceback node 10 fps_mode jobid=abc",
            providerMetadata={"progressTelemetry": {"progress": 0.9, "progressGrounded": True, "phase": "sampling"}},
        )

    monkeypatch.setattr(orchestrator, "_adapter", lambda _gid: type("Adapter", (), {"get_status": staticmethod(_status)})())
    orchestrator._refresh_shot(None, shot)
    assert shot.segments[0].status == "failed"
    assert "node" not in (shot.segments[0].error or "").lower()
    assert shot.segments[0].generationMetadata["renderStatus"]["status"] == "failed"
