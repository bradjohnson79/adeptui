"""Normalize detector boxes into PerceptionPacket unit space."""

from __future__ import annotations

from typing import Any


def normalize_box(box: dict[str, Any], width: int = 0, height: int = 0) -> dict[str, float]:
    """Convert HF pixel boxes to [0, 1]. Already-normalized boxes pass through."""
    x0 = float(box.get("x0") if box.get("x0") is not None else box.get("xmin") or 0.0)
    y0 = float(box.get("y0") if box.get("y0") is not None else box.get("ymin") or 0.0)
    x1 = float(box.get("x1") if box.get("x1") is not None else box.get("xmax") or 0.0)
    y1 = float(box.get("y1") if box.get("y1") is not None else box.get("ymax") or 0.0)
    if max(x0, y0, x1, y1) > 1.0 and width > 0 and height > 0:
        x0, x1 = x0 / float(width), x1 / float(width)
        y0, y1 = y0 / float(height), y1 / float(height)
    return {
        "x0": max(0.0, min(1.0, x0)),
        "y0": max(0.0, min(1.0, y0)),
        "x1": max(0.0, min(1.0, x1)),
        "y1": max(0.0, min(1.0, y1)),
    }
