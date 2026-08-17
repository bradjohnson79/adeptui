"""Canonical specialist roster for the Co-Director foundation.

Phase 7 (CDX-087): the canonical roster lives in ONE place —
app.codirector.intelligence.specialist_registry.SpecialistRegistry
(built from the prompt library). The ids below are the foundation's
*heuristic-internal* vocabulary (snake_case) used by the deterministic
keyword router and runners. They are NOT a second roster: every foundation
specialist that has a functional equivalent in the canonical registry is
linked to it through CANONICAL_ALIASES, and canonical_specialist_id
read-throughs the live registry so the canonical side is the source of truth
for availability. Foundation ids without an equivalent (e.g.
cinematic_psychology) remain pure heuristics with no canonical LLM
department — they are never presented as LLM specialist work.
"""

from __future__ import annotations

from typing import Any

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

# Foundation heuristic id -> canonical SpecialistRegistry id, where a
# functional equivalent exists. This is the ONLY alias vocabulary; the
# canonical side (hyphenated ids from the prompt library) is authoritative.
# cinematic_psychology is intentionally absent: no canonical department
# equivalent exists, so it stays a foundation-only heuristic.
CANONICAL_ALIASES: dict[str, str] = {
    "creative_director": "director",
    "story_architect": "storyteller",
    "character_architect": "character-creator",
    "world_builder": "worldbuilding-specialist",
    "cinematography_director": "cinematographer",
    "lighting_director": "lighting-supervisor",
    "production_designer": "production-designer",
    "editor": "editor",
    "sound_director": "sound-designer",
    "performance_director": "performance-director",
    "continuity_supervisor": "continuity-analyst",
}

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

_registry_cache: Any = None


def _load_registry() -> Any:
    """Load the canonical SpecialistRegistry once per process (read-only)."""
    global _registry_cache
    if _registry_cache is None:
        try:
            from ...intelligence.specialist_registry import SpecialistRegistry

            _registry_cache = SpecialistRegistry()
        except Exception:  # pragma: no cover - registry unavailable fallback
            _registry_cache = None
    return _registry_cache


def is_known_specialist(specialist_id: str) -> bool:
    """Return True when the specialist id is part of the frozen roster."""

    return specialist_id in SPECIALIST_IDS


def canonical_specialist_id(foundation_id: str, registry: Any = None) -> str | None:
    """Resolve a foundation specialist id to its canonical SpecialistRegistry id.

    Read-through semantics (CDX-087): the canonical id is returned only when
    the equivalent actually exists in the live canonical registry. Foundation
    ids without a declared equivalent return None — they are foundation-only
    heuristics, not canonical departments.
    """

    alias = CANONICAL_ALIASES.get(foundation_id)
    if alias is None:
        return None
    reg = registry if registry is not None else _load_registry()
    if reg is None or reg.get(alias) is None:
        return None
    return alias


def unresolved_canonical_aliases(registry: Any = None) -> list[str]:
    """Return foundation ids whose canonical alias is missing from the registry.

    Diagnostic helper: a non-empty result means the prompt library dropped a
    specialist that the foundation still routes to (or the alias is stale).
    """

    reg = registry if registry is not None else _load_registry()
    if reg is None:
        return list(CANONICAL_ALIASES.keys())
    return [sid for sid, alias in CANONICAL_ALIASES.items() if reg.get(alias) is None]


__all__ = [
    "CANONICAL_ALIASES",
    "SPECIALIST_IDS",
    "canonical_specialist_id",
    "is_known_specialist",
    "unresolved_canonical_aliases",
]
