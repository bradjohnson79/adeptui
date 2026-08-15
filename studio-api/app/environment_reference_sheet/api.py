"""Read-only API for ERS review surfaces."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .store import list_sheets, load_sheet

router = APIRouter(prefix="/environment-reference-sheets", tags=["environment-reference-sheets"])


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _summary(sheet) -> dict[str, Any]:
    rendered = getattr(getattr(sheet, "composition", None), "renderedAssetIds", None) or {}
    composite = getattr(sheet, "ers_composite_asset_id", None)
    if not composite and isinstance(rendered, dict):
        composite = rendered.get("composite") or rendered.get("png") or rendered.get("sheet")
    approved = [
        view.direction
        for view in sheet.directionalViews
        if view.status == "approved" and view.approvedAssetId
    ]
    return {
        "sheetId": sheet.sheetId,
        "projectId": sheet.projectId,
        "name": sheet.name,
        "status": sheet.status,
        "sceneId": sheet.sceneId,
        "locationStableId": sheet.registration.locationStableId,
        "continuityStatus": sheet.continuity.status,
        "approvedDirections": approved,
        "ers_composite_asset_id": composite,
        "has_reference": bool(composite or approved),
        "exportKinds": [item.exportKind for item in sheet.exports if item.status == "created"],
        "updatedAt": sheet.updatedAt,
    }


@router.get("/projects/{project_id}")
def api_list_sheets(project_id: str, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    sheets = list_sheets(project_id)
    return {"sheets": [_summary(sheet) for sheet in sheets]}


@router.get("/projects/{project_id}/{sheet_id}")
def api_get_sheet(project_id: str, sheet_id: str, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise HTTPException(404, "Environment Reference Sheet not found")
    return {"sheet": sheet.model_dump(mode="json"), "summary": _summary(sheet)}
