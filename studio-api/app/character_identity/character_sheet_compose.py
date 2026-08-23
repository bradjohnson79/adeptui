"""Adept-drawn Character Reference Sheet compositor (G11).

Image generators produce visual tiles only. This module owns titles, view
labels, notes, wardrobe/gear, and technical specs. It does not invent
character biography: panel bodies come from profile fields or an empty
placeholder. Detail macros are omitted when not supplied (no fake pixels).
"""

from __future__ import annotations

from typing import Any, Sequence

# Law view order matches visual_sheet.CANDIDATE_SHEET_VIEW_ROLES.
LAW_VIEW_ROLES: tuple[str, ...] = (
    "hero_identity",
    "full_body_three_quarter_front",
    "full_body_side_left",
    "full_body_back",
    "closeup_front",
)
LAW_VIEW_DISPLAY_LABELS: tuple[str, ...] = (
    "Front",
    "3/4",
    "Side",
    "Back",
    "Close-Up",
)
LAW_VIEW_ROLE_TO_LABEL: dict[str, str] = dict(zip(LAW_VIEW_ROLES, LAW_VIEW_DISPLAY_LABELS))

# 2K production document. Long edge is 2560 (prefer), never below 2048.
CRS_SHEET_LONG_EDGE = 2560
CRS_SHEET_MIN_LONG_EDGE = 2048

PANEL_NOTES = "notes"
PANEL_WARDROBE = "wardrobe"
PANEL_SPECS = "specs"
PANEL_TITLES: dict[str, str] = {
    PANEL_NOTES: "Character Notes",
    PANEL_WARDROBE: "Wardrobe / Gear",
    PANEL_SPECS: "Technical Specs",
}
EMPTY_PLACEHOLDER = "—"

_PAD = 28
_GAP = 18
_HEADER_H = 100
_LABEL_BAR_H = 36
_BG = (18, 18, 20)
_TILE_BG = (24, 24, 24)
_BAR = (10, 10, 12)
_TEXT = (244, 244, 248)
_MUTED = (168, 172, 184)
_GOLD = (210, 186, 128)
_PANEL_BG = (22, 22, 26)
_PANEL_LINE = (48, 48, 56)
_BODY = (196, 198, 206)


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _join_fields(items: Sequence[Any]) -> str:
    parts = [str(item).strip() for item in items if str(item or "").strip()]
    return "; ".join(parts)


def sheet_texts_from_profile(profile: dict[str, Any] | None) -> dict[str, str]:
    """Pull Adept-drawn panel copy from profile fields only.

    Missing fields stay empty. Callers render section headers plus
    EMPTY_PLACEHOLDER rather than inventing biography.
    """
    blob = dict(profile or {})
    name = _first_text(blob.get("name"))
    role = _first_text(blob.get("role"))
    notes = _first_text(
        blob.get("notes"),
        blob.get("description"),
        blob.get("visual_description"),
    )
    wardrobe = blob.get("active_wardrobe") or blob.get("wardrobe") or {}
    if isinstance(wardrobe, str):
        wardrobe_txt = wardrobe.strip()
    elif isinstance(wardrobe, dict):
        wardrobe_txt = _join_fields(
            [
                wardrobe.get("name"),
                wardrobe.get("description"),
                wardrobe.get("materials"),
                wardrobe.get("colors"),
                wardrobe.get("footwear"),
                wardrobe.get("accessories"),
            ]
        )
    else:
        wardrobe_txt = ""
    spec_bits: list[str] = []
    height = _first_text(blob.get("height_description"), blob.get("height"))
    if height:
        spec_bits.append(f"Height: {height}")
    body = _first_text(blob.get("body_type"))
    if body:
        spec_bits.append(f"Body: {body}")
    species = _first_text(blob.get("species_or_type"))
    if species:
        spec_bits.append(f"Type: {species}")
    return {
        "name": name,
        "role": role,
        "notes": notes,
        "wardrobe": wardrobe_txt,
        "specs": " · ".join(spec_bits),
        "height": height,
    }


def _font(size: int):
    from PIL import ImageFont

    candidates = (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, width: int) -> list[str]:
    raw = (text or "").replace("\r", "").strip()
    if not raw:
        return [EMPTY_PLACEHOLDER]
    lines: list[str] = []
    for paragraph in raw.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [EMPTY_PLACEHOLDER]


