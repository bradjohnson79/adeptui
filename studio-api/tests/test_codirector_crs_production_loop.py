"""CRS production completion law — wrapper enqueue is not production complete."""

from __future__ import annotations

from app.codirector.execution.contracts import ChildJobStatus, ExecutionPlan, ExecutionStatus
from app.codirector.execution.crs_lineage import (
    apply_crs_completion_law,
    bind_crs_child,
    extract_crs_job_id,
)


def test_extract_real_job_id_from_pack() -> None:
    pack = {
        "jobs": {"hero": {"jobId": "job-real-1", "status": "queued"}},
        "candidates": [{"jobId": "job-real-1", "status": "queued"}],
    }
    assert extract_crs_job_id(pack) == "job-real-1"


def test_bind_queued_when_wrapper_ok_without_asset() -> None:
    plan = ExecutionPlan(
        execution_id="exec-1",
        capability="character.generate_visual_sheet",
        project_id="proj-1",
    )
    bind_crs_child(
        plan,
        tool_id="character_creator.propose_visual_sheet",
        tool_result={
            "ok": True,
            "characterId": "char-1",
            "pack": {
                "characterId": "char-1",
                "status": "GENERATING",
                "jobs": {"hero": {"jobId": "job-qwen-1", "status": "queued"}},
                "candidates": [{"jobId": "job-qwen-1"}],
                "crsRevision": 5,
            },
        },
        ok=True,
        error=None,
        fallback_job_id="synthetic-uuid",
    )
    assert plan.child_jobs[0].job_id == "job-qwen-1"
    assert plan.child_jobs[0].status == ChildJobStatus.QUEUED
    assert plan.status == ExecutionStatus.QUEUED
    assert plan.result_asset_ids == []
    assert plan.plan_data["production_state"] == "queued"
    assert plan.plan_data["orchestration_state"] == "complete"


def test_child_done_without_asset_is_not_ready() -> None:
    plan = ExecutionPlan(
        execution_id="exec-2",
        capability="character.generate_visual_sheet",
        project_id="proj-1",
        status=ExecutionStatus.COMPLETED,
        result_asset_ids=[],
    )
    plan.child_jobs = []
    from app.codirector.execution.contracts import ChildJobView

    plan.child_jobs = [
        ChildJobView(job_id="job-1", status=ChildJobStatus.COMPLETED, asset_id=None),
    ]
    apply_crs_completion_law(plan)
    assert plan.status == ExecutionStatus.RUNNING
    assert plan.plan_data["production_state"] == "running"


def test_child_done_with_asset_is_ready() -> None:
    plan = ExecutionPlan(
        execution_id="exec-3",
        capability="character.generate_visual_sheet",
        project_id="proj-1",
        status=ExecutionStatus.COMPLETED,
        result_asset_ids=["asset-crs-1"],
    )
    apply_crs_completion_law(plan)
    assert plan.status == ExecutionStatus.COMPLETED
    assert plan.plan_data["production_state"] == "completed"


def test_stale_job_id_does_not_match_current_production_id() -> None:
    plan = ExecutionPlan(
        execution_id="exec-4",
        capability="character.generate_visual_sheet",
        project_id="proj-1",
    )
    bind_crs_child(
        plan,
        tool_id="character_creator.propose_visual_sheet",
        tool_result={"pack": {"jobs": {"hero": {"jobId": "job-current"}}}},
        ok=True,
        error=None,
        fallback_job_id="stale-id",
    )
    assert plan.plan_data["production_job_id"] == "job-current"
    assert plan.child_jobs[0].job_id != "stale-id"


def test_propose_sources_are_auto_or_explicit_gpt() -> None:
    from app.codirector.tools.handlers.character_creator import _crs_generator_sources

    auto = _crs_generator_sources({"candidates": True, "candidateCount": 4})
    assert auto["local"][0]["family"] == "auto"
    assert auto["local"][0]["family"] != "qwen2512"
    assert auto["local"][0]["batchCount"] == 1
    assert auto["api"] is None
    gpt = _crs_generator_sources({"generator": "gpt-image-2"})
    assert gpt["api"][0]["modelId"] == "gpt-image-2"
    assert gpt["local"] is None
