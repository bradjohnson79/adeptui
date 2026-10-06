"""Code-assembled Movement strip below the frozen ERS 3×3 core.

The LLM production_ers sheet stays 16:9. After camera overlay, this module
builds a taller canvas: core + camera-reference band + movement refs.
Mini hero crop always uses the core rectangle, never the expanded height.
"""

from __future__ import annotations

from typing import Any

from .ers_camera_overlay import ERS_TOPDOWN_PANEL
from .movement import compute_arrows, hydrate_movement_segments, movement_alias

ERS_CORE_WIDTH = 2560
ERS_CORE_HEIGHT = 1440
CAMERA_BAND_HEIGHT = 360
MOVEMENT_CELL_HEIGHT = 420
MOVEMENT_MAX_SHOWN = 5


def core_size(width: int, height: int) -> tuple[int, int]:
    """Return the frozen 16:9 core size for an assembled taller sheet.

    Square or other native ERS canvases keep their full size. Only a wide
    2K-class sheet that is taller than 16:9 is treated as core-plus-strip.
    """
    expected = int(round(width * 9 / 16))
    assembled = width >= 2000 and height > expected + 16
    if not assembled:
        return width, height
    return width, expected


def layout_rects(width: int, height: int | None = None, movement_count: int = 0) -> dict[str, Any]:
    """Pixel rectangles for core, camera band, and movement cells. No overlap."""
    core_w, core_h = width, ERS_CORE_HEIGHT if width == ERS_CORE_WIDTH else int(round(width * 9 / 16))
    camera_top = core_h
    camera_h = CAMERA_BAND_HEIGHT
    shown = max(0, min(int(movement_count or 0), MOVEMENT_MAX_SHOWN))
    movement_h = MOVEMENT_CELL_HEIGHT if shown else 0
    movement_top = camera_top + camera_h
    total_h = movement_top + movement_h
    cells = []
    if shown:
        cell_w = core_w / shown
        for index in range(shown):
            cells.append(
                {
                    "index": index,
                    "left": index * cell_w,
                    "top": float(movement_top),
                    "width": cell_w,
                    "height": float(movement_h),
                    "alias": movement_alias(index + 1),
                }
            )
    core = {"left": 0.0, "top": 0.0, "width": float(core_w), "height": float(core_h)}
    camera = {"left": 0.0, "top": float(camera_top), "width": float(core_w), "height": float(camera_h)}
    movement = {"left": 0.0, "top": float(movement_top), "width": float(core_w), "height": float(movement_h)}
    hero = {
        "left": ERS_TOPDOWN_PANEL["left"] * 0,  # keep hero as panel 0 of CORE
        "top": 0.0,
        "width": (1.0 / 3.0) * core_w,
        "height": (1.0 / 3.0) * core_h,
    }
    hero = {"left": 0.0, "top": 0.0, "width": core_w / 3.0, "height": core_h / 3.0}
    return {
        "width": core_w,
        "height": total_h,
        "core": core,
        "cameraBand": camera,
        "movementBand": movement,
        "movementCells": cells,
        "heroPanel": hero,
    }


