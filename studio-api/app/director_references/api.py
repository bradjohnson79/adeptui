"""REST API for Timeline reference presets (item routes live on Master /director-timeline)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .errors import DirectorReferenceError
from .schemas import CreatePresetRequest
from .service import TimelineReferenceService

router = APIRouter(tags=["director-references"])


def _svc(db: Session) -> TimelineReferenceService:
    return TimelineReferenceService(db)


def _http(err: DirectorReferenceError) -> HTTPException:
    status = 404
    if err.code == "feature_disabled":
        status = 404
    elif err.code in ("version_conflict", "reference_cycle_detected", "invalid_reference_role", "invalid_influence"):
        status = 409 if err.code in ("version_conflict", "reference_cycle_detected") else 400
    elif err.code in ("binding_not_found", "timeline_item_not_found", "reference_asset_not_found", "preset_not_found", "version_not_found"):
        status = 404
    return HTTPException(status_code=status, detail=err.to_dict())


@router.get("/projects/{project_id}/reference-presets")
def list_presets(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    try:
        return _svc(db).list_presets(project_id)
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post("/projects/{project_id}/reference-presets")
def create_preset(
    project_id: str,
    body: CreatePresetRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).create_preset(
            project_id,
            body.name,
            body.description,
            [b.model_dump() for b in body.bindings],
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc
