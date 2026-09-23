"""ERS review surfaces + derivative edit enqueue + version/approve authority."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .store import (
    check_environment_tag_collision,
    get_canonical_sheet_id,
    list_sheets,
    list_visible_sheets,
    load_sheet,
    load_visible_sheet,
    save_sheet,
    sheet_is_global,
    sync_environment_scope,
)

router = APIRouter(prefix="/environment-reference-sheets", tags=["environment-reference-sheets"])


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _summary(sheet) -> dict[str, Any]:
    from .versioning import version_summary

    canonical = get_canonical_sheet_id(sheet.projectId)
    base = version_summary(sheet, canonical_id=canonical)
    approved_dirs = [
        view.direction
        for view in sheet.directionalViews
        if view.status == "approved" and view.approvedAssetId
    ]
    base.update(
        {
            "sceneId": sheet.sceneId,
            "locationStableId": sheet.registration.locationStableId,
            "continuityStatus": sheet.continuity.status,
            "approvedDirections": approved_dirs,
            "exportKinds": [item.exportKind for item in sheet.exports if item.status == "created"],
        }
    )
    return base


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@router.get("/projects/{project_id}")
def api_list_sheets(project_id: str, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    sheets = list_visible_sheets(db, project_id)
    canonical = get_canonical_sheet_id(project_id)
    return {
        "sheets": [_summary(sheet) for sheet in sheets],
        "canonicalSheetId": canonical,
    }


@router.get("/projects/{project_id}/canonical")
def api_get_canonical(
    project_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    from .versioning import resolve_canonical_sheet, version_summary

    canonical_id = get_canonical_sheet_id(project_id)
    sheet = resolve_canonical_sheet(project_id)
    return {
        "canonicalSheetId": canonical_id if sheet else None,
        "sheet": sheet.model_dump(mode="json") if sheet else None,
        "summary": version_summary(sheet, canonical_id=canonical_id) if sheet else None,
    }



@router.get("/projects/{project_id}/{sheet_id}/delete-preview")
def api_delete_preview(project_id: str, sheet_id: str, response: Response, db: Session = Depends(get_db)):
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    from ..creator_scope.contract import ENTITY_ENVIRONMENT
    from ..creator_scope.service import delete_preview_payload
    sheet = load_visible_sheet(db, project_id, sheet_id)
    if sheet is None:
        raise HTTPException(404, "Environment Reference Sheet not found")
    if sheet.projectId != project_id:
        raise HTTPException(403, "Global environments can only be deleted from the project that created them.")
    payload = delete_preview_payload(
        db,
        entity_type=ENTITY_ENVIRONMENT,
        entity_id=sheet_id,
        name=sheet.name,
        is_global=sheet_is_global(sheet),
        owning_project_id=sheet.projectId,
    )
    return payload


@router.delete("/projects/{project_id}/{sheet_id}")
def api_delete_sheet(
    project_id: str,
    sheet_id: str,
    confirm_cross_project: bool = False,
    db: Session = Depends(get_db),
):
    _require_project(db, project_id)
    from .store import delete_environment_sheet
    try:
        return delete_environment_sheet(db, project_id, sheet_id, confirm_cross_project=confirm_cross_project)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:
        from ..creator_scope.contract import CreatorScopeError
        if isinstance(exc, CreatorScopeError):
            raise HTTPException(status_code=exc.status, detail=exc.as_detail()) from exc
        raise HTTPException(500, str(exc)) from exc


@router.get("/projects/{project_id}/{sheet_id}")
def api_get_sheet(project_id: str, sheet_id: str, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    sheet = load_visible_sheet(db, project_id, sheet_id)
    if sheet is None:
        raise HTTPException(404, "Environment Reference Sheet not found")
    return {
        "sheet": sheet.model_dump(mode="json"),
        "summary": _summary(sheet),
        "canonicalSheetId": get_canonical_sheet_id(project_id),
    }


class ErsIdentityBody(BaseModel):
    name: str | None = None
    isGlobal: bool | None = None
    is_global: bool | None = None


class ErsCreatorSaveBody(BaseModel):
    """Full Environment Creator form persist. Does not generate an ERS image."""

    sheetId: str | None = None
    sheet_id: str | None = None
    name: str = ""
    description: str | None = None
    environmentPrompt: str | None = None
    isGlobal: bool | None = None
    is_global: bool | None = None
    referenceImageAssetId: str | None = None
    storyTheme: Any | None = None
    aspectRatio: str | None = None
    generator: str | None = None
    characters: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    plan: dict[str, Any] | None = None


@router.post("/projects/{project_id}/save")
def api_save_environment_creator(
    project_id: str,
    body: ErsCreatorSaveBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create or update the Environment Creator entity. Never regenerates the ERS composite."""
    _require_project(db, project_id)
    from .creator_save import upsert_environment_creator_sheet

    try:
        sheet, created = upsert_environment_creator_sheet(
            db,
            project_id=project_id,
            payload=body.model_dump(mode="python"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:
        from ..creator_scope.contract import CreatorScopeError

        if isinstance(exc, CreatorScopeError):
            raise HTTPException(status_code=exc.status, detail=exc.as_detail()) from exc
        if isinstance(exc, ValueError):
            status = 409 if "already used" in str(exc).lower() else 400
            raise HTTPException(status, str(exc)) from exc
        raise
    return {
        "sheet": sheet.model_dump(mode="json"),
        "summary": _summary(sheet),
        "created": created,
    }


@router.patch("/projects/{project_id}/{sheet_id}/identity")
def api_patch_sheet_identity(
    project_id: str,
    sheet_id: str,
    body: ErsIdentityBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    sheet = load_visible_sheet(db, project_id, sheet_id)
    if sheet is None:
        raise HTTPException(404, "Environment Reference Sheet not found")
    if sheet.projectId != project_id:
        raise HTTPException(403, "Global environments can only be edited from the project that created them.")
    from ..creator_scope.contract import normalize_is_global
    from .contracts import utc_now

    next_name = (body.name if body.name is not None else sheet.name).strip() or sheet.name
    next_global = sheet_is_global(sheet)
    if body.isGlobal is not None or body.is_global is not None:
        next_global = normalize_is_global(
            body.isGlobal if body.isGlobal is not None else body.is_global,
            default=next_global,
        )
    try:
        check_environment_tag_collision(
            db,
            project_id=project_id,
            name=next_name,
            exclude_id=sheet.sheetId,
            making_global=next_global,
        )
    except Exception as exc:
        from ..creator_scope.contract import CreatorScopeError

        if isinstance(exc, CreatorScopeError):
            raise HTTPException(status_code=exc.status, detail=exc.as_detail()) from exc
        if isinstance(exc, ValueError):
            raise HTTPException(409, str(exc)) from exc
        raise
    sheet.name = next_name
    sheet.isGlobal = next_global
    sheet.updatedAt = utc_now()
    save_sheet(sheet)
    sync_environment_scope(db, sheet)
    return {"sheet": sheet.model_dump(mode="json"), "summary": _summary(sheet)}


class ErsApproveReferenceBody(BaseModel):
    assetId: str = Field(..., min_length=1)


@router.post("/projects/{project_id}/{sheet_id}/approve-reference")
def api_approve_reference_as_environment(
    project_id: str,
    sheet_id: str,
    body: ErsApproveReferenceBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Path A: approve the attached reference image as the official environment
    visual for this identity. Converges on the same contract as a generated
    ERS approval (composite + status=approved + canonical pointer)."""
    _require_project(db, project_id)
    from .direct_approve import approve_reference_as_environment

    try:
        return approve_reference_as_environment(
            db,
            project_id,
            sheet_id,
            asset_id=body.assetId,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        if message.startswith("NOT_AN_IMAGE"):
            raise HTTPException(400, message.removeprefix("NOT_AN_IMAGE: ").strip()) from exc
        raise HTTPException(400, message) from exc


@router.post("/projects/{project_id}/{sheet_id}/clear-approval")
def api_clear_reference_environment_approval(
    project_id: str,
    sheet_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Clear approval + official visual (creator explicit). Library bytes kept."""
    _require_project(db, project_id)
    from .direct_approve import clear_reference_environment_approval

    try:
        return clear_reference_environment_approval(db, project_id, sheet_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/projects/{project_id}/{sheet_id}/semantic-gate/use-anyway")
def api_ers_gate_use_anyway(
    project_id: str,
    sheet_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Creator explicitly approves a sheet despite a non-PASS semantic verdict."""
    _require_project(db, project_id)
    from ..codirector.vision.ers_gate import record_ers_gate_override

    result = record_ers_gate_override(project_id=project_id, sheet_id=sheet_id)
    if not result.get("ok"):
        raise HTTPException(404, "Environment Reference Sheet not found")
    return result


# --- Backend seam: derivative-only edit enqueue (locked ERS_EDIT_API_CONTRACT) ---


class ErsEditEnqueueBody(BaseModel):
    editPrompt: str = Field(..., min_length=1)
    maskAssetId: str | None = None
    maskPng: str | None = None
    sourceAssetId: str | None = None
    width: int | None = None
    height: int | None = None
    # Spatial guidance only — never baked into source ERS pixels (Chief addendum).
    drawingOverlay: dict[str, Any] | None = None
    textLabels: list[dict[str, Any]] | None = None
    numberedMarkers: list[dict[str, Any]] | None = None


@router.post("/projects/{project_id}/{sheet_id}/edit/enqueue")
def api_ers_edit_enqueue(
    project_id: str,
    sheet_id: str,
    body: ErsEditEnqueueBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Enqueue Certified zimage.inpaint. Does not mutate sheet composite."""
    _require_project(db, project_id)
    from .edit import enqueue_ers_edit

    try:
        return enqueue_ers_edit(
            db,
            project_id,
            sheet_id,
            edit_prompt=body.editPrompt,
            mask_asset_id=body.maskAssetId or None,
            mask_png=body.maskPng or None,
            source_asset_id=body.sourceAssetId or None,
            width=body.width,
            height=body.height,
            drawing_overlay=body.drawingOverlay,
            text_labels=body.textLabels,
            numbered_markers=body.numberedMarkers,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/projects/{project_id}/{sheet_id}/edit/jobs/{job_id}")
def api_ers_edit_job(
    project_id: str,
    sheet_id: str,
    job_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Read-only edit job status. Does not mutate sheet composite."""
    _require_project(db, project_id)
    from .edit import get_ers_edit_job

    try:
        return get_ers_edit_job(db, project_id, sheet_id, job_id)
    except Exception as exc:
        raise _http_error(exc) from exc


# --- Version lane (LOCKED CONTRACT) ---


class ErsCreateVersionBody(BaseModel):
    derivativeAssetId: str = Field(..., min_length=1)
    editPrompt: str | None = None


class ErsCompareBody(BaseModel):
    otherSheetId: str = Field(..., min_length=1)


class ErsApproveBody(BaseModel):
    approvedBy: str | None = "creator"


@router.post("/projects/{project_id}/{sheet_id}/versions")
def api_create_ers_version(
    project_id: str,
    sheet_id: str,
    body: ErsCreateVersionBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create NEW draft ERS vN from derivative. Never overwrites parent composite."""
    _require_project(db, project_id)
    from .versioning import create_ers_version_from_derivative

    try:
        return create_ers_version_from_derivative(
            project_id,
            sheet_id,
            derivative_asset_id=body.derivativeAssetId,
            edit_prompt=body.editPrompt,
            actor="creator",
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/projects/{project_id}/{sheet_id}/versions")
def api_list_ers_versions(
    project_id: str,
    sheet_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    response.headers["Cache-Control"] = "no-store"
    from .versioning import list_versions, version_summary

    versions = list_versions(project_id, sheet_id)
    if not versions:
        # Anchor missing
        if load_sheet(project_id, sheet_id) is None:
            raise HTTPException(404, "Environment Reference Sheet not found")
    canonical = get_canonical_sheet_id(project_id)
    return {
        "sheetId": sheet_id,
        "canonicalSheetId": canonical,
        "versions": [version_summary(v, canonical_id=canonical) for v in versions],
    }


@router.post("/projects/{project_id}/{sheet_id}/versions/{version_sheet_id}/approve")
def api_approve_ers_version(
    project_id: str,
    sheet_id: str,
    version_sheet_id: str,
    body: ErsApproveBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Sole flip of downstream canonical. sheet_id is lineage context (parent or any)."""
    _require_project(db, project_id)
    from .versioning import approve_ers_version, list_versions

    # Ensure version belongs to lineage of sheet_id when both exist.
    anchor = load_sheet(project_id, sheet_id)
    target = load_sheet(project_id, version_sheet_id)
    if target is None:
        raise HTTPException(404, "Environment Reference Sheet not found")
    if anchor is not None:
        lineage_ids = {v.sheetId for v in list_versions(project_id, sheet_id)}
        if version_sheet_id not in lineage_ids and version_sheet_id != sheet_id:
            # Allow approving the anchor itself (v1 bootstrap) even before lineage fields.
            if version_sheet_id != sheet_id:
                raise HTTPException(
                    400,
                    "versionSheetId is not in the lineage of sheetId",
                )

    from .versioning import approve_ers_version as _approve

    try:
        return _approve(
            project_id,
            version_sheet_id,
            approved_by=str((body.approvedBy if body else None) or "creator"),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/projects/{project_id}/{sheet_id}/versions/compare")
def api_compare_ers_versions(
    project_id: str,
    sheet_id: str,
    body: ErsCompareBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .versioning import compare_versions

    try:
        return compare_versions(project_id, sheet_id, body.otherSheetId)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/projects/{project_id}/{sheet_id}/versions/{version_sheet_id}/revert-select")
def api_revert_select_ers_version(
    project_id: str,
    sheet_id: str,
    version_sheet_id: str,
    body: ErsApproveBody | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Creator revert-select: re-point canonical to a prior version (Approve path)."""
    _require_project(db, project_id)
    from .versioning import revert_select_version

    try:
        return revert_select_version(
            project_id,
            version_sheet_id,
            approved_by=str((body.approvedBy if body else None) or "creator"),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


