"""Deterministic context assembly for Production Bible domain packages."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from . import operations as ops
from .completeness import bible_health_counts, score_character, score_location
from .conflicts import detect_all_conflicts
from .domain.schemas import ReferenceLinkData, VisualLanguageData
from .schemas import BibleEntity


class ContextRetrievalService:
    """Assembles read-only context packages without LLM involvement."""

    @staticmethod
    def _load_entities(db: Session, project_id: str) -> tuple[list[BibleEntity], Any | None]:
        bible = ops.get_bible(db, project_id)
        if not bible:
            return [], None
        version = ops.get_current_version(db, bible)
        if not version:
            return [], None
        entities = [ops.entity_row_to_schema(row) for row in ops.entities_for_version(db, version.id)]
        return entities, version

    @staticmethod
    def project_summary(db: Session, project_id: str) -> dict[str, Any]:
        entities, version = ContextRetrievalService._load_entities(db, project_id)
        health = bible_health_counts(entities)
        conflicts = detect_all_conflicts(entities)
        profile = next((e for e in entities if e.entityType == "project_profile"), None)
        return {
            "projectId": project_id,
            "found": bool(version),
            "bibleVersionNumber": version.version_number if version else None,
            "health": {**health, "conflictCount": len(conflicts)},
            "projectProfile": profile.model_dump(mode="json") if profile else None,
            "conflictCount": len(conflicts),
        }

    @staticmethod
    def character_context(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        entities, version = ContextRetrievalService._load_entities(db, project_id)
        character = next(
            (e for e in entities if e.stableId == stable_id and e.entityType == "character"),
            None,
        )
        if not character:
            return {"found": False, "projectId": project_id, "stableId": stable_id}

        def _related(entity_type: str, predicate) -> list[dict[str, Any]]:
            return [e.model_dump(mode="json") for e in entities if e.entityType == entity_type and predicate(e)]

        return {
            "found": True,
            "projectId": project_id,
            "stableId": stable_id,
            "bibleVersionNumber": version.version_number if version else None,
            "character": character.model_dump(mode="json"),
            "readiness": score_character(character),
            "relationships": _related(
                "relationship",
                lambda e: e.data.get("fromStableId") == stable_id or e.data.get("toStableId") == stable_id,
            ),
            "wardrobe": _related("wardrobe", lambda e: e.data.get("characterStableId") == stable_id),
            "referenceLinks": _related("reference_link", lambda e: e.data.get("targetStableId") == stable_id),
            "canonRecords": _related("canon_record", lambda e: e.data.get("entityStableId") == stable_id),
            "appearanceStates": _related("appearance_state", lambda e: e.data.get("characterStableId") == stable_id),
            "continuityStates": _related("continuity_state", lambda e: e.data.get("entityStableId") == stable_id),
        }

    @staticmethod
    def location_context(db: Session, project_id: str, stable_id: str) -> dict[str, Any]:
        entities, version = ContextRetrievalService._load_entities(db, project_id)
        location = next(
            (e for e in entities if e.stableId == stable_id and e.entityType == "location"),
            None,
        )
        if not location:
            return {"found": False, "projectId": project_id, "stableId": stable_id}

        return {
            "found": True,
            "projectId": project_id,
            "stableId": stable_id,
            "bibleVersionNumber": version.version_number if version else None,
            "location": location.model_dump(mode="json"),
            "readiness": score_location(location),
            "childLocations": [
                e.model_dump(mode="json")
                for e in entities
                if e.entityType == "location" and e.data.get("parentStableId") == stable_id
            ],
            "objects": [
                e.model_dump(mode="json")
                for e in entities
                if e.entityType in ("prop", "production_object") and e.data.get("locationStableId") == stable_id
            ],
            "referenceLinks": [
                e.model_dump(mode="json")
                for e in entities
                if e.entityType == "reference_link" and e.data.get("targetStableId") == stable_id
            ],
        }

    @staticmethod
    def scene_context(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
        entities, version = ContextRetrievalService._load_entities(db, project_id)
        facts: list[dict[str, Any]] = []
        if version:
            for row in ops.facts_for_version(db, version.id):
                if scene_id in (row.data_json or "") or scene_id in (row.statement or ""):
                    facts.append(ops.fact_row_to_schema(row).model_dump(mode="json"))

        def _scene_entities(entity_type: str) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for entity in entities:
                if entity.entityType != entity_type:
                    continue
                data = entity.data
                scene_ids = data.get("sceneIds") or []
                if data.get("sceneId") == scene_id or scene_id in scene_ids:
                    out.append(entity.model_dump(mode="json"))
            return out

        visual = next(
            (
                e
                for e in entities
                if e.entityType in ("visual_language", "visual_style")
                and (e.data.get("sceneId") == scene_id or not e.data.get("sceneOverride"))
            ),
            None,
        )
        return {
            "found": True,
            "projectId": project_id,
            "sceneId": scene_id,
            "bibleVersionNumber": version.version_number if version else None,
            "sceneFacts": facts,
            "characters": _scene_entities("appearance_state"),
            "wardrobe": _scene_entities("wardrobe"),
            "canonRecords": _scene_entities("canon_record"),
            "continuityStates": _scene_entities("continuity_state"),
            "visualLanguage": visual.model_dump(mode="json") if visual else None,
            "timelineEntries": _scene_entities("timeline_entry"),
        }

    @staticmethod
    def generation_package(
        db: Session, project_id: str, *, scene_id: Optional[str] = None
    ) -> dict[str, Any]:
        entities, version = ContextRetrievalService._load_entities(db, project_id)
        primary: list[dict[str, Any]] = []
        supporting: list[dict[str, Any]] = []
        negative: list[dict[str, Any]] = []
        for link in (e for e in entities if e.entityType == "reference_link"):
            try:
                data = ReferenceLinkData.model_validate(link.data)
            except Exception:
                continue
            payload = link.model_dump(mode="json")
            if data.polarity == "negative":
                negative.append(payload)
            elif data.primary:
                primary.append(payload)
            else:
                supporting.append(payload)

        visual = next((e for e in entities if e.entityType in ("visual_language", "visual_style")), None)
        style_constraints: dict[str, Any] = {}
        if visual:
            try:
                style_constraints = VisualLanguageData.model_validate(visual.data).model_dump(mode="json")
            except Exception:
                style_constraints = visual.data

        continuity = [
            e.model_dump(mode="json")
            for e in entities
            if e.entityType == "continuity_state"
            and (not scene_id or e.data.get("sceneId") == scene_id)
            and not e.data.get("resolved")
        ]
        return {
            "projectId": project_id,
            "sceneId": scene_id,
            "bibleVersionNumber": version.version_number if version else None,
            "primaryReferences": primary,
            "supportingReferences": supporting,
            "negativeReferences": negative,
            "styleConstraints": style_constraints,
            "continuityConstraints": continuity,
            "conflicts": detect_all_conflicts(entities),
        }
