"""FastAPI routes for the M2.3 Production Bible domain layer."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ..errors import CoDirectorError, status_code_for_error
from .domain_service import BibleDomainService
from .context_retrieval import ContextRetrievalService
from .seed import seed_demo_bible

router = APIRouter(prefix="/projects/{project_id}/bible", tags=["bible-domain"])


def _http_error(err: CoDirectorError) -> HTTPException:
    return HTTPException(status_code=status_code_for_error(err.code), detail=err.to_dict())


class EntityCreateBody(BaseModel):
    entityKey: str
    displayName: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    slug: Optional[str] = None


class EntityPatchBody(BaseModel):
    displayName: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    contentRevision: Optional[int] = None


class ReferenceLinkBody(BaseModel):
    assetId: str
    targetStableId: str
    purpose: str = "identity"
    primary: bool = False


class CanonCreateBody(BaseModel):
    claim: str
    entityStableId: Optional[str] = None
    sceneId: Optional[str] = None
    supersedesStableId: Optional[str] = None


class RelationshipCreateBody(BaseModel):
    fromStableId: str
    toStableId: str
    kind: str = "other"
    label: str = ""
    description: str = ""
    asymmetric: bool = True


@router.get("/summary")
async def bible_summary(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.get_summary(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/export")
async def bible_export(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.export_json(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.post("/seed-demo")
async def bible_seed_demo(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return seed_demo_bible(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/audit")
async def bible_audit(project_id: str, limit: int = 100, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        events = BibleDomainService.list_audit(db, project_id, limit=limit)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "events": events}


@router.get("/characters")
async def list_characters(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        characters = BibleDomainService.list_by_type(db, project_id, "character")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "characters": characters}


@router.post("/characters")
async def create_character(project_id: str, body: EntityCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="character",
            entity_key=body.entityKey,
            display_name=body.displayName,
            data=body.data,
            slug=body.slug,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/characters/{stable_id}")
async def get_character(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.get_entity(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.patch("/characters/{stable_id}")
async def patch_character(
    project_id: str, stable_id: str, body: EntityPatchBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        return BibleDomainService.update_entity(
            db,
            project_id,
            stable_id,
            display_name=body.displayName,
            data=body.data,
            content_revision=body.contentRevision,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.post("/characters/{stable_id}/approve")
async def approve_character(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.approve_entity(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.post("/characters/{stable_id}/lock")
async def lock_character(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.lock_entity(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/locations")
async def list_locations(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        locations = BibleDomainService.list_by_type(db, project_id, "location")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "locations": locations}


@router.post("/locations")
async def create_location(project_id: str, body: EntityCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="location",
            entity_key=body.entityKey,
            display_name=body.displayName,
            data=body.data,
            slug=body.slug,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/locations/{stable_id}")
async def get_location(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.get_entity(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.patch("/locations/{stable_id}")
async def patch_location(
    project_id: str, stable_id: str, body: EntityPatchBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        return BibleDomainService.update_entity(
            db,
            project_id,
            stable_id,
            display_name=body.displayName,
            data=body.data,
            content_revision=body.contentRevision,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/objects")
async def list_objects(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        objects = BibleDomainService.list_by_type(db, project_id, "production_object")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "objects": objects}


@router.post("/objects")
async def create_object(project_id: str, body: EntityCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="production_object",
            entity_key=body.entityKey,
            display_name=body.displayName,
            data=body.data,
            slug=body.slug,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/wardrobe")
async def list_wardrobe(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        wardrobe = BibleDomainService.list_by_type(db, project_id, "wardrobe")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "wardrobe": wardrobe}


@router.post("/wardrobe")
async def create_wardrobe(project_id: str, body: EntityCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="wardrobe",
            entity_key=body.entityKey,
            display_name=body.displayName,
            data=body.data,
            slug=body.slug,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/relationships")
async def list_relationships(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        relationships = BibleDomainService.list_by_type(db, project_id, "relationship")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "relationships": relationships}


@router.post("/relationships")
async def create_relationship(
    project_id: str, body: RelationshipCreateBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="relationship",
            entity_key=f"rel-{body.fromStableId[:8]}-{body.toStableId[:8]}",
            display_name=body.label or f"{body.kind} relationship",
            data=body.model_dump(),
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/canon")
async def list_canon(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        records = BibleDomainService.list_canon(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "canonRecords": records}


@router.post("/canon")
async def create_canon(project_id: str, body: CanonCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        record = BibleDomainService.create_canon_record(
            db,
            project_id,
            claim=body.claim,
            entity_stable_id=body.entityStableId,
            scene_id=body.sceneId,
            supersedes_stable_id=body.supersedesStableId,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err
    return record


@router.get("/decisions")
async def list_decisions(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        decisions = BibleDomainService.list_by_type(db, project_id, "production_decision")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "decisions": decisions}


@router.post("/decisions")
async def create_decision(project_id: str, body: EntityCreateBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.create_entity(
            db,
            project_id,
            entity_type="production_decision",
            entity_key=body.entityKey,
            display_name=body.displayName,
            data=body.data,
            slug=body.slug,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/continuity")
async def list_continuity(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        states = BibleDomainService.list_by_type(db, project_id, "continuity_state")
        warnings = BibleDomainService.sync_conflicts(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "continuityStates": states, "warnings": warnings}


@router.get("/timeline")
async def list_timeline(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        entries = BibleDomainService.list_by_type(db, project_id, "timeline_entry")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "timelineEntries": entries}


@router.post("/references")
async def link_reference(project_id: str, body: ReferenceLinkBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.link_reference(
            db,
            project_id,
            asset_id=body.assetId,
            target_stable_id=body.targetStableId,
            purpose=body.purpose,
            primary=body.primary,
        )
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.delete("/references/{stable_id}")
async def unlink_reference(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return BibleDomainService.unlink_reference(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/context/scene/{scene_id}")
async def scene_context(project_id: str, scene_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return ContextRetrievalService.scene_context(db, project_id, scene_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/context/character/{stable_id}")
async def character_context(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return ContextRetrievalService.character_context(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/context/location/{stable_id}")
async def location_context(project_id: str, stable_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return ContextRetrievalService.location_context(db, project_id, stable_id)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/generation-package")
async def generation_package(
    project_id: str, sceneId: Optional[str] = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        return ContextRetrievalService.generation_package(db, project_id, scene_id=sceneId)
    except CoDirectorError as err:
        raise _http_error(err) from err


@router.get("/conflicts")
async def list_conflicts(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        BibleDomainService.sync_conflicts(db, project_id)
        conflicts = BibleDomainService.list_by_type(db, project_id, "conflict_record")
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "conflicts": conflicts, "count": len(conflicts)}


@router.post("/conflicts/sync")
async def sync_conflicts(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        conflicts = BibleDomainService.sync_conflicts(db, project_id)
    except CoDirectorError as err:
        raise _http_error(err) from err
    return {"projectId": project_id, "conflicts": conflicts, "count": len(conflicts)}
