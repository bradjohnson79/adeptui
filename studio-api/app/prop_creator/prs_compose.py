"""Programmatic Prop Reference Sheet. Image model does not invent this page.

Identity lock: the hero tile is the approved source still (contain/fit).
Does not overwrite the approved still — writes a new Library PNG.
One canonical Timeline tag: %PascalCase (never ~ for props).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import Asset
from ..scene_references.sheet_tags import pascal_alias
from ..spatial_map.ers_contracts import PropEntity

PRS_TAG = "prop_reference_sheet"
_BG = (18, 18, 20)
_GOLD = (210, 186, 128)
_TEXT = (244, 244, 248)
_MUTED = (168, 172, 184)


def _asset_path(asset: Asset) -> Path | None:
    raw = str(getattr(asset, "path", "") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        return path
    alt = Path(settings.data_dir) / raw
    return alt if alt.is_file() else None


def _wrap(text: str, width: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if len(trial) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def compose_prop_reference_sheet(
    image_path: Path,
    facts: dict[str, str],
    out_path: Path,
) -> Path:
    from PIL import Image, ImageDraw, ImageOps

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1600, 900), _BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1600, 88), fill=(10, 10, 12))
    draw.text((32, 24), "PROP REFERENCE SHEET", fill=_GOLD)
    title = facts.get("name") or "Prop"
    draw.text((32, 54), title, fill=_TEXT)

    source = Image.open(image_path).convert("RGB")
    tile = ImageOps.contain(source, (820, 720))
    canvas.paste(tile, (40, 120))

    y = 120
    for key in ("name", "tag", "description", "source", "style", "notes"):
        value = str(facts.get(key) or "").strip()
        if not value:
            continue
        draw.text((900, y), key.upper(), fill=_GOLD)
        y += 28
        for line in _wrap(value, 42)[:8]:
            draw.text((900, y), line, fill=_TEXT if key != "notes" else _MUTED)
            y += 26
        y += 16

    canvas.save(out_path, "PNG")
    return out_path


def compose_and_ingest_prs(
    db: Session,
    project_id: str,
    prop: PropEntity,
) -> Asset | None:
    """Build a PRS from the approved still + PropEntity JSON. Never invent a prop."""
    aid = str(prop.approved_asset_id or "").strip()
    if not aid:
        return None
    source = db.get(Asset, aid)
    if source is None or source.project_id != project_id:
        return None
    path = _asset_path(source)
    if path is None:
        return None
    alias = pascal_alias(prop.display_label or prop.tag or "Prop")
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"prs_{prop.id[:8]}_{uuid.uuid4().hex[:8]}.png"
    compose_prop_reference_sheet(
        path,
        {
            "name": prop.display_label or alias,
            "tag": f"%{alias}",
            "description": prop.description or prop.notes or "",
            "source": f"approved still {aid}" + (f" ({path.name})" if path else ""),
            "style": prop.visual_style or "",
            "notes": prop.notes or "",
        },
        dest,
    )
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=f"{alias} PRS.png",
        path=str(dest),
        kind="image",
        tag=PRS_TAG,
        labels_json=json.dumps(["prop_reference_sheet", "prs", alias, f"prop:{prop.id}"]),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


ADVANCED_PRS_TAG = "advanced_prop_reference_sheet"
_ADV_SIZE = 2048


def compose_advanced_prop_reference_sheet(
    angle_images: list[tuple[str, Path]],
    facts: dict[str, str],
    out_path: Path,
    *,
    meta_json: str = "",
) -> Path:
    """Stitch approved Advanced angles + metadata onto a 2K PRS. Never invent angles."""
    from PIL import Image, ImageDraw, ImageOps

    if not angle_images:
        raise ValueError("compose_advanced_prop_reference_sheet requires at least one approved angle image")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    W = H = _ADV_SIZE
    canvas = Image.new("RGB", (W, H), _BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, W, 96), fill=(10, 10, 12))
    draw.text((36, 28), "ADVANCED PROP REFERENCE SHEET", fill=_GOLD)
    title = facts.get("name") or "Prop"
    draw.text((36, 58), title, fill=_TEXT)

    grid_left, grid_top = 36, 120
    grid_w, grid_h = 1320, 1680
    meta_x = 1380
    n = len(angle_images)
    cols = 3 if n >= 3 else max(1, n)
    rows = (n + cols - 1) // cols
    gap = 16
    cell_w = (grid_w - gap * (cols - 1)) // cols
    cell_h = (grid_h - gap * (rows - 1)) // rows

    for i, (label, path) in enumerate(angle_images):
        row, col = i // cols, i % cols
        x = grid_left + col * (cell_w + gap)
        y = grid_top + row * (cell_h + gap)
        draw.rectangle((x, y, x + cell_w, y + cell_h), outline=(40, 44, 56), width=2)
        draw.text((x + 10, y + 8), label.upper(), fill=_GOLD)
        try:
            src = Image.open(path).convert("RGB")
            tile = ImageOps.contain(src, (cell_w - 20, cell_h - 40))
            px = x + (cell_w - tile.width) // 2
            py = y + 28 + (cell_h - 40 - tile.height) // 2
            canvas.paste(tile, (px, py))
        except Exception:
            draw.text((x + 10, y + 40), "(missing image)", fill=_MUTED)

    y = 120
    draw.text((meta_x, y), "PROP METADATA", fill=_GOLD)
    y += 36
    for key in ("name", "tag", "type", "description", "style", "notes", "angles"):
        value = str(facts.get(key) or "").strip()
        if not value:
            continue
        draw.text((meta_x, y), key.upper(), fill=_GOLD)
        y += 26
        for line in _wrap(value, 36)[:10]:
            draw.text((meta_x, y), line, fill=_TEXT if key != "notes" else _MUTED)
            y += 22
        y += 12
        if y > H - 200:
            break

    if meta_json.strip():
        draw.text((meta_x, min(y + 8, H - 180)), "JSON", fill=_GOLD)
        y2 = min(y + 34, H - 160)
        for line in _wrap(meta_json.replace("\n", " "), 36)[:8]:
            draw.text((meta_x, y2), line, fill=_MUTED)
            y2 += 20

    canvas.save(out_path, "PNG")
    return out_path


def compose_and_ingest_advanced_prs(
    db: Session,
    project_id: str,
    prop: PropEntity,
    angle_paths: list[tuple[str, Path]],
) -> Asset:
    """Ingest Advanced multi-angle PRS. Caller enforces approved-angle gate."""
    alias = pascal_alias(prop.display_label or prop.tag or "Prop")
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"adv_prs_{prop.id[:8]}_{uuid.uuid4().hex[:8]}.png"
    angle_names = ", ".join(a for a, _ in angle_paths)
    meta = {
        "id": prop.id,
        "tag": prop.tag,
        "mode": "advanced",
        "advanced_type": prop.advanced_type or "",
        "primary_approved_asset_id": prop.primary_approved_asset_id or "",
        "angles": {k: {"approved": True} for k, _ in angle_paths},
    }
    compose_advanced_prop_reference_sheet(
        angle_paths,
        {
            "name": prop.display_label or alias,
            "tag": f"%{alias}",
            "type": str(prop.advanced_type or ""),
            "description": prop.description or prop.primary_prompt or prop.notes or "",
            "style": prop.visual_style or "",
            "notes": prop.notes or "",
            "angles": angle_names,
        },
        dest,
        meta_json=json.dumps(meta, separators=(",", ":")),
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prompt_meta = {
        "assetId": "",
        "projectId": project_id,
        "propId": prop.id,
        "propName": prop.display_label or alias,
        "assetType": "image",
        "role": "prop_reference_sheet",
        "view": "sheet",
        "source": "composed",
        "createdAt": now,
        "updatedAt": now,
    }
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=f"{alias} Advanced PRS.png",
        path=str(dest),
        kind="image",
        tag=f"{prop.display_label or alias} — Reference Sheet"[:64],
        labels_json=json.dumps(
            [
                ADVANCED_PRS_TAG,
                PRS_TAG,
                "prs",
                "advanced",
                alias,
                f"prop:{prop.id}",
            ]
        ),
        prompt_meta_json=json.dumps({**prompt_meta, "assetId": ""}, ensure_ascii=False),
    )
    db.add(asset)
    db.flush()
    prompt_meta["assetId"] = asset.id
    asset.prompt_meta_json = json.dumps(prompt_meta, ensure_ascii=False)
    db.commit()
    db.refresh(asset)
    return asset
