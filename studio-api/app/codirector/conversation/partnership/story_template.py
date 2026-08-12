"""Rapid story-development template from confirmed/emerging facts — no invented facts."""

from __future__ import annotations

import re

from .schemas import CreativeDeliverable, CreativeDeliverableStatus


_FIELDS = [
    ("working_title", r"\btitled?\s+[\"']?([^\"'.\n]+)"),
    ("format", r"\b(feature|short film|series|pilot|web series|youtube)\b"),
    ("genre", r"\b(thriller|horror|drama|comedy|sci-?fi|fantasy|documentary)\b"),
    ("tone", r"\b(tone|moody|dark|hopeful|tense|intimate)\b"),
]


def build_story_template(
    *,
    project_id: str,
    user_message: str,
    brief_fields: dict[str, str] | None = None,
    ownership_mode,
    why_now: str = "",
) -> CreativeDeliverable:
    brief = brief_fields or {}
    text = user_message or ""
    lowered = text.lower()
    marks: dict[str, str] = {}
    rows: list[str] = ["# Story Template", ""]

    def add(label: str, value: str | None, mark: str) -> None:
        key = label.lower().replace(" ", "_")
        if value:
            rows.append(f"- **{label}** [{mark}]: {value}")
            marks[key] = mark
        else:
            rows.append(f"- **{label}** [Needs decision]: —")
            marks[key] = "Needs decision"

    title = brief.get("project_identity") or brief.get("working_title")
    if not title:
        m = re.search(r"\btitled?\s+[\"']([^\"']+)", text, re.I)
        title = m.group(1).strip() if m else None
    add("Working title", title, "Emerging" if title else "Needs decision")

    fmt = brief.get("format")
    if not fmt:
        for cand in ("feature", "short film", "series", "pilot", "youtube"):
            if cand in lowered:
                fmt = cand
                break
    add("Format", fmt, "Confirmed" if fmt and fmt in brief else ("Emerging" if fmt else "Needs decision"))

    genre = brief.get("genre")
    if not genre:
        for g in ("thriller", "horror", "drama", "comedy", "sci-fi", "fantasy"):
            if g in lowered:
                genre = g
                break
    add("Genre", genre, "Emerging" if genre else "Needs decision")
    add("Tone", brief.get("tone"), "Emerging" if brief.get("tone") else "Needs decision")
    add("Audience promise", brief.get("audience_experience"), "Emerging" if brief.get("audience_experience") else "Needs decision")

    premise = brief.get("premise") or (text.strip()[:400] if len(text.split()) >= 20 else None)
    add("Core premise", premise, "Confirmed" if brief.get("premise") else ("Emerging" if premise else "Needs decision"))

    protagonist = brief.get("main_characters")
    if not protagonist:
        m = re.search(
            r"\b((?:a|an|the)\s+(?:disgraced\s+)?(?:young\s+)?(?:\w+\s+){0,3}(?:biologist|detective|artist|teacher|soldier|doctor|girl|boy|woman|man))\b",
            text,
            re.I,
        )
        protagonist = m.group(1) if m else None
    add("Protagonist", protagonist, "Emerging" if protagonist else "Needs decision")
    add("Protagonist goal", None, "Needs decision")
    add("Central conflict", brief.get("central_conflict"), "Emerging" if brief.get("central_conflict") else "Needs decision")
    add("Inciting event", None, "Needs decision")
    add("Key relationships", None, "Needs decision")
    add("World or setting", brief.get("setting"), "Emerging" if brief.get("setting") else "Needs decision")
    add("Story stakes", None, "Needs decision")
    themes = brief.get("themes")
    add("Themes", themes, "Emerging" if themes else "Needs decision")
    add("Visual identity", brief.get("visual_direction"), "Emerging" if brief.get("visual_direction") else "Needs decision")
    add("Open questions", brief.get("open_questions") or "Ending and destination still open", "Emerging")
    add("Possible destination", brief.get("destination"), "Needs decision")

    assumptions = [
        "Fields marked Emerging or Interpretation are not locked.",
        "Missing facts were not invented.",
    ]
    content = "\n".join(rows)
    return CreativeDeliverable(
        project_id=project_id,
        type="story_template",
        title="Story template draft",
        ownership_mode=ownership_mode,
        current_author="CO_DIRECTOR",
        status=CreativeDeliverableStatus.DRAFT,
        content=content,
        preview_content=premise or text[:200],
        why_now=why_now,
        approval_required=True,
        field_marks=marks,
        assumptions=assumptions,
        revision_count=1,
        revision_history=[content[:2000]],
    )
