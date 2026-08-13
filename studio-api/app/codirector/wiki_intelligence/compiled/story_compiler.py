"""Synthesize Story page — never Theme×N record dump."""

from __future__ import annotations

import re
from typing import Any

from ..classification import classify_conversation_turn
from .contracts import CompiledStorySummary


def _clean_theme(text: str) -> str | None:
    t = re.sub(r"^(emerging\s+)?theme\s*[:\-]\s*", "", (text or "").strip(), flags=re.I)
    t = t.strip()
    if not t or t.lower() in {"theme", "emerging theme"}:
        return None
    if len(t) < 4:
        return None
    return t[0].upper() + t[1:] if t else None


def _is_canon_narrative(text: str) -> bool:
    """Classify a conversation turn as canon narrative (used for theme/conflict
    mining only — never for Logline/Short/Long, which come from the Story record).
    """
    return classify_conversation_turn(text) == "story_canon"


# Maps the public StoryEntry camelCase field names to the SQLAlchemy row's
# snake_case column attributes. Used by `_story_record_field` to read either a
# dict or a StoryEntryRow transparently.
_SNAKE_MAP: dict[str, str] = {
    "logline": "logline",
    "shortSummary": "short_summary",
    "longSummary": "long_summary",
}


def _story_record_field(story_record: Any, field: str) -> str:
    """Read a Story field from a StoryEntry row/dict, normalized to a stripped
    string. Returns "" when the record or field is missing/empty.

    Accepts both SQLAlchemy row attributes (logline / short_summary /
    long_summary) and dict shapes (logline / shortSummary / longSummary).
    """
    if story_record is None:
        return ""
    value: Any = ""
    if isinstance(story_record, dict):
        value = story_record.get(field) or story_record.get(_SNAKE_MAP.get(field, ""))
    else:
        value = getattr(story_record, field, None)
        if value is None:
            value = getattr(story_record, _SNAKE_MAP.get(field, ""), None)
    return str(value or "").strip()


def compile_story_summary(
    *,
    story_texts: list[str] | None = None,
    open_questions: list[str] | None = None,
    episode_summaries: list[str] | None = None,
    source_ids: list[str] | None = None,
    story_record: Any = None,
) -> CompiledStorySummary:
    """Compile the Story summary.

    Logline / Short Summary / Long Summary are sourced EXCLUSIVELY from the
    saved Story record (`story_record`). Conversation never writes those
    fields. When the Story record is None or its fields are empty, the
    Story fields are genuinely empty — no filler, no placeholder prose,
    no inferred plot.

    Conversation material may still feed other Wiki sections (themes,
    central conflicts, open questions) but NEVER Logline / Short / Long.
    """
    story_texts = story_texts or []
    open_questions = open_questions or []
    episode_summaries = episode_summaries or []
    source_ids = source_ids or []

    # Story-record-only Logline / Short / Long. Blank means blank — no
    # compilation from `story_texts`, no fallback filler.
    logline = _story_record_field(story_record, "logline")
    short = _story_record_field(story_record, "shortSummary")
    long_summary = _story_record_field(story_record, "longSummary")

    canon_texts: list[str] = []
    for t in story_texts:
        stripped = (t or "").strip()
        if not stripped:
            continue
        if _is_canon_narrative(stripped):
            canon_texts.append(stripped)

    # Themes may be mined from any conversation text (labeled Theme: X /
    # Emerging theme) — they never paste as Logline prose.
    themes: list[str] = []
    for t in story_texts:
        if re.search(r"\btheme\b", t, re.I) or "memory" in t.lower() or "agency" in t.lower():
            cleaned = _clean_theme(t)
            if cleaned and cleaned.lower() not in {x.lower() for x in themes}:
                themes.append(cleaned)
        if len(themes) >= 5:
            break

    # Conflicts may only be drawn from canon narrative — never from a
    # production_request or user_preference that happens to contain "vs".
    conflicts: list[str] = []
    for t in canon_texts:
        if re.search(r"\b(conflict|versus|vs\.?|tension|strained)\b", t, re.I):
            conflicts.append(t.strip()[:160])
        if len(conflicts) >= 3:
            break

    narrative_frame = ""
    if logline or short or long_summary:
        narrative_frame = "Based on the established project material so far."
    return CompiledStorySummary(
        logline=logline,
        shortSummary=short,
        longSummary=long_summary,
        themes=themes[:5],
        centralConflicts=conflicts,
        narrativeFrame=narrative_frame,
        unresolvedQuestions=[q for q in open_questions if q][:5],
        sourceRecordIds=source_ids[:20],
    )


def compile_story_page(
    summary: CompiledStorySummary,
    episode_children: list[dict[str, Any]],
    *,
    story_record: Any = None,
) -> dict[str, Any]:
    """Render the Story page.

    Logline / Short Summary / Long Summary sections are sourced EXCLUSIVELY
    from the saved Story record (`story_record`) — never from the compiled
    `summary`'s Story fields (which are themselves Story-record-sourced, but
    the page renderer reads the authoritative record directly to remain
    independent of any stale cache).

    When ALL three Story fields are empty, the page renders the warm
    "still taking shape" nudge for the creator. Otherwise blank sections are
    simply omitted (no filler prose).
    """
    logline = _story_record_field(story_record, "logline")
    short = _story_record_field(story_record, "shortSummary")
    long_summary = _story_record_field(story_record, "longSummary")

    sections: list[dict[str, Any]] = []
    if logline:
        sections.append({"id": "sec-logline", "title": "Logline", "body": logline, "bullets": []})
    if short:
        sections.append(
            {"id": "sec-short", "title": "Short Summary", "body": short, "bullets": []}
        )
    if long_summary:
        sections.append(
            {"id": "sec-long", "title": "Long Summary", "body": long_summary, "bullets": []}
        )
    # Warm sparse nudge when the Story record has no Logline / Short / Long.
    if not logline and not short and not long_summary:
        sections.append(
            {
                "id": "sec-long-pending",
                "title": "Long Summary",
                "body": (
                    "The story is still taking shape.\n\n"
                    "As more of it becomes established, Co-Director will expand "
                    "this summary automatically."
                ),
                "bullets": [],
                "developStoryAction": True,
            }
        )
    if summary.themes:
        sections.append(
            {"id": "sec-themes", "title": "Themes", "body": "", "bullets": summary.themes}
        )
    if summary.centralConflicts:
        sections.append(
            {
                "id": "sec-conflicts",
                "title": "Central Conflict",
                "body": "",
                "bullets": summary.centralConflicts,
            }
        )
    if episode_children:
        sections.append(
            {
                "id": "sec-episodes",
                "title": "Episodes",
                "body": "",
                "bullets": [c.get("label") or c.get("title") or "" for c in episode_children],
            }
        )
    if summary.unresolvedQuestions:
        sections.append(
            {
                "id": "sec-open",
                "title": "Open Story Questions",
                "body": "",
                "bullets": summary.unresolvedQuestions,
            }
        )
    return {
        "pageId": "page-story",
        "pageType": "STORY",
        "title": "Story",
        "summary": logline or short,
        "sections": sections,
        "relatedPageIds": [c.get("pageId") for c in episode_children if c.get("pageId")],
        "sourceRecordIds": summary.sourceRecordIds,
        "canonState": "CONFIRMED",
        "questionsToExplore": summary.unresolvedQuestions[:5],
    }
