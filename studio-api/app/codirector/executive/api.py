"""FastAPI routes for Co-Director M2.7 Production Executive."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ... import feature_flags as feature_flags_mod
from ...db import get_db
from .schemas import CreateJobRequest, JobActionRequest, MarkApprovalRequest
from .service import ProductionExecutiveService
from .store import JobStore
from .worker import production_worker

router = APIRouter(prefix="/jobs", tags=["codirector-production-executive"])


def _require_flag() -> None:
    if not feature_flags_mod.feature_flags.production_executive_v1:
        raise HTTPException(status_code=404, detail="Production Executive is not enabled.")


class ClosedLoopRequest(BaseModel):
    projectId: str
    sceneId: str
    owner: str = "user"
    idempotencyKey: Optional[str] = None
    provider: str = "local"


class WorkerDrainRequest(BaseModel):
    maxSteps: int = Field(default=50, ge=1, le=500)


@router.post("")
def create_job(body: CreateJobRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    ProductionExecutiveService.ensure_worker()
    job = ProductionExecutiveService.create_job(db, body)
    return {"job": job.model_dump()}


@router.post("/closed-loop")
def create_closed_loop(body: ClosedLoopRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    ProductionExecutiveService.ensure_worker()
    return ProductionExecutiveService.create_closed_loop(
        db,
        project_id=body.projectId,
        scene_id=body.sceneId,
        owner=body.owner,
        idempotency_key=body.idempotencyKey,
        provider=body.provider,
    )


@router.get("")
def list_queue(
    projectId: str = Query(...),
    status: Optional[str] = Query(None),
    sceneId: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    jobs = JobStore.list_jobs(
        db, project_id=projectId, status=status, scene_id=sceneId, limit=limit
    )
    return {"projectId": projectId, "jobs": [j.model_dump() for j in jobs]}


@router.get("/events")
def list_events(
    projectId: str = Query(...),
    jobId: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    events = JobStore.list_events(db, project_id=projectId, job_id=jobId, limit=limit)
    return {"projectId": projectId, "events": [e.model_dump() for e in events]}


@router.get("/notifications")
def list_notifications(
    projectId: str = Query(...),
    unreadOnly: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    notes = JobStore.list_notifications(
        db, projectId, unread_only=unreadOnly, limit=limit
    )
    return {"projectId": projectId, "notifications": [n.model_dump() for n in notes]}


@router.get("/statistics")
def statistics(projectId: str = Query(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    return JobStore.statistics(db, projectId)


@router.get("/scene-progress")
def scene_progress(
    projectId: str = Query(...),
    sceneId: str = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    return JobStore.scene_progress(db, projectId, sceneId).model_dump()


@router.post("/worker/drain")
def worker_drain(body: WorkerDrainRequest) -> dict[str, Any]:
    """Test/ops helper: synchronously process runnable jobs."""
    _require_flag()
    steps = production_worker.drain(max_steps=body.maxSteps)
    return {"steps": steps, "workerRunning": production_worker.running}


@router.get("/{job_id}")
def inspect_job(
    job_id: str,
    projectId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    job = JobStore.get_job(db, job_id, project_id=projectId)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job": job.model_dump()}


@router.get("/{job_id}/dependencies")
def job_dependencies(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    job = JobStore.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "jobId": job_id,
        "dependsOn": JobStore.dependency_statuses(db, job_id),
        "dependents": JobStore.list_dependents(db, job_id),
    }


@router.get("/{job_id}/history")
def job_history(job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    job = JobStore.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "jobId": job_id,
        "attempts": [a.model_dump() for a in JobStore.list_attempts(db, job_id)],
        "audit": [a.model_dump() for a in JobStore.list_audit(db, job_id)],
        "events": [
            e.model_dump()
            for e in JobStore.list_events(db, project_id=job.projectId, job_id=job_id)
        ],
    }


@router.post("/{job_id}/pause")
def pause_job(
    job_id: str, body: JobActionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_flag()
    try:
        job = ProductionExecutiveService.pause(db, job_id, actor=body.actor, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/{job_id}/resume")
def resume_job(
    job_id: str, body: JobActionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_flag()
    try:
        job = ProductionExecutiveService.resume(db, job_id, actor=body.actor, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/{job_id}/retry")
def retry_job(
    job_id: str, body: JobActionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_flag()
    try:
        job = ProductionExecutiveService.retry(db, job_id, actor=body.actor, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str, body: JobActionRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_flag()
    try:
        job = ProductionExecutiveService.cancel(db, job_id, actor=body.actor, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump()}


@router.post("/{job_id}/mark-approval")
def mark_approval(
    job_id: str, body: MarkApprovalRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Signal that M2.2 approval completed. Production Executive never auto-approves."""
    _require_flag()
    try:
        job = ProductionExecutiveService.mark_approval(db, job_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job": job.model_dump(), "autoApproved": False}