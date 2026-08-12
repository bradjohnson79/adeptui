"""ERS rendering and offline export helpers."""

from __future__ import annotations

import json
import textwrap
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from ..db import Asset
from .contracts import ERSExportRecord, EnvironmentReferenceSheet, utc_now
from .store import exports_dir

_CARD_BG = (19, 25, 33)
_PANEL_BG = (34, 44, 57)
_TEXT = (234, 240, 246)
_MUTED = (171, 183, 197)


def _asset_by_id(db: Session, project_id: str, asset_id: str | None) -> Asset | None:
    if not asset_id:
        return None
    asset = db.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        return None
    return asset


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_png(db: Session, sheet: EnvironmentReferenceSheet) -> Path:
    export_root = exports_dir(sheet.projectId, sheet.sheetId)
    canvas = Image.new("RGB", (1800, 1200), _CARD_BG)
    draw = ImageDraw.Draw(canvas)
    title_font = _font(44)
    body_font = _font(24)
    small_font = _font(18)

    draw.rounded_rectangle((40, 40, 1760, 180), radius=24, fill=_PANEL_BG)
    draw.text((72, 72), sheet.name, fill=_TEXT, font=title_font)
    draw.text((72, 126), "Environment Reference Sheet", fill=_MUTED, font=body_font)

    description_lines = _wrap(draw, sheet.description, body_font, 740)
    draw.rounded_rectangle((40, 220, 860, 520), radius=18, fill=_PANEL_BG)
    draw.text((64, 248), "Visual DNA", fill=_TEXT, font=body_font)
    y = 294
    for line in description_lines[:7]:
        draw.text((64, y), line, fill=_MUTED, font=small_font)
        y += 28

    highlights = [
        f"North lock: {sheet.spatialMap.northLockDirection.title()}" if sheet.spatialMap else "North lock: missing",
        f"Spatial Map: {sheet.spatialMap.mapId}" if sheet.spatialMap else "Spatial Map: missing",
        f"Continuity: {sheet.continuity.status}",
        sheet.composition.continuitySummary or sheet.continuity.summary,
    ]
    for idx, line in enumerate(highlights):
        draw.text((64, 410 + idx * 28), line, fill=_TEXT if idx < 2 else _MUTED, font=small_font)

    slots = [
        ("north", (920, 220, 1320, 500)),
        ("east", (1360, 220, 1760, 500)),
        ("south", (920, 540, 1320, 820)),
        ("west", (1360, 540, 1760, 820)),
    ]
    for direction, box in slots:
        draw.rounded_rectangle(box, radius=18, fill=_PANEL_BG)
        draw.text((box[0] + 18, box[1] + 16), direction.title(), fill=_TEXT, font=body_font)
        view = next((item for item in sheet.directionalViews if item.direction == direction), None)
        asset = _asset_by_id(db, sheet.projectId, view.approvedAssetId if view else None)
        if asset and Path(asset.path).is_file():
            try:
                image = Image.open(asset.path).convert("RGB")
                image.thumbnail((box[2] - box[0] - 36, box[3] - box[1] - 72))
                paste_x = box[0] + ((box[2] - box[0] - image.width) // 2)
                paste_y = box[1] + 56 + ((box[3] - box[1] - 72 - image.height) // 2)
                canvas.paste(image, (paste_x, paste_y))
            except Exception:
                draw.text((box[0] + 20, box[1] + 70), "Could not read approved image.", fill=_MUTED, font=small_font)
        else:
            status = view.status if view else "missing"
            draw.text((box[0] + 20, box[1] + 70), f"No approved image yet ({status}).", fill=_MUTED, font=small_font)
        prompt = (view.prompt if view else "").strip()
        prompt_preview = textwrap.shorten(prompt, width=90, placeholder="...")
        draw.text((box[0] + 20, box[3] - 38), prompt_preview or "Prompt unavailable.", fill=_MUTED, font=small_font)

    draw.rounded_rectangle((40, 560, 860, 1120), radius=18, fill=_PANEL_BG)
    draw.text((64, 590), "Continuity Notes", fill=_TEXT, font=body_font)
    notes = [item.message for item in sheet.continuity.findings] or [sheet.continuity.summary]
    y = 634
    for note in notes[:10]:
        for line in _wrap(draw, f"- {note}", small_font, 740)[:3]:
            draw.text((64, y), line, fill=_MUTED, font=small_font)
            y += 24
        y += 8

    png_path = export_root / f"{sheet.sheetId}.png"
    canvas.save(png_path, format="PNG")
    return png_path


def render_pdf(png_path: Path, sheet: EnvironmentReferenceSheet) -> Path:
    pdf_path = png_path.with_suffix(".pdf")
    image = Image.open(png_path).convert("RGB")
    image.save(pdf_path, "PDF", resolution=144.0)
    return pdf_path


def build_offline_package(db: Session, sheet: EnvironmentReferenceSheet) -> tuple[bytes, str]:
    root_name = f"{sheet.name.strip().replace(' ', '_')[:48] or 'ers'}_offline"
    asset_refs: dict[str, str] = {}
    media_payloads: dict[str, bytes] = {}
    for view in sheet.directionalViews:
        asset = _asset_by_id(db, sheet.projectId, view.approvedAssetId)
        if asset and Path(asset.path).is_file():
            ext = Path(asset.path).suffix or ".png"
            rel = f"media/{view.direction}{ext}"
            asset_refs[view.direction] = rel
            media_payloads[rel] = Path(asset.path).read_bytes()

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{sheet.name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #111822; color: #edf2f7; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }}
    .card {{ background: #1d2733; border-radius: 16px; padding: 16px; }}
    img {{ max-width: 100%; border-radius: 12px; display: block; }}
    .muted {{ color: #b4c1cf; }}
  </style>
</head>
<body>
  <h1>{sheet.name}</h1>
  <p class="muted">{sheet.description}</p>
  <p>North lock: {sheet.spatialMap.northLockDirection.title() if sheet.spatialMap else "Missing"} | Continuity: {sheet.continuity.status}</p>
  <div class="grid">
    {''.join(
        f"<section class='card'><h2>{view.direction.title()}</h2>"
        + (f"<img src='{asset_refs.get(view.direction, '')}' alt='{view.direction} view' />" if view.direction in asset_refs else "<p class='muted'>No approved image yet.</p>")
        + f"<p class='muted'>{view.prompt}</p></section>"
        for view in sheet.directionalViews
    )}
  </div>
  <section class="card" style="margin-top:20px">
    <h2>Continuity</h2>
    <p>{sheet.continuity.summary}</p>
    <ul>{''.join(f'<li>{item.message}</li>' for item in sheet.continuity.findings)}</ul>
  </section>
</body>
</html>"""
    buffer = BytesIO()
    archive_name = f"{root_name}.zip"
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        prefix = f"{root_name}/"
        archive.writestr(prefix + "index.html", html)
        archive.writestr(
            prefix + "data/ers.json",
            json.dumps(sheet.model_dump(mode="json"), indent=2, ensure_ascii=False),
        )
        archive.writestr(
            prefix + "README.txt",
            "Open index.html in a browser. This package is self-contained and uses only relative media paths.\n",
        )
        for rel_path, payload in media_payloads.items():
            archive.writestr(prefix + rel_path, payload)
    return buffer.getvalue(), archive_name


def update_export_record(sheet: EnvironmentReferenceSheet, export: ERSExportRecord) -> EnvironmentReferenceSheet:
    remaining = [item for item in sheet.exports if item.exportKind != export.exportKind]
    sheet.exports = [*remaining, export]
    sheet.updatedAt = utc_now()
    return sheet
