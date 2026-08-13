"""Script statistics — runtime is always estimated."""

from __future__ import annotations

from .htmltext import document_text
from .models import ScriptDocument, ScriptStats


def compute_stats(doc: ScriptDocument) -> ScriptStats:
    if doc.contentType == "html" and doc.contentHtml:
        return _stats_from_html(doc)
    return _stats_from_elements(doc)


def _stats_from_elements(doc: ScriptDocument) -> ScriptStats:
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
    pages = max(1.0, round(words / 180.0, 1)) if words else 1.0
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


def _stats_from_html(doc: ScriptDocument) -> ScriptStats:
    text = document_text(doc)
    words = len(text.split())
    scenes = sum(1 for e in doc.elements if e.type == "scene_heading")
    pages = max(1.0, round(words / 180.0, 1)) if words else 1.0
    return ScriptStats(
        pagesEstimated=pages,
        scenes=scenes,
        words=words,
        characters=0,
        dialoguePercent=0.0,
        actionPercent=0.0,
        runtimeMinutesEstimated=pages,
        paginationMode="estimated",
    )
