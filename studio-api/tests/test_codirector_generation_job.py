"""GenerationJob projection — honest progress, no invented percents."""

from __future__ import annotations

from app.codirector.execution.contracts import ChildJobStatus, ChildJobView, ExecutionPlan, ExecutionStatus
from pathlib import Path

from app.codirector.generation_job.project import execution_json, project_generation_job


def _plan(**kwargs) -> ExecutionPlan:
    base = dict(
        execution_id="exec-1",
        capability="image.generate",
        project_id="proj-1",
        status=ExecutionStatus.RUNNING,
        progress=0.0,
        child_jobs=[
            ChildJobView(
                job_id="job-1",
                label="Generated Image",
                status=ChildJobStatus.RUNNING,
                progress=0.0,
                stage="Sampling",
            )
        ],
    )
    base.update(kwargs)
    return ExecutionPlan(**base)


def test_generation_job_omits_percent_when_runtime_reports_zero() -> None:
    job = project_generation_job(_plan())
    assert job.id == "job-1"
    assert job.progressPercent is None
    assert job.stage == "Generating"
    assert job.modality == "image"
    assert job.operation == "image.generate"
    assert job.cancellable is True


def test_coarse_comfy_buckets_are_not_shown_as_percent() -> None:
    plan = _plan()
    plan.child_jobs[0].progress = 0.55
    assert project_generation_job(plan).progressPercent is None
    plan.child_jobs[0].progress = 0.2
    assert project_generation_job(plan).progressPercent is None


def test_generation_job_uses_runtime_percent_only_when_positive() -> None:
    plan = _plan()
    plan.child_jobs[0].progress = 0.47
    job = project_generation_job(plan)
    assert job.progressPercent == 47


def test_completed_job_is_100_and_not_cancellable() -> None:
    plan = _plan(
        status=ExecutionStatus.COMPLETED,
        progress=1.0,
        result_asset_ids=["asset-9"],
        child_jobs=[
            ChildJobView(
                job_id="job-1",
                status=ChildJobStatus.COMPLETED,
                progress=1.0,
                stage="Completed",
                asset_id="asset-9",
            )
        ],
    )
    job = project_generation_job(plan)
    assert job.status == "completed"
    assert job.progressPercent == 100
    assert job.stage == "Complete"
    assert job.outputAsset == "asset-9"
    assert job.cancellable is False


def test_first_frame_role_projects_from_plan_data() -> None:
    plan = _plan()
    plan.plan_data = {
        "productionRole": "video_first_frame",
        "intendedVideoProvider": "minimax-h3",
        "modality": "image",
    }
    job = project_generation_job(plan)
    assert job.productionRole == "video_first_frame"
    assert job.intendedVideoProvider == "minimax-h3"


def test_timeline_handoff_does_not_project_100_percent() -> None:
    plan = _plan(
        capability="timeline.generate_shot",
        status=ExecutionStatus.PREVIEW,
        surface_type="timeline_handoff",
        plan_data={"timelineHandoff": True, "shotIndex": 14, "owner": "timeline"},
        child_jobs=[
            ChildJobView(
                job_id="timeline-handoff-exec-1",
                label="Timeline shot 14",
                status=ChildJobStatus.PREVIEW,
            )
        ],
    )
    job = project_generation_job(plan)
    assert job.progressPercent is None
    assert job.status != "completed"
    assert job.stage == "Open Timeline"
    assert job.metadata.get("handoff") is True


def test_open_modality_accepts_voice_and_upscale() -> None:
    plan = _plan(capability="voice.generate")
    job = project_generation_job(plan)
    assert job.modality == "voice"
    plan2 = _plan()
    plan2.plan_data = {"modality": "upscale"}
    assert project_generation_job(plan2).modality == "upscale"


def test_audio_capabilities_project_generation_job() -> None:
    for cap, modality in (
        ("voice.generate", "voice"),
        ("music.generate", "music"),
        ("sfx.generate", "sfx"),
    ):
        job = project_generation_job(_plan(capability=cap))
        assert job.modality == modality
        assert job.operation == cap


def test_job_scoped_override_projects() -> None:
    plan = _plan()
    plan.plan_data = {"jobScopedOverride": True, "modality": "video"}
    job = project_generation_job(plan)
    assert job.jobScopedOverride is True


def test_failed_and_cancelled_are_terminal() -> None:
    failed = project_generation_job(_plan(status=ExecutionStatus.FAILED, child_jobs=[
        ChildJobView(job_id="job-1", status=ChildJobStatus.FAILED, stage="Failed")
    ]))
    assert failed.status == "failed"
    assert failed.progressPercent is None
    cancelled = project_generation_job(_plan(status=ExecutionStatus.CANCELLED, child_jobs=[
        ChildJobView(job_id="job-1", status=ChildJobStatus.CANCELLED, stage="Cancelled")
    ]))
    assert cancelled.status == "cancelled"


def test_status_messenger_payload_includes_generation_job() -> None:
    from app.codirector.execution.status_messenger import _serialize_plan_summary

    payload = _serialize_plan_summary(_plan())
    assert payload["generationJob"]["id"] == "job-1"
    assert "providerLabel" in payload["generationJob"]


def test_execution_json_is_the_only_plan_serializer() -> None:
    plan = _plan()
    payload = execution_json(plan)
    assert payload["generationJob"]["id"] == "job-1"
    api = Path(__file__).resolve().parents[1] / "app" / "codirector" / "execution" / "api.py"
    text = api.read_text(encoding="utf-8")
    assert "execution_json(" in text
    assert "attach_generation_job(" not in text
    assert "plan.model_dump" not in text
    service = Path(__file__).resolve().parents[1] / "app" / "codirector" / "service.py"
    svc = service.read_text(encoding="utf-8")
    assert "execution_json(plan)" in svc
    messenger = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "codirector"
        / "execution"
        / "status_messenger.py"
    ).read_text(encoding="utf-8")
    assert "execution_json(" in messenger
    assert "plan.model_dump" not in messenger


def test_dispatcher_persists_before_handle() -> None:
    src = (Path(__file__).resolve().parents[1] / "app" / "codirector" / "execution" / "dispatcher.py").read_text(
        encoding="utf-8"
    )
    persist = src.find("save_pack(db, project_id, plan)")
    handle = src.find("result = handle(")
    assert persist != -1 and handle != -1
    assert persist < handle
