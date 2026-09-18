"""Project GenerationJob from frozen ExecutionPlan + Studio Job."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Job
from ..execution.contracts import ExecutionPlan
from .contracts import GenerationJob


_STAGE_MAP = {
    "planning": "Preparing",
    "resolving": "Preparing",
    "waitingforapproval": "Preparing",
    "queued": "Queued",
    "preparing": "Preparing",
    "preparingcontrols": "Preparing",
    "preparingmasks": "Preparing",
    "loadingmodels": "Loading model",
    "loading model": "Loading model",
    "loading_models": "Loading model",
    "encoding": "Encoding",
    "sampling": "Generating",
    "generating": "Generating",
    "processing": "Generating",
    "running": "Generating",
    "compositing": "Decoding",
    "decoding": "Decoding",
    "saving": "Saving",
    "validating": "Saving",
    "registeringasset": "Saving",
    "creatingversion": "Saving",
    "completed": "Complete",
    "cancelling": "Cancelled",
    "cancelled": "Cancelled",
    "failed": "Failed",
}

_OPERATION_MODALITY = {
    "image.generate": "image",
    "image.edit": "edit",
    "image.generate_batch": "image",
    "video.generate": "video",
    "video.three_frame": "video",
    "voice.generate": "voice",
    "music.generate": "music",
    "sfx.generate": "sfx",
    "atlas.generate": "image",
    "atlas.assign": "image",
    "ers.generate": "image",
    "scene.generate": "image",
    "storyboard.generate": "image",
    "character.generate_visual_sheet": "image",
    "timeline.generate_shot": "video",
    "timeline.prepare_scene": "video",
}


def _creator_stage(raw: str, status: str) -> str:
    key = (raw or "").replace(" ", "").replace("_", "").lower()
    if key in _STAGE_MAP:
        return _STAGE_MAP[key]
    status_key = (status or "").lower()
    if status_key in {"completed", "failed", "cancelled"}:
        return _STAGE_MAP.get(status_key, status_key.title())
    if status_key in {"queued", "preparing"}:
        return status_key.title()
    if status_key == "running":
        return "Generating"
    return "Preparing"


def _elapsed_sec(created_at: Any) -> Optional[float]:
    if created_at is None:
        return None
    try:
        if isinstance(created_at, str):
            stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            stamp = created_at
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds())
    except Exception:
        return None


def _params(job: Optional[Job]) -> dict[str, Any]:
    if job is None:
        return {}
    try:
        data = json.loads(job.params_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# Coarse Comfy buckets (0.2 queued / 0.55 running) are not sampler percents.
_COARSE_FRACTIONS = {0.2, 0.55}


def _honest_percent(raw: Any) -> Optional[int]:
    """Numeric percent only when the runtime reported real progress — never coarse buckets."""
    try:
        value = float(raw or 0.0)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value <= 1.0:
        rounded = round(value, 2)
        if rounded in _COARSE_FRACTIONS:
            return None
        return max(1, min(100, int(round(value * 100))))
    return max(1, min(100, int(round(value))))


def _capability_operation(capability: str) -> str:
    return capability or "image.generate"


def project_generation_job(
    plan: ExecutionPlan,
    job: Optional[Job] = None,
    *,
    db: Optional[Session] = None,
) -> GenerationJob:
    """Build the shared GenerationJob projection. Never invents a percent."""

    child = plan.child_jobs[0] if plan.child_jobs else None
    job_id = ""
    if job is not None:
        job_id = job.id
    elif child is not None:
        job_id = child.job_id
    if not job_id:
        job_id = plan.execution_id

    if job is None and db is not None and child is not None and child.job_id:
        job = db.get(Job, child.job_id)

    params = _params(job)
    creative = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    plan_data = dict(plan.plan_data or {})
    runtime = params.get("imageRuntime") if isinstance(params.get("imageRuntime"), dict) else {}
    video_runtime = params.get("videoRuntime") if isinstance(params.get("videoRuntime"), dict) else {}

    status = (job.status if job is not None else plan.status.value).lower()
    if status == "cancel_requested":
        status = "cancelled"
    if status not in {"queued", "preparing", "running", "completed", "failed", "cancelled"}:
        if status in {"preview"}:
            status = "preparing"
        else:
            status = "running" if child and child.status.value == "running" else plan.status.value

    raw_stage = ""
    if job is not None:
        raw_stage = str(job.stage or job.message or "")
    if not raw_stage and child is not None:
        raw_stage = child.stage or child.message or ""
    if not raw_stage:
        raw_stage = runtime.get("stage") or video_runtime.get("stage") or plan.status.value

    reported = None
    if job is not None:
        reported = _honest_percent(job.progress)
    if reported is None and child is not None:
        reported = _honest_percent(child.progress)
    if reported is None:
        # Pack progress is completed/total — only use it when a child actually finished.
        if plan.completed_children and plan.total_children:
            reported = _honest_percent(plan.progress)

    operation = _capability_operation(plan.capability)
    modality = str(
        plan_data.get("modality")
        or creative.get("modality")
        or _OPERATION_MODALITY.get(operation, operation.split(".")[0] if "." in operation else "image")
    )
    asset_id = None
    if plan.result_asset_ids:
        asset_id = plan.result_asset_ids[0]
    elif child is not None:
        asset_id = child.asset_id

    error = plan.error or (child.error if child is not None else None) or (job.message if job is not None and status == "failed" else None)
    provider = (
        plan.provider
        or runtime.get("provider")
        or runtime.get("provider_kind")
        or video_runtime.get("provider")
        or video_runtime.get("provider_kind")
        or creative.get("resolvedProvider")
        or ""
    )
    model = (
        plan.model
        or runtime.get("engine")
        or runtime.get("workflow_key")
        or video_runtime.get("workflow_key")
        or creative.get("workflowKey")
        or ""
    )

    if plan.surface_type == "timeline_handoff" or plan_data.get("timelineHandoff"):
        return GenerationJob(
            id=job_id,
            executionId=plan.execution_id,
            modality="video",
            operation=plan.capability or "timeline.generate_shot",
            provider="",
            model="",
            status="preparing",
            stage="Open Timeline",
            progressPercent=None,
            elapsedSec=_elapsed_sec(getattr(job, "created_at", None) or plan.created_at),
            outputAsset=None,
            error=None,
            cancellable=False,
            metadata={"capability": plan.capability, "surfaceType": plan.surface_type, "handoff": True},
        )

    return GenerationJob(
        id=job_id,
        executionId=plan.execution_id,
        modality=modality,
        operation=operation,
        provider=str(provider or ""),
        model=str(model or ""),
        status=status,  # type: ignore[arg-type]
        stage=_creator_stage(str(raw_stage), status),
        progressPercent=100 if status == "completed" else reported,
        elapsedSec=_elapsed_sec(getattr(job, "created_at", None) or plan.created_at),
        queuePosition=None,
        outputAsset=asset_id,
        error=error,
        cancellable=status in {"queued", "preparing", "running"},
        productionRole=str(plan_data.get("productionRole") or creative.get("productionRole") or ""),
        intendedVideoProvider=str(
            plan_data.get("intendedVideoProvider") or creative.get("intendedVideoProvider") or ""
        ),
        jobScopedOverride=bool(plan_data.get("jobScopedOverride") or creative.get("jobScopedOverride")),
        metadata={
            "capability": plan.capability,
            "surfaceType": plan.surface_type,
        },
    )


def attach_generation_job(payload: dict[str, Any], plan: ExecutionPlan, db: Optional[Session] = None) -> dict[str, Any]:
    """Add generationJob onto an existing execution payload without renaming fields."""

    out = dict(payload)
    job = project_generation_job(plan, db=db)
    dumped = job.model_dump(mode="json")
    from ..preferences.resolver import creator_provider_label

    dumped["providerLabel"] = creator_provider_label(job.provider) if job.provider else ""
    out["generationJob"] = dumped
    return out


def execution_json(plan: ExecutionPlan, db: Optional[Session] = None) -> dict[str, Any]:
    """Canonical serializer for every execution-plan HTTP/SSE response.

    Callers must not model_dump or hand-build an execution payload afterward.
    """

    return attach_generation_job(plan.model_dump(mode="json"), plan, db=db)
