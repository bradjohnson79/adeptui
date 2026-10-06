"""ERS editable-master + instant snapshot capture (no provider image generation).

Submit path:
  1) save overlay state onto the original editable master
  2) bake base + overlays + Legend into a real PNG asset
  3) create a snapshot sheet record named \"<OriginalName> SS-<N>\"
  4) return immediately for Project ERS list + close Edit/Inpaint

Snapshots are frozen visual instances. They never replace the master composite
and are not editable masters. Snapshot numbers are monotonic per original and
never recycle after delete.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from .contracts import EnvironmentReferenceSheet, utc_now
from .store import list_sheets, load_sheet, save_sheet


SNAPSHOT_KIND = "snapshot"
ORIGINAL_KIND = "original"
SS_NAME_RE = re.compile(r"\s+SS-(\d+)\s*$", re.IGNORECASE)

DIRECTION_MOVEMENT_MAX_WORDS = 50


def normalize_direction_movement(raw: Any) -> str:
    """Plain-text Direction/Movement note, capped at 50 words."""
    if raw is None:
        return ""
    text_val = str(raw).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text_val:
        return ""
    words = text_val.split()
    if len(words) > DIRECTION_MOVEMENT_MAX_WORDS:
        words = words[:DIRECTION_MOVEMENT_MAX_WORDS]
    return " ".join(words)


def extract_direction_movement(legend: dict[str, Any] | None, explicit: Any = None) -> str:
    if explicit is not None and str(explicit).strip():
        return normalize_direction_movement(explicit)
    if isinstance(legend, dict):
        for key in ("directionMovement", "direction_movement", "movement", "movementText"):
            if legend.get(key) is not None and str(legend.get(key)).strip():
                return normalize_direction_movement(legend.get(key))
    return ""




def is_snapshot_sheet(sheet: EnvironmentReferenceSheet | dict[str, Any] | None) -> bool:
    if sheet is None:
        return False
    if isinstance(sheet, dict):
        kind = str(sheet.get("recordKind") or "").strip().lower()
        if kind == SNAPSHOT_KIND:
            return True
        if sheet.get("isEditableMaster") is False and sheet.get("snapshotNumber") is not None:
            return True
        return bool(sheet.get("snapshotOfSheetId"))
    kind = str(getattr(sheet, "recordKind", "") or "").strip().lower()
    if kind == SNAPSHOT_KIND:
        return True
    if getattr(sheet, "isEditableMaster", True) is False and getattr(sheet, "snapshotNumber", None) is not None:
        return True
    return bool(getattr(sheet, "snapshotOfSheetId", None))


def resolve_editable_master(
    project_id: str,
    sheet_id: str,
) -> EnvironmentReferenceSheet:
    """Prefer the original editable master; redirect snapshots to their parent."""
    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError(f"Environment Reference Sheet not found: {sheet_id}")
    if not is_snapshot_sheet(sheet):
        return sheet
    parent_id = (
        str(getattr(sheet, "snapshotOfSheetId", None) or "").strip()
        or str(getattr(sheet, "parentSheetId", None) or "").strip()
    )
    if not parent_id:
        raise ValueError("Snapshot has no parent editable master")
    parent = load_sheet(project_id, parent_id)
    if parent is None:
        raise FileNotFoundError(f"Editable master not found for snapshot: {parent_id}")
    if is_snapshot_sheet(parent):
        raise ValueError("Snapshot parent must be an editable original master")
    return parent


def _original_display_name(master: EnvironmentReferenceSheet) -> str:
    name = str(master.name or "").strip() or "Environment"
    # Strip any accidental SS suffix so naming stays clean.
    return SS_NAME_RE.sub("", name).strip() or "Environment"


def _list_snapshots_for_master(project_id: str, master_id: str) -> list[EnvironmentReferenceSheet]:
    out: list[EnvironmentReferenceSheet] = []
    for sheet in list_sheets(project_id):
        if not is_snapshot_sheet(sheet):
            continue
        parent = (
            str(getattr(sheet, "snapshotOfSheetId", None) or "").strip()
            or str(getattr(sheet, "parentSheetId", None) or "").strip()
        )
        if parent == master_id:
            out.append(sheet)
    return out


def next_snapshot_number(master: EnvironmentReferenceSheet) -> int:
    """Monotonic SS-N per original. Deleted numbers are never reused."""
    high = int(getattr(master, "snapshotSequenceHighWater", 0) or 0)
    existing_max = 0
    for snap in _list_snapshots_for_master(master.projectId, master.sheetId):
        n = int(getattr(snap, "snapshotNumber", 0) or 0)
        if n <= 0:
            m = SS_NAME_RE.search(str(snap.name or ""))
            if m:
                n = int(m.group(1))
        if n > existing_max:
            existing_max = n
    return max(high, existing_max) + 1


def snapshot_display_name(original_name: str, number: int) -> str:
    base = SS_NAME_RE.sub("", str(original_name or "").strip()).strip() or "Environment"
    return f"{base} SS-{int(number)}"


def _decode_png_b64(raw: str | None) -> bytes | None:
    if not raw or not isinstance(raw, str):
        return None
    b64 = raw.split(",", 1)[-1] if "," in raw else raw
    b64 = b64.strip()
    if not b64:
        return None
    try:
        data = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid PNG base64: {exc}") from exc
    return data or None


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_legend(
    canvas: Image.Image,
    legend: dict[str, Any] | None,
) -> None:
    if not isinstance(legend, dict):
        return
    position = legend.get("position") if isinstance(legend.get("position"), dict) else None
    if not position:
        return
    w, h = canvas.size
    left = float(position.get("left") or 0)
    top = float(position.get("top") or 0)
    width = float(position.get("width") or 0.16)
    height = float(position.get("height") or 0.42)
    x0 = int(max(0, min(w - 1, left * w)))
    y0 = int(max(0, min(h - 1, top * h)))
    x1 = int(max(x0 + 1, min(w, (left + width) * w)))
    y1 = int(max(y0 + 1, min(h, (top + height) * h)))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([x0, y0, x1, y1], fill=(18, 22, 32, 210), outline=(180, 190, 210, 255), width=2)
    font = _load_font(max(12, int((y1 - y0) / 22)))
    title_font = _load_font(max(14, int((y1 - y0) / 18)))
    cy = y0 + 8
    draw.text((x0 + 8, cy), "Legend", fill=(235, 238, 245, 255), font=title_font)
    cy += int((y1 - y0) * 0.08) + 10

    def _slots(key: str, heading: str) -> None:
        nonlocal cy
        slots = legend.get(key) if isinstance(legend.get(key), list) else []
        draw.text((x0 + 8, cy), heading, fill=(170, 180, 200, 255), font=font)
        cy += int((y1 - y0) * 0.055) + 4
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            label = str(slot.get("label") or "").strip()
            color = str(slot.get("color") or "#9ca3af").strip() or "#9ca3af"
            try:
                rgb = tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            except Exception:
                rgb = (156, 163, 175)
            sw = max(10, int((x1 - x0) * 0.12))
            sh = max(10, int((y1 - y0) * 0.035))
            draw.rectangle([x0 + 8, cy, x0 + 8 + sw, cy + sh], fill=(*rgb, 255), outline=(255, 255, 255, 180))
            draw.text((x0 + 14 + sw, cy), label or "—", fill=(230, 233, 240, 255), font=font)
            cy += sh + 6
            if cy > y1 - 8:
                break

    _slots("characters", "Characters")
    _slots("props", "Props")
    movement = extract_direction_movement(legend)
    if movement and cy <= y1 - 8:
        draw.text((x0 + 8, cy), "Direction / Movement", fill=(170, 180, 200, 255), font=font)
        line_h = max(12, int((y1 - y0) * 0.04) + 4)
        cy += int((y1 - y0) * 0.055) + 4
        max_w = max(20, (x1 - x0) - 16)
        line = ""
        for word in movement.split():
            trial = (line + " " + word).strip()
            bbox = draw.textbbox((0, 0), trial, font=font)
            if (bbox[2] - bbox[0] <= max_w) or not line:
                line = trial
            else:
                draw.text((x0 + 8, cy), line, fill=(230, 233, 240, 255), font=font)
                cy += line_h
                line = word
                if cy > y1 - 8:
                    line = ""
                    break
        if line and cy <= y1 - 8:
            draw.text((x0 + 8, cy), line, fill=(230, 233, 240, 255), font=font)
    canvas.alpha_composite(overlay)


def _draw_markers_and_labels(
    canvas: Image.Image,
    *,
    text_labels: list[dict[str, Any]] | None,
    numbered_markers: list[dict[str, Any]] | None,
) -> None:
    w, h = canvas.size
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(14, int(min(w, h) * 0.018)))

    for label in text_labels or []:
        if not isinstance(label, dict):
            continue
        text = str(label.get("text") or "").strip()
        if not text:
            continue
        x = float(label.get("x") or 0) * w
        y = float(label.get("y") or 0) * h
        color = str(label.get("color") or "#ffffff").strip() or "#ffffff"
        try:
            rgb = tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        except Exception:
            rgb = (255, 255, 255)
        size = int(label.get("fontSize") or 16)
        use_font = _load_font(max(10, size))
        draw.text((x, y), text, fill=(*rgb, 255), font=use_font)

    for marker in numbered_markers or []:
        if not isinstance(marker, dict):
            continue
        x = float(marker.get("x") or 0) * w
        y = float(marker.get("y") or 0) * h
        number = int(marker.get("number") or 0)
        r = max(10, int(min(w, h) * 0.012))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(220, 60, 60, 230), outline=(255, 255, 255, 255), width=2)
        text = str(number or marker.get("label") or "")
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x - tw / 2, y - th / 2), text, fill=(255, 255, 255, 255), font=font)

    canvas.alpha_composite(overlay)


def bake_snapshot_image(
    *,
    source_path: str | Path,
    legend: dict[str, Any] | None = None,
    drawing_overlay: dict[str, Any] | None = None,
    text_labels: list[dict[str, Any]] | None = None,
    numbered_markers: list[dict[str, Any]] | None = None,
) -> Image.Image:
    """Flatten base + overlays + Legend into one RGBA image (local only)."""
    src = Path(source_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source asset file missing: {src}")
    with Image.open(src) as im:
        canvas = im.convert("RGBA")

    # Drawing raster (vectors already rasterized by FE when present).
    raster_b64 = None
    if isinstance(drawing_overlay, dict):
        raster_b64 = drawing_overlay.get("rasterBase64") or drawing_overlay.get("rasterPngBase64")
        asset_path = drawing_overlay.get("path")
        if not raster_b64 and asset_path and Path(str(asset_path)).is_file():
            with Image.open(str(asset_path)) as ov:
                overlay_im = ov.convert("RGBA")
            if overlay_im.size != canvas.size:
                overlay_im = overlay_im.resize(canvas.size, Image.Resampling.LANCZOS)
            canvas.alpha_composite(overlay_im)
    raw = _decode_png_b64(raster_b64 if isinstance(raster_b64, str) else None)
    if raw:
        from io import BytesIO

        with Image.open(BytesIO(raw)) as ov:
            overlay_im = ov.convert("RGBA")
        if overlay_im.size != canvas.size:
            overlay_im = overlay_im.resize(canvas.size, Image.Resampling.LANCZOS)
        canvas.alpha_composite(overlay_im)

    _draw_markers_and_labels(canvas, text_labels=text_labels, numbered_markers=numbered_markers)
    _draw_legend(canvas, legend)
    return canvas


def _persist_overlay_on_master(
    master: EnvironmentReferenceSheet,
    *,
    source_asset_id: str,
    legend: dict[str, Any] | None,
    guidance: dict[str, Any] | None,
) -> EnvironmentReferenceSheet:
    """Save structured overlay onto the editable master. Never replaces composite pixels."""
    state = {
        "sourceAssetId": source_asset_id,
        "savedAt": utc_now(),
        "legend": legend,
        "guidance": guidance or {},
    }
    master.overlayState = state
    master.updatedAt = utc_now()
    # Ensure master flags stay authoritative.
    master.recordKind = ORIGINAL_KIND
    master.isEditableMaster = True
    if not str(getattr(master, "rootSheetId", None) or "").strip():
        master.rootSheetId = master.sheetId
    save_sheet(master)
    return master


def _register_baked_asset(
    db: Session,
    *,
    project_id: str,
    parent_asset_id: str,
    image: Image.Image,
    snapshot_name: str,
    snapshot_number: int,
    master_sheet_id: str,
) -> Any:
    import tempfile

    from ..generation_tools.lineage import register_derived_asset

    # Write outside project assets so register_derived_asset can copy safely.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        tmp = Path(handle.name)
    try:
        image.convert("RGBA").save(tmp, format="PNG")
        asset = register_derived_asset(
            db,
            project_id=project_id,
            source_path=tmp,
            kind="image",
            tag=f"ers_snapshot_ss{snapshot_number}"[:64],
            parent_asset_id=parent_asset_id,
            op="ers_snapshot_bake",
            model=None,
            prompt_meta={
                "ersSnapshot": True,
                "snapshotNumber": snapshot_number,
                "snapshotName": snapshot_name,
                "masterSheetId": master_sheet_id,
                "imageGenInvoked": False,
                "provider": None,
                "bake": "local_flatten",
            },
            library_key=None,
            filename=f"ers_snapshot_ss{snapshot_number}_{uuid4().hex[:10]}.png",
        )
    finally:
        try:
            if tmp.is_file():
                tmp.unlink()
        except Exception:
            pass
    return asset


def capture_ers_snapshot(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    source_asset_id: str | None = None,
    legend: Any = None,
    drawing_overlay: Any = None,
    text_labels: Any = None,
    numbered_markers: Any = None,
    direction_movement: Any = None,
    actor: str = "creator",
) -> dict[str, Any]:
    """Instant local snapshot: save overlay → bake → SS-N record. Zero image-gen providers."""
    from .edit import (
        _guidance_bundle,
        _normalize_drawing_overlay,
        _normalize_numbered_markers,
        _normalize_text_labels,
        resolve_source_asset_id,
    )
    from ..db import Asset

    master = resolve_editable_master(project_id, sheet_id)
    if is_snapshot_sheet(master):
        raise ValueError("Cannot capture snapshot from a non-editable sheet")

    master_composite_before = str(getattr(master, "ers_composite_asset_id", "") or "").strip()
    source_id = resolve_source_asset_id(master, source_asset_id)
    source = db.get(Asset, source_id)
    if source is None or str(getattr(source, "project_id", "")) != project_id:
        raise FileNotFoundError(f"Source asset not found: {source_id}")
    if not source.path or not Path(source.path).is_file():
        raise FileNotFoundError(f"Source asset file missing on disk: {source_id}")

    legend_payload: dict[str, Any] | None = None
    if isinstance(legend, dict):
        legend_payload = dict(legend)
    elif legend is not None:
        raise ValueError("legend must be an object when provided")

    movement_text = extract_direction_movement(legend_payload, direction_movement)
    if legend_payload is None:
        legend_payload = {}
    legend_payload["directionMovement"] = movement_text

    drawing = _normalize_drawing_overlay(drawing_overlay) if drawing_overlay is not None else None
    labels = _normalize_text_labels(text_labels) if text_labels is not None else []
    markers = _normalize_numbered_markers(numbered_markers) if numbered_markers is not None else []

    guidance = _guidance_bundle(
        project_id=project_id,
        sheet_id=master.sheetId,
        source_asset_id=source_id,
        drawing_overlay=drawing,
        text_labels=labels,
        numbered_markers=markers,
        overlay_bake_policy="guidance_only",
    )

    # 1) Persist overlay on original master (pixels unchanged).
    # Master movement note updates to current text; prior SS notes remain untouched.
    master_movement_before = normalize_direction_movement(getattr(master, "directionMovement", None))
    master = _persist_overlay_on_master(
        master,
        source_asset_id=source_id,
        legend=legend_payload,
        guidance=guidance,
    )
    master.directionMovement = movement_text
    master.movementSequenceIndex = 0  # Prime Movement
    master.updatedAt = utc_now()
    save_sheet(master)

    # Attach overlay raster path into drawing for bake when guidance persisted one.
    bake_overlay = dict(drawing or {}) if drawing else {}
    if guidance.get("overlayAssetId") and not bake_overlay.get("rasterBase64") and not bake_overlay.get("rasterPngBase64"):
        from ..image_product.store import project_dir as ip_project_dir

        ov_path = ip_project_dir(project_id) / "overlays" / f"{guidance['overlayAssetId']}.png"
        if ov_path.is_file():
            bake_overlay["path"] = str(ov_path)

    # 2+3) Bake composite image artifact locally.
    baked = bake_snapshot_image(
        source_path=source.path,
        legend=legend_payload,
        drawing_overlay=bake_overlay or None,
        text_labels=labels,
        numbered_markers=markers,
    )

    number = next_snapshot_number(master)
    original_name = _original_display_name(master)
    display_name = snapshot_display_name(original_name, number)

    asset = _register_baked_asset(
        db,
        project_id=project_id,
        parent_asset_id=source_id,
        image=baked,
        snapshot_name=display_name,
        snapshot_number=number,
        master_sheet_id=master.sheetId,
    )

    # Advance high-water on master BEFORE saving snapshot so numbering is durable.
    master.snapshotSequenceHighWater = number
    master.updatedAt = utc_now()
    save_sheet(master)

    # 4) Create snapshot record (not an editable master; not a new environment identity).
    payload = master.model_dump(mode="json")
    new_id = str(uuid4())
    payload["sheetId"] = new_id
    payload["name"] = display_name
    payload["status"] = "registered"
    payload["recordKind"] = SNAPSHOT_KIND
    payload["isEditableMaster"] = False
    payload["snapshotNumber"] = number
    payload["snapshotOfSheetId"] = master.sheetId
    payload["parentSheetId"] = master.sheetId
    payload["rootSheetId"] = str(getattr(master, "rootSheetId", None) or master.sheetId)
    payload["versionNumber"] = int(getattr(master, "versionNumber", 1) or 1)
    payload["createdAt"] = utc_now()
    payload["updatedAt"] = utc_now()
    payload["ers_composite_asset_id"] = asset.id
    payload["overlayState"] = None
    payload["snapshotSequenceHighWater"] = 0
    # Snapshot owns its own Direction/Movement note (does not overwrite original / earlier SS).
    payload["directionMovement"] = movement_text
    payload["movementSequenceIndex"] = number

    composition = dict(payload.get("composition") or {})
    rendered = dict(composition.get("renderedAssetIds") or {})
    rendered["composite"] = asset.id
    rendered["png"] = asset.id
    rendered["snapshot"] = asset.id
    composition["renderedAssetIds"] = rendered
    composition["lastRenderedAt"] = utc_now()
    composition["sheetTitle"] = display_name
    composition["heroSummary"] = f"Snapshot SS-{number} of {original_name}"
    payload["composition"] = composition

    provenance = dict(payload.get("provenance") or {})
    provenance.update(
        {
            "createdAt": utc_now(),
            "actor": actor,
            "source": "ers_snapshot_capture",
            "note": "Instant local bake snapshot; master overlay preserved; no image generation",
            "details": {
                "masterSheetId": master.sheetId,
                "snapshotNumber": number,
                "bakedAssetId": asset.id,
                "sourceAssetId": source_id,
                "imageGenInvoked": False,
                "providersInvoked": [],
                "directionMovement": movement_text,
                "movementSequenceIndex": number,
                "masterDirectionMovementBefore": master_movement_before,
            },
        }
    )
    payload["provenance"] = provenance

    # Snapshots are not approval-gated new environments.
    creation_plan = dict(payload.get("creationPlan") or {})
    creation_plan["summary"] = f"Frozen snapshot SS-{number}"
    creation_plan["creatorPreview"] = display_name
    creation_plan["approvalRequirements"] = []
    payload["creationPlan"] = creation_plan

    child = EnvironmentReferenceSheet.model_validate(payload)
    save_sheet(child)

    # Invariant: master composite never replaced by snapshot bake.
    master_after = load_sheet(project_id, master.sheetId)
    master_composite_after = str(getattr(master_after, "ers_composite_asset_id", "") or "").strip()
    if master_composite_before and master_composite_before != master_composite_after:
        raise RuntimeError("Invariant violated: master composite mutated during snapshot capture")

    return {
        "ok": True,
        "imageGenInvoked": False,
        "providersInvoked": [],
        "kind": "ers_snapshot",
        "message": f"Snapshot {display_name} captured.",
        "masterSheetId": master.sheetId,
        "masterName": original_name,
        "masterCompositeAssetId": master_composite_after or master_composite_before or source_id,
        "snapshotSheetId": child.sheetId,
        "snapshotNumber": number,
        "snapshotName": display_name,
        "bakedAssetId": asset.id,
        "sourceAssetId": source_id,
        "overlaySaved": True,
        "directionMovement": movement_text,
        "movementSequenceIndex": number,
        "masterDirectionMovement": movement_text,
        "sheet": child.model_dump(mode="json"),
        "summary": snapshot_summary(child),
    }



def list_display_label(sheet: EnvironmentReferenceSheet, original_name: str | None = None) -> str:
    """UI-only list label. Original keeps exact name; SS-# only on snapshots."""
    if is_snapshot_sheet(sheet):
        base = SS_NAME_RE.sub("", str(original_name or getattr(sheet, "name", "") or "Environment")).strip()
        base = base or "Environment"
        n = int(getattr(sheet, "snapshotNumber", 0) or 0)
        if n <= 0:
            m = SS_NAME_RE.search(str(sheet.name or ""))
            n = int(m.group(1)) if m else 0
        return f"{base} SS-{n}" if n else str(sheet.name or base)
    # Original: exact existing name — never append Prime Movement / movement labels.
    raw = str(original_name or getattr(sheet, "name", "") or "Environment").strip() or "Environment"
    return raw

