"""Working Context HTTP surface. Chat reads this; it is not a GPU router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import Project, get_db
from .working_context_service import (
    apply_instruction,
    apply_patch,
    assemble,
    diagnostics,
    record_approval,
    render_working_context_block,
)

router = APIRouter(tags=["codirector-working-context"])


def _require_project(db: Session, project_id: str) -> None:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail={"error": "PROJECT_NOT_FOUND", "projectId": project_id})


class WorkingContextPatch(BaseModel):
    activeSceneId: str | None = None
    activeShotId: str | None = None
    scene: dict[str, Any] | None = None
    performance: dict[str, Any] | None = None
    camera: dict[str, Any] | None = None
    preferenceHints: list[dict[str, Any]] | None = None


class CompileConfidenceBody(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)
    characterId: str = ""
    candidateSceneIds: list[str] = Field(default_factory=list)
    candidateCharacterIds: list[str] = Field(default_factory=list)


class ApprovalBody(BaseModel):
    what: str = Field(min_length=1, max_length=64)
    source: str = "creator"
    sceneId: str = ""
    shotId: str = ""
    assetId: str = ""
    characterId: str = ""


@router.get("/projects/{project_id}/working-context")
def get_working_context(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    ctx = assemble(db, project_id)
    return ctx.model_dump(mode="json")


@router.patch("/projects/{project_id}/working-context")
def patch_working_context(
    project_id: str, body: WorkingContextPatch, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    ctx = apply_patch(db, project_id, patch)
    return ctx.model_dump(mode="json")


@router.post("/projects/{project_id}/working-context/compile-confidence")
def compile_working_context_confidence(
    project_id: str, body: CompileConfidenceBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    ctx = apply_instruction(
        db,
        project_id,
        body.instruction,
        character_id=body.characterId,
        candidate_scene_ids=body.candidateSceneIds or None,
        candidate_character_ids=body.candidateCharacterIds or None,
    )
    return {
        "context": ctx.model_dump(mode="json"),
        "confidence": ctx.confidence.model_dump(mode="json"),
        "diagnostics": diagnostics(ctx),
        "promptBlock": render_working_context_block(ctx),
    }


@router.post("/projects/{project_id}/working-context/approvals")
def post_working_context_approval(
    project_id: str, body: ApprovalBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    ctx = record_approval(
        db,
        project_id,
        what=body.what,
        source=body.source,
        scene_id=body.sceneId,
        shot_id=body.shotId,
        asset_id=body.assetId,
        character_id=body.characterId,
    )
    return ctx.model_dump(mode="json")


@router.get("/projects/{project_id}/working-context/diagnostics")
def get_working_context_diagnostics(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    ctx = assemble(db, project_id)
    return diagnostics(ctx)
