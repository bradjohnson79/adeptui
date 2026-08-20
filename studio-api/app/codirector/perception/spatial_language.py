"""Filmmaker spatial language for Scene Creator compile.

Does not add fields to the frozen ShotRequest schema. Relations become
prompt / creativeContext lines.
"""

from __future__ import annotations

import re
from typing import Any

RELATION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bbehind\b", "BEHIND"),
    (r"\bin front of\b", "IN_FRONT_OF"),
    (r"\bbeside\b", "BESIDE"),
    (r"\bnext to\b", "BESIDE"),
    (r"\bon the\b", "ON"),
    (r"\bon\b", "ON"),
    (r"\bunder\b", "UNDER"),
    (r"\bleft of\b", "LEFT_OF"),
    (r"\bright of\b", "RIGHT_OF"),
    (r"\binside\b", "INSIDE"),
    (r"\boutside\b", "OUTSIDE"),
    (r"\bfacing\b", "FACING"),
    (r"\bnear\b", "NEAR"),
)

ZONE_PHRASES: tuple[str, ...] = (
    "customer side",
    "employee side",
    "behind the counter",
    "behind the service counter",
    "on the counter",
    "on the service counter",
    "in front of the counter",
    "walkable area",
    "doorway",
    "entrance",
    "foreground",
    "midground",
    "background",
    "left area",
    "right area",
    "work area",
    "seating area",
)


def detect_zone_phrases(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for phrase in ZONE_PHRASES:
        if phrase in lowered and phrase not in found:
            found.append(phrase)
    return found


def detect_relation_tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for pattern, token in RELATION_PATTERNS:
        if re.search(pattern, lowered) and token not in found:
            found.append(token)
    return found


def extract_spatial_lines(text: str, extra_phrases: list[str] | None = None) -> list[str]:
    lines: list[str] = []
    for phrase in detect_zone_phrases(text):
        lines.append(f"Zone: {phrase}")
    for token in detect_relation_tokens(text):
        lines.append(f"Spatial relation: {token.replace('_', ' ').lower()}")
    for phrase in extra_phrases or []:
        cleaned = str(phrase or "").strip()
        if cleaned and cleaned not in lines:
            lines.append(cleaned)
    return lines


def match_known_names(text: str, names: list[str]) -> list[str]:
    """Whole-word match of known character / prop names without requiring @/#."""
    found: list[str] = []
    blob = text or ""
    for name in names:
        label = str(name or "").strip()
        if not label:
            continue
        if re.search(rf"\b{re.escape(label)}\b", blob, flags=re.IGNORECASE):
            found.append(label)
    return found


def compile_spatial_glossary(draft: Any | None) -> list[str]:
    if draft is None:
        return []
    lines: list[str] = []
    for zone in getattr(draft, "zonePhrases", []) or []:
        phrase = str(getattr(zone, "phrase", "") or "")
        if phrase:
            lines.append(f"Zone: {phrase}")
    for rel in getattr(draft, "relationships", []) or []:
        subject = str(getattr(rel, "subjectLabel", "") or "")
        relation = str(getattr(rel, "relation", "") or "").replace("_", " ").lower()
        obj = str(getattr(rel, "objectLabel", "") or "")
        if subject and relation and obj:
            lines.append(f"{subject} {relation} {obj}")
    return lines
