"""Prompt-facing identity tags. One canonical tag per entity.

Database slugs and collision aliases may exist internally.
Only the canonical tag is generator-facing.
"""

from __future__ import annotations

import re
from typing import Literal

EntityKind = Literal["character", "prop", "environment"]

PREFIX = {"character": "@", "prop": "%", "environment": "#"}

_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?P<suffix>-?\d+)$")
_KEBAB_RE = re.compile(r"-")
_GENERIC = frozenset(
    {
        "environment",
        "environmentreference",
        "reference",
        "prop",
        "character",
        "image",
        "sheet",
        "library",
        "asset",
    }
)
_FORBIDDEN_PROMPT_TOKENS = (
    "VentureSpaceship2",
    "VentureSpaceship3",
    "VentureSpaceship4",
    "venture-spaceship-4",
    "EarthHorizon2",
    "CadeSStarfighter2",
    "CadeSStarfighter3",
    "CadesStarfighter2",
    "CadesStarfighter3",
)


def prompt_canonical_token(display_name: str) -> str:
    """Venture Spaceship → VentureSpaceship. Cade's Starfighter → CadeSStarfighter."""
    text = re.sub(r"['’]s\b", "S", display_name or "", flags=re.I)
    parts = re.findall(r"[A-Za-z0-9]+", text)
    return "".join(part[:1].upper() + part[1:] for part in parts) if parts else ""


def prefix_for(kind: str | None) -> str:
    return PREFIX.get((kind or "").strip().lower(), "%")


def prompt_canonical_tag(kind: str, display_name: str, stored: str | None = None) -> str:
    """Return @/%/# + grammar token. Prefer a stored canonical tag if it is already grammar."""
    mark = prefix_for(kind)
    named = prompt_canonical_token(display_name)
    named_match = _SUFFIX_RE.match(named)
    if named_match and named[:1].isupper() and named_match.group("base").isalpha():
        named = named_match.group("base")
    if named and _looks_like_sheet_label(named):
        named = ""
    stored_raw = (stored or "").strip()
    if stored_raw[:1] in {"@", "#", "%"}:
        stored_raw = stored_raw[1:]
    if stored_raw and not _is_legacy_or_slug(stored_raw, named):
        if named and stored_raw.lower() == named.lower():
            return f"{mark}{named}"
        if not named or _is_generic_token(named):
            return f"{mark}{stored_raw}"
        if stored_raw.lower() in named.lower() and _looks_like_sheet_label(named):
            return f"{mark}{stored_raw}"
    if named:
        return f"{mark}{named}"
    compact = re.sub(r"[^A-Za-z0-9]+", "", stored_raw)
    if _KEBAB_RE.search(stored_raw) or _is_generic_token(stored_raw):
        compact = ""
    else:
        match = _SUFFIX_RE.match(compact)
        if match and compact[:1].isupper() and match.group("base").isalpha():
            compact = match.group("base")
    return f"{mark}{compact}" if compact else ""


def sanitize_generator_tag(kind: str, raw: str, display: str = "") -> str:
    """Never emit a kebab slug, collision suffix, or the wrong prefix."""
    token = canonical_token_only(raw)
    return prompt_canonical_tag(kind, display or token, token)


def canonical_token_only(tag: str) -> str:
    token = (tag or "").strip()
    if token[:1] in {"@", "#", "%", "*", "~"}:
        return token[1:]
    return token


def _is_generic_token(token: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", token or "").lower()
    return not compact or compact in _GENERIC or compact.endswith("reference") or compact.endswith("sheet")


def _looks_like_sheet_label(token: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]+", "", token or "").lower()
    return any(part in compact for part in ("reference", "sheet", "advancedprs", "prs"))


def _is_legacy_or_slug(token: str, named: str) -> bool:
    raw = (token or "").strip()
    if not raw:
        return True
    compact = re.sub(r"[^A-Za-z0-9]+", "", raw)
    if _is_generic_token(raw):
        return True
    if _KEBAB_RE.search(raw):
        return True
    match = _SUFFIX_RE.match(compact)
    if match:
        base = match.group("base")
        if named and (base.lower() == named.lower() or named.lower() == compact.lower()):
            return True
        if compact[:1].isupper() and base.isalpha():
            return True
    return False


def is_forbidden_prompt_token(text: str) -> list[str]:
    blob = text or ""
    return [token for token in _FORBIDDEN_PROMPT_TOKENS if token in blob]


def looks_like_collision_alias(token: str, display_name: str = "") -> bool:
    named = prompt_canonical_token(display_name)
    return _is_legacy_or_slug(canonical_token_only(token), named)


def is_sheet_or_generic_label(token: str) -> bool:
    """Asset/sheet filenames must never become prompt-facing identity."""
    return _looks_like_sheet_label(token) or _is_generic_token(token)
