"""Spatial Map correction routes — contract + Correct Area compat.

Mounted under /api (see main.py). Correct Area engine: Certified zimage.inpaint
(Brad unlock). Atlas/ERS generation remains GPT Image 2 (unchanged).

Primary contract:
  POST /api/spatial-map/correct
  POST /api/spatial-map/correct/accept
  POST /api/spatial-map/correct/undo
  POST /api/spatial-map/correct/reset

Compat (Mask UI Correct Area):
  /api/spatial-map/projects/{projectId}/maps/{documentId}/correct-area*
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import Project, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spatial-map", tags=["spatial-map-correct"])


class CorrectBody(BaseModel):
    """POST /api/spatial-map/correct request."""

    projectId: str = ""
    project_id: str = ""
    sourceAssetId: str = ""
    backgroundAssetId: str = ""  # alias
    currentSpatialMapAssetId: str = ""
    maskPng: str = ""
    maskAssetId: str = ""
    width: int | None = None
    height: int | None = None
    correctionPrompt: str = ""
    preserveStyle: bool = True
    preservePerspective: bool = True
    preserveLighting: bool = True
    mapId: str = ""
    documentId: str = ""  # alias of mapId


class AcceptBody(BaseModel):
    """POST /api/spatial-map/correct/accept — overlay-safe background swap only."""

    projectId: str = ""
    project_id: str = ""
    resultAssetId: str = ""
    acceptToken: str = ""
    mapId: str = ""
    documentId: str = ""


class UndoResetBody(BaseModel):
    projectId: str = ""
    project_id: str = ""
    mapId: str = ""
    documentId: str = ""


class CorrectAreaBody(BaseModel):
    prompt: str = ""
    maskAssetId: str = ""
    mask_asset_id: str = ""
    sourceAssetId: str = ""
    source_asset_id: str = ""
    width: int | None = None
    height: int | None = None
    preserveStyle: bool = True
    preservePerspective: bool = True
    preserveLighting: bool = True


class AcceptCorrectionBody(BaseModel):
    sessionId: str = ""
    session_id: str = ""
    outputAssetId: str = ""
    output_asset_id: str = ""
    resultAssetId: str = ""
    acceptToken: str = ""


class AttachPreviewBody(BaseModel):
    sessionId: str = Field(..., min_length=1)
    outputAssetId: str = Field(..., min_length=1)


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    logger.exception("Spatial Map correct error")
    return HTTPException(500, str(exc))


def _pid(body_project: str, path_project: str | None = None) -> str:
    return (path_project or body_project or "").strip()


# ----- Primary contract -------------------------------------------------


@router.get("/correct/engine")
def api_correct_engine(
    projectId: str = "",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if projectId:
        _require_project(db, projectId)
    from .correction import engine_status

    return engine_status()


@router.post("/correct")
def api_spatial_map_correct(
    body: CorrectBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Enqueue Certified zimage.inpaint via Image Core; frozen prompt preserved."""
    project_id = _pid(body.projectId or body.project_id)
    if not project_id:
        raise HTTPException(400, "projectId required")
    _require_project(db, project_id)
    from .correction import correct

    try:
        return correct(
            db,
            project_id,
            source_asset_id=body.sourceAssetId or None,
            background_asset_id=body.backgroundAssetId or None,
            mask_png=body.maskPng or None,
            mask_asset_id=body.maskAssetId or None,
            width=body.width,
            height=body.height,
            correction_prompt=body.correctionPrompt,
            preserve_style=body.preserveStyle,
            preserve_perspective=body.preservePerspective,
            preserve_lighting=body.preserveLighting,
            current_spatial_map_asset_id=body.currentSpatialMapAssetId or None,
            map_id=body.mapId or body.documentId or None,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/correct/accept")
def api_spatial_map_correct_accept(
    body: AcceptBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Accept → update_document({ backgroundAssetId }) only. Never createMap."""
    project_id = _pid(body.projectId or body.project_id)
    map_id = (body.mapId or body.documentId or "").strip()
    if not project_id or not map_id:
        raise HTTPException(400, "projectId and mapId required")
    _require_project(db, project_id)
    from .correction import accept_correction

    try:
        return accept_correction(
            db,
            project_id,
            map_id,
            result_asset_id=body.resultAssetId or None,
            accept_token=body.acceptToken or None,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/correct/undo")
def api_spatial_map_correct_undo(
    body: UndoResetBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    project_id = _pid(body.projectId or body.project_id)
    map_id = (body.mapId or body.documentId or "").strip()
    if not project_id or not map_id:
        raise HTTPException(400, "projectId and mapId required")
    _require_project(db, project_id)
    from .correction import undo_correction

    try:
        return undo_correction(db, project_id, map_id)
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/correct/reset")
def api_spatial_map_correct_reset(
    body: UndoResetBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reset background to recorded Original. Overlays untouched (not map Reset wipe)."""
    project_id = _pid(body.projectId or body.project_id)
    map_id = (body.mapId or body.documentId or "").strip()
    if not project_id or not map_id:
        raise HTTPException(400, "projectId and mapId required")
    _require_project(db, project_id)
    from .correction import reset_correction

    try:
        return reset_correction(db, project_id, map_id)
    except Exception as exc:
        raise _service_error(exc) from exc


# ----- Correct Area UI compat -------------------------------------------


@router.get("/projects/{project_id}/maps/{document_id}/correct-area")
def api_correct_area_state(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import get_correction_state
    from .service import get_document

    get_document(db, project_id, document_id)
    return get_correction_state(project_id, document_id, db=db)


@router.get("/projects/{project_id}/correct-area/engine")
def api_correct_area_engine(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import engine_status

    return engine_status()


@router.post("/projects/{project_id}/maps/{document_id}/correct-area")
def api_start_correct_area(
    project_id: str,
    document_id: str,
    body: CorrectAreaBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import start_correction

    try:
        return start_correction(
            db,
            project_id,
            document_id,
            mask_asset_id=body.maskAssetId or body.mask_asset_id,
            prompt=body.prompt,
            source_asset_id=body.sourceAssetId or body.source_asset_id or None,
            width=body.width,
            height=body.height,
            preserve_style=body.preserveStyle,
            preserve_perspective=body.preservePerspective,
            preserve_lighting=body.preserveLighting,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/maps/{document_id}/correct-area/accept")
def api_accept_correct_area(
    project_id: str,
    document_id: str,
    body: AcceptCorrectionBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import accept_correction

    parsed = body or AcceptCorrectionBody()
    try:
        return accept_correction(
            db,
            project_id,
            document_id,
            session_id=parsed.sessionId or parsed.session_id or None,
            output_asset_id=parsed.outputAssetId or parsed.output_asset_id or None,
            result_asset_id=parsed.resultAssetId or None,
            accept_token=parsed.acceptToken or None,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/maps/{document_id}/correct-area/undo")
def api_undo_correct_area(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import undo_correction

    try:
        return undo_correction(db, project_id, document_id)
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/maps/{document_id}/correct-area/reset")
def api_reset_correct_area(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .correction import reset_correction

    try:
        return reset_correction(db, project_id, document_id)
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/maps/{document_id}/correct-area/attach-preview")
def api_attach_correct_area_preview(
    project_id: str,
    document_id: str,
    body: AttachPreviewBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Brad / Primary test hook: attach existing asset after supervised run (no provider)."""
    _require_project(db, project_id)
    from .correction import attach_preview_output
    from .service import get_document

    get_document(db, project_id, document_id)
    try:
        return attach_preview_output(
            project_id,
            document_id,
            session_id=body.sessionId,
            output_asset_id=body.outputAssetId,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
