"""Project-scoped authorization for continuity domain."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db import Asset, Project


def require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Project not found."},
        )
    return project


def assert_same_project(entity_project_id: str, project_id: str, *, what: str = "resource") -> None:
    if entity_project_id != project_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CROSS_PROJECT_DENIED",
                "message": f"Cross-project {what} access is denied.",
            },
        )


def require_project_asset(db: Session, project_id: str, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(
            status_code=404,
            detail={"code": "ASSET_NOT_FOUND", "message": "Asset not found."},
        )
    # Asset.project_id is the owning project for project-scoped assets
    owner = getattr(asset, "project_id", None) or getattr(asset, "projectId", None)
    if owner and str(owner) != project_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CROSS_PROJECT_DENIED",
                "message": "Cross-project asset access is denied.",
            },
        )
    return asset
