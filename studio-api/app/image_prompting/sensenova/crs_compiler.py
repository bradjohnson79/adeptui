"""SenseNova-only native production Character Reference Sheet compiler.

Target layout is the Korri-style production CRS (structure only).
Do not copy Korri, Adept Chronicles branding, or any production character.
Flux/Qwen keep the simpler 4-view contract and must not use this compiler.
"""

from __future__ import annotations

from typing import Any

SENSENOVA_CRS_LAYOUT = "native_production_crs"
SENSENOVA_SHEET_KIND = "native_production_crs"

_LAYOUT_BANNER = (
    "LAYOUT EXEMPLAR RULES (binding): Copy only page structure, section density, "
    "and professional typography hierarchy. Do NOT reproduce Korri, Adept Chronicles "
    "logo or title, purple eyes, circuit tattoos, pigtails, or any exemplar identity. "
    "The Lab character described below is the only person on this sheet."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_sensenova_crs_prompt(
    *,
    name: str,
    description: str = "",
    visual_description: str = "",
    traits: dict[str, Any] | None = None,
    has_character_reference: bool = False,
    has_layout_exemplar: bool = False,
    extra: str = "",
) -> dict[str, str]:
    """Return {prompt, negative} for one native SenseNova production CRS."""
    traits = traits if isinstance(traits, dict) else {}
    who = _text(name) or "the character"
    look = _text(visual_description) or _text(description)
    face = _text(traits.get("face") or traits.get("face_features"))
    hair = _text(traits.get("hair") or traits.get("hair_style") or traits.get("hair_color"))
    eyes = _text(traits.get("eyes") or traits.get("eye_color"))
    skin = _text(traits.get("skin") or traits.get("skin_tone"))
    build = _text(traits.get("build") or traits.get("body") or traits.get("body_proportions"))
    outfit = _text(traits.get("outfit") or traits.get("wardrobe"))
    accessory = _text(traits.get("accessories") or traits.get("accessory") or traits.get("markings"))

    identity_bits = [look, face, hair, eyes, skin, build, outfit, accessory, _text(extra)]
    identity = ". ".join(bit for bit in identity_bits if bit)

    ref_block = ""
    if has_character_reference:
        ref_block = (
            "CHARACTER REFERENCE: A single character photo is attached. Reproduce that "
            "person's face, hair, skin, body, and wardrobe faithfully. The written "
            "profile is supplemental only. Do not invent a second person.\n"
        )
    layout_block = f"{_LAYOUT_BANNER}\n" if has_layout_exemplar else ""

    prompt = (
        f"{layout_block}{ref_block}"
        "Create ONE professional production Character Reference Sheet as a single composed page. "
        "This is a production design document, not a collage of unrelated people and not a 2x2 dump.\n"
        f"Character name: {who}.\n"
        f"Identity lock (same person in every panel): {identity or who}.\n"
        "Required page structure:\n"
        f"1. Header with the character name {who} in large type. Optional age/role only if supplied. "
        "No franchise logos. No Adept Chronicles branding.\n"
        "2. Full-body turnaround of the SAME character: FRONT, 3/4, SIDE, BACK. Neutral studio gray. "
        "Readable wardrobe, footwear, and proportions.\n"
        "3. Head-and-neck close-up only (minimal shoulders). Not a torso or waist-up portrait.\n"
        "4. Useful detail crops: eyes, hair, skin, and one distinctive accessory or marking.\n"
        "5. Short notes / wardrobe / details text only if lettering stays readable. Prefer accurate "
        "labels over decorative gibberish. If text would be illegible, use clean section titles only.\n"
        "Preserve face, hairstyle, hair color, eye color, skin tone, body, outfit, accessories, "
        "and footwear across every panel. One character only."
    )
    negative = (
        "multiple different people, identity drift, Korri, Adept Chronicles logo, "
        "circuit-arm tattoo copy, four unrelated portraits, unlabeled 2x2 dump, "
        "single cinematic beauty shot, extra limbs, extra characters, watermark, "
        "illegible dense gibberish text, 3/4 omitted, missing back view, "
        "waist-up close-up, full-body used as the close-up"
    )
    return {"prompt": prompt, "negative": negative, "layout": SENSENOVA_CRS_LAYOUT}
