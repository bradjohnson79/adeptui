"""SpatialDraft persistence and Accept-into-slot.

Amendment #3: this is the only write path from perception into
characters[] / props[] / cameras[]. Imagery never writes placements.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from .contracts import (
    CHARACTER_COLORS,
    MAX_CAMERA_SLOTS,
    MAX_CHARACTER_SLOTS,
    MAX_PROP_SLOTS,
    PROP_COLORS,
    AcceptFailure,
    AcceptRequest,
    AcceptResult,
    FactStatus,
    ProposedSlotFill,
    SpatialDraft,
    UserCorrection,
    _now,
)

logger = logging.getLogger(__name__)

DRAFT_CATEGORY = "spatial_draft"


def save_spatial_draft(db: Session, draft: SpatialDraft) -> SpatialDraft:
    from ...spatial_map.ers_persistence import _upsert_trait

    draft.updatedAt = _now()
    _upsert_trait(
        db,
        project_id=draft.projectId,
        category=DRAFT_CATEGORY,
        key=draft.mapId,
        value=draft.model_dump_json(),
        provenance="co_director_perception",
    )
    return draft


def load_spatial_draft(db: Session, project_id: str, map_id: str) -> SpatialDraft | None:
    from ...spatial_map.ers_persistence import _load_trait_value

    raw = _load_trait_value(db, project_id=project_id, category=DRAFT_CATEGORY, key=map_id)
    if not raw:
        return None
    try:
        return SpatialDraft.model_validate_json(raw)
    except Exception as exc:
        logger.warning("Failed to load SpatialDraft %s: %s", map_id, exc)
        return None


def apply_user_corrections(draft: SpatialDraft, corrections: list[UserCorrection]) -> SpatialDraft:
    """Filmmaker corrections outrank inference. Never reverse them on rebuild."""
    existing = {item.factKey: item for item in draft.userCorrections}
    for correction in corrections:
        existing[correction.factKey] = correction
    draft.userCorrections = list(existing.values())
    rejected = {
        item.factKey.split(":", 1)[-1].lower()
        for item in draft.userCorrections
        if item.action == "reject"
    }
    kept: list[ProposedSlotFill] = []
    for fill in draft.proposedFills:
        keys = {fill.id.lower(), fill.label.lower(), fill.tag.lstrip("@#").lower()}
        if keys & rejected:
            fill.factStatus = "rejected"
            continue
        override = (
            existing.get(f"fill:{fill.id}")
            or existing.get(f"fill:{fill.label.lower()}")
            or existing.get(fill.id)
            or existing.get(fill.label.lower())
        )
        if override and override.action == "rename":
            fill.label = str(override.value.get("label") or fill.label)
            fill.tag = str(override.value.get("tag") or fill.tag)
            fill.factStatus = "corrected"
            fill.authority = "filmmaker"
        if override and override.action == "move":
            if "normalizedX" in override.value:
                fill.normalizedX = float(override.value["normalizedX"])
            if "normalizedY" in override.value:
                fill.normalizedY = float(override.value["normalizedY"])
            fill.factStatus = "corrected"
            fill.authority = "filmmaker"
        kept.append(fill)
    draft.proposedFills = kept
    for rel in draft.relationships:
        key = f"rel:{rel.id}"
        override = existing.get(key)
        if override and override.action == "relationship":
            rel.relation = override.value.get("relation") or rel.relation
            rel.factStatus = "corrected"
            rel.authority = "filmmaker"
        if override and override.action == "reject":
            rel.factStatus = "rejected"
    draft.relationships = [rel for rel in draft.relationships if rel.factStatus != "rejected"]
    for zone in draft.zonePhrases:
        override = existing.get(f"zone:{zone.id}")
        if override and override.action == "rename":
            zone.phrase = str(override.value.get("phrase") or zone.phrase)
            zone.factStatus = "corrected"
        if override and override.action == "reject":
            zone.factStatus = "rejected"
    draft.zonePhrases = [zone for zone in draft.zonePhrases if zone.factStatus != "rejected"]
    draft.updatedAt = _now()
    return draft


def _occupied_slots(document: Any, kind: str) -> set[int]:
    if kind == "character":
        return {int(item.slotIndex) for item in document.characters if int(getattr(item, "slotIndex", -1)) >= 0}
    if kind == "prop":
        return {int(item.slotIndex) for item in document.props if int(getattr(item, "slotIndex", -1)) >= 0}
    return {int(getattr(item, "cameraSlot", -1)) for item in document.cameras if int(getattr(item, "cameraSlot", -1)) >= 0}


def _ensure_prop_entity(db: Session, project_id: str, label: str, tag: str) -> str:
    from ...spatial_map.ers_contracts import PropEntity, normalize_prop_tag
    from ...spatial_map.ers_persistence import list_prop_entities, save_prop_entity

    clean = normalize_prop_tag(tag or label)
    for existing in list_prop_entities(db, project_id):
        if existing.tag == clean or existing.display_label.lower() == label.lower():
            return existing.id
    prop = PropEntity(project_id=project_id, tag=clean, display_label=label or clean)
    save_prop_entity(db, project_id, prop)
    return prop.id


def _character_is_approved(db: Session, project_id: str, character_id: str) -> bool:
    from .character_canon import register_character_canon

    if not character_id:
        return False
    result = register_character_canon(db, project_id, character_id)
    return bool(result.get("ok"))


def accept_into_slots(
    db: Session,
    project_id: str,
    map_id: str,
    request: AcceptRequest,
) -> AcceptResult:
    from ...spatial_map.schemas import (
        SpatialCameraCreateBody,
        SpatialCharacterPlacementBody,
        SpatialPropPlacementBody,
    )
    from ...spatial_map.service import create_camera, get_document, place_character, place_prop

    draft = load_spatial_draft(db, project_id, map_id)
    if draft is None:
        return AcceptResult(
            ok=False,
            failures=[
                AcceptFailure(code="DRAFT_NOT_FOUND", message="CD Scene Review has not run for this map.")
            ],
        )
    fills = {item.id: item for item in draft.proposedFills}
    result = AcceptResult(draft=draft)
    try:
        document = get_document(db, project_id, map_id)
    except Exception as exc:
        return AcceptResult(
            ok=False,
            failures=[AcceptFailure(code="SPATIAL_MAP_NOT_FOUND", message=str(exc)[:200])],
            draft=draft,
        )

    for item in request.items:
        fill = fills.get(item.fillId)
        if fill is None:
            result.failures.append(AcceptFailure(fillId=item.fillId, code="FILL_NOT_FOUND", message="That suggestion is gone."))
            continue
        if fill.factStatus == "rejected":
            result.failures.append(AcceptFailure(fillId=fill.id, code="FILL_REJECTED", message="That suggestion was rejected."))
            continue
        occupied = _occupied_slots(document, fill.kind)
        if fill.slotIndex in occupied and not item.overwrite:
            result.failures.append(
                AcceptFailure(
                    fillId=fill.id,
                    code="SLOT_OCCUPIED",
                    message="That slot already has a placement. Accept will not overwrite it.",
                )
            )
            continue
        try:
            if fill.kind == "character":
                if len(document.characters) >= MAX_CHARACTER_SLOTS and fill.slotIndex not in occupied:
                    result.failures.append(
                        AcceptFailure(fillId=fill.id, code="ACCEPT_LIMIT_REACHED", message="Character slots are full.")
                    )
                    continue
                if not _character_is_approved(db, project_id, fill.characterId):
                    result.failures.append(
                        AcceptFailure(
                            fillId=fill.id,
                            code="ACCEPT_DRAFT_CRS",
                            message="Approve this character's look before placing them on the map.",
                        )
                    )
                    continue
                color = fill.colorKey or CHARACTER_COLORS[fill.slotIndex % 4]
                document = place_character(
                    db,
                    project_id,
                    map_id,
                    SpatialCharacterPlacementBody(
                        characterId=fill.characterId,
                        label=fill.label,
                        tag=fill.tag or f"@{fill.label}",
                        miniPrompt=fill.miniPrompt,
                        slotIndex=fill.slotIndex,
                        colorKey=color,
                        normalizedX=fill.normalizedX,
                        normalizedY=fill.normalizedY,
                    ),
                )
            elif fill.kind == "prop":
                if len(document.props) >= MAX_PROP_SLOTS and fill.slotIndex not in occupied:
                    result.failures.append(
                        AcceptFailure(fillId=fill.id, code="ACCEPT_LIMIT_REACHED", message="Prop slots are full.")
                    )
                    continue
                prop_id = fill.propId or _ensure_prop_entity(db, project_id, fill.label, fill.tag)
                color = fill.colorKey or PROP_COLORS[fill.slotIndex % 4]
                document = place_prop(
                    db,
                    project_id,
                    map_id,
                    SpatialPropPlacementBody(
                        label=fill.label,
                        propId=prop_id,
                        tag=fill.tag or f"#{prop_id}",
                        miniPrompt=fill.miniPrompt,
                        slotIndex=fill.slotIndex,
                        colorKey=color,
                        normalizedX=fill.normalizedX,
                        normalizedY=fill.normalizedY,
                    ),
                )
            else:
                if len(document.cameras) >= MAX_CAMERA_SLOTS and fill.slotIndex not in occupied:
                    result.failures.append(
                        AcceptFailure(fillId=fill.id, code="ACCEPT_LIMIT_REACHED", message="Camera slots are full.")
                    )
                    continue
                document = create_camera(
                    db,
                    project_id,
                    map_id,
                    SpatialCameraCreateBody(
                        label=fill.label or "Camera",
                        cameraSlot=fill.slotIndex,
                        orientation=fill.orientation or "N",
                        shotSize=fill.shotSize or "auto",
                        primarySubject=fill.primarySubject or "auto",
                        normalizedX=fill.normalizedX,
                        normalizedY=fill.normalizedY,
                    ),
                )
            fill.factStatus = "accepted"
            fill.authority = "accepted_draft"
            result.acceptedFillIds.append(fill.id)
            result.documentWritten = True
        except Exception as exc:
            logger.warning("Accept failed for %s: %s", fill.id, exc)
            result.failures.append(AcceptFailure(fillId=fill.id, code="ACCEPT_FAILED", message=str(exc)[:200]))

    save_spatial_draft(db, draft)
    result.draft = draft
    result.ok = bool(result.acceptedFillIds) and not result.failures
    if result.acceptedFillIds and result.failures:
        result.ok = False
    elif result.acceptedFillIds:
        result.ok = True
    return result
