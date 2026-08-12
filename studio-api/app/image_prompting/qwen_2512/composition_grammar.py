"""Composition and staging blocks for Qwen-Image-2512 prompts."""

from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def compile_pose_block(
    composition: Mapping[str, Any] | None,
    motion: Mapping[str, Any] | None,
    performance: Mapping[str, Any] | None,
) -> str:
    composition = composition or {}
    motion = motion or {}
    performance = performance or {}
    parts = [
        _first_non_empty(composition.get("pose"), motion.get("defaultStandingPosture")),
        _first_non_empty(composition.get("gesture"), motion.get("handGestures")),
        _first_non_empty(composition.get("head"), motion.get("headMovement")),
        _first_non_empty(composition.get("expression"), performance.get("defaultFacialTension")),
        _first_non_empty(composition.get("energy"), motion.get("energyLevel")),
    ]
    return "; ".join(part for part in parts if part)


def compile_composition_block(composition: Mapping[str, Any] | None) -> str:
    composition = composition or {}
    ordered_keys = (
        "shot_type",
        "framing",
        "camera_angle",
        "lens",
        "distance",
        "orientation",
        "focus",
        "subject_count",
    )
    parts = []
    for key in ordered_keys:
        text = _text(composition.get(key))
        if text:
            parts.append(f"{key.replace('_', ' ')}: {text}")
    # Amendment 2: when full_body composition is requested, emit a canonical
    # full-body casting composition block so any caller (not just visual_sheet)
    # enforces the rule. This makes the requirement structural, not prompt-prose.
    if composition.get("full_body"):
        full_body_block = (
            "full body casting composition: full-body character casting image; "
            "show the complete character from head to feet; "
            "entire body visible inside the frame; standing or naturally posed; "
            "clear readable silhouette; character centered with enough space around the body; "
            "do not crop the head, arms, hands, legs, or feet; "
            "no close-up, no headshot, no bust portrait, no waist-up framing"
        )
        parts.append(full_body_block)
    return "; ".join(parts) if parts else "Single-subject composition with the character clearly readable."


def compile_environment_block(
    composition: Mapping[str, Any] | None,
    style_profile: Mapping[str, Any] | None,
) -> str:
    composition = composition or {}
    style_profile = style_profile or {}
    parts = [
        _text(composition.get("environment")),
        _text(composition.get("background")),
        _text(composition.get("lighting")),
        _text(style_profile.get("lighting")),
    ]
    deduped: list[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    return "; ".join(deduped) if deduped else "Clean readable environment with lighting that supports facial clarity and continuity."
