"""Load locked character canon packs (Korri v1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_CANON_DIR = _REPO / "config" / "character-canon"


def load_canon(slug: str = "korri", version: str = "v1") -> dict[str, Any]:
    path = _CANON_DIR / f"{slug}.{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Canon pack not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Canon pack must be an object")
    return data


def korri_v1() -> dict[str, Any]:
    return load_canon("korri", "v1")


def apply_korri_canon_to_create_defaults() -> dict[str, Any]:
    c = korri_v1()
    ident = c.get("identity") or {}
    appearance = c.get("appearance") or {}
    hair = appearance.get("hair") or {}
    skin = appearance.get("skin") or {}
    return {
        "name": ident.get("name") or "Korri",
        "slug": ident.get("slug") or "korri",
        "role": ident.get("role") or "",
        "apparent_age": str(ident.get("age") or "18"),
        "species_or_type": ident.get("speciesOrType") or "human_sun_sprite_hybrid",
        "height_description": ident.get("heightDescription") or "",
        "body_type": ident.get("bodyType") or "",
        "skin": {
            "skin_tone": skin.get("skin_tone") or "pale",
            "texture": skin.get("texture") or "",
            "tattoos": skin.get("tattoos") or "",
            "closeup_preservation_notes": "Preserve pointed ears, purple eyes, pale tone, wooden earrings",
        },
        "hair": {
            "primary_color": hair.get("primary_color") or "black",
            "canonical_style": hair.get("canonical_style") or "twin ponytails",
            "length": hair.get("length") or "long",
            "continuity_restrictions": hair.get("continuity_restrictions") or "",
            "alternate_styles": [],
        },
        "personality": c.get("personality") or {},
        "motion": c.get("motion") or {},
        "performance": c.get("performance") or {},
        "emotion": {
            "baseline": "mischievous / irreverent",
            "range": "wide — teasing to fierce loyalty to rare vulnerability",
            "sarcasmBehavior": "Default delivery; dry teasing",
            "angerBehavior": "Sharp, quick, still light-footed",
            "vulnerabilityBehavior": "Energy drops; rare stillness",
            "intensityLimits": "Avoid melodrama; keep Sass Queen voice",
            "triggers": ["ceremony", "being talked down to", "threats to sister"],
        },
        "relationships": c.get("relationships") or [],
        "continuity": {
            "locked_features": c.get("lockedTraits") or [],
            "forbid_invention": c.get("forbidInvention") or [],
            "notes": "Korri v1 canon — character sheet is authoritative",
        },
        "wardrobe": c.get("wardrobe") or {},
    }