def plan_labeled_character_sheet(
    view_count: int = 5,
    *,
    profile: dict[str, Any] | None = None,
    labels: Sequence[str] | None = None,
    roles: Sequence[str] | None = None,
    long_edge: int = CRS_SHEET_LONG_EDGE,
) -> dict[str, Any]:
    """Deterministic 5-view 3x2 CRS layout with header + text panels.

    Returns regions and the exact strings Adept will draw. Tests should
    assert this contract rather than OCR.
    """
    if view_count != 5:
        raise ValueError(f"labeled law sheet plans 5 views, got {view_count}")
    edge = max(int(long_edge or CRS_SHEET_LONG_EDGE), CRS_SHEET_MIN_LONG_EDGE)
    cols, rows = 3, 2
    inner_w = edge - (2 * _PAD)
    tile = (inner_w - (cols - 1) * _GAP) // cols
    grid_w = cols * tile + (cols - 1) * _GAP
    grid_h = rows * tile + (rows - 1) * _GAP
    ox = _PAD + (inner_w - grid_w) // 2
    oy = _HEADER_H
    width = edge
    height = _HEADER_H + grid_h + _PAD

    view_roles = list(roles or LAW_VIEW_ROLES)
    view_labels = list(labels or LAW_VIEW_DISPLAY_LABELS)
    if len(view_labels) < 5:
        view_labels = list(LAW_VIEW_DISPLAY_LABELS)
    if len(view_roles) < 5:
        view_roles = list(LAW_VIEW_ROLES)

    texts = sheet_texts_from_profile(profile)
    header_bbox = [_PAD, 12, width - _PAD, _HEADER_H - 8]
    views: list[dict[str, Any]] = []
    for idx in range(5):
        col = idx % cols
        row = idx // cols
        x0 = ox + col * (tile + _GAP)
        y0 = oy + row * (tile + _GAP)
        x1 = x0 + tile
        y1 = y0 + tile
        views.append(
            {
                "index": idx,
                "role": view_roles[idx],
                "label": view_labels[idx],
                "bbox": [x0, y0, x1, y1],
                "labelBbox": [x0, y1 - _LABEL_BAR_H, x1, y1],
            }
        )

    tx0 = ox + 2 * (tile + _GAP)
    ty0 = oy + 1 * (tile + _GAP)
    tx1 = tx0 + tile
    ty1 = ty0 + tile
    text_cell = {"bbox": [tx0, ty0, tx1, ty1], "reserved": "notes_wardrobe_specs"}
    band_h = (ty1 - ty0) // 3
    panel_specs = (
        (PANEL_NOTES, texts["notes"]),
        (PANEL_WARDROBE, texts["wardrobe"]),
        (PANEL_SPECS, texts["specs"]),
    )
    panels: list[dict[str, Any]] = []
    for i, (pid, body) in enumerate(panel_specs):
        y0 = ty0 + i * band_h
        y1 = ty1 if i == 2 else y0 + band_h
        panels.append(
            {
                "id": pid,
                "title": PANEL_TITLES[pid],
                "text": body,
                "placeholder": not bool(body),
                "bbox": [tx0, y0, tx1, y1],
            }
        )

    drawn: list[str] = []
    if texts["name"]:
        drawn.append(texts["name"])
    if texts["role"]:
        drawn.append(texts["role"])
    drawn.extend(view_labels[:5])
    for panel in panels:
        drawn.append(panel["title"])
        drawn.append(panel["text"] if panel["text"] else EMPTY_PLACEHOLDER)

    return {
        "layout": "law_views_labeled",
        "composer": "adept",
        "width": width,
        "height": height,
        "longEdge": max(width, height),
        "minLongEdge": CRS_SHEET_MIN_LONG_EDGE,
        "grid": {
            "cols": cols,
            "rows": rows,
            "tileSize": tile,
            "gap": _GAP,
            "pad": _PAD,
        },
        "header": {
            "name": texts["name"],
            "role": texts["role"],
            "bbox": header_bbox,
        },
        "labels": list(view_labels[:5]),
        "views": views,
        "textCell": text_cell,
        "panels": panels,
        "drawnStrings": drawn,
        "profileTexts": texts,
    }


