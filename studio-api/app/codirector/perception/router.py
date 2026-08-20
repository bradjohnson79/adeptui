"""Embedded perception API. Chat panel is not required."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db import get_db
from .contracts import AcceptRequest, UserCorrection
from .service import get_capability, review_scene
from .spatial_draft import apply_user_corrections, load_spatial_draft, save_spatial_draft

router = APIRouter(prefix="/perception", tags=["creation-perception"])


class CorrectionBody(BaseModel):
    corrections: list[UserCorrection]


class AutoMaskBody(BaseModel):
    mapId: str
    label: str = ""


@router.get("/capability")
def api_capability() -> dict[str, Any]:
    return {"capability": get_capability().model_dump()}


@router.get("/projects/{project_id}/maps/{map_id}/draft")
def api_get_draft(project_id: str, map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    draft = load_spatial_draft(db, project_id, map_id)
    return {
        "draft": draft.model_dump() if draft else None,
        "capability": get_capability().model_dump(),
    }


@router.post("/projects/{project_id}/maps/{map_id}/review")
def api_review(project_id: str, map_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        draft = review_scene(db, project_id, map_id)
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"code": "SCENE_REVIEW_FAILED", "message": str(exc)[:240]}) from exc
    return {"draft": draft.model_dump(), "capability": get_capability().model_dump()}


@router.post("/projects/{project_id}/maps/{map_id}/accept")
def api_accept(
    project_id: str,
    map_id: str,
    body: AcceptRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from .spatial_draft import accept_into_slots

    result = accept_into_slots(db, project_id, map_id, body)
    db.commit()
    return result.model_dump()


@router.post("/projects/{project_id}/maps/{map_id}/corrections")
def api_corrections(
    project_id: str,
    map_id: str,
    body: CorrectionBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    draft = load_spatial_draft(db, project_id, map_id)
    if draft is None:
        raise HTTPException(status_code=404, detail={"code": "DRAFT_NOT_FOUND", "message": "Run CD Scene Review first."})
    draft = apply_user_corrections(draft, body.corrections)
    save_spatial_draft(db, draft)
    db.commit()
    return {"draft": draft.model_dump()}


@router.post("/projects/{project_id}/auto-mask")
def api_auto_mask(project_id: str, body: AutoMaskBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    from .auto_mask import resolve_auto_mask

    return resolve_auto_mask(db, project_id, body.mapId, body.label)
