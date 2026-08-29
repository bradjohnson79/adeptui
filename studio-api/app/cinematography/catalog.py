"""Cinematography IDs and labels for Timeline camera compile.

Copied from studio-web/src/cinematography (types.ts + labels.ts) so Timeline
generation twins FE field names and does not import Spatial Map UI modules.
"""

from __future__ import annotations

from typing import Any

CAMERA_FOCUS_ENVIRONMENT_ID = "environment"

CAMERA_SHOT_IDS: tuple[str, ...] = (
    "auto",
    "wide",
    "medium_wide",
    "medium",
    "medium_close",
    "close_up",
    "extreme_close",
)

CAMERA_LENS_IDS: tuple[str, ...] = (
    "auto",
    "18",
    "24",
    "28",
    "35",
    "40",
    "50",
    "65",
    "85",
    "100",
    "135",
    "fisheye",
)

LIGHTING_PRESET_IDS: tuple[str, ...] = (
    "auto",
    "daylight",
    "overcast",
    "golden_hour",
    "blue_hour",
    "twilight",
    "night",
    "moonlight",
    "interior_warm",
    "interior_cool",
    "practical_lamps",
    "candlelight",
    "high_key",
    "low_key",
    "dramatic",
    "soft_diffused",
    "hard_sun",
    "neon",
    "sci_fi",
    "fantasy",
    "horror",
)

# Stable ID tuples kept under the historical catalog names used by compile/tests.
SHOT_SIZES = CAMERA_SHOT_IDS
LENS_VALUES = CAMERA_LENS_IDS
LIGHTING_MOODS = LIGHTING_PRESET_IDS
SHOT_SIZE_IDS = CAMERA_SHOT_IDS

CAMERA_SHOT_LABELS: dict[str, str] = {
    "auto": "Auto",
    "wide": "Wide",
    "medium_wide": "Medium Wide",
    "medium": "Medium",
    "medium_close": "Medium Close",
    "close_up": "Close Up",
    "extreme_close": "Extreme Close",
}

CAMERA_LENS_LABELS: dict[str, str] = {
    "auto": "Auto",
    "18": "18mm",
    "24": "24mm",
    "28": "28mm",
    "35": "35mm",
    "40": "40mm",
    "50": "50mm",
    "65": "65mm",
    "85": "85mm",
    "100": "100mm",
    "135": "135mm",
    "fisheye": "Fisheye",
}

LIGHTING_PRESET_LABELS: dict[str, str] = {
    "auto": "Auto",
    "daylight": "Daylight",
    "overcast": "Overcast",
    "golden_hour": "Golden Hour",
    "blue_hour": "Blue Hour",
    "twilight": "Twilight",
    "night": "Night",
    "moonlight": "Moonlight",
    "interior_warm": "Interior Warm",
    "interior_cool": "Interior Cool",
    "practical_lamps": "Practical Lamps",
    "candlelight": "Candlelight",
    "high_key": "High Key",
    "low_key": "Low Key",
    "dramatic": "Dramatic",
    "soft_diffused": "Soft Diffused",
    "hard_sun": "Hard Sun",
    "neon": "Neon",
    "sci_fi": "Sci-Fi",
    "fantasy": "Fantasy",
    "horror": "Horror",
}

# Back-compat names for existing catalog imports (same maps, FE labels).
SHOT_SIZE_LABELS = CAMERA_SHOT_LABELS
LENS_LABELS = CAMERA_LENS_LABELS
LIGHTING_MOOD_LABELS = LIGHTING_PRESET_LABELS

def normalize_catalog_id(value: Any, allowed: tuple[str, ...], field: str) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw not in allowed:
        raise ValueError(f"invalid {field}: {value!r}")
    return raw


def hydrate_camera_shot(value: Any) -> str:
    v = str(value or "auto").strip().lower().replace(" ", "_").replace("-", "_")
    return v if v in CAMERA_SHOT_IDS else "auto"


def hydrate_camera_lens(value: Any) -> str:
    raw = str(value if value is not None else "auto").strip().lower().replace("_", "-").replace(" ", "-")
    if raw.endswith("mm"):
        raw = raw[:-2].strip("- ")
    if raw in {"fisheye", "fish-eye"}:
        return "fisheye"
    if raw in CAMERA_LENS_IDS:
        return raw
    try:
        as_int = str(int(round(float(raw))))
    except (TypeError, ValueError):
        return "auto"
    return as_int if as_int in CAMERA_LENS_IDS else "auto"


def hydrate_lighting_preset(value: Any) -> str:
    raw = str(value if value is not None else "auto").strip().lower().replace(" ", "_").replace("-", "_")
    aliased = "sci_fi" if raw in {"scifi", "science_fiction"} else raw
    return aliased if aliased in LIGHTING_PRESET_IDS else "auto"


def camera_shot_label(value: Any) -> str:
    return CAMERA_SHOT_LABELS[hydrate_camera_shot(value)]


def camera_lens_label(value: Any) -> str:
    return CAMERA_LENS_LABELS[hydrate_camera_lens(value)]


def lighting_preset_label(value: Any) -> str:
    return LIGHTING_PRESET_LABELS[hydrate_lighting_preset(value)]


def camera_focus_label(focus_id: Any, focus_name: Any = None) -> str:
    ident = str(focus_id or "").strip()
    if not ident or ident == CAMERA_FOCUS_ENVIRONMENT_ID:
        return "Environment" if ident == CAMERA_FOCUS_ENVIRONMENT_ID else ""
    name = str(focus_name or "").strip()
    if not name:
        return ""
    return name if name.startswith("@") else "@" + "".join(name.split())


def format_camera_clip_label(parts: dict[str, Any] | None = None, **kwargs: Any) -> str:
    """Compact camera clip label. Reuses caller-supplied motionLabel (Timeline catalog)."""
    data = dict(parts or {})
    data.update(kwargs)
    chunks: list[str] = []
    shot_id = data.get("shot_id") or data.get("shotId")
    lens_id = data.get("lens_id") or data.get("lensId")
    focus_id = data.get("focus_id") or data.get("focusId")
    focus_name = data.get("focus_name") or data.get("focusName")
    motion_label = data.get("motion_label") or data.get("motionLabel")
    if shot_id and str(shot_id) != "auto":
        chunks.append(camera_shot_label(shot_id))
    if lens_id and str(lens_id) != "auto":
        chunks.append(camera_lens_label(lens_id))
    focus = camera_focus_label(focus_id, focus_name)
    if focus:
        chunks.append(focus)
    motion = str(motion_label or "").strip()
    if motion:
        chunks.append(motion)
    return " \u00b7 ".join(chunks)
