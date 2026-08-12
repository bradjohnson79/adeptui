"""Authorization helpers for scene reference mutations."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import Asset, Project


def require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def require_asset_in_project(db: Session, project_id: str, asset_id: str) -> Asset:
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CROSS_PROJECT_ASSET_DENIED",
                "message": "Asset is not in this project; cross-project reference reuse is denied.",
            },
        )
    return asset


def deny_external_url(url: str | None) -> None:
    if url and (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EXTERNAL_URL_REF_DENIED",
                "message": "External URL references are not allowed; use project assets only.",
            },
        )
