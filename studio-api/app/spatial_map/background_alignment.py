"""Spatial Map Atlas background alignment — translation + uniform scale.

Canonical offsets are fractions of the Spatial Map square (the SVG viewBox /
ERS panel). Render pixels = offset * size. Scale is a unitless multiplier on
contain-fit. The atlas keeps its native aspect; the grid stays square.
Missing or invalid offsets hydrate to zero; missing or invalid scale hydrates
to 1 so historical maps stay valid. Source width/height 0 = unknown until
measured. No rotation.
"""

from __future__ import annotations

import math
from typing import Any

ALIGNMENT_MAX = 0.45
SCALE_MIN = 0.1
SCALE_MAX = 8.0
SOURCE_SIZE_MAX = 65535.0


def clamp_offset(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return max(-ALIGNMENT_MAX, min(ALIGNMENT_MAX, number))


def clamp_scale(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(number):
        return 1.0
    return max(SCALE_MIN, min(SCALE_MAX, number))


def clamp_source_size(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number) or number <= 0:
        return 0.0
    return min(SOURCE_SIZE_MAX, number)


def source_aspect(width: float, height: float) -> float:
    if width <= 0 or height <= 0:
        return 1.0
    return float(width) / float(height)


def contain_rect(size: float, aspect: float) -> tuple[float, float, float, float]:
    """x, y, w, h of a contain-fit rectangle inside a size×size square."""
    ratio = aspect if math.isfinite(aspect) and aspect > 0 else 1.0
    if ratio >= 1.0:
        height = size / ratio
        return 0.0, (size - height) / 2.0, size, height
    width = size * ratio
    return (size - width) / 2.0, 0.0, width, size


def hydrate_alignment(raw: Any) -> dict[str, float]:
    if raw is None:
        return {
            "offsetX": 0.0,
            "offsetY": 0.0,
            "scale": 1.0,
            "sourceWidth": 0.0,
            "sourceHeight": 0.0,
            "sourceAspectRatio": 1.0,
        }
    if isinstance(raw, dict):
        width = clamp_source_size(raw.get("sourceWidth", 0.0))
        height = clamp_source_size(raw.get("sourceHeight", 0.0))
        raw_aspect = raw.get("sourceAspectRatio")
        try:
            aspect = float(raw_aspect) if raw_aspect is not None else source_aspect(width, height)
        except (TypeError, ValueError):
            aspect = source_aspect(width, height)
        if not math.isfinite(aspect) or aspect <= 0:
            aspect = source_aspect(width, height)
        return {
            "offsetX": clamp_offset(raw.get("offsetX", 0.0)),
            "offsetY": clamp_offset(raw.get("offsetY", 0.0)),
            "scale": clamp_scale(raw.get("scale", 1.0)),
            "sourceWidth": width,
            "sourceHeight": height,
            "sourceAspectRatio": aspect,
        }
    width = clamp_source_size(getattr(raw, "sourceWidth", 0.0))
    height = clamp_source_size(getattr(raw, "sourceHeight", 0.0))
    raw_aspect = getattr(raw, "sourceAspectRatio", None)
    try:
        aspect = float(raw_aspect) if raw_aspect is not None else source_aspect(width, height)
    except (TypeError, ValueError):
        aspect = source_aspect(width, height)
    if not math.isfinite(aspect) or aspect <= 0:
        aspect = source_aspect(width, height)
    return {
        "offsetX": clamp_offset(getattr(raw, "offsetX", 0.0)),
        "offsetY": clamp_offset(getattr(raw, "offsetY", 0.0)),
        "scale": clamp_scale(getattr(raw, "scale", 1.0)),
        "sourceWidth": width,
        "sourceHeight": height,
        "sourceAspectRatio": aspect,
    }


def pixels_from_alignment(offset: float, size: float) -> float:
    if not math.isfinite(size) or size <= 0:
        return 0.0
    return clamp_offset(offset) * float(size)


def alignment_from_pixels(pixels: float, size: float) -> float:
    if not math.isfinite(size) or size <= 0:
        return 0.0
    return clamp_offset(float(pixels) / float(size))
