"""Camera lens, FOV, lighting mood, and shot-distance helpers.

Canonical sensor (not exposed in UI): Full Frame 36 mm horizontal.
1 Spatial Map square = 1 meter. Distance is omitted unless a real subject exists.
"""

from __future__ import annotations

import math
from typing import Any

FULL_FRAME_HORIZONTAL_MM = 36.0

LENS_VALUES: tuple[str, ...] = (
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

FISHEYE_LENS = "fisheye"
FISHEYE_ALIASES = frozenset({"fisheye", "fish_eye", "fish-eye", "fish eye"})

FISHEYE_PROMPT_LINES: tuple[str, ...] = (
    "cinematic fisheye lens",
    "extremely wide field of view",
    "characteristic curved/barrel edge distortion",
    "exaggerated near/far spatial relationships",
    "camera position and orientation still governed by Spatial Map",
    "primary subject and distance still respected",
    "environment topology and identities unchanged",
)

LIGHTING_MOODS: tuple[str, ...] = (
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

LIGHTING_MOOD_LABELS: dict[str, str] = {
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

LOCAL_MINI_GENERATORS = frozenset({"qwen2512", "zimage"})
API_MINI_GENERATORS = frozenset({"gpt-image-2"})
# Documented Mini API fan-out cap. Not a camera-count hardcode.
# Override with STUDIO_MINI_API_MAX_CONCURRENT. Provider/rate-limit
# metadata wins when present.
DEFAULT_MINI_API_MAX_CONCURRENT = 6


def is_fisheye_lens(value: Any) -> bool:
    raw = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    return raw in {"fisheye", "fish-eye"} or str(value or "").strip().lower() in FISHEYE_ALIASES


def hydrate_lens(value: Any) -> str:
    raw = str(value or "auto").strip().lower()
    if is_fisheye_lens(raw):
        return FISHEYE_LENS
    if raw.endswith("mm"):
        raw = raw[:-2].strip()
    if raw in LENS_VALUES:
        return raw
    try:
        as_int = str(int(round(float(raw))))
        if as_int in LENS_VALUES:
            return as_int
    except (TypeError, ValueError):
        pass
    return "auto"


def hydrate_lighting_mood(value: Any) -> str:
    raw = str(value or "auto").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "scifi": "sci_fi",
        "sci_fi": "sci_fi",
        "science_fiction": "sci_fi",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in LIGHTING_MOODS else "auto"


def lighting_mood_label(value: Any) -> str:
    key = hydrate_lighting_mood(value)
    return LIGHTING_MOOD_LABELS.get(key, "Auto")


def lens_mm_for(lens: str, fallback: float = 35.0) -> float:
    key = hydrate_lens(lens)
    if key == "auto" or key == FISHEYE_LENS:
        try:
            mm = float(fallback)
            return mm if math.isfinite(mm) else 35.0
        except (TypeError, ValueError):
            return 35.0
    return float(int(key))


def fisheye_prompt_lines() -> list[str]:
    return [
        "Lens: fisheye. Cinematic fisheye projection — not a rectilinear wide lens and not 18mm.",
        *FISHEYE_PROMPT_LINES,
    ]


def fov_degrees_from_lens_mm(lens_mm: float, sensor_mm: float = FULL_FRAME_HORIZONTAL_MM) -> float:
    mm = float(lens_mm)
    if not math.isfinite(mm) or mm <= 0:
        mm = 35.0
    return 2.0 * math.degrees(math.atan((sensor_mm / 2.0) / mm))


def snap_fov_preset(fov_degrees: float) -> str:
    if fov_degrees >= 65.0:
        return "wide"
    if fov_degrees <= 35.0:
        return "narrow"
    return "medium"


def reconcile_lens_fov(
    *,
    lens: Any,
    fov_preset: Any,
    lens_mm: Any = None,
    last_control: str | None = None,
) -> dict[str, Any]:
    """Last explicit control wins.

    lens=auto → fovPreset remains authority.
    Manual lens → lens is framing authority; fovPreset is snapped.
    FOV button change → lens returns to auto.
    """
    fov = str(fov_preset or "medium").strip().lower()
    if fov not in {"narrow", "medium", "wide"}:
        fov = "medium"
    key = hydrate_lens(lens)
    if last_control == "fov":
        key = "auto"
    fallback_mm = float(lens_mm) if lens_mm is not None else 35.0
    mm = lens_mm_for(key, fallback=fallback_mm)
    derived: float | None = None
    if key == FISHEYE_LENS:
        # Special projection. Do not run focalLength → rectilinear FOV.
        # Map cone may read wide; that is not an 18 mm claim.
        return {
            "lens": FISHEYE_LENS,
            "lensMm": mm,
            "fovPreset": "wide",
            "fovDegrees": None,
        }
    if key != "auto":
        derived = fov_degrees_from_lens_mm(mm)
        fov = snap_fov_preset(derived)
        mm = float(int(key))
    return {
        "lens": key,
        "lensMm": mm,
        "fovPreset": fov,
        "fovDegrees": derived,
    }


def apply_reconcile_to_camera(camera: Any, updates: dict[str, Any] | None = None) -> None:
    patch = dict(updates or {})
    last = None
    if "fovPreset" in patch and "lens" not in patch:
        last = "fov"
    if "lens" in patch:
        last = "lens"
    result = reconcile_lens_fov(
        lens=patch.get("lens", getattr(camera, "lens", "auto")),
        fov_preset=patch.get("fovPreset", getattr(camera, "fovPreset", "medium")),
        lens_mm=patch.get("lensMm", getattr(camera, "lensMm", 35.0)),
        last_control=last,
    )
    camera.lens = result["lens"]
    camera.lensMm = result["lensMm"]
    camera.fovPreset = result["fovPreset"]
    if getattr(camera, "lightingMood", None) in (None, ""):
        camera.lightingMood = "auto"
    else:
        camera.lightingMood = hydrate_lighting_mood(getattr(camera, "lightingMood", "auto"))


def is_local_mini_generator(generator: Any) -> bool:
    return str(generator or "").strip().lower() in LOCAL_MINI_GENERATORS


def is_api_mini_generator(generator: Any) -> bool:
    return str(generator or "").strip().lower() in API_MINI_GENERATORS


def provider_mini_api_concurrency_cap(generator: Any = None) -> int | None:
    """Return a provider-advertised concurrency cap when one exists.

    GPT Image 2 / Kie do not publish a hard cap in this runtime. None means
    use the Studio Mini setting only.
    """
    _ = generator
    return None


def mini_api_max_concurrent(generator: Any = None) -> int:
    try:
        from ..config import settings

        raw = getattr(settings, "mini_api_max_concurrent", DEFAULT_MINI_API_MAX_CONCURRENT)
        cap = int(raw)
    except Exception:
        cap = DEFAULT_MINI_API_MAX_CONCURRENT
    advertised = provider_mini_api_concurrency_cap(generator)
    if advertised is not None:
        try:
            cap = min(cap, max(1, int(advertised)))
        except (TypeError, ValueError):
            pass
    return max(1, cap)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _xyz(entity: Any) -> tuple[float, float] | None:
    if entity is None:
        return None
    if isinstance(entity, dict):
        x = _finite(entity.get("x"))
        z = _finite(entity.get("z"))
        if x is not None and z is not None:
            return x, z
        pos = entity.get("positionMeters") or {}
        if isinstance(pos, dict):
            x = _finite(pos.get("x"))
            z = _finite(pos.get("z"))
            if x is not None and z is not None:
                return x, z
        return None
    x = _finite(getattr(entity, "x", None))
    z = _finite(getattr(entity, "z", None))
    if x is not None and z is not None:
        return x, z
    pos = getattr(entity, "positionMeters", None)
    if pos is not None:
        x = _finite(getattr(pos, "x", None) if not isinstance(pos, dict) else pos.get("x"))
        z = _finite(getattr(pos, "z", None) if not isinstance(pos, dict) else pos.get("z"))
        if x is not None and z is not None:
            return x, z
    return None


def subject_distance_meters(camera: Any, subject: Any) -> float | None:
    """Planar meters between camera and a real primary subject. Never invented."""
    cam = _xyz(camera)
    sub = _xyz(subject)
    if cam is None or sub is None:
        return None
    dist = math.hypot(sub[0] - cam[0], sub[1] - cam[1])
    if not math.isfinite(dist):
        return None
    return round(dist, 2)


def validate_camera_for_mini(camera: Any, *, distance: float | None, has_subject: bool) -> str | None:
    data = camera if isinstance(camera, dict) else None

    def _get(name: str, default: Any = None) -> Any:
        if data is not None:
            return data.get(name, default)
        return getattr(camera, name, default)

    if _get("visible", True) is False:
        return "Camera is disabled."
    x = _finite(_get("x"))
    z = _finite(_get("z"))
    nx = _finite(_get("normalizedX"))
    ny = _finite(_get("normalizedY"))
    if (x is None or z is None) and (nx is None or ny is None):
        return "Camera is missing a finite position."
    yaw = _finite(_get("yawDegrees"))
    if yaw is None:
        return "Camera is missing a finite facing."
    lens = hydrate_lens(_get("lens", "auto"))
    if lens not in LENS_VALUES:
        return "Camera lens is invalid."
    mood = hydrate_lighting_mood(_get("lightingMood", "auto"))
    if mood not in LIGHTING_MOODS:
        return "Camera lighting mood is invalid."
    if has_subject and distance is not None and not math.isfinite(distance):
        return "Camera subject distance is not finite."
    return None


def lighting_mood_prompt_line(mood: Any, *, env_identity: str = "", scene_summary: str = "") -> str:
    key = hydrate_lighting_mood(mood)
    if key == "auto":
        canon = (env_identity or scene_summary or "").strip()
        if canon:
            return (
                f"Lighting follows the Environment Reference Sheet and scene intent ({canon[:180]}). "
                "Do not force generic daylight."
            )
        return (
            "Lighting follows the Environment Reference Sheet and scene intent. "
            "Do not force generic daylight."
        )
    label = lighting_mood_label(key)
    extra = ""
    if key == "sci_fi":
        extra = " Sci-Fi is a lighting mood only — do not invent cyberpunk neon unless the scene already supports it."
    elif key == "fantasy":
        extra = " Fantasy is a lighting mood only — do not invent magic unless the scene already supports it."
    return (
        f"Lighting mood: {label}. Apply this mood to illumination only. "
        f"Do not change architecture, identity, placement, or camera geography.{extra}"
    )
