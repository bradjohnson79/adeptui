"""Resolve which specialist IDs are available for Wiki department routing."""

from __future__ import annotations

from functools import lru_cache

# Planned new specialists — treated as available once prompt files exist.
_PLANNED_WIKI_ROLES = (
    "costume-designer",
    "props-master",
    "storyboard-artist",
    "worldbuilding-specialist",
    "research-specialist",
    "marketing-pitch",
    "project-bible-steward",
)


@lru_cache(maxsize=1)
def available_specialist_ids() -> frozenset[str]:
    ids: set[str] = set()
    try:
        from ..intelligence.specialist_registry import SpecialistRegistry

        for d in SpecialistRegistry().all_enabled():
            ids.add(d.id)
    except Exception:
        pass
    # Include planned roles so routing assigns them once prompts are registered;
    # if still missing from registry, orchestrator uses heuristic findings under that ID.
    ids.update(_PLANNED_WIKI_ROLES)
    return frozenset(ids)


def clear_roster_cache() -> None:
    available_specialist_ids.cache_clear()
