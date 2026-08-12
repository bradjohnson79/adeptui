"""Unified product-level job projection across surfaces (W6P-11)."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import Job


STAGES = (
    "Planning",
    "Resolving",
    "WaitingForApproval",
    "Queued",
    "Preparing",
    "LoadingModels",
    "Encoding",
    "Sampling",
    "Decoding",
    "Assembling",
    "Validating",
    "RegisteringAsset",
    "PlacingOnTimeline",
    "Completed",
    "Cancelling",
    "Cancelled",
    "Failed",
)


def _stage_for_job(job: Job) -> str:
    status = (job.status or "").lower()
    msg = (job.message or "").lower()
    if status in {"cancel_requested", "cancelling"}:
        return "Cancelling"
    if status == "cancelled":
        return "Cancelled"
    if status == "failed":
        return "Failed"
    if status == "completed":
        return "Completed"
    if status == "queued":
        return "Queued"
    if "validat" in msg:
        return "Validating"
    if "register" in msg:
        return "RegisteringAsset"
    if "sample" in msg or "denois" in msg:
        return "Sampling"
    if "load" in msg and "model" in msg:
        return "LoadingModels"
    if "encode" in msg:
        return "Encoding"
    if "decode" in msg:
        return "Decoding"
    if "assembl" in msg or "stitch" in msg:
        return "Assembling"
    if status == "running":
        return "Preparing"
    return "Queued"


def project_job(job: Job) -> dict[str, Any]:
    params: dict[str, Any] = {}
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    intent = params.get("productionIntent") if isinstance(params.get("productionIntent"), dict) else {}
    vr = params.get("videoRuntime") if isinstance(params.get("videoRuntime"), dict) else {}
    progress = float(job.progress or 0.0)
    # Never invent numeric progress — expose only when runtime provided a value > 0
    credible_progress = progress if progress > 0 else None
    return {
        "jobId": job.id,
        "projectId": job.project_id,
        "sceneId": job.scene_id,
        "shotId": params.get("shot_id") or intent.get("shotId"),
        "operation": intent.get("operation") or job.kind,
        "workflowKey": vr.get("workflow_key") or vr.get("workflowKey"),
        "provider": vr.get("provider_kind") or vr.get("provider") or "local",
        "state": job.status,
        "stage": _stage_for_job(job),
        "progress": credible_progress,
        "progressMode": "numeric" if credible_progress is not None else "stage",
        "message": job.message,
        "intentId": intent.get("intentId") or vr.get("intent_id"),
        "toolId": intent.get("toolId"),
        "cancellationState": (
            "cancel_requested"
            if job.status == "cancel_requested"
            else (
                "cancelling"
                if job.status == "cancelling"
                else ("cancelled" if job.status == "cancelled" else None)
            )
        ),
        "retryAvailable": job.status in {"failed", "cancelled"},
        "resultLink": None if job.status != "completed" else f"/api/jobs/{job.id}",
        "failureReason": job.message if job.status == "failed" else None,
        "createdAt": getattr(job, "created_at", None),
        "updatedAt": getattr(job, "updated_at", None),
    }


def list_project_jobs(db: Session, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        db.query(Job)
        .filter(Job.project_id == project_id)
        .order_by(Job.created_at.desc() if hasattr(Job, "created_at") else Job.id.desc())
        .limit(limit)
        .all()
    )
    return [project_job(j) for j in rows]


def get_projected_job(db: Session, job_id: str) -> Optional[dict[str, Any]]:
    job = db.get(Job, job_id)
    if job is None:
        return None
    return project_job(job)
