"""Stamp Spatial Map cameras onto the ERS Spatial / Top-Down panel.

One-way overlay (Amendment #3): never writes back to Spatial Map placements.
Uses the same normalized [-1, 1] transform as SpatialGrid / grid.py.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from .ers_projection import compile_structured_cameras
from .grid import cell_center_normalized, density_for_scale, orientation_to_yaw

logger = logging.getLogger(__name__)

# Frozen production_ers 3×3. Panel 2 = Spatial / Top-Down (column 1, row 0).
# Origin is top-left. Values are fractions of sheet width / height.
ERS_TOPDOWN_PANEL = {
    "left": 1.0 / 3.0,
    "top": 0.0,
    "width": 1.0 / 3.0,
    "height": 1.0 / 3.0,
}

FOV_ANGLES = {"narrow": 20.0, "medium": 45.0, "wide": 75.0}

# Keep labels inside the inscribed map square.
_MAP_INSET = 0.08


class OverlayClipError(RuntimeError):
    """Camera would land outside the frozen top-down panel."""


def normalized_to_panel_pixel(
    nx: float,
    ny: float,
    *,
    panel_left: float,
    panel_top: float,
    panel_width: float,
    panel_height: float,
    image_width: int,
    image_height: int,
) -> tuple[float, float]:
    """Map Spatial Map normalized [-1, 1] into the inscribed square of panel 2.

    x: west→east, y: north→south. No axis swap, no rotation.
    """
    side = min(panel_width, panel_height) * (1.0 - 2.0 * _MAP_INSET)
    square_left = panel_left + (panel_width - side) / 2.0
    square_top = panel_top + (panel_height - side) / 2.0
    px = (square_left + ((nx + 1.0) / 2.0) * side) * image_width
    py = (square_top + ((ny + 1.0) / 2.0) * side) * image_height
    return px, py


def panel_rect_px(image_width: int, image_height: int, panel: dict[str, float] | None = None) -> tuple[float, float, float, float]:
    spec = panel or ERS_TOPDOWN_PANEL
    left = float(spec["left"]) * image_width
    top = float(spec["top"]) * image_height
    width = float(spec["width"]) * image_width
    height = float(spec["height"]) * image_height
    return left, top, width, height


def camera_normalized(camera: dict[str, Any], density: int) -> tuple[float, float]:
    nx = camera.get("normalizedX")
    ny = camera.get("normalizedY")
    if nx is not None and ny is not None:
        return float(nx), float(ny)
    col = int(camera.get("gridColumn") or 0)
    row = int(camera.get("gridRow") or 0)
    return cell_center_normalized(col, row, density)


def map_cameras_to_overlay(
    cameras: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
    density: int = 10,
    panel: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    left, top, width, height = panel_rect_px(image_width, image_height, panel)
    mapped: list[dict[str, Any]] = []
    for camera in cameras:
        nx, ny = camera_normalized(camera, density)
        px, py = normalized_to_panel_pixel(
            nx,
            ny,
            panel_left=left / image_width,
            panel_top=top / image_height,
            panel_width=width / image_width,
            panel_height=height / image_height,
            image_width=image_width,
            image_height=image_height,
        )
        pad = 8.0
        if px < left + pad or px > left + width - pad or py < top + pad or py > top + height - pad:
            raise OverlayClipError(
                f"Camera {camera.get('label') or camera.get('id')} maps outside the "
                f"Spatial / Top-Down panel ({px:.1f},{py:.1f} not in "
                f"{left:.1f},{top:.1f} {width:.1f}x{height:.1f}). Overlay aborted."
            )
        mapped.append({**camera, "overlayX": px, "overlayY": py, "normalizedX": nx, "normalizedY": ny})
    return mapped


def _draw_fov(draw: Any, cx: float, cy: float, orientation: str, fov_preset: str, radius: float) -> None:
    angle = FOV_ANGLES.get(str(fov_preset or "medium").lower(), FOV_ANGLES["medium"])
    yaw = orientation_to_yaw(orientation)
    svg_angle = math.radians(yaw - 90.0)
    half = math.radians(angle / 2.0)
    steps = 12
    points = [(cx, cy)]
    start = svg_angle - half
    end = svg_angle + half
    for i in range(steps + 1):
        t = start + (end - start) * (i / steps)
        points.append((cx + radius * math.cos(t), cy + radius * math.sin(t)))
    draw.polygon(points, fill=(14, 165, 233, 90))


def _draw_marker(draw: Any, cx: float, cy: float, label: str, orientation: str, size: float) -> None:
    yaw = math.radians(orientation_to_yaw(orientation))
    w = size
    h = size * 0.65
    hw, hh = w / 2.0, h / 2.0
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    rot = []
    for x, y in corners:
        rx = x * math.cos(yaw) - y * math.sin(yaw)
        ry = x * math.sin(yaw) + y * math.cos(yaw)
        rot.append((cx + rx, cy + ry))
    draw.polygon(rot, fill=(31, 41, 55, 230), outline=(226, 232, 240, 255))
    r = size * 0.2
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(51, 65, 85, 255), outline=(148, 163, 184, 255))
    r2 = size * 0.1
    draw.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(14, 165, 233, 255))
    try:
        draw.text((cx, cy + size * 0.55), str(label), fill=(248, 250, 252, 255), anchor="ma")
    except TypeError:
        draw.text((cx - 8, cy + size * 0.4), str(label), fill=(248, 250, 252, 255))


def stamp_cameras_on_ers_image(
    image_path: str | Path,
    cameras: list[dict[str, Any]] | None,
    *,
    density: int = 10,
    panel: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Draw C1–C4 + FOV onto panel 2. Returns overlay metadata."""
    from PIL import Image, ImageDraw

    compiled = compile_structured_cameras(cameras)
    active = list(compiled.get("cameras") or [])
    path = Path(image_path)
    if not active:
        return {"status": "skipped", "reason": "no_active_cameras", "count": 0}
    with Image.open(path) as src:
        image = src.convert("RGBA")
        from .ers_movement_strip import core_size

        core_w, core_h = core_size(image.width, image.height)
        mapped = map_cameras_to_overlay(
            active,
            image_width=core_w,
            image_height=core_h,
            density=density,
            panel=panel,
        )
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        left, top, width, height = panel_rect_px(core_w, core_h, panel)
        radius = max(28.0, min(width, height) * 0.12)
        marker = max(18.0, min(width, height) * 0.06)
        for cam in mapped:
            _draw_fov(
                draw,
                cam["overlayX"],
                cam["overlayY"],
                str(cam.get("orientation") or "N"),
                str(cam.get("fovPreset") or "medium"),
                radius,
            )
        for cam in mapped:
            _draw_marker(
                draw,
                cam["overlayX"],
                cam["overlayY"],
                str(cam.get("label") or "C"),
                str(cam.get("orientation") or "N"),
                marker,
            )
        composed = Image.alpha_composite(image, overlay)
        composed.convert(src.mode if src.mode in {"RGB", "RGBA"} else "RGB").save(path)
    return {
        "status": "stamped",
        "count": len(mapped),
        "labels": [str(c.get("label")) for c in mapped],
        "panel": panel or ERS_TOPDOWN_PANEL,
    }


def stamp_saved_cameras_on_ers(image_path: str | Path, db: Any, project_id: str, params: dict[str, Any]) -> dict[str, Any]:
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    cameras = ctx.get("cameras")
    density = density_for_scale(ctx.get("gridScale") or params.get("gridScale") or 0)
    if not cameras:
        map_id = str(ctx.get("spatialMapId") or params.get("spatialMapId") or "").strip()
        if map_id and db is not None:
            from .service import get_document

            document = get_document(db, project_id, map_id)
            cameras = list(compile_structured_cameras(getattr(document, "cameras", None) or []).get("cameras") or [])
            density = density_for_scale(getattr(document, "gridScale", 0))
    stamped = stamp_cameras_on_ers_image(image_path, cameras or [], density=density)
    try:
        from .ers_movement_strip import assemble_ers_with_movement_strip
        from .service import get_document as _get_doc

        map_id = str(ctx.get("spatialMapId") or params.get("spatialMapId") or "").strip()
        document = None
        if map_id and db is not None:
            document = _get_doc(db, project_id, map_id)
        stamped["movementStrip"] = assemble_ers_with_movement_strip(image_path, document)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ERS movement strip assembly skipped: %s", exc)
    return stamped
