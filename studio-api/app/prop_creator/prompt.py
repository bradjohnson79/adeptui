"""Canonical PropEntity → Prop Generation Prompt compiler.

Generators must not independently reinterpret the profile. Base facts
(name, description, style) are compiled once, then product-identity
view instructions are appended.
"""

from __future__ import annotations

from typing import Any

from ..spatial_map.ers_contracts import PropEntity

STYLE_LABELS: dict[str, str] = {
    "live_action": "live action",
    "documentary_realism": "photorealistic",
    "anime": "anime",
    "realistic_anime": "realistic anime",
    "stylized_3d_animation": "stylized 3D animation",
    "stop_motion": "stop motion",
    "claymation": "claymation",
    "graphic_novel": "comic / graphic novel",
    "watercolor": "watercolor",
    "oil_painting": "oil painting",
    "cartoon": "cartoon",
    "concept_art": "concept art",
}

IDENTITY_VIEW = (
    "Single complete prop identity image, the full prop centered and clearly visible, "
    "minimal occlusion, neutral simple presentation, production-reference quality. "
    "No character holding the prop, no environment scene, no four-view sheet, "
    "no collage, no extra props, no unreadable text unless lettering is part of the prop."
)

NEGATIVE_PROMPT = (
    "character holding the prop, person, hands, environment scene, landscape, "
    "four-view sheet, collage, grid, multiple views, watermark, low quality, "
    "cropped, truncated, busy background"
)


def compile_prop_prompt(prop: PropEntity) -> dict[str, Any]:
    name = (prop.display_label or prop.tag or "prop").strip()
    description = (prop.description or prop.notes or "").strip()
    style_key = (prop.visual_style or "").strip()
    style_label = STYLE_LABELS.get(style_key, style_key.replace("_", " ").strip())

    facts: list[str] = [f"Prop: {name}."]
    if description:
        facts.append(description.rstrip(".") + ".")
    if style_label:
        facts.append(f"Image style: {style_label}.")
    facts.append(IDENTITY_VIEW)

    prompt = " ".join(facts)
    return {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "name": name,
        "description": description,
        "visual_style": style_key,
        "style_label": style_label,
    }
