"""Scene Creator region-edit / inpaint route.

Kept off ``router.py`` so the orientation3d agent can edit that file without
merge collisions. Mounted the same way as the Scene Creator router.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Project, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scene-creator", tags=["scene-creator-region-edit"])


class RegionEditBody(BaseModel):
    operation: str = "remove"
    prompt: str = ""
    maskAssetId: str = ""
    mask_asset_id: str = ""
    sourceAssetId: str = ""
    source_asset_id: str = ""
    stage: str = "preview"
    local_family: str = ""
    local_enabled: bool = True
    api_enabled: bool = False
    api_model: str = ""


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _service_error(exc: Exception) -> HTTPException:
    from .ers_resolver import ErsResolveError
    from .service import SceneCreatorError

    if isinstance(exc, (SceneCreatorError, ErsResolveError, ValueError)):
        return HTTPException(400, str(exc))
    logger.exception("Scene Creator region edit error")
    return HTTPException(500, str(exc))


@router.post("/projects/{project_id}/shots/{shot_id}/region-edit")
def api_region_edit_shot(
    project_id: str,
    shot_id: str,
    body: RegionEditBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import region_edit_shot

    try:
        shot = region_edit_shot(
            db,
            project_id,
            shot_id,
            operation=body.operation,
            prompt=body.prompt,
            mask_asset_id=body.maskAssetId or body.mask_asset_id,
            source_asset_id=body.sourceAssetId or body.source_asset_id,
            stage=body.stage,
            local_family=body.local_family,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            api_model=body.api_model,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}
