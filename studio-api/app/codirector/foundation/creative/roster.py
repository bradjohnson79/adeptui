"""Canonical specialist roster for the Co-Director foundation."""

from __future__ import annotations

SPECIALIST_IDS: tuple[str, ...] = (
    "creative_director",
    "story_architect",
    "character_architect",
    "world_builder",
    "cinematic_psychology",
    "cinematography_director",
    "lighting_director",
    "production_designer",
    "editor",
    "sound_director",
    "performance_director",
    "continuity_supervisor",
)

_SPECIALIST_LABELS: dict[str, str] = {
    "creative_director": "Creative Director",
    "story_architect": "Story Architect",
    "character_architect": "Character Architect",
    "world_builder": "World Builder",
    "cinematic_psychology": "Cinematic Psychology",
    "cinematography_director": "Cinematography Director",
    "lighting_director": "Lighting Director",
    "production_designer": "Production Designer",
    "editor": "Editor",
    "sound_director": "Sound Director",
    "performance_director": "Performance Director",
    "continuity_supervisor": "Continuity Supervisor",
}


def is_known_specialist(specialist_id: str) -> bool:
    """Return True when the specialist id is part of the frozen roster."""

    return specialist_id in SPECIALIST_IDS


__all__ = ["SPECIALIST_IDS", "is_known_specialist"]
