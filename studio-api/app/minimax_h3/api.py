"""FastAPI routes for the MiniMax H3 planning surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .capability import capability_matrix
from .contracts import AdeptMiniMaxH3Request
from .service import (
    access_snapshot,
    cancel,
    create_job_or_block,
    get_job,
    get_plan,
    prepare_plan,
    preflight,
    readiness,
    request_fallback_ltx,
    retry,
)
from .three_frame import build_segmented_plan

router = APIRouter(prefix="/minimax-h3", tags=["minimax-h3"])


class H3JobCreateRequest(BaseModel):
    projectId: str
    planId: str
    approvalId: str | None = None


class H3FallbackRequest(BaseModel):
    projectId: str
    planId: str
    approvalId: str | None = None
    acceptedBy: str = "creator"


class H3CancelRequest(BaseModel):
    projectId: str
    planId: str
    reason: str | None = None


class H3CancelJobRequest(BaseModel):
    projectId: str
    planId: str
    jobId: str | None = None
    reason: str | None = None


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _require_plan(project_id: str, plan_id: str):
    plan = get_plan(project_id, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="MiniMax H3 plan not found")
    return plan


@router.get("/capability")
def get_capability(territory: str) -> dict[str, Any]:
    return capability_matrix(territory)


@router.get("/readiness")
def get_readiness() -> dict[str, Any]:
    """Probe the isolated Route A runtime readiness (owner-only)."""
    return readiness()


@router.get("/access")
def get_access() -> dict[str, Any]:
    """Public-safety flags snapshot for the MiniMax H3 surface."""
    return access_snapshot()


@router.post("/prepare-plan")
def prepare_plan_route(request: AdeptMiniMaxH3Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, request.projectId)
    plan = prepare_plan(request)
    return {
        "ok": True,
        "planId": plan.planId,
        "creatorPreview": plan.creatorSummary,
        "plan": plan.model_dump(mode="json"),
        "preflight": plan.preflight.model_dump(mode="json") if plan.preflight else None,
    }


@router.post("/preflight")
def preflight_route(request: AdeptMiniMaxH3Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, request.projectId)
    plan = preflight(prepare_plan(request), approval_id=request.approvalId)
    return {"ok": True, "preflight": plan.preflight.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}


@router.post("/three-frame/plan")
def three_frame_plan_route(request: AdeptMiniMaxH3Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, request.projectId)
    if request.mode != "three-frame":
        raise HTTPException(status_code=400, detail="Use mode=three-frame for this endpoint.")
    return {"ok": True, "threeFramePlan": build_segmented_plan(request).model_dump(mode="json")}


@router.post("/jobs")
def create_job_route(body: H3JobCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, body.projectId)
    _require_plan(body.projectId, body.planId)
    return create_job_or_block(body.projectId, body.planId, approval_id=body.approvalId)


@router.get("/jobs/{project_id}/{job_id}")
def get_job_route(project_id: str, job_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return get_job(project_id, job_id)


@router.post("/jobs/cancel")
def cancel_job_route(body: H3CancelJobRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, body.projectId)
    _require_plan(body.projectId, body.planId)
    plan = cancel(body.projectId, body.planId, reason=body.reason)
    job_summary: dict[str, Any] | None = None
    if body.jobId:
        job_summary = get_job(body.projectId, body.jobId).get("job")
    return {
        "ok": True,
        "plan": plan.model_dump(mode="json"),
        "job": job_summary,
        "message": "MiniMax H3 generation cancelled. The runtime was interrupted.",
    }


@router.post("/fallback/ltx")
def accept_ltx_fallback_route(body: H3FallbackRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, body.projectId)
    plan = request_fallback_ltx(body.projectId, body.planId, accepted_by=body.acceptedBy)
    return {
        "ok": True,
        "planId": plan.planId,
        "message": "LTX fallback was recorded explicitly. MiniMax H3 did not auto-switch.",
        "plan": plan.model_dump(mode="json"),
        "fallback": plan.fallbackOffer.model_dump(mode="json") if plan.fallbackOffer else None,
        "preserved": {
            "prompt": plan.request.prompt,
            "frames": [item.model_dump(mode="json") for item in plan.referenceAssignments],
            "audioAssetId": plan.request.audioAssetId,
        },
    }


@router.get("/plans/{project_id}/{plan_id}")
def get_plan_route(project_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    return {"ok": True, "plan": plan.model_dump(mode="json")}


@router.post("/cancel")
def cancel_route(body: H3CancelRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, body.projectId)
    plan = cancel(body.projectId, body.planId, reason=body.reason)
    return {"ok": True, "plan": plan.model_dump(mode="json")}


@router.post("/retry")
def retry_route(body: H3JobCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, body.projectId)
    plan = retry(body.projectId, body.planId, approval_id=body.approvalId)
    return {"ok": True, "plan": plan.model_dump(mode="json"), "preflight": plan.preflight.model_dump(mode="json")}
