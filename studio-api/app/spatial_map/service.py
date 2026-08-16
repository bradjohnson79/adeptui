from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..db import Project, Scene
from .capture_intelligence import build_scene_capture_plan
from .collage import create_collage as create_spatial_collage
from .collage import upsert_view as upsert_collage_view
from .errors import SpatialMapErrorCode, raise_http_error
from .grid import (
    apply_cell_placement,
    clamp_grid_scale,
    derive_cell_from_normalized,
    migrate_document,
    normalized_to_world,
    refresh_derived_cells,
)
from .limits import CAMERA_LIMIT, enforce_camera_limit, enforce_character_limit, enforce_prop_limit
from .models import SpatialMapDocumentRow, ensure_tables as ensure_model_tables
from .reference_bundle import compile_reference_bundle, creative_position_labels
from .scene_intent import build_scene_intent, merge_scene_description_edit
from .attachment import (
    PropAttachmentError,
    apply_attach,
    apply_detach,
    apply_relationship_update,
    clear_independent_grid_position,
    has_independent_grid_position,
    props_attached_to_character,
    validate_prop_attachment,
)
from .schemas import (
    SpatialAssignSceneBody,
    SpatialCamera,
    SpatialCameraCreateBody,
    SpatialCameraUpdateBody,
    SpatialCapturePlanBody,
    SpatialCharacterPlacement,
    SpatialCharacterPlacementBody,
    SpatialCharacterPlacementUpdateBody,
    SpatialCollageCreateBody,
    SpatialConsistencyCheck,
    SpatialMapCreateBody,
    SpatialMapDocument,
    SpatialMapUpdateBody,
    SpatialMovementPath,
    SpatialMovementPathCreateBody,
    SpatialPropAttachBody,
    SpatialPropPlacement,
    SpatialPropPlacementBody,
    SpatialPropPlacementUpdateBody,
    SpatialPropRelationshipUpdateBody,
    SpatialReferenceBundle,
    SpatialVariantCreateBody,
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_tables() -> None:
    ensure_model_tables()


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise raise_http_error(SpatialMapErrorCode.PROJECT_NOT_FOUND, projectId=project_id)
    return project


def _scene_or_404(db: Session, project_id: str, scene_id: str) -> Scene:
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise raise_http_error(SpatialMapErrorCode.SCENE_NOT_FOUND, projectId=project_id, sceneId=scene_id)
    return scene


def _row_or_404(db: Session, project_id: str, document_id: str) -> SpatialMapDocumentRow:
    row = db.get(SpatialMapDocumentRow, document_id)
    if not row or row.project_id != project_id:
        raise raise_http_error(
            SpatialMapErrorCode.SPATIAL_MAP_NOT_FOUND,
            projectId=project_id,
            documentId=document_id,
        )
    return row


def _parse_document(row: SpatialMapDocumentRow) -> SpatialMapDocument:
    try:
        data = json.loads(row.document_json or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("id", row.id)
    data["projectId"] = row.project_id
    data["sceneId"] = row.scene_id
    data["locationId"] = row.location_id
    data["title"] = data.get("title") or row.title
    try:
        doc = SpatialMapDocument.model_validate(data)
    except Exception:
        doc = SpatialMapDocument(
            id=row.id,
            projectId=row.project_id,
            sceneId=row.scene_id,
            locationId=row.location_id,
            title=row.title,
        )
    doc.warnings = consistency_warnings(doc)
    migrate_document(doc)
    return doc


def _load_document(db: Session, row: SpatialMapDocumentRow) -> SpatialMapDocument:
    # GET/list may migrate in memory for the response; persist only on explicit write.
    return _parse_document(row)


def _next_version(current: str | None) -> str:
    try:
        version = int(current or "0")
    except (TypeError, ValueError):
        version = 0
    return str(max(1, version + 1))


def _find_item(items: list[Any], item_id: str, *, kind: str) -> Any:
    for item in items:
        if getattr(item, "id", None) == item_id:
            return item
    raise raise_http_error(SpatialMapErrorCode.PLACEMENT_NOT_FOUND, placementId=item_id, placementType=kind)


def _raise_attachment_invalid(exc: Exception | str) -> None:
    raise raise_http_error(SpatialMapErrorCode.ATTACHMENT_INVALID, str(exc))


def _body_has_independent_grid(body: Any) -> bool:
    nx = getattr(body, "normalizedX", None)
    ny = getattr(body, "normalizedY", None)
    if nx is not None and ny is not None:
        return True
    try:
        row = int(getattr(body, "gridRow", -1))
        col = int(getattr(body, "gridColumn", -1))
    except (TypeError, ValueError):
        return False
    return row >= 0 and col >= 0


def _updates_write_independent_grid(updates: dict[str, Any]) -> bool:
    keys = {"normalizedX", "normalizedY", "gridRow", "gridColumn"}
    if not keys.intersection(updates):
        return False
    has_norm = updates.get("normalizedX") is not None and updates.get("normalizedY") is not None
    row = updates.get("gridRow")
    col = updates.get("gridColumn")
    has_cell = False
    if row is not None and col is not None:
        try:
            has_cell = int(row) >= 0 and int(col) >= 0
        except (TypeError, ValueError):
            has_cell = False
    return bool(has_norm or has_cell)


def _validate_document_attachments(document: SpatialMapDocument) -> None:
    for prop in document.props:
        try:
            validate_prop_attachment(prop)
        except PropAttachmentError as exc:
            _raise_attachment_invalid(exc)
        if getattr(prop, "placementMode", None) == "attached" and has_independent_grid_position(prop):
            _raise_attachment_invalid("attached prop cannot have an independent grid position")


def _save_document(db: Session, row: SpatialMapDocumentRow, document: SpatialMapDocument) -> SpatialMapDocument:
    _validate_document_attachments(document)
    document.updatedAt = _now()
    if not document.createdAt:
        document.createdAt = document.updatedAt
    document.version = _next_version(document.version)
    document.projectId = row.project_id
    document.sceneId = row.scene_id
    document.locationId = row.location_id
    document.warnings = consistency_warnings(document)
    row.title = document.title
    row.document_json = document.model_dump_json()
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _parse_document(row)


def _apply_placement_from_values(
    entity: Any,
    document: SpatialMapDocument,
    *,
    grid_row: int | None,
    grid_column: int | None,
    normalized_x: float | None,
    normalized_y: float | None,
    clear_if_negative_cells: bool = False,
) -> None:
    """Shared Cartesian placement for characters, props, and cameras.

    Normalized coords are the physical authority. Create bodies default
    gridRow/gridColumn to -1, which must not wipe a provided normalized pair.
    Explicit update of both cells to -1 still clears placement (Reset).
    """
    from .grid import density_for_scale

    cell_density = density_for_scale(document.gridScale)
    has_norm = normalized_x is not None and normalized_y is not None
    has_cell = (
        grid_row is not None
        and grid_column is not None
        and int(grid_row) >= 0
        and int(grid_column) >= 0
    )
    wants_clear = (
        grid_row is not None
        and grid_column is not None
        and int(grid_row) < 0
        and int(grid_column) < 0
    )
    if has_cell:
        apply_cell_placement(entity, int(grid_column), int(grid_row), cell_density, document.bounds)
        return
    if wants_clear and (clear_if_negative_cells or not has_norm):
        entity.gridRow = -1
        entity.gridColumn = -1
        entity.normalizedX = None
        entity.normalizedY = None
        return
    if has_norm:
        entity.normalizedX = normalized_x
        entity.normalizedY = normalized_y
        derive_cell_from_normalized(entity, cell_density)
        world_x, world_z = normalized_to_world(normalized_x, normalized_y, document.bounds)
        entity.x = world_x
        entity.z = world_z


def _apply_placement_from_body(entity: Any, body: Any, document: SpatialMapDocument) -> None:
    _apply_placement_from_values(
        entity,
        document,
        grid_row=getattr(body, "gridRow", None),
        grid_column=getattr(body, "gridColumn", None),
        normalized_x=getattr(body, "normalizedX", None),
        normalized_y=getattr(body, "normalizedY", None),
        clear_if_negative_cells=False,
    )


def _sync_coords_after_update(entity: Any, updates: dict[str, Any], document: SpatialMapDocument) -> None:
    coord_keys = {"gridRow", "gridColumn", "normalizedX", "normalizedY"}
    if not coord_keys.intersection(updates):
        return
    norm_in_update = "normalizedX" in updates and "normalizedY" in updates
    cell_in_update = "gridRow" in updates and "gridColumn" in updates
    _apply_placement_from_values(
        entity,
        document,
        grid_row=updates["gridRow"] if "gridRow" in updates else (None if norm_in_update else getattr(entity, "gridRow", None)),
        grid_column=updates["gridColumn"] if "gridColumn" in updates else (None if norm_in_update else getattr(entity, "gridColumn", None)),
        normalized_x=updates["normalizedX"] if "normalizedX" in updates else (None if cell_in_update else getattr(entity, "normalizedX", None)),
        normalized_y=updates["normalizedY"] if "normalizedY" in updates else (None if cell_in_update else getattr(entity, "normalizedY", None)),
        clear_if_negative_cells=cell_in_update,
    )


def list_documents(db: Session, project_id: str) -> list[SpatialMapDocument]:
    _project_or_404(db, project_id)
    rows = (
        db.query(SpatialMapDocumentRow)
        .filter(SpatialMapDocumentRow.project_id == project_id)
        .order_by(SpatialMapDocumentRow.updated_at.desc())
        .all()
    )
    return [_load_document(db, row) for row in rows]


def create_document(db: Session, project_id: str, body: SpatialMapCreateBody) -> SpatialMapDocument:
    _project_or_404(db, project_id)
    if body.sceneId:
        _scene_or_404(db, project_id, body.sceneId)
    now = _now()
    scene_intent = body.sceneIntent
    if scene_intent is None and body.sceneDescription:
        project = db.get(Project, project_id)
        scene_intent = build_scene_intent(
            body.sceneDescription,
            project_name=str(getattr(project, "name", "") or ""),
            source_reference_asset_ids=[body.backgroundAssetId] if body.backgroundAssetId else [],
            originating_prompt=body.originatingUserPrompt or "",
        )
    document = SpatialMapDocument(
        id=str(uuid.uuid4()),
        projectId=project_id,
        sceneId=body.sceneId,
        locationId=body.locationId,
        title=body.title or "Spatial Map",
        notes=body.notes or "",
        tags=[],
        bounds=body.bounds,
        backgroundAssetId=body.backgroundAssetId,
        masterEnvironmentPrompt=(body.masterEnvironmentPrompt or "").strip(),
        sceneIntent=scene_intent,
        originalEnvironmentReferenceAssetId=body.originalEnvironmentReferenceAssetId,
        originatingUserPrompt=(body.originatingUserPrompt or "").strip(),
        providerHonesty=body.providerHonesty,
        assignedSceneIds=[body.sceneId] if body.sceneId else [],
        placementGrid="cartesian-v1",
        gridScale=0,
        createdAt=now,
        updatedAt=now,
    )
    row = SpatialMapDocumentRow(
        id=document.id,
        project_id=project_id,
        scene_id=body.sceneId,
        location_id=body.locationId,
        title=document.title,
        document_json=document.model_dump_json(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _parse_document(row)


def get_document(db: Session, project_id: str, document_id: str) -> SpatialMapDocument:
    _project_or_404(db, project_id)
    return _load_document(db, _row_or_404(db, project_id, document_id))


def update_document(db: Session, project_id: str, document_id: str, body: SpatialMapUpdateBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    explicit = body.model_fields_set
    if body.sceneId:
        _scene_or_404(db, project_id, body.sceneId)
        row.scene_id = body.sceneId
        if body.sceneId not in document.assignedSceneIds:
            document.assignedSceneIds.append(body.sceneId)
    if body.locationId is not None:
        row.location_id = body.locationId
    if body.title is not None:
        document.title = body.title
    if body.notes is not None:
        document.notes = body.notes
    if body.tags is not None:
        document.tags = [tag.strip() for tag in body.tags if tag and tag.strip()]
    if body.bounds is not None:
        document.bounds = body.bounds
    # Distinguish "not provided" (keep existing) from "explicitly null" (clear).
    if "backgroundAssetId" in explicit:
        document.backgroundAssetId = body.backgroundAssetId
    if body.masterEnvironmentPrompt is not None:
        document.masterEnvironmentPrompt = body.masterEnvironmentPrompt.strip()
    if body.sceneIntent is not None:
        document.sceneIntent = body.sceneIntent
    elif body.sceneDescription is not None:
        # Edit Scene Description: merge into the existing snapshot so curated
        # subjects/props/traits and lineage survive a text-only edit.
        project = db.get(Project, project_id)
        prior_ids = (
            list(document.sceneIntent.sourceReferenceAssetIds)
            if document.sceneIntent is not None
            else []
        )
        document.sceneIntent = merge_scene_description_edit(
            document.sceneIntent,
            body.sceneDescription,
            project_name=str(getattr(project, "name", "") or ""),
            fallback_source_reference_asset_ids=prior_ids
            or ([document.originalEnvironmentReferenceAssetId] if document.originalEnvironmentReferenceAssetId else []),
            originating_prompt=document.originatingUserPrompt,
        )
    if "originalEnvironmentReferenceAssetId" in explicit:
        document.originalEnvironmentReferenceAssetId = body.originalEnvironmentReferenceAssetId
    if body.originatingUserPrompt is not None:
        document.originatingUserPrompt = body.originatingUserPrompt.strip()
    if body.providerHonesty is not None:
        document.providerHonesty = body.providerHonesty
    if body.gridScale is not None:
        document.gridScale = clamp_grid_scale(body.gridScale)
        refresh_derived_cells(document)
    return _save_document(db, row, document)


def place_character(
    db: Session,
    project_id: str,
    document_id: str,
    body: SpatialCharacterPlacementBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    enforce_character_limit(len(document.characters))
    document.characters.append(
        SpatialCharacterPlacement(
            characterId=body.characterId,
            label=body.label,
            assetId=body.assetId,
            anchorId=body.anchorId,
            notes=body.notes,
            x=body.x,
            y=body.y,
            z=body.z,
            yawDegrees=body.yawDegrees,
            pitchDegrees=body.pitchDegrees,
            rollDegrees=body.rollDegrees,
            scale=body.scale,
            pose=body.pose,
            expression=body.expression,
            eyeLine=body.eyeLine,
            providerHonesty=document.providerHonesty,
            gridRow=body.gridRow,
            gridColumn=body.gridColumn,
            slotIndex=body.slotIndex,
            colorKey=body.colorKey,
            miniPrompt=body.miniPrompt,
            tag=body.tag,
            normalizedX=body.normalizedX,
            normalizedY=body.normalizedY,
            visible=body.visible,
        )
    )
    _apply_placement_from_body(document.characters[-1], body, document)
    return _save_document(db, row, document)


def place_prop(db: Session, project_id: str, document_id: str, body: SpatialPropPlacementBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    enforce_prop_limit(len(document.props))
    placement = SpatialPropPlacement(
        label=body.label,
        propId=body.propId,
        assetId=body.assetId,
        anchorId=body.anchorId,
        notes=body.notes,
        category=body.category,
        state=body.state,
        x=body.x,
        y=body.y,
        z=body.z,
        yawDegrees=body.yawDegrees,
        pitchDegrees=body.pitchDegrees,
        rollDegrees=body.rollDegrees,
        scale=body.scale,
        providerHonesty=document.providerHonesty,
        gridRow=body.gridRow,
        gridColumn=body.gridColumn,
        slotIndex=body.slotIndex,
        colorKey=body.colorKey,
        miniPrompt=body.miniPrompt,
        tag=body.tag,
        normalizedX=body.normalizedX,
        normalizedY=body.normalizedY,
        visible=body.visible,
        placementMode=body.placementMode,
        attachedCharacterSlot=body.attachedCharacterSlot,
        attachedCharacterId=body.attachedCharacterId,
        relationship=body.relationship,
        attachmentPoint=body.attachmentPoint,
    )
    if placement.placementMode == "attached":
        if _body_has_independent_grid(body):
            _raise_attachment_invalid("attached prop cannot have an independent grid position")
        clear_independent_grid_position(placement)
    else:
        _apply_placement_from_body(placement, body, document)
    document.props.append(placement)
    return _save_document(db, row, document)


def update_character(
    db: Session,
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialCharacterPlacementUpdateBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.characters, placement_id, kind="character")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(placement, key, value)
    # Character move updates only this character. Attached props keep attachment
    # and must not receive independent grid positions from the move.
    _sync_coords_after_update(placement, updates, document)
    return _save_document(db, row, document)


def update_prop(
    db: Session,
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropPlacementUpdateBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.props, placement_id, kind="prop")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(placement, key, value)
    try:
        validate_prop_attachment(placement)
    except PropAttachmentError as exc:
        _raise_attachment_invalid(exc)
    if placement.placementMode == "attached":
        if _updates_write_independent_grid(updates):
            _raise_attachment_invalid("attached prop cannot have an independent grid position")
        clear_independent_grid_position(placement)
    else:
        _sync_coords_after_update(placement, updates, document)
    return _save_document(db, row, document)


def create_camera(db: Session, project_id: str, document_id: str, body: SpatialCameraCreateBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    enforce_camera_limit(len(document.cameras))
    hero = body.hero or not document.cameras
    if hero:
        for camera in document.cameras:
            camera.hero = False
    document.cameras.append(
        SpatialCamera(
            label=body.label,
            x=body.x,
            y=body.y,
            z=body.z,
            yawDegrees=body.yawDegrees,
            pitchDegrees=body.pitchDegrees,
            rollDegrees=body.rollDegrees,
            lensMm=body.lensMm,
            heightMeters=body.heightMeters,
            shotType=body.shotType,
            targetCharacterIds=list(body.targetCharacterIds),
            hero=hero,
            lockedFor360=body.lockedFor360,
            cameraSlot=body.cameraSlot,
            orientation=body.orientation,
            fovPreset=body.fovPreset,
            gridRow=body.gridRow,
            gridColumn=body.gridColumn,
            normalizedX=body.normalizedX,
            normalizedY=body.normalizedY,
            visible=body.visible,
        )
    )
    _apply_placement_from_body(document.cameras[-1], body, document)
    return _save_document(db, row, document)


def update_camera(
    db: Session,
    project_id: str,
    document_id: str,
    camera_id: str,
    body: SpatialCameraUpdateBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    camera = _find_item(document.cameras, camera_id, kind="camera")
    updates = body.model_dump(exclude_unset=True)
    if updates.get("hero"):
        for existing in document.cameras:
            existing.hero = existing.id == camera_id
    # If orientation is updated but yawDegrees is not, sync yawDegrees for downstream ERS.
    if "orientation" in updates and "yawDegrees" not in updates:
        updates["yawDegrees"] = _orientation_to_yaw(updates["orientation"])
    for key, value in updates.items():
        setattr(camera, key, value)
    _sync_coords_after_update(camera, updates, document)
    return _save_document(db, row, document)


def _orientation_to_yaw(orientation: str | None) -> float:
    from .grid import orientation_to_yaw

    return orientation_to_yaw(orientation)


def remove_character(
    db: Session,
    project_id: str,
    document_id: str,
    placement_id: str,
    *,
    detach_attached_props: bool = False,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    character = _find_item(document.characters, placement_id, kind="character")
    attached = props_attached_to_character(document.props, character)
    if attached and not detach_attached_props:
        raise raise_http_error(
            SpatialMapErrorCode.CHARACTER_HAS_ATTACHED_PROPS,
            f"Character has {len(attached)} attached prop(s). Detach Props to Unplaced before removing.",
            attachedPropCount=len(attached),
            attachedProps=[
                {
                    "id": prop.id,
                    "propId": prop.propId,
                    "label": prop.label,
                    "relationship": prop.relationship,
                    "attachmentPoint": prop.attachmentPoint,
                }
                for prop in attached
            ],
        )
    for prop in attached:
        apply_detach(prop)
    document.characters = [item for item in document.characters if item.id != placement_id]
    return _save_document(db, row, document)


def remove_prop(db: Session, project_id: str, document_id: str, placement_id: str) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.props, placement_id, kind="prop")
    # Clear attachment first, then unlink the map placement only.
    # Do not delete PropEntity / Library assets.
    apply_detach(placement)
    document.props = [item for item in document.props if item.id != placement_id]
    return _save_document(db, row, document)


def attach_prop(
    db: Session,
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropAttachBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.props, placement_id, kind="prop")
    try:
        apply_attach(
            placement,
            attached_character_id=body.attachedCharacterId,
            attached_character_slot=body.attachedCharacterSlot,
            relationship=body.relationship,
            attachment_point=body.attachmentPoint,
        )
    except PropAttachmentError as exc:
        _raise_attachment_invalid(exc)
    return _save_document(db, row, document)


def detach_prop(db: Session, project_id: str, document_id: str, placement_id: str) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.props, placement_id, kind="prop")
    apply_detach(placement)
    return _save_document(db, row, document)


def update_prop_relationship(
    db: Session,
    project_id: str,
    document_id: str,
    placement_id: str,
    body: SpatialPropRelationshipUpdateBody,
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    placement = _find_item(document.props, placement_id, kind="prop")
    try:
        apply_relationship_update(
            placement,
            relationship=body.relationship,
            attachment_point=body.attachmentPoint,
            update_attachment_point="attachmentPoint" in body.model_fields_set,
        )
    except PropAttachmentError as exc:
        _raise_attachment_invalid(exc)
    return _save_document(db, row, document)


def remove_camera(db: Session, project_id: str, document_id: str, camera_id: str) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    removed = _find_item(document.cameras, camera_id, kind="camera")
    document.cameras = [item for item in document.cameras if item.id != camera_id]
    if removed.hero and document.cameras:
        document.cameras[0].hero = True
    return _save_document(db, row, document)


def create_path(db: Session, project_id: str, document_id: str, body: SpatialMovementPathCreateBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    valid_ids = {
        "character": {item.id for item in document.characters},
        "prop": {item.id for item in document.props},
        "camera": {item.id for item in document.cameras},
    }
    if body.subjectId not in valid_ids.get(body.subjectType, set()):
        raise raise_http_error(
            SpatialMapErrorCode.PATH_SUBJECT_NOT_FOUND,
            subjectType=body.subjectType,
            subjectId=body.subjectId,
        )
    document.paths.append(
        SpatialMovementPath(
            label=body.label,
            subjectType=body.subjectType,
            subjectId=body.subjectId,
            waypoints=body.waypoints,
            notes=body.notes,
            loop=body.loop,
        )
    )
    return _save_document(db, row, document)


def assign_to_scene(db: Session, project_id: str, document_id: str, body: SpatialAssignSceneBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    _scene_or_404(db, project_id, body.sceneId)
    document = _parse_document(row)
    row.scene_id = body.sceneId
    row.location_id = body.locationId
    document.sceneId = body.sceneId
    document.locationId = body.locationId
    if body.sceneId not in document.assignedSceneIds:
        document.assignedSceneIds.append(body.sceneId)
    return _save_document(db, row, document)


def create_variant(db: Session, project_id: str, document_id: str, body: SpatialVariantCreateBody) -> SpatialMapDocument:
    source_row = _row_or_404(db, project_id, document_id)
    source_document = _parse_document(source_row)
    if body.sceneId:
        _scene_or_404(db, project_id, body.sceneId)
    now = _now()
    variant = source_document.model_copy(deep=True)
    variant.id = str(uuid.uuid4())
    variant.title = body.name or f"{source_document.title} Variant"
    variant.variantOfId = source_document.id
    variant.variantIds = []
    variant.sceneId = body.sceneId if body.sceneId is not None else source_document.sceneId
    variant.locationId = body.locationId if body.locationId is not None else source_document.locationId
    variant.assignedSceneIds = list(dict.fromkeys(source_document.assignedSceneIds + ([variant.sceneId] if variant.sceneId else [])))
    if body.notesSuffix:
        variant.notes = f"{source_document.notes}\n{body.notesSuffix}".strip()
    variant.createdAt = now
    variant.updatedAt = now
    variant.version = "1"
    source_document.variantIds = list(dict.fromkeys(source_document.variantIds + [variant.id]))
    source_document.version = _next_version(source_document.version)
    variant_row = SpatialMapDocumentRow(
        id=variant.id,
        project_id=project_id,
        scene_id=variant.sceneId,
        location_id=variant.locationId,
        title=variant.title,
        document_json=variant.model_dump_json(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(variant_row)
    source_row.document_json = source_document.model_dump_json()
    source_row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(variant_row)
    return _parse_document(variant_row)


def build_reference_bundle(
    db: Session,
    project_id: str,
    document_id: str,
    *,
    target: str = "image",
    camera_id: str | None = None,
) -> SpatialReferenceBundle:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    return compile_reference_bundle(
        db,
        document=document,
        target=target,
        camera_id=camera_id,
        warnings=document.warnings,
    )


def create_collage(db: Session, project_id: str, document_id: str, body: SpatialCollageCreateBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    document.collage = create_spatial_collage(
        master_environment_prompt=body.masterEnvironmentPrompt or document.masterEnvironmentPrompt,
        capture_mode=body.captureMode,
        camera_height_meters=body.cameraHeightMeters,
        lens_mm=body.lensMm,
        hero_direction=body.heroDirection,
    )
    if body.masterEnvironmentPrompt:
        document.masterEnvironmentPrompt = body.masterEnvironmentPrompt
    return _save_document(db, row, document)


def update_collage_view(
    db: Session,
    project_id: str,
    document_id: str,
    *,
    direction: str,
    asset_id: str | None = None,
    prompt: str = "",
    status: str = "planned",
) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    if document.collage is None:
        document.collage = create_spatial_collage(master_environment_prompt=document.masterEnvironmentPrompt)
    document.collage = upsert_collage_view(
        document.collage,
        direction=direction,
        asset_id=asset_id,
        prompt=prompt,
        status=status,
    )
    return _save_document(db, row, document)


def create_capture_plan(
    db: Session,
    project_id: str,
    document_id: str,
    body: SpatialCapturePlanBody,
):
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    return build_scene_capture_plan(document, body)


def consistency_check(db: Session, project_id: str, document_id: str) -> SpatialConsistencyCheck:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    return SpatialConsistencyCheck(warnings=consistency_warnings(document))


def consistency_warnings(document: SpatialMapDocument) -> list[str]:
    warnings: list[str] = []
    if len(document.characters) > 4:
        warnings.append("Spatial Map exceeds the certified 4-character limit.")
    if len(document.props) > 4:
        warnings.append("Spatial Map exceeds the certified 4-prop limit.")
    if len(document.cameras) > CAMERA_LIMIT:
        warnings.append(f"Spatial Map exceeds the certified {CAMERA_LIMIT}-camera limit.")
    if not document.cameras:
        warnings.append("No camera has been placed yet.")
    if not document.backgroundAssetId and not document.masterEnvironmentPrompt:
        warnings.append("Map has no background asset or master environment prompt yet.")
    placement_ids = {item.id for item in [*document.characters, *document.props, *document.cameras]}
    for path in document.paths:
        if path.subjectId not in placement_ids:
            warnings.append(f"Movement path '{path.label}' points to a missing subject.")
    for camera in document.cameras:
        missing_targets = [target for target in camera.targetCharacterIds if target not in {item.characterId for item in document.characters}]
        if missing_targets:
            warnings.append(f"Camera '{camera.label}' targets characters that are not placed on the map.")
    if document.collage and not document.collage.minimumDirectionsMet:
        warnings.append("360 collage is missing one or more required directions.")
    return sorted(set(warnings))


def document_summary(document: SpatialMapDocument) -> dict[str, Any]:
    return {
        "documentId": document.id,
        "title": document.title,
        "characterCount": len(document.characters),
        "propCount": len(document.props),
        "cameraCount": len(document.cameras),
        "positionLabels": {
            placement.id: creative_position_labels(x=placement.x, y=placement.y, z=placement.z)
            for placement in [*document.characters, *document.props]
        },
        "warnings": document.warnings,
    }
