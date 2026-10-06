"""One-pass GPT Image 2 full-sheet ERS persist, validation, and derived crops.

The visual sheet is the GPT Image 2 PNG. Machine JSON is Adept-authored from
Spatial Map / Character Creator / cameras. Component tiles stay repair-only.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .ers_collage_templates import ORIGINAL_ERS_V1, lookup_collage_template
from .ers_character_identity_gate import FAIL_CHARACTER_IDENTITY, apply_occupied_identity_gate
from .ers_packet import compile_ers_packet, hydrate_ers_character_canon, human_readable_summary, packet_needs_occupied

logger = logging.getLogger(__name__)

GENERATION_MODE = "full_sheet_api"
PIPELINE_MODE = "full_sheet"
CANONICAL_PANELS = (
    "hero",
    "spatial",
    "three_d",
    "directional",
    "materials",
    "lighting",
    "dna",
    "continuity",
    "occupied",
)


def bake_visual_overlay_on_full_sheet_success(ctx: dict[str, Any] | None = None) -> bool:
    """Normal full_sheet / full_sheet_api success never stamps or strips the GPT PNG.

    Camera overlay and movement-strip remain available for non-visual / explicit
    repair callers. They must not bake into the committed visual ERS.
    """
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def crop_panel_bytes(png: bytes, panel: str, *, template_id: str = ORIGINAL_ERS_V1) -> bytes:
    """Deterministic panel crop. Fail closed when the template has no rectangle."""
    contract = lookup_collage_template(template_id=template_id)
    if contract is None:
        raise RuntimeError(f"ERS template {template_id} is missing.")
    region = contract.panel_content(panel)
    if not region:
        raise RuntimeError(f"ERS template {template_id} has no rectangle for panel {panel}.")
    image = Image.open(BytesIO(png)).convert("RGB")
    w, h = image.size
    box = (
        int(round(w * float(region["left"]))),
        int(round(h * float(region["top"]))),
        int(round(w * (float(region["left"]) + float(region["width"])))),
        int(round(h * (float(region["top"]) + float(region["height"])))),
    )
    box = (
        max(0, min(w, box[0])),
        max(0, min(h, box[1])),
        max(0, min(w, box[2])),
        max(0, min(h, box[3])),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        raise RuntimeError(f"ERS panel {panel} crop is empty.")
    cropped = image.crop(box)
    out = BytesIO()
    cropped.save(out, format="PNG")
    return out.getvalue()



FAIL_EXTRA_BOARD = "FAIL_EXTRA_BOARD"
FAIL_NESTED_OCCUPIED_FRAME = "FAIL_NESTED_OCCUPIED_FRAME"

# Extra height below the canonical 16:9 / template sheet. A ~780px planning
# strip on a 2560-wide 16:9 sheet is ~54% extra and MUST fail. Small GPT
# variance (title bar, few percent) must not.
_EXTRA_BOARD_HEIGHT_RATIO = 0.22

# Nested occupied overlay: an inset rectangle with a coherent 4-sided frame,
# occupying a substantial but not-full fraction of Panel 9.
_NESTED_MIN_AREA = 0.18
_NESTED_MAX_AREA = 0.82
_NESTED_MIN_SIDE_CONTRAST = 28.0


def _template_size(template_id: str = ORIGINAL_ERS_V1) -> tuple[int, int]:
    contract = lookup_collage_template(template_id=template_id)
    if contract is None:
        return (1672, 941)
    return tuple(contract.template_size)


def _occupied_box(width: int, height: int, *, template_id: str = ORIGINAL_ERS_V1) -> tuple[int, int, int, int] | None:
    contract = lookup_collage_template(template_id=template_id)
    if contract is None:
        return None
    region = contract.panel_content("occupied")
    if not region:
        return None
    box = (
        int(round(width * float(region["left"]))),
        int(round(height * float(region["top"]))),
        int(round(width * (float(region["left"]) + float(region["width"])))),
        int(round(height * (float(region["top"]) + float(region["height"])))),
    )
    box = (
        max(0, min(width, box[0])),
        max(0, min(height, box[1])),
        max(0, min(width, box[2])),
        max(0, min(height, box[3])),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return box


def _png_size(png: bytes) -> tuple[int, int]:
    image = Image.open(BytesIO(png))
    return int(image.size[0]), int(image.size[1])


def assess_extra_board_below_canonical(
    width: int | None = None,
    height: int | None = None,
    *,
    png: bytes | None = None,
    template_id: str = ORIGINAL_ERS_V1,
) -> dict[str, Any]:
    """Fail HUGE extra content appended below the canonical 16:9 / template sheet.

    2560x2220 vs ers.original.v1 1672x941 (canonical height 1440 at width 2560,
    extra ~780px) is a layout fail. 2560x1440 and 1672x941 pass.
    """
    if png:
        width, height = _png_size(png)
    w = int(width or 0)
    h = int(height or 0)
    tw, th = _template_size(template_id)
    out: dict[str, Any] = {
        "ok": True,
        "code": None,
        "note": "canonical sheet bounds",
        "width": w,
        "height": h,
        "canonicalWidth": tw,
        "canonicalHeight": th,
        "extraHeightPx": 0.0,
        "extraHeightRatio": 0.0,
    }
    if w <= 0 or h <= 0 or tw <= 0 or th <= 0:
        out["ok"] = True
        out["note"] = "sheet size unavailable; extra-board not assessed"
        return out
    canonical_h = float(w) * float(th) / float(tw)
    extra = float(h) - canonical_h
    ratio = extra / canonical_h if canonical_h > 0 else 0.0
    out["extraHeightPx"] = extra
    out["extraHeightRatio"] = ratio
    if extra > 0 and ratio >= _EXTRA_BOARD_HEIGHT_RATIO:
        out["ok"] = False
        out["code"] = FAIL_EXTRA_BOARD
        out["note"] = (
            f"{FAIL_EXTRA_BOARD}: extra content below canonical sheet bounds "
            f"({w}x{h}; canonical height {canonical_h:.0f}px at this width; "
            f"extra {extra:.0f}px, {ratio:.0%})"
        )
        return out
    return out


def _edge_peaks(profile: np.ndarray, *, margin: float, max_peaks: int = 4) -> list[int]:
    """Strong thin bands inset from the crop edges (frame strokes)."""
    n = int(profile.size)
    if n < 8:
        return []
    lo = max(1, int(round(n * margin)))
    hi = min(n - 1, int(round(n * (1.0 - margin))))
    if hi <= lo + 1:
        return []
    inner = profile[lo:hi]
    floor = float(np.median(inner))
    spread = float(inner.std())
    thresh = max(floor + 1.25 * spread, float(inner.max()) * 0.42, 10.0)
    peaks: list[tuple[float, int]] = []
    i = lo
    while i < hi:
        if profile[i] >= thresh:
            j = i
            best_i = i
            best_v = float(profile[i])
            while j < hi and profile[j] >= thresh * 0.75:
                if float(profile[j]) > best_v:
                    best_v = float(profile[j])
                    best_i = j
                j += 1
            peaks.append((best_v, best_i))
            i = j
        else:
            i += 1
    peaks.sort(reverse=True)
    idxs = [idx for _v, idx in peaks[:max_peaks]]
    idxs.sort()
    return idxs


def assess_panel9_nested_frame(
    png: bytes,
    *,
    template_id: str = ORIGINAL_ERS_V1,
) -> dict[str, Any]:
    """Fail an obvious nested / overlapping second occupied frame in Panel 9.

    Looks for a coherent 4-sided inset stroke. Does not brittle-fail minor GPT
    panel drift, titles outside the occupied box, or a normal occupied scene.
    """
    out: dict[str, Any] = {
        "ok": True,
        "code": None,
        "note": "no nested occupied frame",
        "score": 0.0,
    }
    try:
        image = Image.open(BytesIO(png)).convert("RGB")
    except Exception:
        out["note"] = "sheet bytes unreadable; nested frame not assessed"
        return out
    w, h = image.size
    box = _occupied_box(w, h, template_id=template_id)
    if box is None:
        out["note"] = "occupied region unavailable; nested frame not assessed"
        return out
    crop = image.crop(box)
    cw, ch = crop.size
    if cw < 24 or ch < 16:
        out["note"] = "occupied crop too small; nested frame not assessed"
        return out
    scale = min(160.0 / float(cw), 56.0 / float(ch), 1.0)
    tw = max(48, int(round(cw * scale)))
    th = max(24, int(round(ch * scale)))
    small = crop.resize((tw, th), Image.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    gray = arr.mean(axis=2)
    row_e = np.abs(np.diff(gray, axis=0)).mean(axis=1)
    col_e = np.abs(np.diff(gray, axis=1)).mean(axis=0)
    y_peaks = _edge_peaks(row_e, margin=0.08)
    x_peaks = _edge_peaks(col_e, margin=0.08)
    area = float(tw * th)
    best = 0.0
    for i, y0 in enumerate(y_peaks):
        for y1 in y_peaks[i + 1 :]:
            if y1 - y0 < max(6, int(th * 0.22)):
                continue
            for j, x0 in enumerate(x_peaks):
                for x1 in x_peaks[j + 1 :]:
                    if x1 - x0 < max(10, int(tw * 0.22)):
                        continue
                    frac = ((x1 - x0) * (y1 - y0)) / area
                    if frac < _NESTED_MIN_AREA or frac > _NESTED_MAX_AREA:
                        continue
                    # Four-sided inset: require strong edge energy on every side.
                    if y1 >= row_e.size or x1 >= col_e.size:
                        continue
                    score = min(
                        float(row_e[y0]),
                        float(row_e[y1]),
                        float(col_e[x0]),
                        float(col_e[x1]),
                    )
                    if score > best:
                        best = score
    out["score"] = best
    if best >= _NESTED_MIN_SIDE_CONTRAST:
        out["ok"] = False
        out["code"] = FAIL_NESTED_OCCUPIED_FRAME
        out["note"] = (
            f"{FAIL_NESTED_OCCUPIED_FRAME}: Panel 9 contains an inset/overlapping "
            f"second occupied frame (border contrast {best:.1f})"
        )
        return out
    return out


def assess_full_sheet_layout(
    png: bytes,
    *,
    template_id: str = ORIGINAL_ERS_V1,
) -> dict[str, Any]:
    """Layout-only full-sheet gate. Extra boards and nested occupied frames fail."""
    extra = assess_extra_board_below_canonical(png=png, template_id=template_id)
    if not extra.get("ok"):
        return extra
    nested = assess_panel9_nested_frame(png, template_id=template_id)
    if not nested.get("ok"):
        nested = {**extra, **nested, "extraHeightPx": extra.get("extraHeightPx"), "extraHeightRatio": extra.get("extraHeightRatio")}
        return nested
    return {
        **extra,
        "ok": True,
        "code": None,
        "note": nested.get("note") or extra.get("note") or "canonical sheet layout",
        "score": nested.get("score", 0.0),
    }


def validate_full_sheet(
    db: Any,
    project_id: str,
    *,
    asset_id: str,
    packet: dict[str, Any],
    png: bytes | None = None,
) -> dict[str, Any]:
    """Per-panel status. Identity is blocking for occupied when a saved character is required."""
    panels: dict[str, dict[str, Any]] = {
        key: {"verdict": "NOT_VERIFIED", "reason": "Full-sheet visual review is advisory unless identity is required."}
        for key in CANONICAL_PANELS
    }
    readable = bool(png)
    for key in ("hero", "spatial", "three_d", "directional", "materials", "lighting", "dna", "continuity"):
        panels[key] = {
            "verdict": "PASS" if readable else "NOT_VERIFIED",
            "reason": "Sheet bytes present." if readable else "Sheet bytes unavailable.",
        }
    identity: dict[str, Any] = {}
    if packet_needs_occupied(packet):
        crop_id = asset_id
        if png:
            try:
                from ..config import settings
                from ..db import Asset

                dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
                dest_dir.mkdir(parents=True, exist_ok=True)
                crop_path = dest_dir / f"ers-panel9-{asset_id[:8]}.png"
                crop_path.write_bytes(crop_panel_bytes(png, "occupied"))
                crop_asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    tag="ers_panel9_crop",
                    kind="image",
                    filename=crop_path.name,
                    path=str(crop_path),
                    comfy_name="",
                    scope="project",
                    labels_json=json.dumps(["ERS", "panel9-crop"]),
                    prompt_meta_json=json.dumps(
                        {
                            "libraryVisible": False,
                            "sourceFeature": "ers_full_sheet",
                            "role": "ers_panel9_crop",
                            "derivedFrom": asset_id,
                            "panel": "occupied",
                        }
                    ),
                )
                db.add(crop_asset)
                db.flush()
                crop_id = crop_asset.id
            except Exception as exc:
                logger.info("Full-sheet Panel 9 crop skipped: %s", exc)
        identity = apply_occupied_identity_gate(db, project_id, asset_id=crop_id, packet=packet)
        panels["occupied"] = {
            "verdict": identity.get("verdict") or FAIL_CHARACTER_IDENTITY,
            "reason": identity.get("reason") or "",
        }
    else:
        panels["occupied"] = {"verdict": "N/A", "reason": "No saved character on the Spatial Map."}
    layout: dict[str, Any] = {
        "ok": True,
        "code": None,
        "note": "Sheet bytes unavailable; layout not assessed.",
    }
    if png:
        layout = assess_full_sheet_layout(png)
    blocking_identity = panels["occupied"].get("verdict") == FAIL_CHARACTER_IDENTITY
    blocking_failure = ""
    if not layout.get("ok"):
        blocking_failure = str(layout.get("code") or FAIL_EXTRA_BOARD)
        if layout.get("code") == FAIL_NESTED_OCCUPIED_FRAME and panels["occupied"].get("verdict") in {
            "NOT_VERIFIED",
            "PASS",
            "N/A",
        }:
            panels["occupied"] = {
                "verdict": FAIL_NESTED_OCCUPIED_FRAME,
                "reason": layout.get("note") or FAIL_NESTED_OCCUPIED_FRAME,
            }
    elif blocking_identity:
        blocking_failure = FAIL_CHARACTER_IDENTITY
    return {
        "panels": panels,
        "identity": identity,
        "layout": layout,
        "blockingFailure": blocking_failure,
        "readable": readable,
    }


def persist_full_sheet_ers(
    db: Any,
    project_id: str,
    *,
    asset_id: str,
    sheet_id: str = "",
    package_id: str = "",
    sheet: Any = None,
    package: Any = None,
    spatial_document: Any = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind the GPT full-sheet PNG and write Adept machine JSON. Never 2K-compose."""
    from ..codirector.capabilities.handlers.ers_generate import persist_ers_composite_asset
    from ..config import settings
    from ..db import Asset
    from ..environment_reference_sheet.store import load_sheet, save_sheet
    from .ers_component_pipeline import _stamp_sheet_grounding_fingerprint
    from .ers_persistence import list_ers_packages, load_ers_package, save_ers_package
    from .service import get_document

    ctx = dict(ctx or {})
    asset_id = str(asset_id or "").strip()
    sheet_id = str(sheet_id or "").strip()
    package_id = str(package_id or "").strip()
    project_id = str(project_id or "").strip()

    current_package = package
    if current_package is None and package_id:
        try:
            current_package = load_ers_package(db, project_id, package_id)
        except Exception:
            current_package = None
    if current_package is None and sheet_id:
        packages = [
            p
            for p in list_ers_packages(db, project_id)
            if str((p.metadata or {}).get("sheet_id") or "") == sheet_id
            and not str(p.id).startswith("runtime-")
        ]
        if packages:
            current_package = sorted(
                packages, key=lambda p: p.updated_at or p.created_at or "", reverse=True
            )[0]

    current_sheet = sheet
    if current_sheet is None and sheet_id:
        current_sheet = load_sheet(project_id, sheet_id)

    map_id = str(getattr(current_package, "scene_layout_id", "") or ctx.get("spatialMapId") or "")
    if spatial_document is None and db is not None and map_id:
        try:
            spatial_document = get_document(db, project_id, map_id)
        except Exception:
            spatial_document = None

    packet = hydrate_ers_character_canon(
        db,
        compile_ers_packet(spatial_document, project_id=project_id) if spatial_document is not None else {},
        project_id=project_id,
    )

    png = b""
    row = db.get(Asset, asset_id) if db is not None and asset_id else None
    if row is not None:
        path = Path(str(getattr(row, "path", "") or ""))
        if path.is_file():
            png = path.read_bytes()

    validation = validate_full_sheet(db, project_id, asset_id=asset_id, packet=packet, png=png or None)

    identity_rows = []
    for item in packet.get("characters") or []:
        cid = str(item.get("characterId") or item.get("character_id") or "").strip()
        if not cid:
            continue
        identity_rows.append(
            {
                "placementId": item.get("id"),
                "characterId": cid,
                "displayName": item.get("displayName") or item.get("label"),
                "approvedRevision": item.get("approvedRevision"),
                "referenceAssetId": item.get("referenceAssetId"),
                "characterSheetAssetId": item.get("characterSheetAssetId"),
                "occupiedComponent": "occupied",
                "identityRequired": True,
            }
        )
    machine = {
        **packet,
        "generationMode": GENERATION_MODE,
        "ers_pipeline": PIPELINE_MODE,
        "ersTemplateId": ORIGINAL_ERS_V1,
        "masterAssetId": None,
        "directional_assets": {"north": None, "east": None, "south": None, "west": None},
        "threeDRepresentationAssetId": None,
        "occupiedScaleAssetId": None,
        "threeDKind": "representation",
        "threeDTruthLabel": "illustrative",
        "labels": [
            "HERO ENVIRONMENT",
            "SPATIAL / TOP-DOWN",
            "LEGEND",
            "STRUCTURAL / 3D",
            "NORTH",
            "EAST",
            "SOUTH",
            "WEST",
            "MATERIALS",
            "LIGHTING",
            "ENVIRONMENT DNA",
            "CONTINUITY RULES",
            "OCCUPIED SCALE",
        ],
        "summary": human_readable_summary(packet),
        "composeMode": "full_sheet_api",
        "characterIdentity": identity_rows,
        "identityRequired": bool(identity_rows),
        "visualSheetAssetId": asset_id,
        "panelValidation": validation.get("panels") or {},
        "composedAt": _now(),
    }

    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    pkg8 = str(getattr(current_package, "id", "") or "sheet")[:8]
    json_name = f"ers-machine-{pkg8}.json"
    json_path = dest_dir / json_name
    json_path.write_text(json.dumps(machine, indent=2), encoding="utf-8")
    json_asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag="ers_machine_json",
        kind="json",
        filename=json_name,
        path=str(json_path),
        comfy_name="",
        scope="project",
        labels_json=json.dumps(["ERS", "machine-json"]),
        prompt_meta_json=json.dumps(
            {
                "libraryVisible": True,
                "sourceFeature": "ers_full_sheet",
                "role": "ers_machine_json",
                "ersPackageId": getattr(current_package, "id", None),
                "generationMode": GENERATION_MODE,
                "asset_type": "json",
            }
        ),
    )
    db.add(json_asset)
    db.flush()

    if current_package is not None:
        meta = dict(current_package.metadata or {})
        meta.update(
            {
                "generationMode": GENERATION_MODE,
                "ers_pipeline": PIPELINE_MODE,
                "ersTemplateId": ORIGINAL_ERS_V1,
                "ersCollageTemplateId": ORIGINAL_ERS_V1,
                "collageAssetId": asset_id,
                "machineJsonAssetId": json_asset.id,
                "packet": packet,
                "panelValidation": validation.get("panels") or {},
                "identityGate": validation.get("identity") or {},
                "pipeline_status": "failed" if validation.get("blockingFailure") else "complete",
                "retryComponent": "occupied" if validation.get("blockingFailure") == FAIL_CHARACTER_IDENTITY else None,
                "composedAt": _now(),
                "sheet_id": sheet_id or meta.get("sheet_id"),
            }
        )
        if validation.get("blockingFailure") != FAIL_CHARACTER_IDENTITY:
            meta.pop("retryComponent", None)
        current_package.metadata = {k: v for k, v in meta.items() if v is not None}
        current_package.ers_composite_asset_id = asset_id

    persist_ers_composite_asset(
        db,
        project_id,
        sheet_id=sheet_id or str(getattr(current_sheet, "sheetId", "") or ""),
        asset_id=asset_id,
        package_id=str(getattr(current_package, "id", "") or package_id),
        sheet=current_sheet,
        package=current_package,
    )
    if current_sheet is not None:
        _stamp_sheet_grounding_fingerprint(db, project_id, current_sheet, map_id)
        provenance = getattr(current_sheet, "provenance", None)
        if provenance is not None:
            details = dict(getattr(provenance, "details", None) or {})
            details.update(
                {
                    "generationMode": GENERATION_MODE,
                    "ers_pipeline": PIPELINE_MODE,
                    "ersTemplateId": ORIGINAL_ERS_V1,
                    "provider": "kie",
                    "model": "gpt-image-2-image-to-image",
                    "visualSheetAssetId": asset_id,
                    "machineJsonAssetId": json_asset.id,
                    "referenceAssetIds": list(ctx.get("groundingAssetIds") or []),
                    "characterIds": list(packet.get("characterIds") or ctx.get("characterIds") or []),
                    "panelValidation": validation.get("panels") or {},
                    "identityGate": validation.get("identity") or {},
                    "generatedAt": _now(),
                }
            )
            if ctx.get("groundingFingerprint"):
                details["groundingFingerprint"] = ctx.get("groundingFingerprint")
            provenance.details = details
            save_sheet(current_sheet)
    if current_package is not None:
        save_ers_package(db, project_id, current_package, provenance="ers_full_sheet_persist")

    return {
        "ers_composite_asset_id": asset_id,
        "machineJsonAssetId": json_asset.id,
        "package_id": getattr(current_package, "id", None),
        "generationMode": GENERATION_MODE,
        "validation": validation,
        "has_reference": True,
    }


