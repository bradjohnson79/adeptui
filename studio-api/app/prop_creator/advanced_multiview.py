"""Prop Creator Advanced — Qwen Edit multiview (prop orthographic angles).

Reuses Character Production engine (qwen_image_edit_2509) with prop-specific
viewpoint prompts. Preserve identity / materials / markings; change viewpoint only.
Does not invent a second prop registry. One PropEntity / one %PropName.
"""

from __future__ import annotations

from typing import Any

from ..character_identity.multiview_engine import (
    ENGINE_QWEN_EDIT_2509,
    PRODUCTION_ENGINE,
    QWEN_EDIT_FAMILY,
    QWEN_EDIT_WEIGHTS,
    QWEN_EDIT_WORKFLOW_KEY,
    assert_can_generate,
    production_engine_status,
)
from ..spatial_map.ers_contracts import PROP_ADVANCED_ANGLE_KEYS, PropAngleSlot

PROP_ANGLE_KEYS = PROP_ADVANCED_ANGLE_KEYS
# Additional views are optional enrichment. Primary is the only required identity.
OPTIONAL_VIEWS = ("front", "back", "left", "right", "top", "bottom", "hero")
# Legacy alias — no longer a hard approval / PRS gate.
REQUIRED_ANGLES = OPTIONAL_VIEWS

CAMERA_ROLES = {
    "front": "FRONT",
    "back": "BACK",
    "left": "LEFT",
    "right": "RIGHT",
    "top": "TOP",
    "bottom": "BOTTOM",
    "hero": "HERO",
}

# Viewpoint-only prompts — exact same prop identity; no redesign; single view.
PROP_ANGLE_PROMPTS = {
    "front": (
        "Show this exact same prop as one clear front orthographic view, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "back": (
        "Show this exact same prop as one clear back orthographic view facing away, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "left": (
        "Show this exact same prop as one clear left-side orthographic profile view, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "right": (
        "Show this exact same prop as one clear right-side orthographic profile view, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "top": (
        "Show this exact same prop as one clear top orthographic view looking straight down, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "bottom": (
        "Show this exact same prop as one clear bottom orthographic view looking straight up, "
        "centered, same materials colors markings proportions and silhouette, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it, single view only."
    ),
    "hero": (
        "Show this exact same prop as one dramatic hero three-quarter beauty shot, "
        "same materials colors markings proportions and silhouette, slight cinematic angle, "
        "neutral studio background, no collage, no text, no extra props, "
        "no character holding it unless scale requires a subtle silhouette, single view only."
    ),
}

PROP_ANGLE_NEGATIVE = (
    "redesign, different prop, extra props, environment scene, landscape, "
    "character holding the prop, person, hands, collage, contact sheet, "
    "four panel, split screen, grid, multiple views, watermark, logo, text, caption, "
    "blurry, low quality"
)


def empty_angle(key: str = "") -> PropAngleSlot:
    return PropAngleSlot(
        key=key,
        status="idle",
        asset_id=None,
        approved=False,
        job_id=None,
        seed=None,
        error="",
        source_primary_asset_id=None,
        engine=PRODUCTION_ENGINE,
        workflow_key=QWEN_EDIT_WORKFLOW_KEY,
        progress=None,
    )


def ensure_angles_map(raw: dict[str, Any] | None, *, hero_optional: bool = True) -> dict[str, PropAngleSlot]:
    # Always keep hero slot present; hero_optional only affects approval gates later.
    _ = hero_optional
    out: dict[str, PropAngleSlot] = {}
    src = raw or {}
    for key in PROP_ANGLE_KEYS:
        existing = src.get(key)
        if isinstance(existing, PropAngleSlot):
            slot = existing.model_copy(deep=True)
            slot.key = key
            out[key] = slot
        elif isinstance(existing, dict):
            slot = empty_angle(key)
            slot = PropAngleSlot.model_validate({**slot.model_dump(), **existing, "key": key})
            out[key] = slot
        else:
            out[key] = empty_angle(key)
    return out


def angle_prompt(angle: str, *, prop_name: str = "", identity_brief: str = "") -> str:
    if angle not in PROP_ANGLE_PROMPTS:
        raise ValueError(f"Unknown prop angle: {angle}")
    parts = [PROP_ANGLE_PROMPTS[angle]]
    if prop_name.strip():
        parts.insert(0, f"Prop identity: {prop_name.strip()}.")
    if identity_brief.strip():
        parts.append(f"Identity lock from approved primary: {identity_brief.strip()}")
    return " ".join(parts)


def engine_payload() -> dict[str, Any]:
    status = production_engine_status(force=False)
    return {
        "engine": ENGINE_QWEN_EDIT_2509,
        "productionEngine": PRODUCTION_ENGINE,
        "family": QWEN_EDIT_FAMILY,
        "weightsId": QWEN_EDIT_WEIGHTS,
        "workflowKey": QWEN_EDIT_WORKFLOW_KEY,
        "angles": list(PROP_ANGLE_KEYS),
        "requiredAngles": [],
        "requiredViews": ["primary"],
        "optionalViews": list(OPTIONAL_VIEWS),
        "runtime": status,
    }


__all__ = [
    "PROP_ANGLE_KEYS",
    "OPTIONAL_VIEWS",
    "REQUIRED_ANGLES",
    "CAMERA_ROLES",
    "PROP_ANGLE_PROMPTS",
    "PROP_ANGLE_NEGATIVE",
    "empty_angle",
    "ensure_angles_map",
    "angle_prompt",
    "engine_payload",
    "assert_can_generate",
    "production_engine_status",
    "QWEN_EDIT_FAMILY",
    "QWEN_EDIT_WORKFLOW_KEY",
    "QWEN_EDIT_WEIGHTS",
    "ENGINE_QWEN_EDIT_2509",
    "PRODUCTION_ENGINE",
]