def snapshot_summary(sheet: EnvironmentReferenceSheet) -> dict[str, Any]:
    return {
        "sheetId": sheet.sheetId,
        "projectId": sheet.projectId,
        "name": sheet.name,
        "status": sheet.status,
        "recordKind": getattr(sheet, "recordKind", ORIGINAL_KIND) or ORIGINAL_KIND,
        "isEditableMaster": bool(getattr(sheet, "isEditableMaster", True)),
        "isSnapshot": is_snapshot_sheet(sheet),
        "snapshotNumber": getattr(sheet, "snapshotNumber", None),
        "snapshotOfSheetId": getattr(sheet, "snapshotOfSheetId", None),
        "directionMovement": normalize_direction_movement(getattr(sheet, "directionMovement", None)) or None,
        "movementSequenceIndex": getattr(sheet, "movementSequenceIndex", None),
        "parentSheetId": getattr(sheet, "parentSheetId", None),
        "rootSheetId": getattr(sheet, "rootSheetId", None) or sheet.sheetId,
        "ers_composite_asset_id": getattr(sheet, "ers_composite_asset_id", None),
        "updatedAt": sheet.updatedAt,
        "createdAt": sheet.createdAt,
    }



def _remove_sheet_record(project_id: str, sheet_id: str) -> None:
    """Remove sheet JSON only. High-water / master overlay untouched."""
    from .store import sheets_dir

    sheet_path = sheets_dir(project_id) / f"{sheet_id}.json"
    if sheet_path.is_file():
        sheet_path.unlink()