def compose_labeled_character_sheet(
    view_paths: Sequence[str],
    out_path: str,
    *,
    profile: dict[str, Any] | None = None,
    labels: Sequence[str] | None = None,
    roles: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compose 5 law-view tiles into a labeled 2K CRS document."""
    from PIL import Image, ImageDraw, ImageOps

    paths = [str(p) for p in view_paths]
    if len(paths) != 5:
        raise ValueError(f"labeled law sheet requires 5 view images, got {len(paths)}")

    layout = plan_labeled_character_sheet(
        5, profile=profile, labels=labels, roles=roles
    )
    canvas = Image.new("RGB", (layout["width"], layout["height"]), _BG)
    draw = ImageDraw.Draw(canvas)
    title_font = _font(42)
    role_font = _font(24)
    label_font = _font(22)
    panel_title_font = _font(18)
    panel_body_font = _font(15)

    header = layout["header"]
    hx0, hy0, hx1, hy1 = header["bbox"]
    name = header.get("name") or ""
    role = header.get("role") or ""
    if name:
        draw.text((hx0, hy0 + 6), name, font=title_font, fill=_TEXT)
    if role:
        name_w = int(draw.textlength(name, font=title_font)) if name else 0
        rx = hx0 + (name_w + 28 if name else 0)
        if name and rx + 40 < hx1:
            draw.text((rx, hy0 + 20), role, font=role_font, fill=_MUTED)
        else:
            draw.text((hx0, hy0 + 54), role, font=role_font, fill=_MUTED)

    resample = getattr(Image, "Resampling", Image).LANCZOS
    for cell, src in zip(layout["views"], paths):
        x0, y0, x1, y1 = cell["bbox"]
        tw, th = x1 - x0, y1 - y0
        tile = Image.new("RGB", (tw, th), _TILE_BG)
        im = Image.open(src).convert("RGB")
        contained = ImageOps.contain(im, (tw, th), method=resample)
        tile.paste(
            contained,
            ((tw - contained.width) // 2, (th - contained.height) // 2),
        )
        canvas.paste(tile, (x0, y0))
        lx0, ly0, lx1, ly1 = cell["labelBbox"]
        draw.rectangle([lx0, ly0, lx1 - 1, ly1 - 1], fill=_BAR)
        label = cell["label"]
        lw = int(draw.textlength(label, font=label_font))
        tx = lx0 + max(8, (lx1 - lx0 - lw) // 2)
        draw.text((tx, ly0 + 6), label, font=label_font, fill=_TEXT)

    for panel in layout["panels"]:
        x0, y0, x1, y1 = panel["bbox"]
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=_PANEL_BG, outline=_PANEL_LINE)
        draw.text((x0 + 10, y0 + 8), panel["title"], font=panel_title_font, fill=_GOLD)
        body = panel["text"] if panel["text"] else EMPTY_PLACEHOLDER
        for i, line in enumerate(_wrap(draw, body, panel_body_font, x1 - x0 - 20)):
            yy = y0 + 32 + i * 18
            if yy + 16 > y1 - 6:
                break
            draw.text((x0 + 10, yy), line, font=panel_body_font, fill=_BODY)

    dest = str(out_path)
    canvas.save(dest, format="PNG")
    layout["path"] = dest
    return layout


V2_SHEET_WIDTH = 2560
V2_SHEET_HEIGHT = 1080


def _v2_table_lines(profile: dict[str, Any] | None, extra_facts: dict[str, Any] | None) -> list[tuple[str, str]]:
    texts = sheet_texts_from_profile(profile)
    facts = dict(extra_facts or {})
    rows = [
        ("Name", texts.get("name") or _first_text((profile or {}).get("name"))),
        ("Style", _first_text((profile or {}).get("visual_style"))),
        ("Gender", _first_text((profile or {}).get("gender_presentation"))),
        ("Description", texts.get("notes")),
        ("Build", texts.get("specs")),
        ("Hair", _first_text(facts.get("hair"), facts.get("rear_hair"), facts.get("hair_front"))),
        ("Wardrobe", _first_text(texts.get("wardrobe"), facts.get("wardrobe"), facts.get("back_of_wardrobe"))),
        ("Colors", _first_text(facts.get("colors"), facts.get("colors_from_rear"))),
    ]
    return [(label, value or EMPTY_PLACEHOLDER) for label, value in rows]


def compose_v2_character_sheet(
    front_path: str,
    back_path: str,
    out_path: str,
    *,
    profile: dict[str, Any] | None = None,
    extra_facts: dict[str, Any] | None = None,
    closeup_path: str | None = None,
) -> dict[str, Any]:
    """Deterministic 21:9 (2560x1080) FRONT | BACK | JSON table.

    Optional Standard close-up sits bottom-center under the two views.
    No model layout. Missing table fields print as —.
    """
    from PIL import Image, ImageDraw, ImageOps

    width, height = V2_SHEET_WIDTH, V2_SHEET_HEIGHT
    pad, gap = 24, 16
    table_w = 640
    views_w = width - pad * 2 - gap - table_w
    closeup_band = 220 if closeup_path else 0
    view_h = height - pad * 2 - (closeup_band + gap if closeup_band else 0)
    tile_w = (views_w - gap) // 2

    canvas = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(canvas)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    label_font = _font(22)
    title_font = _font(20)
    body_font = _font(16)

    def _paste(src: str, bbox: tuple[int, int, int, int], label: str) -> None:
        x0, y0, x1, y1 = bbox
        tw, th = x1 - x0, y1 - y0
        tile = Image.new("RGB", (tw, th), _TILE_BG)
        im = Image.open(src).convert("RGB")
        contained = ImageOps.contain(im, (tw, th - _LABEL_BAR_H), method=resample)
        tile.paste(contained, ((tw - contained.width) // 2, (th - _LABEL_BAR_H - contained.height) // 2))
        canvas.paste(tile, (x0, y0))
        draw.rectangle([x0, y1 - _LABEL_BAR_H, x1 - 1, y1 - 1], fill=_BAR)
        lw = int(draw.textlength(label, font=label_font))
        draw.text((x0 + max(8, (tw - lw) // 2), y1 - _LABEL_BAR_H + 6), label, font=label_font, fill=_TEXT)

    fx0 = pad
    fy0 = pad
    fx1 = fx0 + tile_w
    fy1 = fy0 + view_h
    bx0 = fx1 + gap
    bx1 = bx0 + tile_w
    _paste(front_path, (fx0, fy0, fx1, fy1), "Front")
    _paste(back_path, (bx0, fy0, bx1, fy1), "Back")

    if closeup_path:
        cw = min(360, views_w // 2)
        cx0 = pad + (views_w - cw) // 2
        cy0 = fy1 + gap
        _paste(closeup_path, (cx0, cy0, cx0 + cw, height - pad), "Close-up")

    tx0 = pad + views_w + gap
    ty0 = pad
    tx1 = width - pad
    ty1 = height - pad
    draw.rectangle([tx0, ty0, tx1 - 1, ty1 - 1], fill=_PANEL_BG, outline=_PANEL_LINE)
    draw.text((tx0 + 14, ty0 + 10), "Character", font=title_font, fill=_GOLD)
    y = ty0 + 42
    drawn = ["Character"]
    for label, value in _v2_table_lines(profile, extra_facts):
        draw.text((tx0 + 14, y), f"{label}", font=title_font, fill=_MUTED)
        y += 22
        for line in _wrap(draw, value, body_font, tx1 - tx0 - 28):
            draw.text((tx0 + 14, y), line, font=body_font, fill=_BODY)
            drawn.append(f"{label}: {line}")
            y += 18
            if y > ty1 - 24:
                break
        y += 8
        if y > ty1 - 24:
            break

    dest = str(out_path)
    canvas.save(dest, format="PNG")
    return {
        "layout": "v2_21x9",
        "composer": "adept",
        "width": width,
        "height": height,
        "path": dest,
        "hasCloseup": bool(closeup_path),
        "drawnStrings": drawn,
        "grid": {"cols": 3, "rows": 1, "tileSize": tile_w, "gap": gap, "pad": pad},
    }
