"""HTTP API for M3.1a Templates & Presets + Project Types."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import Project, get_db
from ..feature_flags import feature_flags
from . import project_types as project_types_service
from . import service
from .adapters import m213, m28, profile_items

router = APIRouter(prefix="/templates-presets", tags=["templates-presets"])


def _require_flag() -> None:
    if not feature_flags.templates_presets_v1:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "FEATURE_DISABLED",
                "message": "Templates & Presets (M3.1a) is disabled. Set STUDIO_FEATURE_TEMPLATES_PRESETS_V1=1.",
            },
        )
    from .db import ensure_m31a_tables

    ensure_m31a_tables()


class CreateItemBody(BaseModel):
    kind: str
    name: str
    slug: Optional[str] = None
    scope: str = "project"
    category: str = ""
    subcategory: str = ""
    description: str = ""
    intent: dict[str, Any] = Field(default_factory=dict)
    providerMappings: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    shotRef: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    librarySystemKey: str = ""


class VersionBody(BaseModel):
    intent: dict[str, Any] = Field(default_factory=dict)
    providerMappings: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    changelog: str = ""
    lifecycle: Optional[str] = None
    approvalState: Optional[str] = None


class ForkBody(BaseModel):
    name: Optional[str] = None
    scope: str = "project"
    projectId: Optional[str] = None


class ImportBody(BaseModel):
    package: dict[str, Any]
    projectId: Optional[str] = None


class ResolveBody(BaseModel):
    projectId: str
    sceneId: Optional[str] = None
    shotRef: Optional[str] = None
    selections: dict[str, str] = Field(default_factory=dict)


class BindBody(BaseModel):
    projectId: str
    slot: str
    itemId: str
    scopeLevel: str = "project"
    sceneId: Optional[str] = None
    shotRef: Optional[str] = None
    mode: str = "override"
    versionPin: Optional[int] = None
    expectedVersion: Optional[int] = None


class CustomProjectTypeBody(BaseModel):
    projectId: str
    slug: str
    displayName: Optional[str] = None


class ProjectTypeChangeBody(BaseModel):
    primaryProjectType: str
    projectTraits: list[str] = Field(default_factory=list)
    overrides: dict[str, Any] = Field(default_factory=dict)
    applyDimensionDefaults: bool = True


@router.get("/catalog")
def get_catalog(
    kind: Optional[str] = None,
    category: Optional[str] = None,
    scope: Optional[str] = None,
    projectId: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _require_flag()
    return {
        "items": service.catalog(
            db, kind=kind, category=category, scope=scope, project_id=projectId
        )
    }


@router.post("/items")
def create_item(body: CreateItemBody, db: Session = Depends(get_db)):
    _require_flag()
    return service.create_item(db, body.model_dump())


@router.get("/items/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    _require_flag()
    item = service.get_item(db, item_id)
    if not item:
        raise HTTPException(404, "Creative item not found")
    return item


@router.post("/items/{item_id}/versions")
def add_version(item_id: str, body: VersionBody, db: Session = Depends(get_db)):
    _require_flag()
    try:
        return service.add_version(db, item_id, body.model_dump())
    except KeyError:
        raise HTTPException(404, "Creative item not found")


@router.post("/items/{item_id}/fork")
def fork_item(item_id: str, body: ForkBody, db: Session = Depends(get_db)):
    _require_flag()
    try:
        return service.fork(db, item_id, body.model_dump())
    except KeyError:
        raise HTTPException(404, "Creative item not found")


@router.post("/items/{item_id}/approve")
def approve_item(item_id: str, db: Session = Depends(get_db)):
    _require_flag()
    try:
        return service.approve_item(db, item_id)
    except KeyError:
        raise HTTPException(404, "Creative item not found")


@router.post("/items/{item_id}/export")
def export_item(item_id: str, db: Session = Depends(get_db)):
    _require_flag()
    try:
        return service.export_item(db, item_id)
    except KeyError:
        raise HTTPException(404, "Creative item not found")


@router.post("/import")
def import_item(body: ImportBody, db: Session = Depends(get_db)):
    _require_flag()
    try:
        return service.import_item(db, body.package, project_id=body.projectId)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/resolve")
def resolve_plan(body: ResolveBody, db: Session = Depends(get_db)):
    _require_flag()
    return service.resolve(db, body.model_dump())


@router.post("/bindings")
def create_binding(body: BindBody, db: Session = Depends(get_db)):
    _require_flag()
    return service.bind(db, body.model_dump())


@router.get("/project-types")
def list_project_types(primaryOnly: bool = False, db: Session = Depends(get_db)):
    _require_flag()
    return {"types": project_types_service.list_project_types(db, primary_only=primaryOnly)}


@router.post("/project-types/custom")
def save_custom_project_type(body: CustomProjectTypeBody, db: Session = Depends(get_db)):
    _require_flag()
    project = db.get(Project, body.projectId)
    if not project:
        raise HTTPException(404, "Project not found")
    return project_types_service.save_custom_type_from_project(
        db, project, slug=body.slug, display_name=body.displayName
    )


@router.get("/adapters/m28/preview")
def adapter_m28_preview(profileId: str, db: Session = Depends(get_db)):
    _require_flag()
    return m28.preview_shot_profile(db, profileId)


@router.get("/adapters/m213/preview")
def adapter_m213_preview(preset: Optional[str] = None, themeId: Optional[str] = None, db: Session = Depends(get_db)):
    _require_flag()
    if themeId:
        return m213.preview_theme(db, themeId)
    if preset:
        return m213.preview_light_preset(preset)
    return {"presets": m213.list_light_preset_previews()}


@router.get("/adapters/profiles/preview")
def adapter_profiles_preview(profileId: str, db: Session = Depends(get_db)):
    _require_flag()
    return profile_items.preview_profile_item(db, profileId)
