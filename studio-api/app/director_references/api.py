"""REST API for Director 2.0 timeline reference bindings (flag-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .errors import DirectorReferenceError
from .package import ReferencePackageBuilder
from .schemas import (
    AddBindingRequest,
    ApplyPresetRequest,
    ClearReferencesRequest,
    CreatePresetRequest,
    PatchBindingRequest,
    RestoreVersionRequest,
    ValidatePackageRequest,
)
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


@router.get(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references"
)
def get_references(
    project_id: str,
    scene_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).get_references(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references"
)
def add_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: AddBindingRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).add_binding(
            project_id,
            scene_id,
            item_id,
            reference_asset_id=body.referenceAssetId,
            role=body.role,
            influence=body.influence,
            source=body.source,
            bible_entity_stable_id=body.bibleEntityStableId,
            bible_version_id=body.bibleVersionId,
            source_timeline_item_id=body.sourceTimelineItemId,
            label=body.label,
            notes=body.notes,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.patch(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references/{binding_id}"
)
def patch_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    binding_id: str,
    body: PatchBindingRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).patch_binding(
            project_id,
            scene_id,
            item_id,
            binding_id,
            role=body.role,
            influence=body.influence,
            label=body.label,
            notes=body.notes,
            sort_order=body.sortOrder,
            expected_version=body.expectedVersion,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.delete(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references/{binding_id}"
)
def delete_reference(
    project_id: str,
    scene_id: str,
    item_id: str,
    binding_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).delete_binding(project_id, scene_id, item_id, binding_id)
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references/clear"
)
def clear_references(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: ClearReferencesRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = body or ClearReferencesRequest()
    try:
        return _svc(db).clear(
            project_id,
            scene_id,
            item_id,
            expected_version=body.expectedVersion,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references/restore/{version}"
)
def restore_references(
    project_id: str,
    scene_id: str,
    item_id: str,
    version: int,
    body: RestoreVersionRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = body or RestoreVersionRequest()
    try:
        return _svc(db).restore_version(
            project_id,
            scene_id,
            item_id,
            version,
            expected_version=body.expectedVersion,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.get(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/reference-package"
)
def get_reference_package(
    project_id: str,
    scene_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return ReferencePackageBuilder(db).build(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/reference-package/validate"
)
def validate_reference_package(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: ValidatePackageRequest | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = body or ValidatePackageRequest()
    try:
        return ReferencePackageBuilder(db).validate_package(
            project_id,
            scene_id,
            item_id,
            provider_hints=body.providerHints,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/references/continuity-previous"
)
def continuity_previous(
    project_id: str,
    scene_id: str,
    item_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).continuity_previous(project_id, scene_id, item_id)
    except DirectorReferenceError as exc:
        raise _http(exc) from exc


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


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/director/items/{item_id}/reference-presets/apply"
)
def apply_preset(
    project_id: str,
    scene_id: str,
    item_id: str,
    body: ApplyPresetRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return _svc(db).apply_preset(
            project_id,
            scene_id,
            item_id,
            body.presetId,
            mode=body.mode,
            expected_version=body.expectedVersion,
        )
    except DirectorReferenceError as exc:
        raise _http(exc) from exc
