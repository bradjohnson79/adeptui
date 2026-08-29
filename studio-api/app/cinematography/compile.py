"""Canonical camera compile + natural-language instruction."""

from __future__ import annotations

from typing import Any

from .catalog import (
    camera_focus_label,
    camera_lens_label,
    camera_shot_label,
    lighting_preset_label,
)


def _overlap(a_start: float, a_length: float, b_start: float, b_length: float) -> bool:
    a_end = float(a_start) + float(a_length)
    b_end = float(b_start) + float(b_length)
    return float(a_start) < b_end - 1e-9 and float(b_start) < a_end - 1e-9


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _clip_field(clip: Any, *names: str) -> Any:
    if clip is None:
        return None
    if isinstance(clip, dict):
        for name in names:
            if name in clip and clip[name] not in (None, ""):
                return clip[name]
        return None
    for name in names:
        value = getattr(clip, name, None)
        if value not in (None, ""):
            return value
    return None


def compile_canonical_camera(
    *,
    batch: Any = None,
    director_timeline: Any = None,
    window_start: float = 0.0,
    window_length: float | None = None,
) -> dict[str, Any] | None:
    """One canonical camera object for a batch window.

    Fields: motion, rig, text, shot_id, lens_id, focus_id, focus_name, lighting_id.
    Prefers overlapping legacy camera_clips; BatchClip motion/rig fill gaps.
    """
    planned = None
    if batch is not None:
        duration = getattr(batch, "duration", None)
        planned = getattr(duration, "plannedDuration", None) if duration is not None else None
        if planned is None and isinstance(batch, dict):
            planned = (batch.get("duration") or {}).get("plannedDuration")
    length = float(window_length if window_length is not None else (planned or 5.0))
    win_start = float(window_start)
    overlapping: list[Any] = []
    clips = []
    if director_timeline is not None:
        clips = list(getattr(director_timeline, "camera_clips", None) or [])
    for clip in clips:
        if _overlap(float(getattr(clip, "start", 0.0)), float(getattr(clip, "length", 0.0)), win_start, length):
            overlapping.append(clip)
    primary = None
    if overlapping:
        primary = sorted(overlapping, key=lambda c: (float(getattr(c, "start", 0.0)), -float(getattr(c, "length", 0.0))))[0]

    batch_cam = None
    instructions = []
    if batch is not None:
        instructions = list(getattr(batch, "cameraInstructions", None) or [])
        if not instructions and isinstance(batch, dict):
            instructions = list(batch.get("cameraInstructions") or [])
    for item in instructions:
        kind = _clip_field(item, "kind") or "camera"
        if kind == "camera":
            batch_cam = item
            break

    if primary is None and batch_cam is None:
        return None

    camera = {
        "motion": _first_nonempty(
            _clip_field(primary, "motion_id", "motion_type"),
            _clip_field(batch_cam, "motion_type", "motion_id"),
        ),
        "rig": _first_nonempty(
            _clip_field(primary, "rig_id", "rig"),
            _clip_field(batch_cam, "rig", "rig_id"),
        ),
        "text": _first_nonempty(_clip_field(primary, "text"), _clip_field(batch_cam, "text")) or "",
        "shot_id": _first_nonempty(
            _clip_field(primary, "shot_id"),
            _clip_field(batch_cam, "shot_id"),
        ),
        "lens_id": _first_nonempty(
            _clip_field(primary, "lens_id"),
            _clip_field(batch_cam, "lens_id"),
        ),
        "focus_id": _first_nonempty(
            _clip_field(primary, "focus_id"),
            _clip_field(batch_cam, "focus_id"),
        ),
        "focus_name": _first_nonempty(
            _clip_field(primary, "focus_name"),
            _clip_field(batch_cam, "focus_name"),
        ),
        "lighting_id": _first_nonempty(
            _clip_field(primary, "lighting_id"),
            _clip_field(batch_cam, "lighting_id"),
        ),
    }
    meaningful = [
        camera.get("motion"),
        camera.get("rig"),
        (camera.get("text") or "").strip(),
        camera.get("shot_id"),
        camera.get("lens_id"),
        camera.get("focus_id"),
        camera.get("focus_name"),
        camera.get("lighting_id"),
    ]
    if not any(meaningful):
        return None
    return camera


def camera_nl_instruction(camera: dict[str, Any] | None) -> str:
    """Compiled natural-language camera instruction for prompt-only generators."""
    if not camera:
        return ""
    bits: list[str] = []
    shot = camera.get("shot_id")
    if shot and shot != "auto":
        bits.append(camera_shot_label(shot))
    lens = camera.get("lens_id")
    if lens and str(lens) != "auto":
        bits.append(camera_lens_label(lens))
    motion = camera.get("motion")
    rig = camera.get("rig")
    if motion:
        motion_label = str(motion).replace("_", " ")
        if rig:
            bits.append(f"{motion_label} on {str(rig).replace('_', ' ')}")
        else:
            bits.append(motion_label)
    elif rig:
        bits.append(f"on {str(rig).replace('_', ' ')}")
    lighting = camera.get("lighting_id")
    if lighting and lighting != "auto":
        bits.append(f"lighting: {lighting_preset_label(lighting)}")
    focus = camera_focus_label(camera.get("focus_id"), camera.get("focus_name"))
    if focus:
        bits.append(f"focus on {focus}")
    text = str(camera.get("text") or "").strip()
    head = ", ".join(bit for bit in bits if bit)
    if head and text:
        return f"Camera: {head}; {text}"
    if head:
        return f"Camera: {head}"
    if text:
        return f"Camera: {text}"
    return ""
