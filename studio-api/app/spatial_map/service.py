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
from .limits import enforce_camera_limit, enforce_character_limit, enforce_prop_limit
from .models import SpatialMapDocumentRow, ensure_tables as ensure_model_tables
from .reference_bundle import compile_reference_bundle, creative_position_labels
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
    SpatialPropPlacement,
    SpatialPropPlacementBody,
    SpatialPropPlacementUpdateBody,
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
    return doc


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


def _save_document(db: Session, row: SpatialMapDocumentRow, document: SpatialMapDocument) -> SpatialMapDocument:
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


def list_documents(db: Session, project_id: str) -> list[SpatialMapDocument]:
    _project_or_404(db, project_id)
    rows = (
        db.query(SpatialMapDocumentRow)
        .filter(SpatialMapDocumentRow.project_id == project_id)
        .order_by(SpatialMapDocumentRow.updated_at.desc())
        .all()
    )
    return [_parse_document(row) for row in rows]


def create_document(db: Session, project_id: str, body: SpatialMapCreateBody) -> SpatialMapDocument:
    _project_or_404(db, project_id)
    if body.sceneId:
        _scene_or_404(db, project_id, body.sceneId)
    now = _now()
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
        providerHonesty=body.providerHonesty,
        assignedSceneIds=[body.sceneId] if body.sceneId else [],
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
    return _parse_document(_row_or_404(db, project_id, document_id))


def update_document(db: Session, project_id: str, document_id: str, body: SpatialMapUpdateBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
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
    if body.backgroundAssetId is not None:
        document.backgroundAssetId = body.backgroundAssetId
    if body.masterEnvironmentPrompt is not None:
        document.masterEnvironmentPrompt = body.masterEnvironmentPrompt.strip()
    if body.providerHonesty is not None:
        document.providerHonesty = body.providerHonesty
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
        )
    )
    return _save_document(db, row, document)


def place_prop(db: Session, project_id: str, document_id: str, body: SpatialPropPlacementBody) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    enforce_prop_limit(len(document.props))
    document.props.append(
        SpatialPropPlacement(
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
        )
    )
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
        )
    )
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
    for key, value in updates.items():
        setattr(camera, key, value)
    return _save_document(db, row, document)


def remove_character(db: Session, project_id: str, document_id: str, placement_id: str) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    _find_item(document.characters, placement_id, kind="character")
    document.characters = [item for item in document.characters if item.id != placement_id]
    return _save_document(db, row, document)


def remove_prop(db: Session, project_id: str, document_id: str, placement_id: str) -> SpatialMapDocument:
    row = _row_or_404(db, project_id, document_id)
    document = _parse_document(row)
    _find_item(document.props, placement_id, kind="prop")
    document.props = [item for item in document.props if item.id != placement_id]
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
    if len(document.cameras) > 8:
        warnings.append("Spatial Map exceeds the certified 8-camera limit.")
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
