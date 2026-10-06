"""Optional ordinal depth. Skip for simple segmentation."""

from __future__ import annotations

from typing import Any

from .paths import depth_anything_dir, model_present, DEPTH_ANYTHING_MARKERS


def spatial_available() -> bool:
    return model_present(depth_anything_dir(), DEPTH_ANYTHING_MARKERS)


def ordinal_for_box(box: dict[str, float] | None, depth_layers: dict[str, Any] | None) -> str:
    """Best-effort near/mid/far. Never invent metric 3D."""
    if not box:
        return "unknown"
    y = (float(box.get("y0") or 0) + float(box.get("y1") or 1)) / 2.0
    if y > 0.66:
        return "near"
    if y < 0.33:
        return "far"
    return "mid"
