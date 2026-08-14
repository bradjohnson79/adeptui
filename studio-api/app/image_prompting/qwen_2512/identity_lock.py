"""Identity normalization and lock enforcement for Qwen-Image-2512."""

from __future__ import annotations

from typing import Any, Mapping

KORRI_REQUIRED_TRAITS: tuple[str, ...] = (
    "pale skin",
    "purple eyes",
    "black twin ponytails",
    "elongated Sun Sprite Elf ears",
    "petite athletic build",
    "handmade black clothing",
    "wooden accessories",
    "light-circuitry markings (not tattoos)",
)

KORRI_FORBIDDEN_TRAITS: tuple[str, ...] = (
    "blonde hair",
    "blue eyes",
    "aqua eyes",
    "human ears",
    "rounded ears",
    "Anadriya resemblance",
    "Anadriya wardrobe",
)

_FORBIDDEN_TEXT_MATCHES: dict[str, tuple[str, ...]] = {
    "blonde hair": ("blonde hair", "blond hair", "golden hair"),
    "blue eyes": ("blue eyes", "aqua eyes", "cyan eyes"),
    "human ears": ("human ears", "rounded ears", "round ears"),
    "Anadriya resemblance": ("anadriya", "anadriya face", "anadriya styling"),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_markings(raw: str) -> str:
    lowered = raw.lower()
    if "circuit" in lowered or "light" in lowered or "tattoo" in lowered:
        return "light-circuitry markings (not tattoos)"
    return raw


def _normalize_trait(raw: str) -> str:
    text = _text(raw)
    lowered = text.lower()
    if not text:
        return ""
    if "circuit" in lowered or "light" in lowered or "tattoo" in lowered:
        return "light-circuitry markings (not tattoos)"
    if "ear" in lowered and ("elf" in lowered or "pointed" in lowered):
        return "elongated Sun Sprite Elf ears"
    if "black" in lowered and "twin" in lowered and "ponytail" in lowered:
        return "black twin ponytails"
    if "handmade" in lowered and "black" in lowered and ("wardrobe" in lowered or "cloth" in lowered):
        return "handmade black clothing"
    return text


def _split_distinctives(distinctives: Any) -> list[str]:
    if isinstance(distinctives, list):
        items = [_normalize_trait(item) for item in distinctives if _text(item)]
        return list(dict.fromkeys(items))
    if _text(distinctives):
        return [_normalize_trait(distinctives)]
    return []


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def extract_character_blueprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize canon or profile-shaped payloads into one compiler blueprint."""
    identity = payload.get("identity") if isinstance(payload.get("identity"), Mapping) else payload
    appearance = payload.get("appearance") if isinstance(payload.get("appearance"), Mapping) else {}
    wardrobe = payload.get("wardrobe") if isinstance(payload.get("wardrobe"), Mapping) else {}
    personality = payload.get("personality") if isinstance(payload.get("personality"), Mapping) else {}
    motion = payload.get("motion") if isinstance(payload.get("motion"), Mapping) else {}
    performance = payload.get("performance") if isinstance(payload.get("performance"), Mapping) else {}
    continuity = payload.get("continuity") if isinstance(payload.get("continuity"), Mapping) else {}

    hair = appearance.get("hair") if isinstance(appearance.get("hair"), Mapping) else payload.get("hair") or {}
    skin = appearance.get("skin") if isinstance(appearance.get("skin"), Mapping) else payload.get("skin") or {}
    relationships = payload.get("relationships") or []

    distinctives = _split_distinctives(appearance.get("distinctives") or payload.get("distinctives") or [])
    markings = _normalize_trait(_text(skin.get("tattoos") or payload.get("markings") or ""))
    if markings:
        distinctives.append(markings)

    locked_traits = payload.get("lockedTraits") or payload.get("locked_traits") or continuity.get("locked_features") or []
    forbid_invention = (
        payload.get("forbidInvention") or payload.get("forbid_invention") or continuity.get("forbid_invention") or []
    )
    wardrobe_forbidden = wardrobe.get("forbidSilentReplace") or payload.get("wardrobe_forbidden") or []

    body_type = _text(identity.get("bodyType") or payload.get("body_type"))
    if "petite" in body_type.lower() and "athletic" in body_type.lower():
        normalized_body_type = "petite athletic build"
    else:
        normalized_body_type = body_type

    ears = _text(appearance.get("ears") or payload.get("ears") or "")
    if "elf" in ears.lower():
        ears = "elongated Sun Sprite Elf ears"

    return {
        "canon_version": _text(payload.get("canonVersion") or payload.get("canon_version")),
        "name": _text(identity.get("name") or payload.get("name") or "Character"),
        "slug": _text(identity.get("slug") or payload.get("slug")),
        "role": _text(identity.get("role") or payload.get("role")),
        "age": _text(identity.get("age") or payload.get("apparent_age")),
        "species_or_type": _text(identity.get("speciesOrType") or payload.get("species_or_type")),
        "bio": _text(payload.get("description")),
        "visual_description": _text(payload.get("visual_description")),
        "visual_style": _text(payload.get("visual_style")),
        "gender_presentation": _text(
            identity.get("genderPresentation") or payload.get("gender_presentation")
        ),
        "height_description": _text(identity.get("heightDescription") or payload.get("height_description")),
        "body_type": normalized_body_type,
        "hair_color": _text(hair.get("primary_color") or payload.get("hair_color")),
        "hair_style": _text(hair.get("canonical_style") or payload.get("hair_style")),
        "hair_length": _text(hair.get("length") or payload.get("hair_length")),
        "hair_continuity": _text(hair.get("continuity_restrictions") or payload.get("hair_continuity")),
        "eye_color": _text(appearance.get("eyes") or payload.get("eyes") or payload.get("eye_color")),
        "skin_tone": _text(skin.get("skin_tone") or payload.get("skin_tone")),
        "skin_texture": _text(skin.get("texture") or payload.get("skin_texture")),
        "ears": ears,
        "distinctives": _unique(distinctives),
        "wardrobe_name": _text(wardrobe.get("name") or payload.get("wardrobe_name")),
        "wardrobe_description": _text(wardrobe.get("description") or payload.get("wardrobe_description")),
        "wardrobe_materials": _text(wardrobe.get("materials") or payload.get("wardrobe_materials")),
        "wardrobe_colors": _text(wardrobe.get("colors") or payload.get("wardrobe_colors")),
        "wardrobe_footwear": _text(wardrobe.get("footwear") or payload.get("wardrobe_footwear")),
        "wardrobe_accessories": _text(wardrobe.get("accessories") or payload.get("wardrobe_accessories")),
        "wardrobe_forbidden": [_text(item) for item in wardrobe_forbidden if _text(item)],
        "personality": dict(personality),
        "motion": dict(motion),
        "performance": dict(performance),
        "relationships": [item for item in relationships if isinstance(item, Mapping)],
        "locked_traits": [_normalize_trait(item) for item in locked_traits if _text(item)],
        "forbid_invention": [_text(item) for item in forbid_invention if _text(item)],
    }


def _looks_like_korri(blueprint: Mapping[str, Any]) -> bool:
    name = _text(blueprint.get("name")).lower()
    slug = _text(blueprint.get("slug")).lower()
    return name == "korri" or slug == "korri"


def build_identity_anchor(blueprint: Mapping[str, Any]) -> str:
    parts = [
        _text(blueprint.get("name")),
        _text(blueprint.get("role")),
        _text(blueprint.get("gender_presentation")),
        _text(blueprint.get("species_or_type")).replace("_", " "),
        _text(blueprint.get("age")),
        _text(blueprint.get("height_description")),
        _text(blueprint.get("body_type")),
    ]
    anchor = "; ".join(part for part in parts if part)
    bio = _text(blueprint.get("bio"))
    visual = _text(blueprint.get("visual_description"))
    brief: list[str] = []
    if bio:
        brief.append(f"personality/bio: {bio}")
    if visual:
        brief.append(f"visual appearance: {visual}")
    if brief:
        anchor = (anchor + ". " + ". ".join(brief) + ".") if anchor else ". ".join(brief) + "."
    return anchor


def build_identity_lock(blueprint_or_payload: Mapping[str, Any]) -> dict[str, Any]:
    blueprint = extract_character_blueprint(blueprint_or_payload)
    traits = [
        f"{blueprint['hair_color']} {blueprint['hair_style']}".strip(),
        f"{blueprint['eye_color']} eyes".strip(),
        f"{blueprint['skin_tone']} skin".strip(),
        blueprint.get("ears") or "",
        blueprint.get("body_type") or "",
        "handmade black clothing" if "black" in blueprint.get("wardrobe_description", "").lower() else "",
        "wooden accessories"
        if "wood" in blueprint.get("wardrobe_accessories", "").lower()
        or any("wood" in item.lower() for item in blueprint.get("distinctives", []))
        else "",
        "light-circuitry markings (not tattoos)"
        if any("light-circuitry" in item.lower() for item in blueprint.get("distinctives", []))
        else "",
    ]
    traits.extend(blueprint.get("locked_traits", []))
    if _looks_like_korri(blueprint):
        traits.extend(KORRI_REQUIRED_TRAITS)

    forbidden = list(blueprint.get("forbid_invention", []))
    forbidden.extend(blueprint.get("wardrobe_forbidden", []))
    if _looks_like_korri(blueprint):
        forbidden.extend(KORRI_FORBIDDEN_TRAITS)

    return {
        "character_name": blueprint.get("name") or "Character",
        "is_korri": _looks_like_korri(blueprint),
        "anchor": build_identity_anchor(blueprint),
        "locked_traits": _unique([trait for trait in traits if _text(trait)]),
        "forbidden_traits": _unique([item for item in forbidden if _text(item)]),
        "markings_language": "light-circuitry markings (not tattoos)",
    }


def detect_identity_violations(text: str, blueprint_or_lock: Mapping[str, Any]) -> list[str]:
    """Return explicit identity drift findings for production-time validation."""
    lowered = _text(text).lower()
    lock = (
        blueprint_or_lock
        if "locked_traits" in blueprint_or_lock and "forbidden_traits" in blueprint_or_lock
        else build_identity_lock(blueprint_or_lock)
    )
    findings: list[str] = []

    for label, candidates in _FORBIDDEN_TEXT_MATCHES.items():
        if any(candidate in lowered for candidate in candidates):
            findings.append(f"forbidden trait present: {label}")

    if lock.get("is_korri"):
        required_checks = {
            "black twin ponytails": ("black", "twin ponytail"),
            "purple eyes": ("purple eyes",),
            "pale skin": ("pale skin",),
            "elongated Sun Sprite Elf ears": ("sun sprite elf ears", "elongated"),
            "light-circuitry markings (not tattoos)": ("light-circuitry markings", "not tattoos"),
        }
        for label, candidates in required_checks.items():
            if not any(candidate in lowered for candidate in candidates):
                findings.append(f"missing locked trait: {label}")

    if "tattoo" in lowered and "not tattoos" not in lowered:
        findings.append("incorrect markings language: use light-circuitry markings (not tattoos)")

    return findings
