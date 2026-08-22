"""FLUX CRS single-view prompt — one character, one camera, one image.

FLUX.1 uses a T5 caption, not Qwen's numbered 13-block package. Negatives are
appended into the positive caption by ``build_flux_txt2img_workflow``; this
module still returns a separate negative string for job metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...image_prompting.qwen_2512.identity_lock import extract_character_blueprint

FLUX_CRS_PROMPT_FAMILY = "flux_crs_single_view"
FLUX_CRS_MODEL_KEY = "flux-kontext"

# Do not put leftover four-panel / turnaround / character-sheet tokens here.
# Law-view jobs are scanned for those strings even inside negatives. Required
# anti-collage phrases live in LAW_VIEW_SINGLE_FIGURE_RULES and are appended.
FLUX_CRS_NEGATIVE = (
    "multiple people, extra person, duplicate character, second figure, "
    "crowd, inset portrait, contact sheet, split frame, text, labels, "
    "title, watermark, logo"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _join(parts: Sequence[str]) -> str:
    return ", ".join(part for part in parts if _text(part))


def _identity_clause(blueprint: Mapping[str, Any]) -> str:
    bits = [
        _text(blueprint.get("name")) or "the character",
        _text(blueprint.get("species_or_type")),
        _text(blueprint.get("age")),
        _text(blueprint.get("gender_presentation")),
        _text(blueprint.get("body_type")),
        _text(blueprint.get("height_description")),
        _text(blueprint.get("skin_tone")),
        _text(blueprint.get("hair_style")),
        _text(blueprint.get("hair_color")),
        _text(blueprint.get("eye_color")),
        _text(blueprint.get("ears")),
        _text(blueprint.get("visual_description")),
        _join(list(blueprint.get("distinctives") or [])),
        _text(blueprint.get("wardrobe_description")),
        _text(blueprint.get("wardrobe_colors")),
        _text(blueprint.get("wardrobe_accessories")),
    ]
    return _join(bits)


@dataclass(frozen=True)
class FluxCrsPromptPackage:
    prompt: str
    negative_prompt: str
    prompt_family: str
    model_key: str
    validation: dict[str, Any]
    character_name: str


def compile_flux_crs_single_view(
    profile: Mapping[str, Any],
    *,
    prompt_goal: str = "",
    view_instruction: str = "",
    extra_negative_constraints: Sequence[str] | None = None,
    full_body: bool = True,
) -> FluxCrsPromptPackage:
    """Natural-language CRS tile caption for FLUX. Not a Qwen block dump."""
    blueprint = extract_character_blueprint(profile)
    name = _text(blueprint.get("name")) or "the character"
    identity = _identity_clause(blueprint)
    camera = _text(view_instruction) or _text(prompt_goal) or "front-facing, one camera only"
    body = (
        "entire body visible, head to feet in frame, standing alone"
        if full_body
        else "head and shoulders only, one face, no extra figures"
    )
    prompt = (
        f"Photograph of exactly one person, {name}, alone. "
        f"{identity}. "
        f"{camera}. "
        f"{body}. "
        "Neutral simple studio background. One camera, this view only. "
        "one person only, one figure, no other people, no grid, no collage, "
        "no turnaround sheet, no multiple poses in one image. "
        "No duplicate, no alternate views, no panels, no inset, no text."
    )
    extra = ", ".join(_text(item) for item in (extra_negative_constraints or []) if _text(item))
    negative = FLUX_CRS_NEGATIVE if not extra else f"{FLUX_CRS_NEGATIVE}, {extra}"
    return FluxCrsPromptPackage(
        prompt=" ".join(prompt.split()),
        negative_prompt=negative,
        prompt_family=FLUX_CRS_PROMPT_FAMILY,
        model_key=FLUX_CRS_MODEL_KEY,
        validation={"ok": True, "family": "flux", "layout": "single_subject"},
        character_name=name,
    )
