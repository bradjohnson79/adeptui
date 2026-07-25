"""Deterministic conflict detection for Production Bible continuity."""

from __future__ import annotations

from typing import Any

from .domain.schemas import CanonRecordData, ContinuityStateData, ProductionObjectData, WardrobeData
from .schemas import BibleEntity


def detect_continuity_conflicts(entities: list[BibleEntity]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    continuity_states = [e for e in entities if e.entityType == "continuity_state"]
    for state in continuity_states:
        try:
            data = ContinuityStateData.model_validate(state.data)
        except Exception:
            continue
        if data.resolved:
            continue
        if data.expectedValue and data.actualValue and data.expectedValue != data.actualValue:
            conflicts.append(
                {
                    "conflictType": "continuity_handoff_mismatch",
                    "severity": "warning",
                    "description": (
                        f"Continuity mismatch ({data.aspect}): expected '{data.expectedValue}' "
                        f"but found '{data.actualValue}'"
                    ),
                    "entityStableIds": [s for s in [state.stableId, data.entityStableId] if s],
                    "sceneIds": [s for s in [data.sceneId, data.fromSceneId, data.toSceneId] if s],
                    "sourceStableId": state.stableId,
                }
            )
    objects = [e for e in entities if e.entityType in ("prop", "production_object")]
    for obj in objects:
        try:
            data = ProductionObjectData.model_validate(obj.data)
        except Exception:
            continue
        prior_states = [
            cs
            for cs in continuity_states
            if cs.data.get("entityStableId") == obj.stableId and cs.data.get("aspect") == "prop"
        ]
        for cs in prior_states:
            cs_data = ContinuityStateData.model_validate(cs.data)
            if cs_data.expectedValue == "destroyed" and data.state == "intact" and not cs_data.resolved:
                conflicts.append(
                    {
                        "conflictType": "prop_state_inconsistent",
                        "severity": "warning",
                        "description": f"Object '{obj.displayName}' is intact but continuity expected destroyed.",
                        "entityStableIds": [obj.stableId] if obj.stableId else [],
                        "sceneIds": [s for s in [cs_data.sceneId] if s],
                        "sourceStableId": obj.stableId,
                    }
                )
    return conflicts


def detect_canon_conflicts(entities: list[BibleEntity]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    canon_records = [e for e in entities if e.entityType == "canon_record"]
    approved = []
    for rec in canon_records:
        try:
            data = CanonRecordData.model_validate(rec.data)
        except Exception:
            continue
        if data.status == "approved" and rec.lifecycleStatus in ("approved", "locked"):
            approved.append((rec, data))
    for i, (a_rec, a_data) in enumerate(approved):
        for b_rec, b_data in approved[i + 1 :]:
            if a_data.supersedesStableId == b_rec.stableId or b_data.supersedesStableId == a_rec.stableId:
                continue
            if (
                a_data.entityStableId
                and a_data.entityStableId == b_data.entityStableId
                and a_data.claim.strip().lower() != b_data.claim.strip().lower()
                and a_data.claim
                and b_data.claim
            ):
                conflicts.append(
                    {
                        "conflictType": "canon_incompatible",
                        "severity": "error",
                        "description": (
                            f"Incompatible approved canon claims for entity {a_data.entityStableId}: "
                            f"'{a_data.claim}' vs '{b_data.claim}'"
                        ),
                        "entityStableIds": [a_data.entityStableId],
                        "sceneIds": [s for s in [a_data.sceneId, b_data.sceneId] if s],
                        "sourceStableId": a_rec.stableId,
                    }
                )
    return conflicts


def detect_wardrobe_conflicts(entities: list[BibleEntity]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    wardrobes = [e for e in entities if e.entityType == "wardrobe"]
    by_char_scene: dict[tuple[str, str], list[BibleEntity]] = {}
    for w in wardrobes:
        try:
            data = WardrobeData.model_validate(w.data)
        except Exception:
            continue
        for scene_id in data.sceneIds or [""]:
            key = (data.characterStableId, scene_id)
            by_char_scene.setdefault(key, []).append(w)
    for (char_id, scene_id), group in by_char_scene.items():
        if len(group) > 1:
            conflicts.append(
                {
                    "conflictType": "dual_ownership",
                    "severity": "warning",
                    "description": f"Multiple wardrobe records for character {char_id} in scene {scene_id or 'any'}.",
                    "entityStableIds": [w.stableId for w in group if w.stableId],
                    "sceneIds": [scene_id] if scene_id else [],
                    "sourceStableId": group[0].stableId,
                }
            )
    return conflicts


def detect_all_conflicts(entities: list[BibleEntity]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for detector in (detect_continuity_conflicts, detect_canon_conflicts, detect_wardrobe_conflicts):
        for c in detector(entities):
            key = f"{c['conflictType']}:{c['description']}"
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out
