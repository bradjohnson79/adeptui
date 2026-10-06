"""Pixel-based Atlas vs perspective classification."""

from __future__ import annotations

import numpy as np

from app.codirector.routing.atlas_classify import classify_pixels


def _axis_aligned_floorplan(size: int = 128) -> np.ndarray:
    arr = np.full((size, size, 3), 210, dtype=np.uint8)
    for i in range(0, size, 16):
        arr[i : i + 2, :, :] = 40
        arr[:, i : i + 2, :] = 40
    arr[40:88, 40:88, :] = 90
    return arr


def _diagonal_perspective(width: int = 192, height: int = 108) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    vanishing = ((xx * 180 / max(width - 1, 1)) + (yy * 40 / max(height - 1, 1))).astype(np.uint8)
    arr = np.stack([vanishing, np.clip(vanishing + 20, 0, 255), np.clip(vanishing - 10, 0, 255)], axis=2)
    for offset in range(-20, 21, 10):
        for x in range(width):
            y = int(height * 0.2 + x * 0.35 + offset)
            if 0 <= y < height:
                arr[y, x] = [20, 20, 20]
    return arr


def _flat_swatch(size: int = 64) -> np.ndarray:
    return np.full((size, size, 3), 180, dtype=np.uint8)


def _axis_aligned_corridor(width: int = 72, height: int = 128) -> np.ndarray:
    arr = np.full((height, width, 3), 210, dtype=np.uint8)
    arr[:, :4, :] = 40
    arr[:, -4:, :] = 40
    for i in range(0, height, 16):
        arr[i : i + 2, :, :] = 40
    for i in range(0, width, 16):
        arr[:, i : i + 2, :] = 40
    arr[:12, width // 2 - 10 : width // 2 + 10, :] = 90
    arr[height // 2 - 8 : height // 2 + 8, -8:, :] = 70
    return arr


def test_axis_aligned_floorplan_is_atlas() -> None:
    kind, confidence = classify_pixels(_axis_aligned_floorplan(), 128, 128)
    assert kind == "atlas"
    assert confidence >= 0.7


def test_tall_corridor_plate_is_atlas() -> None:
    """Local Designer 9:16 corridor plates are Atlas-class, not uncertain."""
    kind, confidence = classify_pixels(_axis_aligned_corridor(), 72, 128)
    assert kind == "atlas"
    assert confidence >= 0.7


def test_diagonal_master_is_perspective() -> None:
    kind, confidence = classify_pixels(_diagonal_perspective(), 192, 108)
    assert kind == "perspective_environment"
    assert confidence >= 0.7


def test_flat_swatch_is_non_environment_or_uncertain() -> None:
    kind, _confidence = classify_pixels(_flat_swatch(), 64, 64)
    assert kind in {"non_environment", "uncertain"}
