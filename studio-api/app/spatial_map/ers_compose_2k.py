"""Deterministic 2K ERS composition. Never sent through GPT Image 2."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .background_alignment import clamp_scale, hydrate_alignment, pixels_from_alignment
from .ers_packet import COMPONENT_LABELS, human_readable_summary

PANEL_ORDER = ("spatial_map", "master", "north", "east", "south", "west", "three_d", "occupied", "json")
COLLAGE_OCCUPIED_REGION = {"left": 2.0 / 3.0, "top": 2.0 / 3.0, "width": 1.0 / 3.0, "height": 1.0 / 3.0}
ALLOWED_ASPECTS = ("16:9", "21:9", "4:3", "1:1")


def score_layout(aspect: str, *, map_cells: int, json_lines: int) -> float:
    """Higher is better. Prefer wider sheets when JSON or map would be cramped."""
    base = {"16:9": 1.0, "21:9": 0.95, "4:3": 0.82, "1:1": 0.7}[aspect]
    if json_lines > 14 and aspect in {"1:1", "4:3"}:
        base -= 0.25
    if map_cells >= 8 and aspect == "1:1":
        base -= 0.15
    if aspect == "16:9":
        base += 0.08
    return base


def choose_aspect(*, map_cells: int = 0, json_lines: int = 0) -> str:
    return max(ALLOWED_ASPECTS, key=lambda a: score_layout(a, map_cells=map_cells, json_lines=json_lines))


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _contain_atlas(
    src: Image.Image,
    size: int,
    offset_x: float,
    offset_y: float,
    scale: float = 1.0,
) -> Image.Image:
    """xMidYMid meet into a square (letterbox/pillarbox), then translate."""
    canvas = Image.new("RGB", (size, size), (28, 34, 42))
    sw, sh = src.size
    if sw <= 0 or sh <= 0:
        return canvas
    draw = min(size / sw, size / sh) * clamp_scale(scale)
    nw = max(1, int(round(sw * draw)))
    nh = max(1, int(round(sh * draw)))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = (size - nw) // 2 + int(round(pixels_from_alignment(offset_x, size)))
    oy = (size - nh) // 2 + int(round(pixels_from_alignment(offset_y, size)))
    canvas.paste(resized, (ox, oy))
    return canvas


def render_spatial_map_panel(
    packet: dict[str, Any],
    size: int = 768,
    atlas_bytes: bytes | None = None,
) -> Image.Image:
    alignment = hydrate_alignment(packet.get("backgroundAlignment"))
    img = Image.new("RGB", (size, size), (28, 34, 42))
    if atlas_bytes:
        try:
            atlas = Image.open(BytesIO(atlas_bytes)).convert("RGB")
            contained = _contain_atlas(
                atlas, size, alignment["offsetX"], alignment["offsetY"], alignment["scale"]
            )
            img.paste(contained, (0, 0))
        except Exception:
            atlas_bytes = None

    draw = ImageDraw.Draw(img)
    cells = 10
    step = size / cells
    for i in range(cells + 1):
        x = i * step
        draw.line([(x, 0), (x, size)], fill=(70, 82, 96), width=1)
        draw.line([(0, x), (size, x)], fill=(70, 82, 96), width=1)
    draw.text((12, 6), "1 square = 1 meter   N=top", fill=(210, 218, 226), font=_font(14))

    def _xy(item: dict[str, Any]) -> tuple[int, int] | None:
        x, y = item.get("x"), item.get("y")
        if x is None or y is None:
            return None
        # Same square space as SpatialGrid — do not add background offset.
        px = int((float(x) + 1) / 2 * size)
        py = int((float(y) + 1) / 2 * size)
        return px, py

    for c in packet.get("characters") or []:
        pt = _xy(c)
        if not pt:
            continue
        draw.ellipse((pt[0] - 7, pt[1] - 7, pt[0] + 7, pt[1] + 7), fill=(46, 196, 182))
    for p in packet.get("props") or []:
        pt = _xy(p)
        if not pt:
            continue
        draw.rectangle((pt[0] - 6, pt[1] - 6, pt[0] + 6, pt[1] + 6), fill=(232, 168, 56))
    for cam in packet.get("cameras") or []:
        pt = _xy(cam)
        if not pt:
            continue
        draw.polygon([(pt[0], pt[1] - 8), (pt[0] + 8, pt[1] + 6), (pt[0] - 8, pt[1] + 6)], fill=(120, 170, 255))
    return img


def render_json_panel(packet: dict[str, Any], size: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size, (22, 28, 36))
    draw = ImageDraw.Draw(img)
    font = _font(18)
    y = 16
    for line in human_readable_summary(packet):
        draw.text((16, y), line[:90], fill=(230, 236, 242), font=font)
        y += 22
        if y > size[1] - 24:
            break
    return img


def compose_ers_sheet(
    *,
    packet: dict[str, Any],
    panels: dict[str, Image.Image],
    width: int,
    height: int,
) -> Image.Image:
    sheet = Image.new("RGB", (width, height), (14, 18, 24))
    draw = ImageDraw.Draw(sheet)
    label_font = _font(18)
    has_occupied = panels.get("occupied") is not None
    cols, rows = (5, 2) if has_occupied else (4, 2)
    gw, gh = width // cols, height // rows
    slots = {
        "spatial_map": (0, 0),
        "master": (1, 0),
        "north": (2, 0),
        "east": (3, 0),
        "south": (0, 1),
        "west": (1, 1),
        "three_d": (2, 1),
        "json": (3, 1),
    }
    if has_occupied:
        slots["occupied"] = (4, 0)
        slots["json"] = (4, 1)
    for key, (cx, cy) in slots.items():
        box = (cx * gw + 8, cy * gh + 28, (cx + 1) * gw - 8, (cy + 1) * gh - 8)
        bw, bh = box[2] - box[0], box[3] - box[1]
        src = panels.get(key)
        if src is None:
            src = Image.new("RGB", (bw, bh), (34, 42, 52))
        fitted = src.copy()
        fitted.thumbnail((bw, bh))
        ox = box[0] + (bw - fitted.width) // 2
        oy = box[1] + (bh - fitted.height) // 2
        sheet.paste(fitted, (ox, oy))
        draw.text((box[0], cy * gh + 6), COMPONENT_LABELS.get(key, key.upper()), fill=(236, 242, 248), font=label_font)
    return sheet


def compose_ers_png(
    packet: dict[str, Any],
    images: dict[str, bytes],
    *,
    width: int,
    height: int,
) -> bytes:
    panels: dict[str, Image.Image] = {
        "spatial_map": render_spatial_map_panel(packet, atlas_bytes=images.get("atlas")),
        "json": render_json_panel(packet, (640, 640)),
    }
    for key in ("master", "north", "east", "south", "west", "three_d", "occupied"):
        raw = images.get(key)
        if raw:
            panels[key] = Image.open(BytesIO(raw)).convert("RGB")
    sheet = compose_ers_sheet(packet=packet, panels=panels, width=width, height=height)
    out = BytesIO()
    sheet.save(out, format="PNG")
    return out.getvalue()


def _cover_fit(src: Image.Image, dest_w: int, dest_h: int) -> Image.Image:
    """Scale to fill dest, center-crop overflow. No letterbox, no stretch."""
    dest_w = max(1, int(dest_w))
    dest_h = max(1, int(dest_h))
    sw, sh = src.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGB", (dest_w, dest_h), (20, 24, 30))
    scale = max(dest_w / sw, dest_h / sh)
    nw = max(1, int(round(sw * scale)))
    nh = max(1, int(round(sh * scale)))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - dest_w) // 2)
    top = max(0, (nh - dest_h) // 2)
    return resized.crop((left, top, left + dest_w, top + dest_h))


def compose_occupied_into_collage(
    collage_bytes: bytes,
    occupied_bytes: bytes,
    region: dict[str, float] | None = None,
    *,
    collage_asset_id: str = "",
    template_id: str = "",
) -> bytes:
    """Replace the canonical Occupied rectangle on a clean 16:9 sheet.

    Never restitch onto 2560x2220 chrome. The replacement fills the full
    Panel 9 bounds (no smaller inset overlay). Unknown or size-mismatched
    (unscaled) templates still fail closed.
    """
    from .ers_collage_templates import (
        GALLERY_3X3_V1,
        canonical_panel9_box,
        resolve_occupied_region,
        visual_ers_canvas_size,
    )

    collage = Image.open(BytesIO(collage_bytes)).convert("RGB")
    occupied = Image.open(BytesIO(occupied_bytes)).convert("RGB")
    w, h = collage.size
    gallery = str(template_id or "") == GALLERY_3X3_V1
    if gallery:
        resolved = resolve_occupied_region(
            (w, h),
            collage_asset_id=collage_asset_id,
            template_id=template_id,
            gallery_region=(region or COLLAGE_OCCUPIED_REGION),
        )
        box = (
            int(round(w * float(resolved["left"]))),
            int(round(h * float(resolved["top"]))),
            int(round(w * (float(resolved["left"]) + float(resolved["width"])))),
            int(round(h * (float(resolved["top"]) + float(resolved["height"])))),
        )
        canvas = collage
    else:
        # Fail closed for missing / mismatched contracts, then crop 2220 chrome
        # to 16:9 and replace canonical Panel 9 on that visual canvas.
        resolve_occupied_region(
            (w, h),
            collage_asset_id=collage_asset_id,
            template_id=template_id,
            gallery_region=None,
        )
        vis_w, vis_h = visual_ers_canvas_size(w, h)
        if (w, h) != (vis_w, vis_h):
            canvas = collage.crop((0, 0, vis_w, vis_h))
        else:
            canvas = collage
        box = canonical_panel9_box(canvas.size)
    box = (
        max(0, min(canvas.size[0], box[0])),
        max(0, min(canvas.size[1], box[1])),
        max(0, min(canvas.size[0], box[2])),
        max(0, min(canvas.size[1], box[3])),
    )
    bw, bh = max(1, box[2] - box[0]), max(1, box[3] - box[1])
    fitted = _cover_fit(occupied, bw, bh)
    canvas.paste(fitted, (box[0], box[1]))
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
