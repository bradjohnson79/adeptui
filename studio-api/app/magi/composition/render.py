"""Pillow-based deterministic flatten of overlay compositions onto a source image."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..overlays.fonts import resolve_font


def _load_pil():
    from PIL import Image, ImageDraw, ImageFont

    return Image, ImageDraw, ImageFont


def _font(ImageFont: Any, font_id: str | None, size: int, weight: int = 400):
    resolved = resolve_font(font_id)
    names = list((resolved.get("font") or {}).get("pillowNames") or ["DejaVuSans"])
    for name in names:
        try:
            return ImageFont.truetype(name, size=max(4, int(size))), resolved
        except Exception:
            continue
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ):
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=max(4, int(size))), resolved
            except Exception:
                continue
    return ImageFont.load_default(), resolved


def _px(norm: float, total: int) -> int:
    return int(round(float(norm) * total))


def _draw_vector(draw: Any, el: dict[str, Any], W: int, H: int) -> None:
    x = _px(el.get("x", 0), W)
    y = _px(el.get("y", 0), H)
    w = max(1, _px(el.get("width", 0.2), W))
    h = max(1, _px(el.get("height", 0.1), H))
    fill = el.get("fill")
    stroke = el.get("stroke")
    sw = int(el.get("strokeWidth") or 0)
    shape = el.get("shape") or "rectangle"
    opacity = float(el.get("opacity") if el.get("opacity") is not None else 1)
    if fill and isinstance(fill, str) and fill.startswith("#") and len(fill) == 7:
        r, g, b = int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16)
        fill_rgba = (r, g, b, int(255 * opacity))
    else:
        fill_rgba = None
    stroke_rgba = None
    if stroke and isinstance(stroke, str) and stroke.startswith("#") and len(stroke) == 7:
        r, g, b = int(stroke[1:3], 16), int(stroke[3:5], 16), int(stroke[5:7], 16)
        stroke_rgba = (r, g, b, int(255 * opacity))

    box = [x, y, x + w, y + h]
    if shape in ("rectangle", "accent_bar", "divider"):
        draw.rectangle(box, fill=fill_rgba, outline=stroke_rgba, width=max(sw, 0))
    elif shape == "rounded_rectangle":
        rr = int(el.get("cornerRadius") or 8)
        draw.rounded_rectangle(box, radius=rr, fill=fill_rgba, outline=stroke_rgba, width=max(sw, 0))
    elif shape in ("circle", "ellipse"):
        draw.ellipse(box, fill=fill_rgba, outline=stroke_rgba, width=max(sw, 0))
    elif shape == "line":
        draw.line([(x, y + h // 2), (x + w, y + h // 2)], fill=stroke_rgba or fill_rgba, width=max(sw, 2))
    elif shape == "triangle":
        draw.polygon([(x + w // 2, y), (x + w, y + h), (x, y + h)], fill=fill_rgba, outline=stroke_rgba)
    elif shape == "chevron":
        draw.polygon(
            [(x, y), (x + w * 0.7, y), (x + w, y + h // 2), (x + w * 0.7, y + h), (x, y + h), (x + w * 0.25, y + h // 2)],
            fill=fill_rgba,
            outline=stroke_rgba,
        )


def _draw_text(img: Any, ImageDraw: Any, ImageFont: Any, el: dict[str, Any], W: int, H: int, fonts_used: list) -> None:
    if el.get("visible") is False:
        return
    style = el.get("textStyle") or {}
    text = str(el.get("text") or "")
    size = float(style.get("fontSize") or 32)
    # fontSize is composition pixels when > 1, else treat as normalized
    font_px = int(size if size > 3 else size * H)
    font, resolved = _font(ImageFont, style.get("fontFamily") or style.get("fontId"), font_px, int(style.get("fontWeight") or 400))
    fonts_used.append(
        {
            "elementId": el.get("id"),
            "requested": style.get("fontFamily") or style.get("fontId"),
            "resolved": (resolved.get("font") or {}).get("id"),
            "substituted": bool(resolved.get("substituted")),
        }
    )
    x = _px(el.get("x", 0.1), W)
    y = _px(el.get("y", 0.1), H)
    w = max(1, _px(el.get("width", 0.4), W))
    h = max(1, _px(el.get("height", 0.1), H))
    opacity = float(el.get("opacity") if el.get("opacity") is not None else 1)
    color = style.get("color") or "#FFFFFF"
    if isinstance(color, str) and color.startswith("#") and len(color) == 7:
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fill = (r, g, b, int(255 * opacity))
    else:
        fill = (255, 255, 255, int(255 * opacity))

    from PIL import Image as PILImage

    layer = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bg = el.get("backgroundStyle") or {}
    if bg.get("enabled"):
        bf = bg.get("fill") or "#000000"
        bop = float(bg.get("opacity") if bg.get("opacity") is not None else 0.55)
        if isinstance(bf, str) and bf.startswith("#") and len(bf) == 7:
            br, bgc, bb = int(bf[1:3], 16), int(bf[3:5], 16), int(bf[5:7], 16)
            pad_t = int(bg.get("paddingTop") or 6)
            pad_r = int(bg.get("paddingRight") or 10)
            pad_b = int(bg.get("paddingBottom") or 6)
            pad_l = int(bg.get("paddingLeft") or 10)
            rr = int(bg.get("cornerRadius") or 0)
            box = [0, 0, w - 1, h - 1]
            # inset by nothing — fill full element; padding reserved for text
            fill_bg = (br, bgc, bb, int(255 * bop * opacity))
            if rr > 0:
                draw.rounded_rectangle(box, radius=rr, fill=fill_bg)
            else:
                draw.rectangle(box, fill=fill_bg)
            tx, ty = pad_l, pad_t
        else:
            tx, ty = 8, 6
    else:
        tx, ty = 0, 0

    if style.get("uppercase"):
        text = text.upper()
    if style.get("shadowEnabled"):
        sc = style.get("shadowColor") or "#000000"
        if isinstance(sc, str) and sc.startswith("#") and len(sc) == 7:
            sr, sg, sb = int(sc[1:3], 16), int(sc[3:5], 16), int(sc[5:7], 16)
            ox = int(style.get("shadowOffsetX") or 2)
            oy = int(style.get("shadowOffsetY") or 2)
            draw.text((tx + ox, ty + oy), text, font=font, fill=(sr, sg, sb, int(180 * opacity)))
    stroke_w = int(style.get("strokeWidth") or 0)
    stroke_c = style.get("strokeColor")
    if stroke_w > 0 and stroke_c:
        # simple outline via multi-offset
        if isinstance(stroke_c, str) and stroke_c.startswith("#") and len(stroke_c) == 7:
            cr, cg, cb = int(stroke_c[1:3], 16), int(stroke_c[3:5], 16), int(stroke_c[5:7], 16)
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx or dy:
                        draw.text((tx + dx, ty + dy), text, font=font, fill=(cr, cg, cb, int(255 * opacity)))
    draw.text((tx, ty), text, font=font, fill=fill)

    rot = float(el.get("rotation") or 0)
    if abs(rot) > 0.01:
        layer = layer.rotate(-rot, expand=True, resample=PILImage.BICUBIC)
    img.alpha_composite(layer, (x, y))


def _walk(img: Any, ImageDraw: Any, ImageFont: Any, els: list[dict[str, Any]], W: int, H: int, fonts_used: list) -> None:
    ordered = sorted(els, key=lambda e: int(e.get("zIndex") or 0))
    for el in ordered:
        if el.get("visible") is False or el.get("locked") and False:
            if el.get("visible") is False:
                continue
        t = el.get("type")
        if t == "vector":
            # draw on temp layer for opacity
            from PIL import Image as PILImage

            layer = PILImage.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            _draw_vector(d, el, W, H)
            img.alpha_composite(layer)
        elif t == "text":
            _draw_text(img, ImageDraw, ImageFont, el, W, H, fonts_used)
        elif t == "group":
            _walk(img, ImageDraw, ImageFont, list(el.get("children") or []), W, H, fonts_used)


def render_composition_to_png(
    *,
    source_image_path: str | Path | None,
    composition: dict[str, Any],
    out_path: str | Path,
) -> dict[str, Any]:
    Image, ImageDraw, ImageFont = _load_pil()
    W = int(composition.get("canvasWidth") or 1920)
    H = int(composition.get("canvasHeight") or 1080)
    if source_image_path and Path(source_image_path).is_file():
        base = Image.open(source_image_path).convert("RGBA")
        W, H = base.size
        # keep composition dims for provenance but render at source size
    else:
        base = Image.new("RGBA", (W, H), (0, 0, 0, 255))

    fonts_used: list[dict[str, Any]] = []
    overlays = list(composition.get("overlays") or [])
    _walk(base, ImageDraw, ImageFont, overlays, base.width, base.height, fonts_used)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    base.save(out, "PNG")
    return {
        "path": str(out),
        "width": base.width,
        "height": base.height,
        "overlayIds": [e.get("id") for e in overlays if e.get("id")],
        "fontsUsed": fonts_used,
        "schemaVersion": composition.get("schemaVersion"),
        "compositionId": composition.get("compositionId"),
        "sourceAssetId": composition.get("sourceAssetId"),
        "animationCertified": False,
        "staticRender": True,
    }
