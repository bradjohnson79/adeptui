"""Automatic review cadence from existing Timeline facts. No second VLM."""

from __future__ import annotations

from typing import Any

from .contracts import CoDirectorContinuityPolicy, ReviewCadence

_ACTION_MARKERS = (
    "fight",
    "punch",
    "run",
    "chase",
    "sprint",
    "dodge",
    "whip pan",
    "crash",
    "explode",
    "stunt",
    "choreograph",
    "action",
    "walk",
    "walking",
    "turn",
    "turning",
)
_CAMERA_MARKERS = (
    "dolly",
    "tracking shot",
    "handheld",
    "orbit",
    "crane",
    "steadicam",
    "push in",
    "pull out",
)
_STATIC_MARKERS = (
    "dialogue",
    "talks",
    "says",
    "conversation",
    "sits",
    "sitting",
    "establish",
    "establishing",
    "wide still",
)


def resolve_cadence(
    policy: CoDirectorContinuityPolicy,
    *,
    prompt: str = "",
    camera_motion: str = "",
    character_count: int = 0,
    has_movement_layers: bool = False,
) -> ReviewCadence:
    if policy.reviewCadence != "automatic":
        return policy.reviewCadence
    blob = f"{prompt} {camera_motion}".lower()
    action_like = any(m in blob for m in _ACTION_MARKERS) or any(m in blob for m in _CAMERA_MARKERS)
    if has_movement_layers or character_count >= 2:
        action_like = True
    if action_like:
        return "interval_3"
    if any(m in blob for m in _STATIC_MARKERS):
        return "interval_5"
    return "every_batch"


def window_seconds(cadence: ReviewCadence, generated_duration: float | None) -> float:
    actual = float(generated_duration or 5.0)
    if cadence == "interval_3":
        return min(3.0, actual)
    if cadence == "interval_5":
        return min(5.0, actual)
    return actual


def intended_text_from_batch(batch: Any) -> str:
    parts: list[str] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        for key in ("userDirection", "productionPrompt", "text", "dialogue"):
            value = getattr(seg, key, None)
            if value:
                parts.append(str(value).strip())
    return "\n".join(p for p in parts if p)
