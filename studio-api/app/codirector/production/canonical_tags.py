"""Prompt-facing identity tags. Never mint collision aliases into Timed Prompt language."""

from __future__ import annotations

import re

from ...creator_scope.contract import canonical_tag as scope_canonical_tag
from ...scene_references.sheet_tags import PREFIX_CRS, PREFIX_ERS, PREFIX_PRS

_SUFFIX_RE = re.compile(r"^(?P<base>.+?)(?P<suffix>-?\d+)$")
_GENERIC_TOKENS = frozenset(
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


def identity_token(raw: str | None) -> str:
    return scope_canonical_tag(raw)


def prompt_pascal(value: str) -> str:
    """Display name → prompt grammar. Cade's Starfighter → CadeSStarfighter."""
    text = re.sub(r"['’]s\b", "S", value or "", flags=re.I)
    parts = re.findall(r"[A-Za-z0-9]+", text)
    return "".join(part[:1].upper() + part[1:] for part in parts) if parts else ""


def _is_generic(token: str) -> bool:
    compact = identity_token(token).lower()
    return not compact or compact in _GENERIC_TOKENS or compact.endswith("reference")


def _is_internal_unique(raw: str) -> bool:
    token = (raw or "").strip()
    if not token:
        return False
    if token[:1] in {"@", "#", "%", "~", "*"}:
        token = token[1:]
    return "-" in token


def strip_collision_suffix(stored: str, display_name: str = "") -> str:
    """Drop uniqueness suffixes (VentureSpaceship3 / VentureSpaceship-3) when they are aliases."""
    token = identity_token(stored)
    named = prompt_pascal(display_name) or identity_token(display_name)
    if not token:
        return named
    match = _SUFFIX_RE.match(token)
    if not match:
        return token
    base = match.group("base")
    if named and base.lower() == named.lower():
        return named
    if named:
        return named
    return base


def prompt_facing_tag(prefix: str, stored_tag: str, display_name: str) -> str:
    """Authoritative identity → prompt tag. Prefer grammar names; never keep a collision suffix."""
    from ...creator_scope.identity_tag import sanitize_generator_tag

    mark = prefix[:1] if prefix else ""
    if mark not in {PREFIX_CRS, PREFIX_ERS, PREFIX_PRS, "@", "#", "%"}:
        mark = prefix or "%"
    kind = "character" if mark == PREFIX_CRS else "environment" if mark == PREFIX_ERS else "prop"
    return sanitize_generator_tag(kind, stored_tag, display_name)


def prefix_for_asset_type(asset_type: str | None) -> str:
    kind = (asset_type or "").strip().lower()
    if kind == "environment":
        return PREFIX_ERS
    if kind == "character":
        return PREFIX_CRS
    return PREFIX_PRS


def suffixed_tag_variants(tag: str) -> list[str]:
    token = (tag or "").strip()
    if len(token) < 2:
        return []
    prefix, body = token[:1], token[1:]
    if not body:
        return []
    variants: list[str] = []
    for index in range(2, 100):
        variants.append(f"{prefix}{body}{index}")
        variants.append(f"{prefix}{body}-{index}")
    return variants
