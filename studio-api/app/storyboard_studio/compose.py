"""Deterministic 2K storyboard compositor — paste Library pixels, draw captions.

AI does not redraw the board. Adept assembles the sheet.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import settings
from ..db import Asset, Project, SessionLocal
from .documents import hydrate_panels

CANVAS_W = 2560
CANVAS_H = 1440
HEADER_H = 88
CAPTION_H = 56
GAP = 12
MARGIN = 24
BG = (18, 20, 24)
HEADER_FG = (236, 236, 236)
CAPTION_FG = (230, 230, 230)
TILE_BG = (8, 8, 10)

PAGE_GRIDS: dict[int, tuple[int, int]] = {
    6: (3, 2),
    9: (3, 3),
    12: (4, 3),
}


def grid_for_page_size(page_size: int) -> tuple[int, int]:
    return PAGE_GRIDS.get(int(page_size), (3, 3))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:2]


def _resolve_asset_path(db, asset_id: str | None) -> Path | None:
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if not asset or not asset.path:
        return None
    path = Path(asset.path)
    if path.is_file():
        return path
    return None


def _fit_tile(src: Image.Image, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (width, height), TILE_BG)
    contained = ImageOps.contain(src.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    x = (width - contained.width) // 2
    y = (height - contained.height) // 2
    canvas.paste(contained, (x, y))
    return canvas


def compose_page_image(
    *,
    title: str,
    project_name: str,
    page_index: int,
    page_count: int,
    page_size: int,
    slots: list[dict[str, Any]],
    asset_paths: dict[str, Path],
) -> Image.Image:
    cols, rows = grid_for_page_size(page_size)
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(canvas)
    title_font = _font(28)
    meta_font = _font(16)
    caption_font = _font(15)
    header = f"{project_name}  ·  {title}  ·  Page {page_index + 1} of {page_count}"
    draw.text((MARGIN, 22), header, font=title_font, fill=HEADER_FG)
    draw.text((MARGIN, 58), f"{page_size}-panel storyboard  ·  {CANVAS_W}×{CANVAS_H}", font=meta_font, fill=(170, 174, 180))

    usable_w = CANVAS_W - 2 * MARGIN - GAP * (cols - 1)
    usable_h = CANVAS_H - HEADER_H - MARGIN - GAP * (rows - 1)
    tile_w = usable_w // cols
    tile_h = usable_h // rows
    image_h = max(40, tile_h - CAPTION_H)

    for idx in range(page_size):
        col = idx % cols
        row = idx // cols
        x = MARGIN + col * (tile_w + GAP)
        y = HEADER_H + row * (tile_h + GAP)
        slot = slots[idx] if idx < len(slots) else {}
        aid = slot.get("assetId")
        src_path = asset_paths.get(str(aid)) if aid else None
        if src_path and src_path.is_file():
            try:
                im = Image.open(src_path)
                tile = _fit_tile(im, tile_w, image_h)
                canvas.paste(tile, (x, y))
            except Exception:
                draw.rectangle([x, y, x + tile_w, y + image_h], fill=TILE_BG)
        else:
            draw.rectangle([x, y, x + tile_w, y + image_h], fill=TILE_BG)
            draw.text((x + 12, y + image_h // 2), "Empty", font=caption_font, fill=(120, 120, 120))
        caption = str(slot.get("label") or "")
        cy = y + image_h + 6
        for line in _wrap(draw, caption, caption_font, tile_w - 8):
            draw.text((x + 4, cy), line, font=caption_font, fill=CAPTION_FG)
            cy += 18
    return canvas


def compose_storyboard_2k(
    project_id: str,
    *,
    document_id: str | None = None,
    page_index: int = 0,
) -> dict[str, Any]:
    workspace = hydrate_panels(project_id, document_id)
    doc = workspace.get("document") or {}
    panels = list(workspace.get("panels") or [])
    page_size = int(doc.get("pageSize") or 9)
    pages = list(doc.get("pages") or [])
    if not pages:
        return {"ok": False, "error": "storyboard has no pages"}
    if page_index < 0 or page_index >= len(pages):
        return {"ok": False, "error": "page not found"}
    page = pages[page_index]
    page_panels = [p for p in panels if int(p.get("pageIndex") or 0) == page_index]
    while len(page_panels) < page_size:
        page_panels.append({"assetId": None, "label": ""})
    if any(not p.get("assetId") for p in page_panels[:page_size]):
        return {"ok": False, "error": "Fill every slot on this page before generating the 2K storyboard."}

    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"storyboard_2k_p{page_index + 1}_{uuid.uuid4().hex[:8]}.png"
    out_path = dest_dir / out_name

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project_name = (project.name if project else None) or "Project"
        paths: dict[str, Path] = {}
        for panel in page_panels[:page_size]:
            aid = panel.get("assetId")
            resolved = _resolve_asset_path(db, str(aid) if aid else None)
            if resolved:
                paths[str(aid)] = resolved
        image = compose_page_image(
            title=str(doc.get("title") or "Storyboard"),
            project_name=project_name,
            page_index=page_index,
            page_count=max(1, len(pages)),
            page_size=page_size,
            slots=page_panels[:page_size],
            asset_paths=paths,
        )
        image.save(out_path, format="PNG")
        panel_ids = [str(p.get("panelId") or "") for p in page_panels[:page_size]]
        captions = [str(p.get("label") or "") for p in page_panels[:page_size]]
        source_ids = [str(p.get("assetId")) for p in page_panels[:page_size] if p.get("assetId")]
        meta = {
            "objective": "storyboard_2k_composed",
            "storyboardId": doc.get("id"),
            "pageIndex": page_index,
            "pageSize": page_size,
            "panelAssetIds": source_ids,
            "panelIds": panel_ids,
            "captions": captions,
            "resolution": {"width": CANVAS_W, "height": CANVAS_H},
            "composedAt": _now(),
        }
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=project_id,
            tag="storyboard_sheet",
            kind="image",
            filename=out_name,
            path=str(out_path),
            prompt_meta_json=json.dumps(meta),
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return {
            "ok": True,
            "assetId": asset.id,
            "path": str(out_path),
            "width": CANVAS_W,
            "height": CANVAS_H,
            "pageIndex": page_index,
            "panelAssetIds": source_ids,
            "captions": captions,
        }
