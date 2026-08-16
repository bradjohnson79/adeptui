from __future__ import annotations

"""Aspect ratio + FPS helpers for per-scene render planning."""

from typing import Any

ASPECT_PRESETS = (
    "1:1",
    "4:3",
    "3:2",
    "16:10",
    "16:9",
    "18:9",
    "21:9",
    "9:16",
    "2.39:1",
    "custom",
)

# Shared production contract for Scene Creator + Timeline Generator.
PRODUCTION_ASPECTS = ("1:1", "4:3", "16:9", "21:9")
DEFAULT_PRODUCTION_ASPECT = "16:9"
PRODUCTION_PIXELS: dict[str, dict[str, tuple[int, int]]] = {
    "1:1": {"draft": (512, 512), "final": (1024, 1024)},
    "4:3": {"draft": (512, 384), "final": (1024, 768)},
    "16:9": {"draft": (512, 288), "final": (1280, 720)},
    "21:9": {"draft": (672, 288), "final": (1344, 576)},
}

FPS_CHOICES = (12, 16, 18, 24, 25, 30, 48, 50, 60)

# Engine → allowed aspect labels (approximate; UI warns when mismatched)
ENGINE_ASPECT_HINTS: dict[str, set[str]] = {
    "ltx": set(ASPECT_PRESETS) - {"custom"},
    "wan": set(ASPECT_PRESETS) - {"custom"},
    "fal_seedance": {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"},
    "fal_kling": {"16:9", "9:16", "1:1"},
    "fal_veo": {"16:9", "9:16"},
    "fal_runway": {"16:9", "9:16", "1:1"},
}


def aspect_to_size(aspect: str, base_long: int = 1280) -> tuple[int, int]:
    ratios: dict[str, tuple[int, int]] = {
        "1:1": (1, 1),
        "4:3": (4, 3),
        "3:2": (3, 2),
        "16:10": (16, 10),
        "16:9": (16, 9),
        "18:9": (18, 9),
        "21:9": (21, 9),
        "9:16": (9, 16),
        "2.39:1": (239, 100),
    }
    a, b = ratios.get(aspect, (16, 9))
    if a >= b:
        w = base_long
        h = max(64, round(base_long * b / a / 8) * 8)
        return w, h
    h = base_long
    w = max(64, round(base_long * a / b / 8) * 8)
    return w, h


def resolve_scene_dims(project: Any, scene: Any) -> tuple[int, int]:
    aspect = (getattr(scene, "aspect_ratio", None) or "16:9").strip() or "16:9"
    if aspect == "custom":
        w = int(getattr(scene, "width", 0) or getattr(project, "width", 1280) or 1280)
        h = int(getattr(scene, "height", 0) or getattr(project, "height", 720) or 720)
        return max(64, w), max(64, h)
    base = max(int(getattr(project, "width", 1280) or 1280), int(getattr(project, "height", 720) or 720))
    return aspect_to_size(aspect, base)


def resolve_scene_fps(project: Any, scene: Any) -> int:
    mode = (getattr(scene, "fps_mode", None) or "auto").strip().lower()
    if mode == "auto" or mode == "":
        # VRAM-aware defaults
        vram = int(getattr(project, "vram_gb", 32) or 32)
        duration = float(getattr(scene, "duration_sec", 5) or 5)
        if vram <= 8:
            return 16
        if vram <= 16:
            return 20 if duration <= 5 else 16
        return int(getattr(project, "fps", 24) or 24)
    try:
        fps = int(float(mode))
        if fps in FPS_CHOICES:
            return fps
    except (TypeError, ValueError):
        pass
    override = getattr(scene, "fps", None)
    if override is not None:
        try:
            return int(override)
        except (TypeError, ValueError):
            pass
    return int(getattr(project, "fps", 24) or 24)


def validate_engine_aspect(engine: str, aspect: str) -> list[str]:
    warnings: list[str] = []
    eng = (engine or "ltx").lower()
    if eng == "auto":
        return warnings
    allowed = ENGINE_ASPECT_HINTS.get(eng)
    if not allowed:
        return warnings
    if aspect == "custom":
        warnings.append(f"{eng} may reject custom aspect — verify provider limits before render.")
        return warnings
    if aspect not in allowed and aspect not in {"3:4"}:
        warnings.append(
            f"{eng} typically supports {', '.join(sorted(allowed))}. "
            f"Selected {aspect} may be remapped or rejected."
        )
    return warnings


def normalize_production_aspect(raw: str | None) -> str:
    """Missing / unknown / custom without pixels → 16:9."""
    aspect = (raw or "").strip() or DEFAULT_PRODUCTION_ASPECT
    if aspect in PRODUCTION_ASPECTS:
        return aspect
    return DEFAULT_PRODUCTION_ASPECT


def production_pixels(aspect: str | None, quality: str = "final") -> tuple[int, int]:
    """Adept production intent pixels. Providers may remap to a legal size."""
    key = normalize_production_aspect(aspect)
    bucket = "draft" if (quality or "").strip().lower() in {"draft", "preview"} else "final"
    return PRODUCTION_PIXELS[key][bucket]
