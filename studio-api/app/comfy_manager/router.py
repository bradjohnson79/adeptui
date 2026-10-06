"""Comfy Manager API. Observes Comfy and calls the existing job owner."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import Asset, Job, Project, get_db
from ..queue_worker import job_queue
from .operations import referenced_asset_ids, retry_blockers
from .snapshot import _loads, build_snapshot

router = APIRouter(prefix="/comfy-manager", tags=["comfy-manager"])


@router.get("/snapshot")
def get_snapshot(db: Session = Depends(get_db)) -> dict:
    return build_snapshot(db)


@router.post("/pause")
def pause_submissions() -> dict:
    return job_queue.pause_adept_submissions()


@router.post("/resume")
def resume_submissions() -> dict:
    return job_queue.resume_adept_submissions()


@router.post("/jobs/{job_id}/cancel")
async def cancel_adept_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "That job is not an Adept job. External Comfy work is left alone.")
    result = await job_queue.cancel_and_halt(job_id)
    return {"ok": bool(result.get("ok")), "status": result.get("status"), "promptId": result.get("promptId"), "external": False}


@router.post("/jobs/{job_id}/retry")
async def retry_adept_job(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    params = _loads(job.params_json)
    project = db.get(Project, job.project_id)
    wanted = referenced_asset_ids(params)
    present: set[str] = set()
    if wanted:
        present = {
            row.id
            for row in db.query(Asset).filter(Asset.id.in_(wanted), Asset.project_id == job.project_id).all()
        }
    blocker = retry_blockers(
        project_exists=project is not None,
        params=params,
        present_asset_ids=present,
        status=job.status,
    )
    if blocker:
        raise HTTPException(409, blocker)
    import uuid
    from datetime import datetime

    fresh = Job(
        id=str(uuid.uuid4()),
        project_id=job.project_id,
        scene_id=job.scene_id,
        kind=job.kind,
        status="queued",
        progress=0,
        message="Retry queued from Comfy Manager",
        stage="queued",
        params_json=job.params_json,
        history_json="{}",
    )
    history = {"retryOf": job.id, "retriedAt": datetime.utcnow().isoformat() + "Z"}
    fresh.history_json = __import__("json").dumps(history)
    db.add(fresh)
    db.commit()
    await job_queue.enqueue(fresh.id)
    return {"ok": True, "jobId": fresh.id, "retryOf": job.id}


@router.post("/reconcile")
def reconcile_status(db: Session = Depends(get_db)) -> dict:
    """Re-read Adept and Comfy. Does not mark a job successful."""
    snap = build_snapshot(db)
    return {
        "ok": True,
        "mutated": False,
        "note": "Status was compared again. Nothing was marked successful.",
        "snapshot": snap,
    }


@router.post("/cleanup/preview")
def cleanup_preview() -> dict:
    return {
        "items": [],
        "bytes": 0,
        "note": "No temporary file was proven safe to remove. Nothing will be deleted.",
    }
