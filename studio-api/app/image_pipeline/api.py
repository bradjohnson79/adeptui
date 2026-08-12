"""FastAPI routes for the Adept Image Pipeline foundation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .candidates import attach_evaluation, recommend_candidate, select_candidate
from .contracts import ImageMasteringRequest, ProductionImageRequest, utc_now
from .creative_direction import build_creative_direction
from .mastering import build_mastering_result
from .orchestrator import creator_plan_preview, generate_candidates_for_plan, prepare_plan
from .repair import least_destructive_repair_ladder, reject_regression
from .store import load_candidate_group, load_plan, save_candidate_group, save_plan
from .validation import evaluate_candidate

router = APIRouter(prefix="/image-pipeline", tags=["image-pipeline"])


class CandidateGroupRequest(BaseModel):
    groupId: str


class CandidateSelectRequest(BaseModel):
    groupId: str
    candidateId: str


class CandidateEvaluateRequest(BaseModel):
    groupId: str
    candidateId: str


class CandidateRepairRequest(BaseModel):
    groupId: str
    candidateId: str
    parentCandidateId: str | None = None


class ApprovalRequest(BaseModel):
    kind: str | None = None
    approvedBy: str = "creator"


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _require_plan(project_id: str, plan_id: str):
    plan = load_plan(project_id, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    return plan


def _require_group(project_id: str, group_id: str):
    group = load_candidate_group(project_id, group_id)
    if group is None:
        raise HTTPException(404, "Candidate group not found")
    return group


def _refresh_plan_readiness(plan) -> None:
    unresolved = [req for req in plan.approvalRequirements if req.status == "required"]
    if plan.modelRoute.readiness == "blocked" and plan.modelRoute.requiresApproval and not plan.modelRoute.approvedForUse:
        plan.readiness = "blocked"
    elif unresolved:
        plan.readiness = "warning"
    else:
        plan.readiness = "ready"
    plan.updatedAt = utc_now()


@router.post("/prepare-plan")
def prepare_plan_route(
    request: ProductionImageRequest,
    projectPolicy: str = "Ask",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, request.projectId)
    plan = prepare_plan(request, project_policy=projectPolicy)
    save_plan(plan)
    return {
        "planId": plan.planId,
        "creatorPreview": creator_plan_preview(plan),
        "plan": plan.model_dump(mode="json"),
        "readiness": {"status": plan.readiness, "reasons": plan.readinessReasons},
    }


@router.get("/plans/{project_id}/{plan_id}")
def get_plan(project_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    return {"plan": plan.model_dump(mode="json")}


@router.post("/plans/{project_id}/{plan_id}/creative-direction")
def rebuild_creative_direction(
    project_id: str,
    plan_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    prompt = str(body.get("prompt") or plan.request.prompt)
    style_profile_id = body.get("styleProfileId") or plan.request.styleProfileId
    plan.creativeDirection = build_creative_direction(prompt, plan.shotIntent, style_profile_id)
    plan.previewSummary = plan.previewSummary = (
        f"{plan.request.purpose}: {plan.creativeDirection.creatorSummary or plan.creativeDirection.scenePurpose}"
    )
    plan.updatedAt = utc_now()
    save_plan(plan)
    return {"creativeDirection": plan.creativeDirection.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}


@router.post("/plans/{project_id}/{plan_id}/candidates/generate")
def generate_candidates(
    project_id: str,
    plan_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    requested_count = int(body.get("candidateCount") or plan.request.candidateCount)
    group = generate_candidates_for_plan(plan, requested_count=requested_count, db=db)
    save_candidate_group(group)
    return {
        "readiness": plan.readiness,
        "group": group.model_dump(mode="json"),
        "message": "Real jobs were queued only when the downstream runtime accepted them."
        if group.status == "queued"
        else "Candidate slots were created honestly without pretending finished assets exist.",
    }


@router.post("/plans/{project_id}/{plan_id}/candidates/recommend")
def recommend_candidate_route(
    project_id: str,
    plan_id: str,
    request: CandidateGroupRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    _require_plan(project_id, plan_id)
    group = _require_group(project_id, request.groupId)
    candidate, explanation = recommend_candidate(group)
    save_candidate_group(group)
    return {
        "recommendedCandidateId": candidate.candidateId if candidate else None,
        "explanation": explanation,
        "group": group.model_dump(mode="json"),
    }


@router.post("/plans/{project_id}/{plan_id}/candidates/select")
def select_candidate_route(
    project_id: str,
    plan_id: str,
    request: CandidateSelectRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    _require_plan(project_id, plan_id)
    group = _require_group(project_id, request.groupId)
    select_candidate(group, request.candidateId)
    save_candidate_group(group)
    return {"group": group.model_dump(mode="json")}


@router.post("/plans/{project_id}/{plan_id}/evaluate")
def evaluate_candidate_route(
    project_id: str,
    plan_id: str,
    request: CandidateEvaluateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    group = _require_group(project_id, request.groupId)
    candidate = next((item for item in group.candidates if item.candidateId == request.candidateId), None)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    evaluation = evaluate_candidate(plan, candidate)
    attach_evaluation(group, candidate.candidateId, evaluation)
    save_candidate_group(group)
    return {"evaluation": evaluation.model_dump(mode="json"), "group": group.model_dump(mode="json")}


@router.post("/plans/{project_id}/{plan_id}/repair")
def repair_candidate_route(
    project_id: str,
    plan_id: str,
    request: CandidateRepairRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    _require_plan(project_id, plan_id)
    group = _require_group(project_id, request.groupId)
    candidate = next((item for item in group.candidates if item.candidateId == request.candidateId), None)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    if candidate.evaluation is None:
        raise HTTPException(400, "Candidate must be evaluated before repair instructions can be built")

    regression = None
    if request.parentCandidateId:
        parent = next((item for item in group.candidates if item.candidateId == request.parentCandidateId), None)
        if parent is None or parent.evaluation is None:
            raise HTTPException(400, "Parent candidate evaluation not found")
        regression = reject_regression(parent.evaluation, candidate.evaluation)
    instructions = least_destructive_repair_ladder(candidate.evaluation)
    return {
        "instructions": [item.model_dump(mode="json") for item in instructions],
        "regression": regression,
    }


@router.post("/plans/{project_id}/{plan_id}/master")
def master_candidate_route(
    project_id: str,
    plan_id: str,
    body: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    group = _require_group(project_id, str(body.get("groupId") or ""))
    request = ImageMasteringRequest.model_validate(body.get("request") or body)
    candidate = next((item for item in group.candidates if item.candidateId == request.candidateId), None)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    result = build_mastering_result(request, candidate, plan=plan)
    return {"mastering": result.model_dump(mode="json")}


@router.post("/plans/{project_id}/{plan_id}/approve")
def approve_plan_route(
    project_id: str,
    plan_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    kinds = {request.kind} if request.kind else {item.kind for item in plan.approvalRequirements}
    for requirement in plan.approvalRequirements:
        if requirement.kind in kinds and requirement.status == "required":
            requirement.status = "approved"
            requirement.approvedBy = request.approvedBy
            requirement.approvedAt = utc_now()
    if plan.modelRoute.requiresApproval and (request.kind in {None, "deployment-route"}):
        plan.modelRoute.requiresApproval = False
        plan.modelRoute.approvedForUse = True
        plan.modelRoute.readiness = "ready"
    _refresh_plan_readiness(plan)
    save_plan(plan)
    return {"plan": plan.model_dump(mode="json")}


@router.get("/readiness/{project_id}/{plan_id}")
def plan_readiness(project_id: str, plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(project_id, plan_id)
    _refresh_plan_readiness(plan)
    return {
        "projectId": project_id,
        "planId": plan_id,
        "readiness": plan.readiness,
        "reasons": plan.readinessReasons,
        "route": plan.modelRoute.model_dump(mode="json"),
        "approvalRequirements": [item.model_dump(mode="json") for item in plan.approvalRequirements],
    }

