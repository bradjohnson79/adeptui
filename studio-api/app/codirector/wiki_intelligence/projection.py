"""Professional Wiki projection — nested TOC over structured / knowledge records."""

from __future__ import annotations

from typing import Any

from .classification import classify_entity_type, extract_display_name, is_false_character_name
from .contracts import PROFESSIONAL_TOC_ROOTS

_TOC_LABELS: dict[str, str] = {
    "projectOverview": "Project Overview",
    "story": "Story",
    "characters": "Characters",
    "episodesAndScenes": "Episodes and Scenes",
    "worldAndLore": "World and Lore",
    "locationsAndSets": "Locations and Sets",
    "timelineAndContinuity": "Timeline and Continuity",
    "visualDevelopment": "Visual Development",
    "audioAndPerformance": "Audio and Performance",
    "scriptsAndDevelopment": "Scripts and Development",
    "production": "Production",
    "references": "References",
}

_LEGACY_TO_PRO: dict[str, str] = {
    "knownDetails": "projectOverview",
    "creativeFoundation": "story",
    "characters": "characters",
    "worldAndSetting": "worldAndLore",
    "storyAndEpisodes": "episodesAndScenes",
    "visualIdentity": "visualDevelopment",
    "productionDecisions": "production",
    "openQuestions": "story",
    "references": "references",
}


def _canon_badge(state: str) -> str:
    s = (state or "").lower()
    if s in {"confirmed", "approved"}:
        return "CONFIRMED"
    if s in {"proposed", "reference-only"}:
        return "INFERRED"
    if s == "unresolved":
        return "EXPLORATORY"
    if s == "superseded":
        return "SUPERSEDED"
    if s == "rejected":
        return "DISPUTED"
    return "INFERRED"


def project_professional_toc(sections: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build nested professional TOC; hide empty; count only validated records."""
    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k in PROFESSIONAL_TOC_ROOTS}

    for legacy_key, section in (sections or {}).items():
        pro = _LEGACY_TO_PRO.get(legacy_key, "story")
        for entry in section.get("entries") or []:
            text = str(entry.get("text") or "")
            name = extract_display_name(text)
            et = classify_entity_type(text, hinted_section=legacy_key)
            # Skip invalid character fragments from counts/TOC children
            if legacy_key == "characters" or et == "character":
                if is_false_character_name(name):
                    continue
                pro = "characters"
            elif et == "location":
                pro = "locationsAndSets"
            elif et == "organization" or et == "world_rule":
                pro = "worldAndLore"
            elif et == "timeline_event":
                pro = "timelineAndContinuity"
            elif et == "wardrobe" or et == "prop" or et == "visual":
                pro = "visualDevelopment"
            elif et == "audio":
                pro = "audioAndPerformance"
            elif et == "episode_or_scene":
                pro = "episodesAndScenes"
            elif et == "story":
                pro = "story"
            elif et == "preference":
                pro = "references"
            elif legacy_key == "knownDetails":
                pro = "projectOverview"
            elif legacy_key == "productionDecisions":
                pro = "production"
            elif legacy_key == "references":
                pro = "references"

            buckets.setdefault(pro, []).append(
                {
                    "id": entry.get("id"),
                    "label": name[:80] or text[:80],
                    "canonState": _canon_badge(str(entry.get("state") or "")),
                    "entityType": et,
                }
            )

    toc: list[dict[str, Any]] = []
    for key in PROFESSIONAL_TOC_ROOTS:
        children = buckets.get(key) or []
        if not children:
            continue
        toc.append(
            {
                "key": key,
                "label": _TOC_LABELS.get(key, key),
                "count": len(children),
                "children": children[:40],
            }
        )
    return toc


def attach_professional_projection(wiki: dict[str, Any]) -> dict[str, Any]:
    """Mutate wiki payload with professionalToc + source annotation."""
    sections = wiki.get("sections") or {}
    wiki["professionalToc"] = project_professional_toc(sections)
    # Prefer professional TOC for clients that read `toc`
    wiki["toc"] = [
        {"key": n["key"], "label": n["label"], "count": n["count"]} for n in wiki["professionalToc"]
    ]
    wiki["sourceOfTruth"] = wiki.get("sourceOfTruth") or "projectIntelligence.knowledgeEntries"
    wiki["projection"] = "professional_v1"
    return wiki
