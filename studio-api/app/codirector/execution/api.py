"""Execution REST API — endpoints for starting, advancing, canceling, and approving executions.

Spec §19: "Active Work Surface Controller" — the frontend calls these endpoints
to manage the Live Agent Work Surface.

Endpoints:
- POST   /codirector/projects/{project_id}/executions
- POST   /codirector/projects/{project_id}/executions/{execution_id}/approve
- POST   /codirector/projects/{project_id}/executions/{execution_id}/advance
- POST   /codirector/projects/{project_id}/executions/{execution_id}/cancel
- GET    /codirector/projects/{project_id}/executions/{execution_id}
- GET    /codirector/projects/{project_id}/executions
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from .advance import advance_execution_pack
from .cancel import cancel_execution
from .contracts import ExecutionPlan, ExecutionStatus
from .dispatcher import dispatch
from .pack_store import list_packs, load_pack
from ..routing.unified_intent import UnifiedIntent, UnifiedIntentKind, DispatchStrategy

router = APIRouter(prefix="/projects/{project_id}/executions", tags=["codirector-execution"])


class StartExecutionRequest(BaseModel):
    """Request body for starting an execution."""

    capability: str
    intent: str = "EXECUTION"
    context: dict[str, Any] = Field(default_factory=dict)
    character_name: str = ""
    character_id: str = ""
    scene_id: str = ""
    count: int = 1
    prompt: str = ""
    visual_style: str = ""
    attachment_asset_ids: list[str] = Field(default_factory=list)
    user_instructions: str = ""
    project_style: str = ""
    scene_context: Optional[dict[str, Any]] = None
    character_names: Optional[list[str]] = None
    frame_index: int = 0
    frame_metadata: Optional[dict[str, Any]] = None
    reference_asset_id: Optional[str] = None
    pre_approved: bool = False


@router.post("")
async def start_execution(project_id: str, body: StartExecutionRequest, db: Session = Depends(get_db)) -> dict:
    """Start a new execution."""
    unified_intent = UnifiedIntent(
        intent=UnifiedIntentKind.EXECUTION,
        capability=body.capability,
        confidence=1.0,
        dispatch=DispatchStrategy.DETERMINISTIC,
        classifier_source="deterministic",
    )

    ctx = {
        **body.context,
        "character_name": body.character_name,
        "character_id": body.character_id,
        "scene_id": body.scene_id,
        "count": body.count,
        "prompt": body.prompt,
        "visual_style": body.visual_style,
        "attachment_asset_ids": body.attachment_asset_ids,
        "user_instructions": body.user_instructions,
        "project_style": body.project_style,
        "scene_context": body.scene_context,
        "character_names": body.character_names,
        "frame_index": body.frame_index,
        "frame_metadata": body.frame_metadata,
        "reference_asset_id": body.reference_asset_id,
    }

    plan = await dispatch(db, project_id, unified_intent, ctx, pre_approved=body.pre_approved)
    return plan.model_dump(mode="json")


@router.post("/{execution_id}/advance")
async def advance_execution(project_id: str, execution_id: str, db: Session = Depends(get_db)) -> dict:
    """Advance an execution pack — poll real job state."""
    plan = advance_execution_pack(db, project_id, execution_id)
    if not plan:
        raise HTTPException(status_code=404, detail={"code": "EXECUTION_NOT_FOUND", "message": "Execution not found."})
    return plan.model_dump(mode="json")


@router.post("/{execution_id}/cancel")
async def cancel_execution_endpoint(project_id: str, execution_id: str, db: Session = Depends(get_db)) -> dict:
    """Cancel remaining jobs in an execution."""
    plan = cancel_execution(db, project_id, execution_id)
    if not plan:
        raise HTTPException(status_code=404, detail={"code": "EXECUTION_NOT_FOUND", "message": "Execution not found."})
    return plan.model_dump(mode="json")


@router.get("/{execution_id}")
async def get_execution(project_id: str, execution_id: str, db: Session = Depends(get_db)) -> dict:
    """Get the current state of an execution pack."""
    plan = load_pack(db, project_id, execution_id)
    if not plan:
        raise HTTPException(status_code=404, detail={"code": "EXECUTION_NOT_FOUND", "message": "Execution not found."})
    return plan.model_dump(mode="json")


@router.get("")
async def list_executions(
    project_id: str,
    active: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    """List execution packs for a project."""
    packs = list_packs(db, project_id, active_only=active)
    return {"executions": [p.model_dump(mode="json") for p in packs]}


@router.get("/active/latest")
async def get_active_execution(project_id: str, db: Session = Depends(get_db)) -> dict:
    """Return the most recent non-terminal execution pack for refresh recovery (spec §18)."""
    from .pack_store import get_active_execution_for_project
    plan = get_active_execution_for_project(db, project_id)
    if not plan:
        return {"execution": None}
    return {"execution": plan.model_dump(mode="json")}


@router.post("/{execution_id}/approve")
async def approve_execution(project_id: str, execution_id: str, db: Session = Depends(get_db)) -> dict:
    """Approve a pending execution plan and start actual generation.

    Only works for executions in PREVIEW status that have plan_data.
    Transitions the execution from PREVIEW to QUEUED and creates real GPU jobs.

    Returns the updated (now-running) execution plan on success.
    """
    from .dispatcher import approve_and_execute as _approve

    plan = await _approve(db, project_id, execution_id)
    if not plan:
        raise HTTPException(status_code=404, detail={
            "code": "EXECUTION_NOT_FOUND",
            "message": "Execution not found.",
        })
    if plan.status == ExecutionStatus.PREVIEW:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "APPROVE_FAILED",
                "message": plan.error or "Could not approve execution.",
            },
        )
    return plan.model_dump(mode="json")


class RegenerateFrameRequest(BaseModel):
    """Request body for targeted frame regeneration (spec §43)."""

    child_index: int
    user_instructions: str = ""


@router.post("/{execution_id}/regenerate-frame")
async def regenerate_frame(
    project_id: str,
    execution_id: str,
    body: RegenerateFrameRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Submit a targeted new job for a single frame (spec §43).

    Other frames remain unchanged. Returns the updated plan.
    """
    from .regenerate import regenerate_child_job

    plan = regenerate_child_job(
        db,
        project_id,
        execution_id,
        child_index=body.child_index,
        user_instructions=body.user_instructions,
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail={"code": "EXECUTION_NOT_FOUND", "message": "Execution or child job not found."},
        )
    return plan.model_dump(mode="json")
