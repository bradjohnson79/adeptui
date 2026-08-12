"""Reference helpers for the image pipeline foundation."""

from __future__ import annotations

from .contracts import CharacterLockLevel, ImageReferenceAssignment

_PALETTE = [
    "#D95F5F",
    "#5F8DD9",
    "#D9B65F",
    "#6ABF8A",
    "#A476D9",
    "#D97F5F",
]


def build_reference_assignments(
    reference_asset_ids: list[str],
    character_ids: list[str] | None = None,
) -> list[ImageReferenceAssignment]:
    assignments: list[ImageReferenceAssignment] = []
    for index, asset_id in enumerate(reference_asset_ids or []):
        character_id = (character_ids or [None] * len(reference_asset_ids))[index] if index < len(character_ids or []) else None
        role = "character" if character_id else "visual_reference"
        assignments.append(
            ImageReferenceAssignment(
                assetId=asset_id,
                displayName=f"Reference {index + 1}",
                semanticRole=role,
                semanticRoles=[role, "continuity"] if character_id else [role],
                sourceType="asset",
                characterId=character_id,
                lockLevel=lock_level_for_reference(role),
                dominantColorHex=_PALETTE[index % len(_PALETTE)],
            )
        )
    return assignments


def build_figure_color_map(character_ids: list[str]) -> dict[str, str]:
    return {character_id: _PALETTE[index % len(_PALETTE)] for index, character_id in enumerate(character_ids or [])}


def lock_level_for_reference(semantic_role: str) -> CharacterLockLevel:
    semantic_role = (semantic_role or "").lower()
    if semantic_role in {"hero", "lead", "character", "identity"}:
        return "Strong"
    if semantic_role in {"wardrobe", "prop", "visual_reference"}:
        return "PreserveCore"
    return "Flexible"


def choose_lock_level(character_count: int, production_ready: bool = False) -> CharacterLockLevel:
    if production_ready:
        return "ProductionLock"
    if character_count >= 3:
        return "Strong"
    if character_count == 2:
        return "PreserveCore"
    return "Flexible"

