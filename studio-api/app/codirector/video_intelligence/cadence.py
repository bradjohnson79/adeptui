"""Automatic review cadence from existing Timeline facts. No second VLM.

Full-clip Continuity: when reviewCadence is "automatic", Timeline Co-Director
reviews the entire approved shot (every_batch / full duration, typically <= ~15s).
Creators who want a rolling end-window can still pick interval_3 / interval_5.
"""

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
    generated_duration: float | None = None,
) -> ReviewCadence:
    """Resolve effective cadence.

    Explicit creator choices (interval_3 / interval_5 / every_batch) win.
    Automatic always uses full-clip every_batch so early/mid events in ~15s
    shots survive into the next TemporalContinuityPacket (Continuity Challenge).
    """
    if policy.reviewCadence != "automatic":
        return policy.reviewCadence
    # Keep markers imported/available for diagnostics / future optional heuristics.
    _ = (prompt, camera_motion, character_count, has_movement_layers, generated_duration,
         _ACTION_MARKERS, _CAMERA_MARKERS, _STATIC_MARKERS)
    return "every_batch"


def review_window_kind(cadence: ReviewCadence) -> str:
    if cadence == "interval_3":
        return "tail_3"
    if cadence == "interval_5":
        return "tail_5"
    return "full_clip"


def window_seconds(cadence: ReviewCadence, generated_duration: float | None) -> float:
    actual = float(generated_duration or 5.0)
    if cadence == "interval_3":
        return min(3.0, actual)
    if cadence == "interval_5":
        return min(5.0, actual)
    # every_batch (and automatic -> every_batch): full media length; no 5s cap.
    return actual


def intended_text_from_batch(batch: Any) -> str:
    parts: list[str] = []
    for seg in getattr(batch, "promptSegments", None) or []:
        for key in ("userDirection", "productionPrompt", "text", "dialogue"):
            value = getattr(seg, key, None)
            if value:
                parts.append(str(value).strip())
    return "\n".join(p for p in parts if p)
