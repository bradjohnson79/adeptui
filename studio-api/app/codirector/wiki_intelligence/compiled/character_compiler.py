"""Character pages — immediate profiles; aliases collapse to one canonical name."""

from __future__ import annotations

import re
from typing import Any


_FALSE_CHARACTER = re.compile(
    r"^(theme|project|series|web series|live.?action|16:9|minimax|overview|emerging|"
    r"character/person|character note|untitled|character|video|story|period|continuity|"
    r"world|signal|organization|screenplay|concept|audio|timeline|inciting|unusual|"
    r"adept|episode|scene|act|chapter|treatment|bible|wiki|notes|casting|production|"
    r"i'?ve|i'?d|i'?m|we'?ve|they'?ve|location|reference|prop|wardrobe|"
    r"current|narrative|director|creator|user|default|assistant|suggest|test|sample|"
    r"example|project|understanding|collaboration|working|preference|skip|onboarding|"
    r"tell)\b",
    re.I,
)
_TITLE_ONLY = re.compile(r"^(special agent|agent|dr\.?|doctor|mr\.?|ms\.?|mrs\.?)$", re.I)
_EPISODEISH = re.compile(r"^(episode|scene|act|chapter)\b", re.I)
_COMMON_WORD = re.compile(
    r"^(the|a|an|and|or|but|with|from|into|about|after|before|during|while)$",
    re.I,
)


def _is_junk_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) < 2:
        return True
    if _TITLE_ONLY.match(n) or _FALSE_CHARACTER.match(n) or _EPISODEISH.match(n):
        return True
    if _COMMON_WORD.match(n):
        return True
    # Contractions / fragments
    if "'" in n and len(n.split()) == 1:
        return True
    # Single generic capitalized noun often scraped from headings
    if len(n.split()) == 1 and n.lower() in {
        "character",
        "video",
        "story",
        "period",
        "continuity",
        "world",
        "signal",
        "organization",
        "screenplay",
        "concept",
        "audio",
        "timeline",
        "inciting",
        "unusual",
        "adept",
        "alaska",
        "gakona",
        "current",
        "narrative",
        "director",
        "creator",
        "default",
        "assistant",
        "suggestion",
        "test",
        "sample",
        "example",
        "understanding",
        "collaboration",
        "preference",
        "onboarding",
        "tell",
    }:
        # Allow known proper place names only when multi-word elsewhere; single-token places
        # from knowledge noise are excluded from Characters.
        return True
    return False


def _display_name(text: str) -> str | None:
    t = (text or "").strip()
    t = re.sub(r"^(character|person)\s*[:\-]\s*", "", t, flags=re.I)
    if re.search(r"setting\s*/\s*location|location\s*:", t, re.I):
        return None
    if ":" in t and len(t) > 40:
        return None
    # Prefer "Name is/was ..." → Name
    m = re.match(
        r"^((?:Special Agent|Agent|Dr\.?|Doctor)\s+)?([A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,3})\b",
        t,
    )
    if m:
        name = ((m.group(1) or "") + m.group(2)).strip()
        if _is_junk_name(name):
            return None
        if len(name) < 2:
            return None
        return name
    if _is_junk_name(t):
        return None
    if len(t) <= 48 and re.match(r"^[A-Z]", t) and not t.endswith("."):
        if _is_junk_name(t):
            return None
        return t
    return None


def resolve_characters(
    texts: list[str],
    *,
    alias_map: dict[str, str] | None = None,
    key_characters: list[str] | None = None,
    entity_type_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    alias_map = alias_map or {}
    overrides = {k.lower(): v for k, v in (entity_type_overrides or {}).items()}
    found: dict[str, dict[str, Any]] = {}

    def blocked_by_override(name: str) -> bool:
        """A creator correction has reclassified this entity out of Characters."""
        low = name.strip().lower()
        if not low:
            return False
        for oname, otype in overrides.items():
            if oname and oname in low and otype != "character":
                return True
        return False

    def canonical(name: str) -> str:
        key = name.strip().lower()
        if key in {k.lower(): v for k, v in alias_map.items()}:
            for ak, av in alias_map.items():
                if ak.lower() == key:
                    return av
        # Collapse "Special Agent" alone into longer names when possible
        return name

    seeds = list(key_characters or []) + list(texts)
    for text in seeds:
        name = _display_name(text) if text else None
        if not name:
            # key_characters may already be clean names
            if text and not _is_junk_name(text) and len(text) < 60:
                name = text.strip()
            else:
                continue
        if blocked_by_override(name):
            continue
        canon = canonical(name)
        if _is_junk_name(canon) or blocked_by_override(canon):
            continue
        cid = re.sub(r"[^a-z0-9]+", "-", canon.lower()).strip("-")[:40]
        page_id = f"page-character-{cid}"
        if page_id not in found:
            overview = text if text and name and name.lower() not in text.lower()[: len(name) + 2] else (
                f"{canon} appears in the current project material."
            )
            # Prefer descriptive sentences as overview
            if len(text) > len(canon) + 10:
                overview = text.strip()[:280]
            found[page_id] = {
                "pageId": page_id,
                "pageType": "CHARACTER",
                "title": canon,
                "summary": overview[:200],
                "sections": [
                    {"id": "sec-overview", "title": "Overview", "body": overview[:400], "bullets": []},
                    {
                        "id": "sec-known",
                        "title": "Known Details",
                        "body": "",
                        "bullets": [overview[:160]] if overview else [],
                    },
                ],
                "relatedPageIds": ["page-story"],
                "sourceRecordIds": [],
                "canonState": "CONFIRMED",
                "questionsToExplore": [
                    f"What does {canon.split()[-1]} want most deeply right now?",
                    f"How does {canon.split()[-1]} relate to the central conflict?",
                ][:2],
                "castingLink": f"casting:{cid}",
            }
        else:
            # Enrich known details
            bullets = found[page_id]["sections"][1]["bullets"]
            if text and text.strip() not in bullets and len(bullets) < 8:
                bullets.append(text.strip()[:160])
    return list(found.values())
