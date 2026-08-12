"""FastAPI routes for Multi-Shot Image Planning.

Mounted under `/api` (see app.main), so paths here start with `/projects/...`.
Every endpoint enforces project ownership: a plan/shot/candidate id that belongs
to a different project is answered with 404 — existence is never leaked across
projects. This module is the data/planning layer only; it never queues
generation or talks to a provider runtime.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import Project, Scene, get_db
from . import service
from .contracts import (
    MultiShotCandidateActionRequest,
    MultiShotCandidateCreate,
    MultiShotERSRecommendation,
    MultiShotPlanCreate,
    MultiShotPlanUpdate,
    MultiShotCreate,
    MultiShotReorderRequest,
    MultiShotSendToTimelineRequest,
    MultiShotUpdate,
)

router = APIRouter(prefix="/projects", tags=["multi-shot"])


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _require_scene(db: Session, project_id: str, scene_id: str) -> Scene:
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(404, "Scene not found")
    return scene


def _require_plan(db: Session, project_id: str, plan_id: str):
    plan = service.get_plan_row(db, project_id, plan_id)
    if plan is None:
        raise HTTPException(404, "Multi-shot plan not found")
    return plan


def _require_shot(db: Session, plan, shot_id: str):
    shot = service.get_shot_row(db, plan, shot_id)
    if shot is None:
        raise HTTPException(404, "Shot not found")
    return shot


def _plan_payload(db: Session, plan, include_candidates: bool = True) -> dict[str, Any]:
    shots = []
    for shot in service.list_shot_rows(db, plan):
        candidates = service.list_candidate_rows(db, shot) if include_candidates else None
        shots.append(service.shot_out(shot, candidates))
    return service.plan_out(plan, shots=shots, shot_count=len(shots))


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@router.post("/{project_id}/scenes/{scene_id}/multi-shot-plans")
def create_multi_shot_plan(
    project_id: str,
    scene_id: str,
    body: MultiShotPlanCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    _require_scene(db, project_id, scene_id)
    plan = service.create_plan(db, project_id, scene_id, body)
    return {"plan": service.plan_out(plan, shots=[], shot_count=0)}


@router.get("/{project_id}/scenes/{scene_id}/multi-shot-plans")
def list_multi_shot_plans(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    _require_scene(db, project_id, scene_id)
    plans = [service.plan_out(row, shot_count=count) for row, count in service.list_plans(db, project_id, scene_id)]
    return {"plans": plans}


@router.get("/{project_id}/multi-shot-plans/{plan_id}")
def get_multi_shot_plan(
    project_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    return {"plan": _plan_payload(db, plan)}


@router.patch("/{project_id}/multi-shot-plans/{plan_id}")
def update_multi_shot_plan(
    project_id: str,
    plan_id: str,
    body: MultiShotPlanUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    plan = service.update_plan(db, plan, body)
    return {"plan": _plan_payload(db, plan)}


@router.delete("/{project_id}/multi-shot-plans/{plan_id}")
def delete_multi_shot_plan(
    project_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    service.delete_plan(db, plan)
    return {"ok": True, "deletedPlanId": plan_id}


# ---------------------------------------------------------------------------
# Shots
# ---------------------------------------------------------------------------


@router.post("/{project_id}/multi-shot-plans/{plan_id}/shots")
def add_multi_shot(
    project_id: str,
    plan_id: str,
    body: MultiShotCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = service.add_shot(db, plan, body)
    return {"shot": service.shot_out(shot, candidates=[])}


@router.post("/{project_id}/multi-shot-plans/{plan_id}/shots/reorder")
def reorder_multi_shots(
    project_id: str,
    plan_id: str,
    body: MultiShotReorderRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    try:
        shots = service.reorder_shots(db, plan, body.shot_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"plan": service.plan_out(plan, shots=[service.shot_out(shot) for shot in shots], shot_count=len(shots))}


@router.patch("/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}")
def update_multi_shot(
    project_id: str,
    plan_id: str,
    shot_id: str,
    body: MultiShotUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = _require_shot(db, plan, shot_id)
    shot = service.update_shot(db, shot, body)
    return {"shot": service.shot_out(shot, candidates=service.list_candidate_rows(db, shot))}


@router.delete("/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}")
def delete_multi_shot(
    project_id: str,
    plan_id: str,
    shot_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = _require_shot(db, plan, shot_id)
    service.delete_shot(db, shot)
    return {"ok": True, "deletedShotId": shot_id}


# ---------------------------------------------------------------------------
# Candidates + approval (metadata only — never queues generation)
# ---------------------------------------------------------------------------


@router.post("/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}/candidates")
def add_multi_shot_candidate(
    project_id: str,
    plan_id: str,
    shot_id: str,
    body: MultiShotCandidateCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = _require_shot(db, plan, shot_id)
    candidate = service.add_candidate(db, plan, shot, body)
    return {
        "candidate": service.candidate_out(candidate),
        "shot": service.shot_out(shot, candidates=service.list_candidate_rows(db, shot)),
    }


@router.post("/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}/approve")
def approve_multi_shot_candidate(
    project_id: str,
    plan_id: str,
    shot_id: str,
    body: MultiShotCandidateActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = _require_shot(db, plan, shot_id)
    candidate = service.get_candidate_row(db, shot, body.candidate_id)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    shot = service.approve_candidate(db, shot, candidate)
    return {"shot": service.shot_out(shot, candidates=service.list_candidate_rows(db, shot))}


@router.post("/{project_id}/multi-shot-plans/{plan_id}/shots/{shot_id}/reject")
def reject_multi_shot_candidate(
    project_id: str,
    plan_id: str,
    shot_id: str,
    body: MultiShotCandidateActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    shot = _require_shot(db, plan, shot_id)
    candidate = service.get_candidate_row(db, shot, body.candidate_id)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    shot = service.reject_candidate(db, shot, candidate)
    return {"shot": service.shot_out(shot, candidates=service.list_candidate_rows(db, shot))}


@router.post("/{project_id}/multi-shot-plans/{plan_id}/send-to-timeline")
def send_to_timeline(
    project_id: str,
    plan_id: str,
    body: MultiShotSendToTimelineRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Hand off approved Multi-Shot images to the W46 Timeline as batch blocks.

    Creates one batch per approved shot, attaches the approved image as a visual
    clip, and sets the video prompt as the batch's prompt segment. Idempotent
    when ``onlyMissing`` is true (skips shots already linked to a batch).
    """
    _require_project(db, project_id)
    plan = _require_plan(db, project_id, plan_id)
    try:
        result = service.send_to_timeline(
            db,
            plan,
            only_missing=body.only_missing,
            generator_id=body.generator_id or None,
            default_duration=body.default_duration,
        )
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return {"ok": True, **result}


@router.get("/{project_id}/scenes/{scene_id}/multi-shot-ers-recommendation")
def get_multi_shot_ers_recommendation(
    project_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """ERS advisory for Krea 2 Multi-Shot on this scene."""
    _require_project(db, project_id)
    _require_scene(db, project_id, scene_id)
    rec = service.ers_recommendation_for_scene(db, project_id, scene_id)
    return MultiShotERSRecommendation(**rec).model_dump(by_alias=True)