def persist_repair_lineage(
    package: Any,
    *,
    original_full_sheet_asset_id: str,
    replacement_component: str,
    replacement_asset_id: str,
    restitch_composite_asset_id: str,
) -> None:
    meta = dict(getattr(package, "metadata", None) or {})
    meta["originalFullSheetAssetId"] = original_full_sheet_asset_id
    meta["replacementComponent"] = replacement_component
    meta["replacementAssetId"] = replacement_asset_id
    meta["repairRevision"] = int(meta.get("repairRevision") or 0) + 1
    meta["restitchCompositeAssetId"] = restitch_composite_asset_id
    package.metadata = meta


def stamp_repair_on_sheet(
    sheet: Any,
    *,
    identity: dict[str, Any] | None,
    original_full_sheet_asset_id: str,
    replacement_component: str,
    replacement_asset_id: str,
    restitch_composite_asset_id: str,
    repair_revision: int,
) -> None:
    """Write Occupied repair identity + lineage onto the sheet so reload stays honest."""
    if sheet is None:
        return
    provenance = getattr(sheet, "provenance", None)
    if provenance is None:
        return
    details = dict(getattr(provenance, "details", None) or {})
    if identity:
        details["identityGate"] = identity
    details.update(
        {
            "originalFullSheetAssetId": original_full_sheet_asset_id,
            "replacementComponent": replacement_component,
            "replacementAssetId": replacement_asset_id,
            "repairRevision": repair_revision,
            "restitchCompositeAssetId": restitch_composite_asset_id,
            "visualSheetAssetId": restitch_composite_asset_id,
        }
    )
    provenance.details = details


