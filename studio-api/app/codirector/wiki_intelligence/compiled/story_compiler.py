"""Synthesize Story page — never Theme×N record dump."""

from __future__ import annotations

import re
from typing import Any

from ..classification import classify_conversation_turn, is_non_canon_turn
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
    """A story text may populate summaries only if it reads as in-world canon.

    The sync `compile_story_summary` is defense-in-depth: the primary fix is the
    async editor path (page_compiler.compile_wiki_bundle_async → editor.py +
    readiness gates). This guard ensures the sync compiler cannot paste a
    user-preference / production-request / meta-conversation / question turn
    as the Logline / Short Summary / Long Summary when a caller still hits
    the sync path (tests, get_compiled_wiki cache-miss, timeline_context).

    Brainstorming is NOT canon here — only the explicit rebuild operation may
    opt brainstorming into candidate extraction, and even then it should not
    become the Logline.
    """
    return classify_conversation_turn(text) == "story_canon"


def compile_story_summary(
    *,
    story_texts: list[str],
    open_questions: list[str],
    episode_summaries: list[str],
    source_ids: list[str],
) -> CompiledStorySummary:
    # Split canon narrative from non-canon material. Non-canon texts
    # (user_preference / production_request / meta_conversation / question /
    # unknown / brainstorming) must NEVER populate Logline / Short / Long.
    canon_texts: list[str] = []
    non_canon_texts: list[str] = []
    for t in story_texts:
        stripped = (t or "").strip()
        if not stripped:
            continue
        if _is_canon_narrative(stripped):
            canon_texts.append(stripped)
        else:
            non_canon_texts.append(stripped)

    # Prefer longer narrative sentences for summaries, drawn ONLY from canon.
    narrative = [t for t in canon_texts if len(t) >= 40]
    themes: list[str] = []
    # Themes may be mined from either canon or non-canon text — themes are
    # labeled (Theme: X / Emerging theme) and never paste as Logline prose.
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
    # Conflicts may only be drawn from canon narrative — never from a
    # production_request or user_preference that happens to contain "vs".
    for t in canon_texts:
        if re.search(r"\b(conflict|versus|vs\.?|tension|strained)\b", t, re.I):
            conflicts.append(t.strip()[:160])
        if len(conflicts) >= 3:
            break

    # Honesty rule: when there is no canon narrative material, leave Logline /
    # Short / Long genuinely empty. Do NOT write placeholder prose, do NOT
    # paste Co-Director instructions, do NOT paste conversation excerpts.
    # The Story page renders a warm "still taking shape" nudge for the creator.
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
