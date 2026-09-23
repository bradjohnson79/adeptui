"""REST router for Co-Director Prop Creator Express.

Mounted at ``/api/prop-creator``. Operates on existing PropEntity records.
Does not create a second prop registry.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Project, get_db
from .service import (
    PropCreatorError,
    adopt_identity_from_asset,
    approve_candidate,
    compose_prop_reference_sheet_for_prop,
    create_or_update_prop,
    delete_prop,
    generate_candidates,
    get_prop,
    list_props,
    retry_candidate,
    upload_identity_from_bytes,
    use_as_prop_identity,
    workspace,
)
from . import advanced_service
from . import advanced_multiview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prop-creator", tags=["prop-creator"])


class UpsertBody(BaseModel):
    prop_id: str = ""
    name: str = ""
    # None = leave existing (Advanced upserts must not race/clear Standard fields)
    visual_style: str | None = None
    description: str | None = None
    reference_asset_id: str | None = None
    clear_reference: bool = False
    generator: dict[str, Any] | None = None
    use_as_identity: bool = False
    identity_asset_id: str = ""
    # Advanced (optional; Standard path ignores)
    mode: str | None = None
    advanced_type: str | None = None
    primary_prompt: str | None = None
    hero_optional: bool | None = None
    is_global: bool | None = None
    isGlobal: bool | None = None


class GenerateBody(BaseModel):
    local_enabled: bool = True
    api_enabled: bool = False
    local_family: str = ""
    api_model: str = ""
    candidate_count: int = 4
    generatorSources: dict[str, Any] | None = None


class ApproveBody(BaseModel):
    candidate_id: str


class UseAsIdentityBody(BaseModel):
    asset_id: str = ""
    source_type: str = "library"


def _project(db: Session, project_id: str) -> None:
    row = db.get(Project, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")


def _err(exc: PropCreatorError) -> HTTPException:
    detail: dict[str, Any] = {"code": exc.code or "PROP_ERROR", "message": str(exc)}
    if exc.extra:
        detail.update(exc.extra)
        detail["details"] = exc.extra
    return HTTPException(status_code=exc.status_code, detail=detail)


@router.get("/projects/{project_id}/workspace")
def get_workspace(project_id: str, prop_id: str = "", db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return workspace(db, project_id, prop_id=prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.get("/projects/{project_id}/props")
def get_props(project_id: str, approved_only: bool = False, db: Session = Depends(get_db)):
    _project(db, project_id)
    return {"props": [p.model_dump() for p in list_props(db, project_id, approved_only=approved_only)]}


@router.post("/projects/{project_id}/props")
def post_prop(project_id: str, body: UpsertBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        prop = create_or_update_prop(
            db,
            project_id,
            prop_id=body.prop_id,
            name=body.name,
            visual_style=body.visual_style,
            description=body.description,
            reference_asset_id=body.reference_asset_id,
            clear_reference=body.clear_reference,
            generator=body.generator,
            use_as_identity=body.use_as_identity,
            identity_asset_id=body.identity_asset_id,
            mode=body.mode,
            advanced_type=body.advanced_type,
            primary_prompt=body.primary_prompt,
            hero_optional=body.hero_optional,
            is_global=body.isGlobal if body.isGlobal is not None else body.is_global,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.get("/projects/{project_id}/props/{prop_id}")
def get_one(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": get_prop(db, project_id, prop_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/generate")
def post_generate(project_id: str, prop_id: str, body: GenerateBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        prop = generate_candidates(
            db,
            project_id,
            prop_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
            candidate_count=body.candidate_count,
            generator_sources=body.generatorSources,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/props/{prop_id}/approve")
def post_approve(project_id: str, prop_id: str, body: ApproveBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": approve_candidate(db, project_id, prop_id, body.candidate_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc





@router.post("/projects/{project_id}/props/{prop_id}/reference-sheet/compose")
def post_compose_prop_reference_sheet(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    """Basic PRS: compose_and_ingest_prs. Does not overwrite approved still. Tag remains %PascalCase."""
    _project(db, project_id)
    try:
        prop, sheet_id = compose_prop_reference_sheet_for_prop(db, project_id, prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc
    tag = str(getattr(prop, "canonical_tag", "") or "")
    if tag and not tag.startswith("%"):
        tag = f"%{tag}"
    return {"prop": prop.model_dump(), "sheet_asset_id": sheet_id, "canonical_tag": tag}


@router.post("/projects/{project_id}/props/{prop_id}/use-as-identity")
def post_use_as_identity(project_id: str, prop_id: str, body: UseAsIdentityBody, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {
            "prop": use_as_prop_identity(
                db,
                project_id,
                prop_id,
                asset_id=body.asset_id,
                source_type=body.source_type,
            ).model_dump()
        }
    except PropCreatorError as exc:
        raise _err(exc) from exc

@router.post("/projects/{project_id}/props/{prop_id}/candidates/{candidate_id}/retry")
def post_retry(project_id: str, prop_id: str, candidate_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    try:
        return {"prop": retry_candidate(db, project_id, prop_id, candidate_id).model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




class AdvancedPrimaryApproveBody(BaseModel):
    candidate_id: str = ""
    asset_id: str = ""


class AngleApproveBody(BaseModel):
    approved: bool = True


class AdoptViewBody(BaseModel):
    asset_id: str = ""
    assetId: str = ""
    source_type: str = "uploaded"
    sourceType: str = ""


@router.get("/projects/{project_id}/props/{prop_id}/advanced/engine")
def get_advanced_engine(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    """Runtime payload for Prop Advanced angles (Qwen Edit). Offline-honest."""
    _project(db, project_id)
    try:
        get_prop(db, project_id, prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc
    return advanced_multiview.engine_payload()


@router.post("/projects/{project_id}/props/{prop_id}/advanced/primary/generate")
def post_advanced_primary_generate(
    project_id: str, prop_id: str, body: GenerateBody, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.generate_primary(
            db,
            project_id,
            prop_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
            candidate_count=body.candidate_count,
            generator_sources=body.generatorSources,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/primary/approve")
def post_advanced_primary_approve(
    project_id: str, prop_id: str, body: AdvancedPrimaryApproveBody, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.approve_primary(
            db,
            project_id,
            prop_id,
            candidate_id=body.candidate_id,
            asset_id=body.asset_id,
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/angles/{angle}/generate")
def post_advanced_angle_generate(
    project_id: str, prop_id: str, angle: str, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.generate_angle(db, project_id, prop_id, angle, regenerate=False)
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/angles/{angle}/regenerate")
def post_advanced_angle_regenerate(
    project_id: str, prop_id: str, angle: str, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.generate_angle(db, project_id, prop_id, angle, regenerate=True)
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/primary/upload")
async def post_advanced_primary_upload(
    project_id: str,
    prop_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        payload = await file.read()
        prop = advanced_service.upload_primary_from_bytes(
            db,
            project_id,
            prop_id,
            data=payload,
            filename=file.filename or "",
            content_type=file.content_type or "",
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/angles/{angle}/upload")
async def post_advanced_angle_upload(
    project_id: str,
    prop_id: str,
    angle: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        payload = await file.read()
        prop = advanced_service.upload_angle_from_bytes(
            db,
            project_id,
            prop_id,
            angle,
            data=payload,
            filename=file.filename or "",
            content_type=file.content_type or "",
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/angles/{angle}/adopt")
def post_advanced_angle_adopt(
    project_id: str,
    prop_id: str,
    angle: str,
    body: AdoptViewBody,
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        aid = (body.asset_id or body.assetId or "").strip()
        source = (body.sourceType or body.source_type or "uploaded").strip()
        prop = advanced_service.adopt_angle_from_asset(
            db, project_id, prop_id, angle, aid, source_type=source
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/views/upload")
async def post_identity_upload(
    project_id: str,
    prop_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        payload = await file.read()
        prop = upload_identity_from_bytes(
            db,
            project_id,
            prop_id,
            data=payload,
            filename=file.filename or "",
            content_type=file.content_type or "",
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/views/adopt")
def post_identity_adopt(
    project_id: str,
    prop_id: str,
    body: AdoptViewBody,
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        aid = (body.asset_id or body.assetId or "").strip()
        source = (body.sourceType or body.source_type or "uploaded").strip()
        prop = adopt_identity_from_asset(db, project_id, prop_id, aid, source_type=source)
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/angles/{angle}/approve")
def post_advanced_angle_approve(
    project_id: str,
    prop_id: str,
    angle: str,
    body: AngleApproveBody,
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        prop = advanced_service.approve_angle(
            db, project_id, prop_id, angle, approved=body.approved
        )
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc



@router.post("/projects/{project_id}/props/{prop_id}/advanced/reference-sheet/generate")
def post_advanced_reference_sheet_generate(
    project_id: str, prop_id: str, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.generate_advanced_reference_sheet(db, project_id, prop_id)
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc


@router.post("/projects/{project_id}/props/{prop_id}/advanced/reference-sheet/cancel")
def post_advanced_reference_sheet_cancel(
    project_id: str, prop_id: str, db: Session = Depends(get_db)
):
    _project(db, project_id)
    try:
        prop = advanced_service.cancel_advanced_reference_sheet(db, project_id, prop_id)
        return {"prop": prop.model_dump()}
    except PropCreatorError as exc:
        raise _err(exc) from exc

@router.get("/projects/{project_id}/props/{prop_id}/delete-preview")
def delete_prop_preview(project_id: str, prop_id: str, db: Session = Depends(get_db)):
    _project(db, project_id)
    from ..creator_scope.contract import ENTITY_PROP
    from ..creator_scope.service import delete_preview_payload
    from .service import PropCreatorError, get_prop
    try:
        prop = get_prop(db, project_id, prop_id)
    except PropCreatorError as exc:
        raise _err(exc) from exc
    if prop.project_id != project_id:
        raise HTTPException(403, detail={"code":"OWNER_REQUIRED","message":"Global props can only be deleted from the project that created them."})
    payload = delete_preview_payload(
        db,
        entity_type=ENTITY_PROP,
        entity_id=prop.id,
        name=prop.display_label or prop.tag or "Prop",
        is_global=getattr(prop, "is_global", False) or getattr(prop, "isGlobal", False),
        owning_project_id=prop.project_id,
    )
    return payload


@router.delete("/projects/{project_id}/props/{prop_id}")
def delete_one(
    project_id: str,
    prop_id: str,
    confirm_cross_project: bool = False,
    db: Session = Depends(get_db),
):
    _project(db, project_id)
    try:
        return delete_prop(
            db, project_id, prop_id, confirm_cross_project=confirm_cross_project
        )
    except PropCreatorError as exc:
        raise _err(exc) from exc