def ensure_derived_panel_asset(
    db: Any,
    project_id: str,
    *,
    full_sheet_asset_id: str,
    panel: str,
    template_id: str = ORIGINAL_ERS_V1,
) -> str:
    """Lazy deterministic crop for Mini / downstream. Zero paid jobs."""
    from ..config import settings
    from ..db import Asset

    full_sheet_asset_id = str(full_sheet_asset_id or "").strip()
    panel = str(panel or "").strip().lower()
    if not full_sheet_asset_id or not panel:
        return ""
    existing = (
        db.query(Asset)
        .filter(Asset.project_id == project_id, Asset.tag == f"ers_derived_{panel}")
        .all()
        if db is not None
        else []
    )
    for row in existing:
        try:
            meta = json.loads(str(getattr(row, "prompt_meta_json", "") or "") or "{}")
        except Exception:
            meta = {}
        if str(meta.get("derivedFrom") or "") == full_sheet_asset_id and str(meta.get("panel") or "") == panel:
            return str(row.id)
    src = db.get(Asset, full_sheet_asset_id)
    if src is None:
        return ""
    png = Path(str(getattr(src, "path", "") or "")).read_bytes()
    cropped = crop_panel_bytes(png, panel, template_id=template_id)
    dest_dir = Path(settings.data_dir) / "projects" / project_id / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"ers-derived-{panel}-{full_sheet_asset_id[:8]}.png"
    path = dest_dir / name
    path.write_bytes(cropped)
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=f"ers_derived_{panel}",
        kind="image",
        filename=name,
        path=str(path),
        comfy_name="",
        scope="project",
        parent_asset_id=full_sheet_asset_id,
        labels_json=json.dumps(["ERS", "derived-panel"]),
        prompt_meta_json=json.dumps(
            {
                "libraryVisible": False,
                "sourceFeature": "ers_full_sheet",
                "role": f"ers_derived_{panel}",
                "derivedFrom": full_sheet_asset_id,
                "panel": panel,
            }
        ),
    )
    db.add(asset)
    db.flush()
    return str(asset.id)
