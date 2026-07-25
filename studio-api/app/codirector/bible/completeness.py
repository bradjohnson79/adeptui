"""Completeness scoring for Production Bible entities."""

from __future__ import annotations

from typing import Any

from .domain.schemas import CharacterData, LocationData, ProductionObjectData, VisualLanguageData
from .schemas import BibleEntity


def score_character(entity: BibleEntity) -> str:
    try:
        data = CharacterData.model_validate(entity.data)
    except Exception:
        return "incomplete"
    filled = sum(1 for v in (data.description, data.appearanceSummary, data.personality, data.motivation) if (v or "").strip())
    if entity.lifecycleStatus == "locked":
        return "locked"
    if filled >= 4 and data.readiness in ("production_ready", "generation_ready"):
        return data.readiness
    if filled >= 2:
        return "basic"
    return "incomplete"


def score_location(entity: BibleEntity) -> str:
    try:
        data = LocationData.model_validate(entity.data)
    except Exception:
        return "incomplete"
    filled = sum(1 for v in (data.description, data.atmosphere, data.geography) if (v or "").strip())
    if entity.lifecycleStatus == "locked":
        return "locked"
    if filled >= 3 and data.readiness in ("production_ready", "generation_ready"):
        return data.readiness
    if filled >= 1:
        return "basic"
    return "incomplete"


def score_entity(entity: BibleEntity) -> str:
    if entity.entityType == "character":
        return score_character(entity)
    if entity.entityType == "location":
        return score_location(entity)
    if entity.entityType in ("prop", "production_object"):
        try:
            data = ProductionObjectData.model_validate(entity.data)
            return data.readiness if (data.description or "").strip() else "incomplete"
        except Exception:
            return "incomplete"
    if entity.entityType in ("visual_style", "visual_language"):
        try:
            data = VisualLanguageData.model_validate(entity.data)
            return "basic" if (data.description or "").strip() else "incomplete"
        except Exception:
            return "incomplete"
    if entity.lifecycleStatus == "locked":
        return "locked"
    return "basic" if entity.displayName else "incomplete"


def bible_health_counts(entities: list[BibleEntity]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    readiness: dict[str, int] = {}
    locked = 0
    incomplete = 0
    for e in entities:
        by_type[e.entityType] = by_type.get(e.entityType, 0) + 1
        if e.lifecycleStatus == "locked":
            locked += 1
        score = score_entity(e)
        readiness[score] = readiness.get(score, 0) + 1
        if score == "incomplete":
            incomplete += 1
    return {
        "entityCount": len(entities),
        "byType": by_type,
        "readiness": readiness,
        "lockedCount": locked,
        "incompleteCount": incomplete,
    }
