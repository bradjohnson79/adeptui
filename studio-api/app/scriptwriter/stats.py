"""Script statistics — runtime is always estimated."""

from __future__ import annotations

from .htmltext import document_text, html_scene_elements
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
    """Stats derived from the typed HTML (CDX-051): the HTML document is the
    canonical content, so scene counts and dialogue/action ratios come from
    the HTML-derived element projection, never from stale stored elements."""
    text = document_text(doc)
    words = len(text.split())
    els = html_scene_elements(doc.contentHtml or "")
    scenes = sum(1 for e in els if e.type == "scene_heading")
    dialogue_words = sum(len((e.text or "").split()) for e in els if e.type in ("dialogue", "parenthetical", "character"))
    action_words = sum(len((e.text or "").split()) for e in els if e.type in ("action", "scene_heading", "shot"))
    total = max(1, dialogue_words + action_words)
    chars = {(e.text or "").strip().upper() for e in els if e.type == "character" and e.text.strip()}
    pages = max(1.0, round(words / 180.0, 1)) if words else 1.0
    return ScriptStats(
        pagesEstimated=pages,
        scenes=scenes,
        words=words,
        characters=len(chars),
        dialoguePercent=round(100.0 * dialogue_words / total, 1),
        actionPercent=round(100.0 * action_words / total, 1),
        runtimeMinutesEstimated=pages,
        paginationMode="estimated",
    )
