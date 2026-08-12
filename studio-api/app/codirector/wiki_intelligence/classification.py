"""Entity classification, preference filter, false-character rejection, alias helpers."""

from __future__ import annotations

import re
from typing import Any

from .contracts import FALSE_CHARACTER_TOKENS, PROFESSIONAL_TOC_ROOTS

_PREF_RE = re.compile(
    r"\b(agent gold|working preference|how i(?:'|’)d like us to work|collaboration preference|"
    r"call me |address me as|skip the setup|relationship mode)\b",
    re.I,
)
_LOC_HINT = re.compile(
    r"\b(location|room|set|harbor|archive|city|building|station|facility|anteroom|office|studio)\b",
    re.I,
)
_ORG_HINT = re.compile(
    r"\b(guild|agency|institute|organization|organisation|corp|company|cooperative|faction|council)\b",
    re.I,
)
_WARDROBE_HINT = re.compile(
    r"\b(wears?|wearing|coat|suit|wardrobe|outfit|dress|costume|footwear|accessory)\b",
    re.I,
)
_PROP_HINT = re.compile(
    r"\b(prop|recorder|device|weapon|tool|carries?|carrying|holds?|holding)\b",
    re.I,
)
_TIMELINE_HINT = re.compile(
    r"\b((?:19|20|21)\d{2}|timeline|flashback|flash[- ]forward|chronolog|before|after)\b",
    re.I,
)
_WORLD_HINT = re.compile(
    r"\b(world rule|must never|always |forbidden|continuity|metaphysic|technology|power system)\b",
    re.I,
)
_AGE_RE = re.compile(r"\b(?:age\s+\d{1,3}|\d{1,3}\s+years?\s+old)\b", re.I)
_KNOWN_ORG_TOKENS = re.compile(
    r"\b(fbi|nsa|cia|dw6|darpa|nasa|nato|kgb|mi6|interpol|pentagon|cdc|who|un)\b",
    re.I,
)


def is_user_preference_not_canon(text: str) -> bool:
    return bool(_PREF_RE.search(text or ""))


def is_false_character_name(name: str) -> bool:
    cleaned = re.sub(r"[^a-zA-Z0-9\s'\-]", "", (name or "").strip()).strip().lower()
    if not cleaned or len(cleaned) < 2:
        return True
    if cleaned in FALSE_CHARACTER_TOKENS:
        return True
    if cleaned in {"series synopsis", "project overview", "known details"}:
        return True
    # Pronouns / single generic nouns
    if cleaned in {"she", "he", "they", "it", "we", "you"}:
        return True
    return False


