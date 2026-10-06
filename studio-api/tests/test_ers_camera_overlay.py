"""ERS camera overlay maps Spatial Map normalized coords into panel 2 without axis swap."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.spatial_map.ers_camera_overlay import (
    ERS_TOPDOWN_PANEL,
    map_cameras_to_overlay,
    normalized_to_panel_pixel,
    stamp_cameras_on_ers_image,
)


def test_topdown_panel_is_frozen_section_two() -> None:
    assert ERS_TOPDOWN_PANEL["left"] == 1 / 3
    assert ERS_TOPDOWN_PANEL["top"] == 0.0
    assert ERS_TOPDOWN_PANEL["width"] == 1 / 3
    assert ERS_TOPDOWN_PANEL["height"] == 1 / 3


def test_normalized_origin_is_panel_center_no_axis_swap() -> None:
    w, h = 900, 900
    px, py = normalized_to_panel_pixel(
        0.0,
        0.0,
        panel_left=1 / 3,
        panel_top=0.0,
        panel_width=1 / 3,
        panel_height=1 / 3,
        image_width=w,
        image_height=h,
    )
    # Inscribed square is centered in panel 2.
    panel_cx = (1 / 3 + 1 / 6) * w
    panel_cy = (1 / 6) * h
    assert abs(px - panel_cx) < 1.0
    assert abs(py - panel_cy) < 1.0
    east_x, east_y = normalized_to_panel_pixel(
        1.0,
        0.0,
        panel_left=1 / 3,
        panel_top=0.0,
        panel_width=1 / 3,
        panel_height=1 / 3,
        image_width=w,
        image_height=h,
    )
    south_x, south_y = normalized_to_panel_pixel(
        0.0,
        1.0,
        panel_left=1 / 3,
        panel_top=0.0,
        panel_width=1 / 3,
        panel_height=1 / 3,
        image_width=w,
        image_height=h,
    )
    assert east_x > px
    assert abs(east_y - py) < 1.0
    assert south_y > py
    assert abs(south_x - px) < 1.0


def test_map_cameras_preserves_c1_c4_order_and_labels() -> None:
    cameras = [
        {"id": "1", "label": "C1", "cameraSlot": 0, "gridColumn": 2, "gridRow": 2, "normalizedX": -0.2, "normalizedY": -0.2, "orientation": "E", "visible": True},
        {"id": "2", "label": "C2", "cameraSlot": 1, "gridColumn": 5, "gridRow": 5, "normalizedX": 0.0, "normalizedY": 0.0, "orientation": "S", "visible": True},
        {"id": "3", "label": "C3", "cameraSlot": 2, "gridColumn": 7, "gridRow": 3, "normalizedX": 0.4, "normalizedY": -0.1, "orientation": "W", "visible": True},
        {"id": "4", "label": "C4", "cameraSlot": 3, "gridColumn": 6, "gridRow": 7, "normalizedX": 0.15, "normalizedY": 0.45, "orientation": "N", "visible": True},
    ]
    mapped = map_cameras_to_overlay(cameras, image_width=1200, image_height=1200, density=10)
    assert [c["label"] for c in mapped] == ["C1", "C2", "C3", "C4"]
    c1 = next(c for c in mapped if c["label"] == "C1")
    c3 = next(c for c in mapped if c["label"] == "C3")
    assert c3["overlayX"] > c1["overlayX"]


def test_stamp_writes_pixels(tmp_path: Path) -> None:
    path = tmp_path / "ers.png"
    Image.new("RGB", (900, 900), (20, 20, 20)).save(path)
    cameras = [
        {
            "id": "1",
            "label": "C1",
            "cameraSlot": 0,
            "gridColumn": 5,
            "gridRow": 5,
            "normalizedX": 0.0,
            "normalizedY": 0.0,
            "orientation": "N",
            "fovPreset": "medium",
            "visible": True,
        }
    ]
    meta = stamp_cameras_on_ers_image(path, cameras, density=10)
    assert meta["status"] == "stamped"
    assert meta["labels"] == ["C1"]
    stamped = Image.open(path)
    # Center of panel 2 should no longer be the flat fill.
    cx = int((1 / 3 + 1 / 6) * 900)
    cy = int((1 / 6) * 900)
    pixel = stamped.getpixel((cx, cy))
    assert pixel != (20, 20, 20)
