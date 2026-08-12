"""Character identity resolution — titles/ranks/aliases → one identity."""

from __future__ import annotations

import re
from typing import Any

# Generic titles/ranks — not fixture-specific names.
_TITLE_PREFIXES = (
    "special agent",
    "agent",
    "commander",
    "captain",
    "detective",
    "officer",
    "doctor",
    "dr",
    "professor",
    "prof",
    "sir",
    "madam",
    "mr",
    "mrs",
    "ms",
    "miss",
    "lord",
    "lady",
    "general",
    "colonel",
    "major",
    "lieutenant",
    "sergeant",
    "chief",
    "director",
    "president",
    "minister",
    "father",
    "mother",
    "brother",
    "sister",
)


def strip_title(name: str) -> tuple[str, str | None]:
    raw = re.sub(r"\s+", " ", (name or "").strip())
    lower = raw.lower()
    for title in sorted(_TITLE_PREFIXES, key=len, reverse=True):
        if lower.startswith(title + " "):
            return raw[len(title) :].strip(), title.title() if title != "dr" else "Dr"
        if lower == title:
            return "", title.title()
    return raw, None


def canonical_key(name: str) -> str:
    core, _title = strip_title(name)
    core = re.sub(r"[^\w\s'\-]", "", core).strip().lower()
    parts = [p for p in core.split() if p]
    if not parts:
        return ""
    # Prefer surname for multi-part; keep full for uniqueness when short.
    if len(parts) >= 2:
        return f"{parts[0]}|{parts[-1]}"
    return parts[0]


def resolve_identity(name: str, alias_map: dict[str, str] | None = None) -> dict[str, Any]:
    """Resolve a surface form to a canonical identity record."""
    surface = re.sub(r"\s+", " ", (name or "").strip())
    if not surface:
        return {
            "surface": "",
            "canonicalName": "",
            "title": None,
            "rank": None,
            "aliasOf": None,
            "unresolvedRole": True,
        }
    # Reject false characters / pronouns
    if surface.lower() in {"she", "he", "they", "here", "there", "the", "this", "that"}:
        return {
            "surface": surface,
            "canonicalName": "",
            "title": None,
            "rank": None,
            "aliasOf": None,
            "unresolvedRole": True,
            "rejected": True,
        }

    aliases = alias_map or {}
    lower = surface.lower()
    if lower in aliases:
        return {
            "surface": surface,
            "canonicalName": aliases[lower],
            "title": strip_title(surface)[1],
            "rank": None,
            "aliasOf": aliases[lower],
            "unresolvedRole": False,
        }

    core, title = strip_title(surface)
    # Check surname / partial matches against alias map values
    for alias, canonical in aliases.items():
        if lower == alias or lower.endswith(" " + alias) or alias.endswith(lower):
            return {
                "surface": surface,
                "canonicalName": canonical,
                "title": title,
                "rank": title,
                "aliasOf": canonical,
                "unresolvedRole": False,
            }
        c_lower = canonical.lower()
        if core and (core.lower() == c_lower or core.lower().endswith(c_lower.split()[-1])):
            return {
                "surface": surface,
                "canonicalName": canonical,
                "title": title,
                "rank": title,
                "aliasOf": canonical,
                "unresolvedRole": False,
            }

    canonical = core or surface
    return {
        "surface": surface,
        "canonicalName": canonical,
        "title": title,
        "rank": title,
        "aliasOf": None,
        "unresolvedRole": bool(title and not core),
    }


def learn_aliases_from_correction(
    alias_map: dict[str, str],
    *,
    surfaces: list[str],
    canonical_name: str,
) -> dict[str, str]:
    """Creator correction: multiple surfaces → one canonical name."""
    out = dict(alias_map)
    canon = canonical_name.strip()
    if not canon:
        return out
    out[canon.lower()] = canon
    for surface in surfaces:
        s = (surface or "").strip()
        if not s:
            continue
        out[s.lower()] = canon
        core, _ = strip_title(s)
        if core:
            out[core.lower()] = canon
            parts = core.split()
            if parts:
                out[parts[-1].lower()] = canon
    return out


def same_identity(a: str, b: str, alias_map: dict[str, str] | None = None) -> bool:
    ra = resolve_identity(a, alias_map)
    rb = resolve_identity(b, alias_map)
    if ra.get("rejected") or rb.get("rejected"):
        return False
    ca = str(ra.get("canonicalName") or "").strip()
    cb = str(rb.get("canonicalName") or "").strip()
    if not ca or not cb:
        return False
    if ca.lower() == cb.lower():
        return True
    ka, kb = canonical_key(ca), canonical_key(cb)
    if ka and kb and ka == kb:
        return True
    # Surname-only match: "Agent Barnes" ↔ "Jacob Barnes" / "Special Agent Jacob Barnes"
    parts_a = ca.split()
    parts_b = cb.split()
    if not parts_a or not parts_b:
        return False
    surname_a, surname_b = parts_a[-1].lower(), parts_b[-1].lower()
    if surname_a != surname_b:
        return False
    # Avoid collapsing unrelated people who share only a common surname when both have distinct given names
    if len(parts_a) >= 2 and len(parts_b) >= 2 and parts_a[0].lower() != parts_b[0].lower():
        return False
    return True
