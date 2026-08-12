"""Script statistics — runtime is always estimated."""

from __future__ import annotations

from .models import ScriptDocument, ScriptStats


def compute_stats(doc: ScriptDocument) -> ScriptStats:
    words = 0
    dialogue_words = 0
    action_words = 0
    scenes = 0
    for el in doc.elements:
        if el.omitted:
            continue
        w = len((el.text or "").split())
        words += w
        if el.type == "scene_heading":
            scenes += 1
        if el.type in ("dialogue", "parenthetical", "character"):
            dialogue_words += w
        if el.type in ("action", "scene_heading", "shot"):
            action_words += w
    # ~55 lines / page estimate; ~180 words / page rough
    pages = max(1.0, round(words / 180.0, 1)) if words else 1.0
    # industry rule-of-thumb ~1 page/minute — labeled estimate
    runtime = pages
    total = max(1, dialogue_words + action_words)
    return ScriptStats(
        pagesEstimated=pages,
        scenes=scenes,
        words=words,
        characters=len({(e.text or "").strip().upper() for e in doc.elements if e.type == "character" and e.text.strip()}),
        dialoguePercent=round(100.0 * dialogue_words / total, 1),
        actionPercent=round(100.0 * action_words / total, 1),
        runtimeMinutesEstimated=runtime,
        paginationMode="estimated",
    )
