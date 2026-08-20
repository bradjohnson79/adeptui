"""Embedded Co-Director stills perception. Chat is not required."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from .contracts import (
    CHARACTER_COLORS,
    PROP_COLORS,
    PerceptionCapability,
    PerceptionPacket,
    ProposedRelationship,
    ProposedSlotFill,
    ProposedZonePhrase,
    SpatialDraft,
    UnusedDetection,
    UserCorrection,
    _now,
)
from .importance import cap_slot_counts, filter_entities
from .spatial_draft import apply_user_corrections, load_spatial_draft, save_spatial_draft
from .spatial_language import ZONE_PHRASES

logger = logging.getLogger(__name__)

_COUNTER_RE = re.compile(r"\b(counter|bar|barista)\b", re.IGNORECASE)
_ESPRESSO_RE = re.compile(r"\b(espresso|coffee machine|grinder)\b", re.IGNORECASE)
_PERSON_RE = re.compile(r"\b(person|people|customer|barista|character|woman|man|girl|boy)\b", re.IGNORECASE)


def geometry_capability() -> tuple[str, str]:
    try:
        from .paths import geometry_models_present

        present = geometry_models_present()
    except Exception:
        present = False
    if not present:
        return (
            "unavailable",
            "Automatic placement boxes are not installed. You can still review the scene and place people yourself.",
        )
    return ("testing", "Geometry models are installed. Placement boxes are in Testing — Accept still required.")


def scene_review_capability(canon_available: bool) -> tuple[str, str]:
    if canon_available:
        return ("available", "")
    return (
        "available",
        "Co-Director can still suggest people from approved characters. Environment notes need a scene look.",
    )


def get_capability() -> PerceptionCapability:
    geom_status, geom_reason = geometry_capability()
    auto_mask = "testing" if geom_status == "testing" else "unavailable"
    auto_reason = (
        "Auto-select needs scene geometry. Paint the region if it is unavailable."
        if auto_mask == "unavailable"
        else "Auto-select is Testing. The brush still works."
    )
    return PerceptionCapability(
        sceneReview="available",
        sceneReviewReason="CD Scene Review uses the existing environment look. Chat is not required.",
        geometry=geom_status,  # type: ignore[arg-type]
        geometryReason=geom_reason,
        autoMask=auto_mask,  # type: ignore[arg-type]
        autoMaskReason=auto_reason,
        chatRequired=False,
    )


def _flatten_canon_labels(canon: Any) -> list[str]:
    labels: list[str] = []
    if canon is None:
        return labels

    def _walk(value: Any) -> None:
        if isinstance(value, str) and value.strip() and value.lower() not in {"true", "false", "none"}:
            if len(value.strip()) < 80:
                labels.append(value.strip())
        elif isinstance(value, dict):
            for key, inner in value.items():
                if isinstance(inner, dict) and inner.get("present") is False:
                    continue
                key_text = str(key).replace("_", " ").strip()
                if key_text and key_text not in {"present", "location", "shape", "orientation"}:
                    labels.append(key_text)
                _walk(inner)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    for field in ("furniture", "fixedArchitecture", "geometry", "spatialRelationships", "hardInvariants"):
        _walk(getattr(canon, field, None))
    return labels


def _approved_characters(db: Session, project_id: str) -> list[dict[str, str]]:
    from ...character_identity.service import list_profiles
    from .character_canon import register_character_canon

    out: list[dict[str, str]] = []
    try:
        profiles = list_profiles(db, project_id)
    except Exception:
        return out
    for profile in profiles:
        check = register_character_canon(db, project_id, profile.id)
        if check.get("ok"):
            out.append(
                {
                    "characterId": profile.id,
                    "name": profile.name,
                    "tag": f"@{profile.name}",
                }
            )
    return out


def _guess_coords(label: str, role: str) -> tuple[float, float]:
    if role == "employee" or "behind" in label.lower() or "employee" in label.lower():
        return (-0.18, -0.32)
    if role == "customer" or "customer" in label.lower():
        return (0.18, 0.34)
    if _ESPRESSO_RE.search(label):
        return (-0.28, -0.12)
    if _COUNTER_RE.search(label):
        return (0.0, 0.0)
    if role == "camera":
        return (0.08, 0.62)
    return (0.0, 0.12)


def _relationship_drafts(labels: list[str], characters: list[dict[str, str]]) -> list[ProposedRelationship]:
    rels: list[ProposedRelationship] = []
    counter = next((label for label in labels if _COUNTER_RE.search(label)), "service counter")
    espresso = next((label for label in labels if _ESPRESSO_RE.search(label)), "")
    if espresso:
        rels.append(ProposedRelationship(subjectLabel=espresso, relation="ON", objectLabel=counter))
        rels.append(ProposedRelationship(subjectLabel=espresso, relation="BEHIND", objectLabel=counter))
    if characters:
        rels.append(
            ProposedRelationship(subjectLabel=characters[0]["name"], relation="BEHIND", objectLabel=counter)
        )
    if len(characters) > 1:
        rels.append(
            ProposedRelationship(
                subjectLabel=characters[1]["name"],
                relation="IN_FRONT_OF",
                objectLabel=counter,
            )
        )
        rels.append(
            ProposedRelationship(
                subjectLabel=characters[1]["name"],
                relation="FACING",
                objectLabel=characters[0]["name"],
            )
        )
    rels.append(ProposedRelationship(subjectLabel="employee side", relation="BEHIND", objectLabel=counter))
    rels.append(ProposedRelationship(subjectLabel="customer side", relation="IN_FRONT_OF", objectLabel=counter))
    return rels


def _zone_drafts(text_blob: str) -> list[ProposedZonePhrase]:
    found: list[ProposedZonePhrase] = []
    blob = (text_blob or "").lower()
    defaults = ["employee side", "customer side", "behind the counter", "on the counter"]
    for phrase in defaults:
        found.append(ProposedZonePhrase(phrase=phrase))
    for phrase in ZONE_PHRASES:
        if phrase in blob and phrase not in {item.phrase for item in found}:
            found.append(ProposedZonePhrase(phrase=phrase))
    return found[:8]


def _run_geometry(db: Session, project_id: str, map_id: str, source_asset_id: str) -> PerceptionPacket:
    from .worker_client import run_stills_perception

    return run_stills_perception(
        project_id=project_id,
        map_id=map_id,
        source_asset_id=source_asset_id,
        db=db,
    )


def review_scene(db: Session, project_id: str, map_id: str) -> SpatialDraft:
    """Build or refresh SpatialDraft. Does not write Spatial Map slots."""
    from ...spatial_map.service import get_document
    from ..vision.visual_canon import load_visual_canon

    document = get_document(db, project_id, map_id)
    source_asset_id = str(
        getattr(document, "originalEnvironmentReferenceAssetId", None)
        or getattr(document, "backgroundAssetId", None)
        or ""
    )
    canon = load_visual_canon(db, project_id, map_id)
    canon_available = bool(canon and getattr(canon, "availability", "") == "available")
    geom_status, geom_reason = geometry_capability()

    previous = load_spatial_draft(db, project_id, map_id)
    preserved_corrections: list[UserCorrection] = list(previous.userCorrections) if previous else []

    packet = PerceptionPacket(
        projectId=project_id,
        mapId=map_id,
        sourceAssetId=source_asset_id,
        availability=geom_status,  # type: ignore[arg-type]
        reason=geom_reason,
    )
    if geom_status != "unavailable" and source_asset_id:
        try:
            packet = _run_geometry(db, project_id, map_id, source_asset_id)
        except Exception as exc:
            logger.info("stills geometry skipped: %s", exc)
            packet.availability = "unavailable"
            packet.reason = "Automatic placement boxes are unavailable. You can place people and props yourself."

    kept, unused = filter_entities(packet.entities)
    characters = _approved_characters(db, project_id)
    intent = getattr(document, "sceneIntent", None)
    key_subjects = list(getattr(intent, "keySubjects", None) or [])
    key_props = list(getattr(intent, "keyProps", None) or [])
    summary = str(getattr(intent, "summary", "") or "")

    named = []
    for subject in key_subjects:
        match = next((row for row in characters if row["name"].lower() == str(subject).lower()), None)
        if match and match not in named:
            named.append(match)
    for row in characters:
        if row not in named:
            named.append(row)

    def _reuse_fill_id(*, kind: str, character_id: str = "", label: str = "") -> str:
        if not previous:
            return ""
        for fill in previous.proposedFills:
            if fill.kind != kind:
                continue
            if character_id and fill.characterId == character_id:
                return fill.id
            if label and fill.label.lower() == label.lower():
                return fill.id
        return ""

    char_fills: list[ProposedSlotFill] = []
    for index, row in enumerate(named[:4]):
        role = "employee" if index == 0 else "customer"
        nx, ny = _guess_coords(row["name"], role)
        side = "behind the service counter" if role == "employee" else "on the customer side"
        reused = _reuse_fill_id(kind="character", character_id=row["characterId"], label=row["name"])
        char_fills.append(
            ProposedSlotFill(
                **({"id": reused} if reused else {}),
                kind="character",
                slotIndex=index,
                colorKey=CHARACTER_COLORS[index],
                label=row["name"],
                tag=row["tag"],
                characterId=row["characterId"],
                characterApproved=True,
                normalizedX=nx,
                normalizedY=ny,
                miniPrompt=f"{row['tag']} {side}",
            )
        )

    labels = _flatten_canon_labels(canon)
    labels.extend(key_props)
    for entity in kept:
        if entity.kindHint != "character":
            labels.append(entity.label)
    # de-dupe labels
    seen: set[str] = set()
    unique_labels: list[str] = []
    for label in labels:
        key = label.lower()
        if key in seen or _PERSON_RE.search(label):
            continue
        seen.add(key)
        unique_labels.append(label)

    prop_fills: list[ProposedSlotFill] = []
    priority = [label for label in unique_labels if _COUNTER_RE.search(label) or _ESPRESSO_RE.search(label)]
    rest = [label for label in unique_labels if label not in priority]
    for index, label in enumerate((priority + rest)[:8]):
        nx, ny = _guess_coords(label, "prop")
        reused = _reuse_fill_id(kind="prop", label=label)
        prop_fills.append(
            ProposedSlotFill(
                **({"id": reused} if reused else {}),
                kind="prop",
                slotIndex=index,
                colorKey=PROP_COLORS[index % 4],
                label=label,
                tag=f"#{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')}",
                normalizedX=nx,
                normalizedY=ny,
                miniPrompt=f"{label} in the scene",
                perceptionEntityId=next((ent.id for ent in kept if ent.label.lower() == label.lower()), ""),
            )
        )

    camera_reused = _reuse_fill_id(kind="camera", label="Conversation camera")
    camera_fills = [
        ProposedSlotFill(
            **({"id": camera_reused} if camera_reused else {}),
            kind="camera",
            slotIndex=0,
            label="Conversation camera",
            normalizedX=0.08,
            normalizedY=0.62,
            orientation="N",
            shotSize="medium",
            primarySubject=named[0]["characterId"] if named else "auto",
            miniPrompt="Look at the conversation at the counter",
        )
    ]
    char_fills, prop_fills, camera_fills, overflow = cap_slot_counts(char_fills, prop_fills, camera_fills)
    unused.extend(overflow)
    unused.extend(
        UnusedDetection(label=label, kindHint="prop", reason="overflow_or_low_importance")
        for label in (priority + rest)[4:]
        if all(label != item.label for item in prop_fills)
    )

    review_status, review_reason = scene_review_capability(canon_available)
    draft = SpatialDraft(
        projectId=project_id,
        mapId=map_id,
        sourceAssetId=source_asset_id,
        reviewLabel="CD Scene Review",
        sceneReviewAvailable=review_status == "available",
        geometryStatus=packet.availability,
        geometryReason=packet.reason or geom_reason,
        canonAvailability="available" if canon_available else "unavailable",
        canonUnavailableReason=""
        if canon_available
        else (getattr(canon, "unavailableReason", None) or "No environment look yet."),
        proposedFills=char_fills + prop_fills + camera_fills,
        unusedDetections=unused[:24],
        zonePhrases=_zone_drafts(summary + " " + " ".join(labels)),
        relationships=_relationship_drafts(unique_labels, named),
        userCorrections=preserved_corrections,
        perceptionPacketId=packet.packetId,
        createdAt=previous.createdAt if previous else _now(),
    )
    if preserved_corrections:
        draft = apply_user_corrections(draft, [])
    if review_reason and not draft.canonUnavailableReason:
        draft.canonUnavailableReason = review_reason
    return save_spatial_draft(db, draft)
