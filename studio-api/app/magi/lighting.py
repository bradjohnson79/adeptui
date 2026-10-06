"""MAGI lighting looks.

Lighting is a clip-grade parameter set on the existing finishing color path.
Preview is non-destructive. Final Render bakes the same parameters with FFmpeg.
"""

from __future__ import annotations

from typing import Any

from .finishing import finishing_of
from .sequence.store import get_sequence, save_sequence

LIGHTING_KEYS = ("brightness", "highlights", "shadows", "temperature")

LIGHTING_PRESETS: dict[str, dict[str, float]] = {
    "none": {},
    "soft_bright": {"brightness": 0.08, "shadows": 0.06, "highlights": -0.02, "temperature": 0.02},
    "warm": {"temperature": 0.14, "highlights": 0.04, "shadows": -0.02},
    "cool": {"temperature": -0.14, "shadows": -0.04, "highlights": 0.02},
    "high_contrast": {"highlights": 0.12, "shadows": -0.14, "contrast": 0.18},
    "low_light_lift": {"brightness": 0.06, "shadows": 0.14, "highlights": -0.04},
}

PRESET_NAMES = {
    "none": "none",
    "soft bright": "soft_bright",
    "soft-bright": "soft_bright",
    "soft_bright": "soft_bright",
    "warm": "warm",
    "cool": "cool",
    "high contrast": "high_contrast",
    "high-contrast": "high_contrast",
    "high_contrast": "high_contrast",
    "low light lift": "low_light_lift",
    "low-light-lift": "low_light_lift",
    "low_light_lift": "low_light_lift",
}


def canonical_lighting_preset(value: str) -> str:
    key = " ".join(str(value or "").strip().lower().replace("_", " ").split())
    if key in PRESET_NAMES:
        return PRESET_NAMES[key]
    hyphen = key.replace(" ", "-")
    return PRESET_NAMES.get(hyphen, "")


def picture_clip_ids(sequence: dict[str, Any], clip_id: str | None = None) -> list[str]:
    """One named clip, or every picture clip when the request is for the edit."""
    wanted = str(clip_id or "").strip()
    clips = list(sequence.get("clips") or [])
    if wanted:
        if any(str(clip.get("id") or "") == wanted for clip in clips):
            return [wanted]
        raise ValueError("That clip is not on this MAGI edit.")
    tracks = {str(track.get("id")): track for track in (sequence.get("tracks") or [])}
    ids = [
        str(clip["id"])
        for clip in clips
        if clip.get("id")
        and str((tracks.get(str(clip.get("trackId"))) or {}).get("kind") or "") in {"video", "image"}
    ]
    if ids:
        return ids
    raise ValueError("MAGI has no clip to light.")


def picture_clip_id(sequence: dict[str, Any], clip_id: str | None = None) -> str:
    return picture_clip_ids(sequence, clip_id)[0]


def merge_lighting(
    project_id: str,
    *,
    clip_id: str | None = None,
    preset_id: str | None = None,
    params: dict[str, Any] | None = None,
    deltas: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sequence = get_sequence(project_id)
    targets = picture_clip_ids(sequence, clip_id)
    finishing = finishing_of(sequence)
    grades = dict(finishing.get("clipGrades") or {})
    applied_preset = ""
    current_params: dict[str, Any] = {}
    for target in targets:
        current = dict(grades.get(target) or {})
        current_params = dict(current.get("params") or {})
        applied_preset = str(current.get("lightingPresetId") or "")
        if preset_id is not None:
            canonical = canonical_lighting_preset(preset_id)
            if preset_id and not canonical:
                raise ValueError(f"Unknown lighting preset '{preset_id}'.")
            applied_preset = "" if canonical == "none" else canonical
            for key in LIGHTING_KEYS:
                current_params.pop(key, None)
            current_params.update(LIGHTING_PRESETS.get(canonical) or {})
        for key, value in (params or {}).items():
            if key in LIGHTING_KEYS or key == "contrast":
                current_params[key] = float(value)
        for key, value in (deltas or {}).items():
            if key in LIGHTING_KEYS or key == "contrast":
                current_params[key] = float(current_params.get(key) or 0) + float(value)
        current["presetId"] = str(current.get("presetId") or "")
        current["lightingPresetId"] = applied_preset
        current["params"] = current_params
        grades[target] = current
    target = targets[0]
    finishing["clipGrades"] = grades
    sequence["finishing"] = finishing
    save_sequence(project_id, sequence)
    return {
        "ok": True,
        "liveOnly": True,
        "clipId": target,
        "lightingPresetId": applied_preset,
        "params": current_params,
    }