def _rects_overlap(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (
        a["left"] + a["width"] <= b["left"] + 0.5
        or b["left"] + b["width"] <= a["left"] + 0.5
        or a["top"] + a["height"] <= b["top"] + 0.5
        or b["top"] + b["height"] <= a["top"] + 0.5
    )


def validate_layout(rects: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    core = rects["core"]
    camera = rects["cameraBand"]
    movement = rects["movementBand"]
    hero = rects["heroPanel"]
    if _rects_overlap(core, camera):
        errors.append("core overlaps camera band")
    if movement["height"] and _rects_overlap(core, movement):
        errors.append("core overlaps movement band")
    if movement["height"] and _rects_overlap(camera, movement):
        errors.append("camera band overlaps movement band")
    if hero["top"] + hero["height"] > core["height"] + 0.5:
        errors.append("hero panel is not inside the core")
    if hero["left"] + hero["width"] > core["width"] / 3.0 + 1.0:
        errors.append("hero panel is not panel 0 of the core")
    cells = rects.get("movementCells") or []
    for i, cell in enumerate(cells):
        for other in cells[i + 1 :]:
            if _rects_overlap(cell, other):
                errors.append(f"movement cells {i} and {other['index']} overlap")
    return errors


def assemble_ers_with_movement_strip(
    image_path: str,
    document: Any | None = None,
    *,
    camera_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Paste the core onto a taller canvas and draw compact movement refs."""
    from PIL import Image, ImageDraw, ImageFont

    if document is not None:
        hydrate_movement_segments(document)
    segments = list(getattr(document, "movementSegments", None) or [])
    segments = sorted(segments, key=lambda s: int(getattr(s, "segmentNumber", 0) or 0))
    rects = layout_rects(ERS_CORE_WIDTH, movement_count=len(segments))
    with Image.open(image_path) as src:
        core = src.convert("RGBA")
        core_w, core_h = core_size(core.width, core.height)
        if core.height != core_h or core.width != core_w:
            core = core.crop((0, 0, core_w, core_h))
        if core.size != (int(rects["core"]["width"]), int(rects["core"]["height"])):
            core = core.resize((int(rects["core"]["width"]), int(rects["core"]["height"])), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (int(rects["width"]), int(rects["height"])), (12, 10, 22, 255))
        canvas.paste(core, (0, 0))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        cam_box = rects["cameraBand"]
        draw.rectangle(
            [cam_box["left"], cam_box["top"], cam_box["left"] + cam_box["width"], cam_box["top"] + cam_box["height"]],
            fill=(22, 18, 36, 255),
        )
        labels = camera_labels or [str(getattr(c, "label", "") or "Camera") for c in (getattr(document, "cameras", None) or [])]
        draw.text((16, cam_box["top"] + 16), "Camera Shot References", fill=(221, 214, 254, 255), font=font)
        if labels:
            draw.text((16, cam_box["top"] + 48), " · ".join(labels[:8]), fill=(196, 181, 253, 255), font=font)
        arrows = compute_arrows(document) if document is not None else []
        for cell, segment in zip(rects["movementCells"], segments):
            box = [
                cell["left"] + 8,
                cell["top"] + 8,
                cell["left"] + cell["width"] - 8,
                cell["top"] + cell["height"] - 8,
            ]
            draw.rounded_rectangle(box, radius=12, fill=(28, 22, 48, 255), outline=(167, 139, 250, 255), width=2)
            alias = movement_alias(int(getattr(segment, "segmentNumber", 0) or 0))
            beat = str(getattr(segment, "beatName", "") or "").strip()
            draw.text((box[0] + 12, box[1] + 10), alias + (f"  {beat}" if beat else ""), fill=(237, 233, 254, 255), font=font)
            chars = getattr(segment, "characterStates", None) or []
            for idx, char in enumerate(chars[:4]):
                nx = getattr(char, "normalizedX", None)
                ny = getattr(char, "normalizedY", None)
                if nx is None or ny is None:
                    continue
                px = box[0] + 24 + ((float(nx) + 1.0) / 2.0) * (box[2] - box[0] - 48)
                py = box[1] + 70 + ((float(ny) + 1.0) / 2.0) * (box[3] - box[1] - 110)
                draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(196, 181, 253, 255))
                draw.text((px + 8, py - 6), str(getattr(char, "label", "") or alias), fill=(237, 233, 254, 255), font=font)
                if idx == 0 and arrows:
                    draw.text((box[0] + 12, box[3] - 28), f"{arrows[0].get('fromAlias')}→{arrows[0].get('toAlias')}", fill=(196, 181, 253, 255), font=font)
        canvas.convert("RGB").save(image_path)
    return {"status": "assembled", "layout": rects, "movementCount": len(segments)}