def delete_ers_snapshot(project_id: str, snapshot_sheet_id: str) -> dict[str, Any]:
    """Delete a snapshot only. Never deletes master, siblings, or master overlay."""
    sheet = load_sheet(project_id, snapshot_sheet_id)
    if sheet is None:
        raise FileNotFoundError(f"Environment Reference Sheet not found: {snapshot_sheet_id}")
    if not is_snapshot_sheet(sheet):
        raise ValueError("Only snapshots can be removed via snapshot delete; master is protected")

    master_id = (
        str(getattr(sheet, "snapshotOfSheetId", None) or "").strip()
        or str(getattr(sheet, "parentSheetId", None) or "").strip()
    )
    number = int(getattr(sheet, "snapshotNumber", 0) or 0)
    _remove_sheet_record(project_id, snapshot_sheet_id)

    # High-water on master is intentionally preserved (no recycle).
    high_water = None
    if master_id:
        master = load_sheet(project_id, master_id)
        if master is not None:
            high_water = int(getattr(master, "snapshotSequenceHighWater", 0) or 0)

    return {
        "ok": True,
        "deletedSnapshotSheetId": snapshot_sheet_id,
        "snapshotNumber": number or None,
        "masterSheetId": master_id or None,
        "masterPreserved": True,
        "siblingsPreserved": True,
        "overlayPreserved": True,
        "snapshotSequenceHighWater": high_water,
        "numberRecycled": False,
    }
