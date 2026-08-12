"""Normalize messy theme strings into clean editorial tokens.

Replaces the old `_clean_theme` heuristic in story_compiler.py. Theme records
such as "Theme: consciousness: Thematic thread present in the narration:
consciousness." are reduced to a clean token like "Consciousness".
"""

from __future__ import annotations

import re

_PREFIX_RE = re.compile(
    r"^(emerging\s+)?theme\s*[:\-]\s*",
    re.I,
)
_SUFFIX_NOISE = re.compile(
    r":\s*(thematic\s+thread.*|present\s+in.*|thread\s+in.*|underlying.*|"
    r"recurring.*|central.*|explored.*|throughout.*).*$",
    re.I,
)
_STOP_TOKENS = {
    "theme",
    "emerging theme",
    "themes",
    "narrative",
    "story",
    "the story",
    "project",
    "untitled",
}


def normalize_theme(text: str) -> str | None:
    """Return a clean theme token, or None when the text is not a real theme."""
    t = (text or "").strip()
    if not t:
        return None
    t = _PREFIX_RE.sub("", t)
    t = _SUFFIX_NOISE.sub("", t)
    # Strip trailing colons / dashes / whitespace left after suffix removal.
    t = t.strip().rstrip(":—-").strip()
    if not t:
        return None
    if t.lower() in _STOP_TOKENS:
        return None
    if len(t) < 3:
        return None
    # Title-case multi-word themes; capitalize single words.
    if " " in t:
        token = " ".join(part.capitalize() for part in t.split() if part)
    else:
        token = t[0].upper() + t[1:]
    if token.lower() in _STOP_TOKENS:
        return None
    return token


def normalize_themes(texts: list[str]) -> list[str]:
    """Normalize and deduplicate a list of theme-ish strings, preserving order."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in texts:
        token = normalize_theme(raw)
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


__all__ = ["normalize_theme", "normalize_themes"]