def classify_entity_type(
    text: str,
    *,
    hinted_section: str | None = None,
    entity_type_overrides: dict[str, str] | None = None,
) -> str:
    """Return a professional entity type for routing — conversational context only.

    Phase CK — entity classification is for conversational understanding only.
    It does NOT create canonical project entities.

    `entity_type_overrides` maps normalized (lowercase) entity names to a
    creator-corrected entity type. These are consulted FIRST so a learned
    correction ("Gakona is a location") permanently reclassifies that entity.
    """
    raw = (text or "").strip()
    lower = raw.lower()
    title = raw.split(":", 1)[0].strip()

    # Creator-learned overrides take highest precedence (CREATOR_CORRECTION_PRIORITY).
    if entity_type_overrides:
        for name, etype in entity_type_overrides.items():
            if name and name in lower:
                return etype

    if is_user_preference_not_canon(raw):
        return "preference"

    # Age / attribute detection: "age N" / "N years old" is an ATTRIBUTE, never a character.
    if _AGE_RE.search(raw):
        return "attribute"

    # Known organization acronyms / agency tokens are ORGANIZATION, never a character.
    if _KNOWN_ORG_TOKENS.search(raw) or _KNOWN_ORG_TOKENS.search(title):
        return "organization"

    if hinted_section:
        hs = hinted_section.lower()
        if "character" in hs:
            # Still reject false names when text looks like a name-only entry
            if is_false_character_name(title) or _LOC_HINT.search(raw) or _ORG_HINT.search(raw):
                pass
            else:
                # Phase CK — conversational context only; does not auto-persist
                return "note"
        if "location" in hs or "world" in hs:
            return "location" if not _ORG_HINT.search(raw) else "organization"
    if _ORG_HINT.search(raw) or _ORG_HINT.search(title):
        return "organization"
    if _LOC_HINT.search(raw):
        return "location"
    if _WARDROBE_HINT.search(raw):
        return "wardrobe"
    if _PROP_HINT.search(raw):
        return "prop"
    if _TIMELINE_HINT.search(raw) and len(raw) < 280:
        return "timeline_event"
    if _WORLD_HINT.search(raw):
        return "world_rule"
    if re.search(r"\b(theme|premise|synopsis|logline|act structure|story beat)\b", lower):
        # Phase CK — conversational context only; does not auto-persist
        return "note"
    if re.search(r"\b(lighting|lens|camera|palette|visual|storyboard)\b", lower):
        return "visual"
    if re.search(r"\b(voice|accent|music|ambience|sound|score)\b", lower):
        return "audio"
    if re.search(r"\b(episode|scene|treatment|script|screenplay)\b", lower):
        return "episode_or_scene"
    # Name-like character candidate — Phase CK: conversational context only, does not auto-persist
    if re.match(r"^(?:Dr\.|Agent|Professor|Captain|Detective)?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", raw):
        if not is_false_character_name(title):
            return "note"
    return "note"


def target_section_for_entity(entity_type: str) -> str:
    mapping = {
        "character": "characters",
        "location": "locationsAndSets",
        "organization": "worldAndLore",
        "wardrobe": "visualDevelopment",
        "prop": "visualDevelopment",
        "timeline_event": "timelineAndContinuity",
        "world_rule": "worldAndLore",
        "story": "story",
        "visual": "visualDevelopment",
        "audio": "audioAndPerformance",
        "episode_or_scene": "episodesAndScenes",
        "preference": "references",  # quarantined / not overview
        "note": "story",
    }
    section = mapping.get(entity_type, "story")
    return section if section in PROFESSIONAL_TOC_ROOTS else "story"


def normalize_alias_key(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"^(dr\.|agent|professor|captain|detective)\s+", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def names_are_aliases(a: str, b: str) -> bool:
    ka, kb = normalize_alias_key(a), normalize_alias_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if ka in kb or kb in ka:
        # Prefer longer containment only when token overlap is strong
        short, long = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
        return len(short) >= 4 and short in long
    return False


def extract_display_name(text: str) -> str:
    head = (text or "").split(":", 1)[0].strip()
    head = re.sub(r"^(character|person|location|organization|prop|wardrobe)\s*[–\-:]?\s*", "", head, flags=re.I)
    return head[:80].strip() or (text or "")[:80]


def detect_domains_from_entries(entries: list[dict[str, Any]]) -> list[str]:
    domains: set[str] = set()
    for e in entries:
        text = str(e.get("text") or "")
        et = classify_entity_type(text, hinted_section=str(e.get("section") or ""))
        if et == "character":
            domains.add("characters")
        elif et == "location":
            domains.add("locations")
        elif et == "organization" or et == "world_rule":
            domains.add("world")
        elif et == "timeline_event":
            domains.add("timeline")
        elif et == "wardrobe":
            domains.add("wardrobe")
        elif et == "prop":
            domains.add("props")
        elif et == "visual":
            domains.add("visual")
        elif et == "audio":
            domains.add("audio")
        elif et in {"story", "episode_or_scene"}:
            domains.add("story")
        elif et == "preference":
            domains.add("canon")
        else:
            domains.add("story")
    if not domains:
        domains.add("story")
    domains.add("canon")
    return sorted(domains)
