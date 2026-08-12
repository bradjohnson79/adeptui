"""Screenplay element Enter/Tab transition rules."""

from __future__ import annotations

from .models import ScriptElementType

# Enter: create context-aware next element
ENTER_NEXT: dict[ScriptElementType, ScriptElementType] = {
    "scene_heading": "action",
    "action": "action",
    "character": "dialogue",
    "dialogue": "action",
    "parenthetical": "dialogue",
    "transition": "scene_heading",
    "shot": "action",
    "general": "general",
    "act_break": "scene_heading",
    "section": "action",
    "note": "action",
    "lyric": "lyric",
}

# Tab cycle (common screenplay cycle)
TAB_CYCLE: list[ScriptElementType] = [
    "scene_heading",
    "action",
    "character",
    "parenthetical",
    "dialogue",
    "transition",
]


def next_on_enter(current: ScriptElementType) -> ScriptElementType:
    return ENTER_NEXT.get(current, "action")


def cycle_type(current: ScriptElementType, *, reverse: bool = False) -> ScriptElementType:
    if current not in TAB_CYCLE:
        return "action" if not reverse else "transition"
    idx = TAB_CYCLE.index(current)  # type: ignore[arg-type]
    delta = -1 if reverse else 1
    return TAB_CYCLE[(idx + delta) % len(TAB_CYCLE)]


SHORTCUT_MAP: dict[int, ScriptElementType] = {
    1: "scene_heading",
    2: "action",
    3: "character",
    4: "dialogue",
    5: "parenthetical",
    6: "transition",
}
