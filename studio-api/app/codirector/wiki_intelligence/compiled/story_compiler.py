"""Synthesize Story page — never Theme×N record dump."""

from __future__ import annotations

import re
from typing import Any

from .contracts import CompiledStorySummary


def _clean_theme(text: str) -> str | None:
    t = re.sub(r"^(emerging\s+)?theme\s*[:\-]\s*", "", (text or "").strip(), flags=re.I)
    t = t.strip()
    if not t or t.lower() in {"theme", "emerging theme"}:
        return None
    if len(t) < 4:
        return None
    return t[0].upper() + t[1:] if t else None


def compile_story_summary(
    *,
    story_texts: list[str],
    open_questions: list[str],
    episode_summaries: list[str],
    source_ids: list[str],
) -> CompiledStorySummary:
    # Prefer longer narrative sentences for summaries
    narrative = [t.strip() for t in story_texts if len(t.strip()) >= 40]
    themes: list[str] = []
    for t in story_texts:
        if re.search(r"\btheme\b", t, re.I) or "memory" in t.lower() or "agency" in t.lower():
            cleaned = _clean_theme(t)
            if cleaned and cleaned.lower() not in {x.lower() for x in themes}:
                themes.append(cleaned)
        if len(themes) >= 5:
            break

    logline = ""
    if narrative:
        logline = narrative[0]
        if len(logline) > 220:
            logline = logline[:217].rstrip() + "…"
    short = " ".join(narrative[:2])[:480] if narrative else ""
    long = " ".join(narrative[:6])[:1200] if narrative else short
    if episode_summaries and long:
        long = (long + " " + episode_summaries[0]).strip()[:1400]

    conflicts: list[str] = []
    for t in story_texts:
        if re.search(r"\b(conflict|versus|vs\.?|tension|strained)\b", t, re.I):
            conflicts.append(t.strip()[:160])
        if len(conflicts) >= 3:
            break

    narrative_frame = ""
    if narrative:
        narrative_frame = "Based on the established project material so far."
    return CompiledStorySummary(
        logline=logline,
        shortSummary=short or logline,
        longSummary=long or short or logline,
        themes=themes[:5],
        centralConflicts=conflicts,
        narrativeFrame=narrative_frame,
        unresolvedQuestions=[q for q in open_questions if q][:5],
        sourceRecordIds=source_ids[:20],
    )


def compile_story_page(summary: CompiledStorySummary, episode_children: list[dict[str, Any]]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    if summary.logline:
        sections.append({"id": "sec-logline", "title": "Logline", "body": summary.logline, "bullets": []})
    if summary.shortSummary:
        sections.append(
            {"id": "sec-short", "title": "Short Summary", "body": summary.shortSummary, "bullets": []}
        )
    if summary.longSummary:
        sections.append(
            {"id": "sec-long", "title": "Long Summary", "body": summary.longSummary, "bullets": []}
        )
    # Warm sparse nudge when long summary is omitted.
    if not summary.longSummary and not summary.shortSummary:
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
    elif not summary.longSummary:
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
        "summary": summary.logline or summary.shortSummary,
        "sections": sections,
        "relatedPageIds": [c.get("pageId") for c in episode_children if c.get("pageId")],
        "sourceRecordIds": summary.sourceRecordIds,
        "canonState": "CONFIRMED",
        "questionsToExplore": summary.unresolvedQuestions[:5],
    }
