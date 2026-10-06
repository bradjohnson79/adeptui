"""Select / refine / persist PerceptionSelectionPacket. SAM decode lives in the worker."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from PIL import Image

from ...image_product.masks import get_mask, get_mask_path, save_mask
from .cache import get_cached_selection, load_packet, set_cached_selection, store_packet
from .paths import SAM21_REVISION, selection_models_present
from .perception_router import creator_unavailable_message, plan_perception
from .selection_contracts import (
    PerceptionSelectionPacket,
    RefineRequest,
    SelectRequest,
)
from .spatial_service import ordinal_for_box, spatial_available

logger = logging.getLogger(__name__)

WorkerFn = Callable[[dict[str, Any]], dict[str, Any]]


def _asset_row(db: Any, project_id: str, asset_id: str) -> Any:
    from ...db import Asset

    if db is None:
        return None
    try:
        asset = db.get(Asset, asset_id)
    except Exception:
        return None
    if asset is None or str(getattr(asset, "project_id", "")) != project_id:
        return None
    return asset


def _asset_path(db: Any, project_id: str, asset_id: str) -> str:
    asset = _asset_row(db, project_id, asset_id)
    path = str(getattr(asset, "path", "") or "") if asset is not None else ""
    return path if path and Path(path).is_file() else ""


def _decode_png(b64: str) -> bytes:
    raw = b64.split(",", 1)[-1] if "," in b64 else b64
    return base64.b64decode(raw)


def _persist_mask(
    project_id: str,
    source_asset_id: str,
    png_bytes: bytes,
    role: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return save_mask(
        project_id,
        source_asset_id=source_asset_id,
        png_bytes=png_bytes,
        role=role if role in {"include", "exclude", "replace"} else "include",
        creator="perception",
        metadata=metadata,
    )


def _register_library_png(
    db: Any,
    project_id: str,
    png_bytes: bytes,
    *,
    tag: str,
    parent_asset_id: str,
) -> str:
    from ...config import settings
    from ...db import Asset, Project

    project = db.get(Project, project_id) if db is not None else None
    if project is None:
        return ""
    asset_id = str(uuid4())
    dest_dir = Path(settings.data_dir) / "assets" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{asset_id}.png"
    dest.write_bytes(png_bytes)
    asset = Asset(
        id=asset_id,
        project_id=project_id,
        tag=tag.lstrip("@").strip()[:64],
        kind="image",
        filename=f"{tag or asset_id[:8]}.png",
        path=str(dest),
        comfy_name="",
        parent_asset_id=parent_asset_id or None,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    try:
        from ...project_library.service import assign_asset

        assign_asset(db, asset, classified_by="perception")
    except Exception as exc:  # noqa: BLE001
        logger.info("library assign skipped: %s", exc)
    return asset_id


def apply_subject_alpha(source_path: str, mask_path: str, fill_color: str | None = None) -> bytes:
    source = Image.open(source_path).convert("RGBA")
    mask = Image.open(mask_path).convert("L")
    if mask.size != source.size:
        mask = mask.resize(source.size, Image.Resampling.BILINEAR)
    if fill_color:
        hex_color = fill_color.strip().lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(ch * 2 for ch in hex_color)
        rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) if len(hex_color) == 6 else (0, 0, 0)
        bg = Image.new("RGBA", source.size, (*rgb, 255))
        out = Image.composite(source, bg, mask)
    else:
        out = source.copy()
        out.putalpha(mask)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def select(
    db: Any,
    project_id: str,
    body: SelectRequest,
    *,
    worker: Optional[WorkerFn] = None,
    worker_timeout: int = 180,
    release_generator: bool = True,
) -> dict[str, Any]:
    if not selection_models_present() and worker is None:
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": creator_unavailable_message("select"),
        }
    plan = plan_perception("select", depth_available=spatial_available())
    entity = (body.label or body.kind or "object").strip()
    cached = get_cached_selection(
        project_id=project_id,
        asset_id=body.assetId,
        frame_time_ms=body.frameTimeMs,
        entity=entity,
        model_id="sam21-hiera-tiny",
        model_version=SAM21_REVISION,
        source=body.kind if body.kind in {"subject", "background"} else ("text" if body.label else "click"),
    )
    if cached and cached.get("maskAssetId") and get_mask(project_id, str(cached["maskAssetId"])):
        return {"ok": True, "status": "available", "selection": cached, "cached": True}

    image_path = _asset_path(db, project_id, body.assetId)
    if not image_path and worker is None:
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": "The picture is missing.",
        }

    from .worker_client import run_selection_worker

    def _default_worker(payload: dict[str, Any]) -> dict[str, Any]:
        return run_selection_worker(
            payload,
            timeout=worker_timeout,
            release_generator=release_generator,
        )

    payload = (worker or _default_worker)(
        {
            "mode": "select",
            "imagePath": image_path,
            "point": body.point,
            "box": body.box,
            "label": body.label,
            "kind": body.kind,
            "useDino": plan["dino"],
            "useDepth": plan["depth"],
        }
    )
    if not payload.get("ok"):
        reason = str(payload.get("reason") or "")
        if "TORCH" in reason or "WORKER" in reason:
            message = "Intelligent selection needs its GPU environment. Open Setup and repair Intelligent Selection."
        else:
            message = str(payload.get("message") or creator_unavailable_message("select"))
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": message,
        }
    png_b64 = str(payload.get("maskPngBase64") or "")
    if not png_b64:
        return {
            "ok": False,
            "maskAssetId": "",
            "status": "unavailable",
            "message": "Paint the region.",
        }
    role = body.role
    persist_role = "exclude" if role == "exclude" else ("replace" if role == "replace" else "include")
    record = _persist_mask(
        project_id,
        body.assetId,
        _decode_png(png_b64),
        persist_role,
        {
            "selectionRole": role,
            "kind": body.kind,
            "label": body.label,
            "modelId": "sam21-hiera-tiny",
            "modelVersion": SAM21_REVISION,
        },
    )
    bounds = payload.get("bounds") if isinstance(payload.get("bounds"), dict) else None
    source = (
        "subject"
        if body.kind == "subject"
        else "background"
        if body.kind == "background"
        else "text"
        if body.label
        else "box"
        if body.box
        else "click"
    )
    packet = PerceptionSelectionPacket(
        projectId=project_id,
        assetId=body.assetId,
        frameTimeMs=body.frameTimeMs,
        semanticLabel=str(payload.get("label") or body.label or body.kind),
        kind=body.kind,
        maskAssetId=str(record["maskId"]),
        bounds=bounds,
        confidence=payload.get("confidence"),
        role=role,
        source=source,  # type: ignore[arg-type]
        modelId="sam21-hiera-tiny",
        modelVersion=SAM21_REVISION,
        promptModelId="grounding-dino-tiny" if plan["dino"] else "",
        provenance={
            "device": str(payload.get("device") or ""),
            "ordinalDepth": ordinal_for_box(bounds, None),
            "worker": "stills-perception",
        },
    )
    dumped = packet.model_dump()
    store_packet(dumped)
    set_cached_selection(dumped, entity=entity, source=source)
    return {
        "ok": True,
        "status": "available",
        "maskAssetId": packet.maskAssetId,
        "selection": dumped,
        "overlayPngBase64": png_b64,
        "message": f'Selected {packet.semanticLabel or "the subject"}.',
    }


def refine(
    db: Any,
    project_id: str,
    selection_id: str,
    body: RefineRequest,
    *,
    worker: Optional[WorkerFn] = None,
) -> dict[str, Any]:
    existing = load_packet(project_id, selection_id)
    if not existing:
        return {"ok": False, "message": "That selection is gone. Select again."}
    if body.brushPngBase64:
        record = _persist_mask(
            project_id,
            str(existing.get("assetId") or ""),
            _decode_png(body.brushPngBase64),
            str(body.role or existing.get("role") or "include"),
            {"refinedFrom": selection_id, "source": "refine"},
        )
        existing["maskAssetId"] = record["maskId"]
        existing["source"] = "refine"
        if body.role:
            existing["role"] = body.role
        store_packet(existing)
        return {"ok": True, "selection": existing, "maskAssetId": record["maskId"]}
    request = SelectRequest(
        assetId=str(existing.get("assetId") or ""),
        point=(body.addPoints[0] if body.addPoints else None),
        label=str(existing.get("semanticLabel") or ""),
        kind=existing.get("kind") or "object",
        role=body.role or existing.get("role") or "include",
        frameTimeMs=existing.get("frameTimeMs"),
    )
    return select(db, project_id, request, worker=worker)


def get_selection(project_id: str, selection_id: str) -> dict[str, Any] | None:
    packet = load_packet(project_id, selection_id)
    if not packet:
        return None
    mask_id = str(packet.get("maskAssetId") or "")
    return {
        "selection": packet,
        "mask": get_mask(project_id, mask_id) if mask_id else None,
        "maskPath": get_mask_path(project_id, mask_id) if mask_id else None,
    }


def remove_background(
    db: Any,
    project_id: str,
    asset_id: str,
    *,
    fill_color: str | None = None,
    save_to_library: bool = True,
    tag: str = "",
    worker: Optional[WorkerFn] = None,
) -> dict[str, Any]:
    selected = select(
        db,
        project_id,
        SelectRequest(assetId=asset_id, kind="subject", role="subject"),
        worker=worker,
    )
    if not selected.get("ok"):
        return selected
    packet = selected.get("selection") or {}
    mask_id = str(packet.get("maskAssetId") or "")
    mask_path = get_mask_path(project_id, mask_id)
    source_path = _asset_path(db, project_id, asset_id)
    if not mask_path or not source_path:
        return {"ok": False, "message": "Could not build a transparent picture. Paint the region."}
    png = apply_subject_alpha(source_path, mask_path, fill_color)
    result_asset_id = ""
    if save_to_library:
        result_asset_id = _register_library_png(
            db,
            project_id,
            png,
            tag=tag or "no-background",
            parent_asset_id=asset_id,
        )
    return {
        "ok": True,
        "maskAssetId": mask_id,
        "selection": packet,
        "resultAssetId": result_asset_id,
        "pngBase64": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        "message": "Background removed.",
    }


def extract_subject(
    db: Any,
    project_id: str,
    asset_id: str,
    *,
    tag: str = "posecraft-subject",
    worker: Optional[WorkerFn] = None,
) -> dict[str, Any]:
    result = remove_background(db, project_id, asset_id, save_to_library=True, tag=tag, worker=worker)
    if result.get("ok"):
        result["message"] = "Subject isolated for PoseCraft."
    return result
