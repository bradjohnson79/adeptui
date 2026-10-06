"""ERS sheet region edit — Certified zimage.inpaint, derivative-only.

Enqueue Image Core purpose=region_edit / engine zimage.inpaint against the
ERS composite (or explicit sourceAssetId). Returns a derivative job.

HARD RULES:
- Never persist_ers_composite_asset
- Never overwrite sheet.ers_composite_asset_id
- Never save_sheet as part of edit
- Never set spatialMapCorrect / environment_reference_sheet purpose
- Creator editPrompt is frozen (coDirectorRewrite=False)
- Mask required for local zimage.inpaint; optional for hosted fal/kie/wavespeed edit
- Selected EC provider/model is honored (no silent Kie fallback when fal selected)
- Drawing overlay / labels / markers are guidance-only (not baked into source
  or derivative unless a future explicit bake path is opted in)
- Version v2 create/approve is out of scope
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..image_product import masks as mask_store

ENGINE = "zimage.inpaint"
ENGINE_CERT_ID = "IMG-ZIMAGE-INPAINT-001"
ENGINE_FAMILY = "zimage"
ENGINE_OPERATION = "image.inpaint"
ENGINE_EDIT_OPERATION = "modify"
OVERLAY_BAKE_DEFAULT = "guidance_only"


def _preview_url(project_id: str, asset_id: str | None) -> str | None:
    aid = (asset_id or "").strip()
    if not aid:
        return None
    return f"/api/projects/{project_id}/assets/{aid}/file"


def resolve_sheet_composite_id(sheet: Any) -> str | None:
    """sheet.ers_composite_asset_id or composition.renderedAssetIds composite/png/sheet."""
    composite = getattr(sheet, "ers_composite_asset_id", None)
    if composite:
        return str(composite).strip() or None
    composition = getattr(sheet, "composition", None)
    rendered = getattr(composition, "renderedAssetIds", None) or {}
    if isinstance(rendered, dict):
        for key in ("composite", "png", "sheet"):
            val = rendered.get(key)
            if val:
                return str(val).strip() or None
    return None


def resolve_source_asset_id(sheet: Any, source_asset_id: str | None) -> str:
    explicit = (source_asset_id or "").strip()
    if explicit:
        return explicit
    composite = resolve_sheet_composite_id(sheet)
    if composite:
        return composite
    raise ValueError(
        "sourceAssetId required (sheet has no ers_composite_asset_id / rendered composite)."
    )


def ensure_mask(
    project_id: str,
    *,
    source_asset_id: str,
    mask_asset_id: str | None,
    mask_png: str | None,
    width: int | None,
    height: int | None,
) -> dict[str, Any]:
    """Require maskAssetId and/or maskPng. Persist maskPng via image_product.masks."""
    mid = (mask_asset_id or "").strip()
    if mid:
        mask = mask_store.get_mask(project_id, mid)
        if not mask:
            raise ValueError("Mask not found. Paint a region and save the mask first.")
        return mask
    if not (mask_png or "").strip():
        raise ValueError("maskPng or maskAssetId required (white=edit, black=preserve).")
    dims: dict[str, int] = {}
    if width and height:
        dims = {"width": int(width), "height": int(height)}
    return mask_store.save_mask(
        project_id,
        source_asset_id=source_asset_id,
        png_base64=mask_png,
        role="include",
        dimensions=dims or None,
        creator="ers.edit",
        metadata={"white": "edit", "black": "preserve", "ersEdit": True},
    )


def _source_pixel_size(source: Asset, width: int | None, height: int | None) -> tuple[int, int]:
    sw = int(width or 0)
    sh = int(height or 0)
    if sw > 0 and sh > 0:
        return sw, sh
    path = getattr(source, "path", None) or ""
    if path and Path(path).is_file():
        try:
            from PIL import Image

            with Image.open(path) as im:
                return int(im.size[0]), int(im.size[1])
        except Exception:
            pass
    meta = getattr(source, "prompt_meta_json", None)
    if isinstance(meta, str) and meta:
        try:
            parsed = json.loads(meta)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            try:
                mw = int(parsed.get("width") or parsed.get("w") or 0)
                mh = int(parsed.get("height") or parsed.get("h") or 0)
                if mw > 0 and mh > 0:
                    return mw, mh
            except (TypeError, ValueError):
                pass
    return sw, sh


def _job_result_asset_id(job_obj: Any) -> str | None:
    if job_obj is None:
        return None
    for attr in ("asset_id", "output_asset_id"):
        val = getattr(job_obj, attr, None)
        if val:
            return str(val)
    raw = getattr(job_obj, "params_json", None) or ""
    if raw:
        try:
            params = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            params = None
        if isinstance(params, dict):
            for key in ("output_asset_id", "resultAssetId", "derivativeAssetId", "assetId"):
                val = params.get(key)
                if val:
                    return str(val)
    return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_text_labels(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("textLabels must be an array")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"textLabels[{i}] must be an object")
        text = str(item.get("text") or item.get("label") or "").strip()
        if not text:
            raise ValueError(f"textLabels[{i}].text required")
        entry: dict[str, Any] = {
            "id": str(item.get("id") or f"label-{i + 1}"),
            "text": text,
        }
        for key in ("x", "y", "normalized", "color", "fontSize", "anchor"):
            if key in item and item.get(key) is not None:
                entry[key] = item.get(key)
        out.append(entry)
    return out


def _normalize_numbered_markers(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("numberedMarkers must be an array")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"numberedMarkers[{i}] must be an object")
        number = item.get("number", item.get("n", i + 1))
        try:
            number_i = int(number)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"numberedMarkers[{i}].number must be an integer") from exc
        entry: dict[str, Any] = {"number": number_i}
        label = item.get("label") or item.get("text")
        if label is not None:
            entry["label"] = str(label)
        for key in ("x", "y", "normalized", "color", "id"):
            if key in item and item.get(key) is not None:
                entry[key] = item.get(key)
        if "id" not in entry:
            entry["id"] = f"marker-{number_i}"
        out.append(entry)
    return out


def _normalize_drawing_overlay(raw: Any) -> dict[str, Any] | None:
    """Accept string base64 or object with rasterBase64/pngBase64 + optional vectors."""
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return {"rasterBase64": text, "vectors": []}
    if not isinstance(raw, dict):
        raise ValueError("drawingOverlay must be a base64 string or object")
    raster = (
        raw.get("rasterBase64")
        or raw.get("rasterPngBase64")
        or raw.get("pngBase64")
        or raw.get("imageBase64")
        or raw.get("base64")
        or None
    )
    if raw.get("rasterAssetId") and not raw.get("assetId"):
        raw = dict(raw)
        raw["assetId"] = raw.get("rasterAssetId")
    if isinstance(raster, str):
        raster = raster.strip() or None
    vectors = raw.get("vectors")
    if vectors is None:
        vectors = raw.get("strokes") or raw.get("shapes") or []
    if vectors is not None and not isinstance(vectors, list):
        raise ValueError("drawingOverlay.vectors must be an array")
    overlay: dict[str, Any] = {
        "vectors": list(vectors or []),
    }
    if raster:
        overlay["rasterBase64"] = raster
    for key in ("width", "height", "mimeType", "assetId"):
        if raw.get(key) is not None:
            overlay[key] = raw.get(key)
    if not overlay.get("rasterBase64") and not overlay.get("vectors") and not overlay.get("assetId"):
        return None
    return overlay


def _persist_drawing_overlay_raster(
    project_id: str,
    *,
    source_asset_id: str,
    overlay: dict[str, Any],
    sheet_id: str,
) -> dict[str, Any] | None:
    """Persist overlay raster beside masks as guidance-only. Never touches source pixels."""
    raster = overlay.get("rasterBase64")
    if not raster or not isinstance(raster, str):
        existing = str(overlay.get("assetId") or "").strip()
        if existing:
            return {
                "overlayAssetId": existing,
                "path": None,
                "persisted": False,
            }
        return None
    from ..image_product.store import project_dir

    b64 = raster.split(",", 1)[-1] if "," in raster else raster
    try:
        raw = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"drawingOverlay rasterBase64 is not valid base64: {exc}") from exc
    if not raw:
        raise ValueError("drawingOverlay rasterBase64 decoded to empty bytes")

    overlay_id = f"overlay-{uuid4().hex[:12]}"
    out_dir = project_dir(project_id) / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{overlay_id}.png"
    out_path.write_bytes(raw)
    checksum = "sha256:" + hashlib.sha256(raw).hexdigest()
    record = {
        "overlayAssetId": overlay_id,
        "projectId": project_id,
        "sourceAssetId": source_asset_id,
        "sheetId": sheet_id,
        "filename": out_path.name,
        "path": str(out_path),
        "checksum": checksum,
        "role": "guidance",
        "creator": "ers.edit",
        "createdAt": _now(),
        "metadata": {
            "ersOverlayGuidance": True,
            "overlayBakePolicy": OVERLAY_BAKE_DEFAULT,
            "notCompositedIntoSource": True,
        },
        "dimensions": {
            k: overlay[k]
            for k in ("width", "height")
            if isinstance(overlay.get(k), int) and overlay.get(k)
        },
        "persisted": True,
    }
    meta_path = out_dir / f"{overlay_id}.json"
    meta_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return record


def _guidance_bundle(
    *,
    project_id: str,
    sheet_id: str,
    source_asset_id: str,
    drawing_overlay: Any,
    text_labels: Any,
    numbered_markers: Any,
    overlay_bake_policy: str | None,
) -> dict[str, Any]:
    """Build guidance-only payload for creativeContext. Does not mutate source/prompt."""
    policy = (overlay_bake_policy or OVERLAY_BAKE_DEFAULT).strip() or OVERLAY_BAKE_DEFAULT
    if policy not in {"guidance_only", "bake_if_prompt_requests"}:
        raise ValueError("overlayBakePolicy must be guidance_only or bake_if_prompt_requests")
    # HARD: never auto-bake into source/derivative in this lane.
    effective_policy = OVERLAY_BAKE_DEFAULT if policy != "guidance_only" else OVERLAY_BAKE_DEFAULT
    # Still record requested policy for provenance, but enforce guidance_only behavior.
    overlay = _normalize_drawing_overlay(drawing_overlay)
    labels = _normalize_text_labels(text_labels)
    markers = _normalize_numbered_markers(numbered_markers)
    if overlay is None and not labels and not markers:
        return {
            "hasGuidance": False,
            "overlayBakePolicy": OVERLAY_BAKE_DEFAULT,
            "requestedOverlayBakePolicy": policy,
        }

    persisted = None
    if overlay is not None:
        persisted = _persist_drawing_overlay_raster(
            project_id,
            source_asset_id=source_asset_id,
            overlay=overlay,
            sheet_id=sheet_id,
        )

    # Strip bulky base64 from creativeContext after persist (keep vectors + id).
    overlay_ctx: dict[str, Any] | None = None
    if overlay is not None:
        overlay_ctx = {
            "vectors": list(overlay.get("vectors") or []),
            "hasRaster": bool(overlay.get("rasterBase64") or (persisted or {}).get("overlayAssetId")),
        }
        for key in ("width", "height", "mimeType"):
            if overlay.get(key) is not None:
                overlay_ctx[key] = overlay.get(key)
        if persisted and persisted.get("overlayAssetId"):
            overlay_ctx["overlayAssetId"] = persisted["overlayAssetId"]
            overlay_ctx["path"] = persisted.get("path")
        elif overlay.get("assetId"):
            overlay_ctx["overlayAssetId"] = overlay.get("assetId")

    return {
        "hasGuidance": True,
        "overlayBakePolicy": effective_policy,
        "requestedOverlayBakePolicy": policy,
        "drawingOverlay": overlay_ctx,
        "textLabels": labels,
        "numberedMarkers": markers,
        "overlayAssetId": (persisted or {}).get("overlayAssetId") if persisted else (
            (overlay or {}).get("assetId") if overlay else None
        ),
        "guidanceModel": {
            "mask": "allowed_edit_region",
            "overlayLabelsMarkers": "spatial_guidance",
            "prompt": "instruction",
            "bakeIntoDerivative": False,
            "bakeIntoSource": False,
        },
    }


def _full_white_mask_png(width: int, height: int) -> str:
    """Include-everything mask (white=edit) for prompt-only edits."""
    from io import BytesIO

    from PIL import Image

    w = max(1, int(width or 0))
    h = max(1, int(height or 0))
    buf = BytesIO()
    Image.new("L", (w, h), 255).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _normalize_requested_provider(
    *,
    requested_provider: str | None = None,
    hosted_model_id: str | None = None,
    fal_image_model_id: str | None = None,
    kie_image_model_id: str | None = None,
    wavespeed_image_model_id: str | None = None,
) -> str:
    """Return fal|kie|wavespeed|\"\" from explicit EC selection. Never invent a provider."""
    from ..image_product.compile import explicit_hosted_provider

    return explicit_hosted_provider(
        {
            "requested_provider": requested_provider,
            "provider": requested_provider,
            "providerKind": requested_provider,
            "hostedModelId": hosted_model_id,
            "falImageModelId": fal_image_model_id,
            "kieImageModelId": kie_image_model_id,
            "wavespeedImageModelId": wavespeed_image_model_id,
        }
    )


def _fal_edit_endpoint(fal_image_model_id: str | None, hosted_model_id: str | None) -> str:
    """Resolve fal still endpoint and force /edit sibling (never T2I)."""
    from ..fal_catalog import fal_still_edit_model_id, resolve_fal_still_endpoint

    resolved = resolve_fal_still_endpoint(
        (fal_image_model_id or "").strip() or None,
        (hosted_model_id or "").strip() or None,
    )
    pin = (resolved or fal_image_model_id or hosted_model_id or "").strip()
    if not pin:
        raise ValueError("fal.ai could not start this environment edit (no model selected).")
    edit_id = fal_still_edit_model_id(pin)
    if not edit_id or "/edit" not in edit_id.lower():
        raise ValueError(
            "Refusing silent T2I-as-edit: selected fal model has no image-to-image /edit variant."
        )
    return edit_id


def _enqueue_payload(
    *,
    project_id: str,
    sheet_id: str,
    source_asset_id: str,
    mask_asset_id: str | None,
    sheet_composite_id: str | None,
    enqueue: dict[str, Any],
    guidance: dict[str, Any] | None = None,
    engine: str | None = None,
) -> dict[str, Any]:
    queue_job_id = str(enqueue.get("queueJobId") or "")
    result_asset_id = enqueue.get("resultAssetId")
    status = str(enqueue.get("status") or "queued")
    engine_key = str(engine or enqueue.get("workflowKey") or ENGINE)
    workflow_key = str(enqueue.get("workflowKey") or engine_key)
    payload = {
        "jobId": queue_job_id,
        "queueJobId": queue_job_id,
        "status": status,
        "workflowKey": workflow_key,
        "derivativeAssetId": result_asset_id,
        "resultAssetId": result_asset_id,
        "sourceAssetId": source_asset_id,
        "sheetId": sheet_id,
        "maskAssetId": mask_asset_id,
        "derivativeOnly": True,
        "ersCompositeAssetId": sheet_composite_id,
        "engine": engine_key,
        "purpose": "region_edit",
        "previewUrl": _preview_url(project_id, result_asset_id if isinstance(result_asset_id, str) else None),
        "family": enqueue.get("family") or ENGINE_FAMILY,
        "operation": enqueue.get("operation") or ENGINE_OPERATION,
        "width": enqueue.get("width"),
        "height": enqueue.get("height"),
        "error": enqueue.get("error"),
        "overlayBakePolicy": OVERLAY_BAKE_DEFAULT,
        "provider": enqueue.get("provider"),
        "requested_provider": enqueue.get("requested_provider"),
    }
    if guidance and guidance.get("hasGuidance"):
        payload["overlayBakePolicy"] = guidance.get("overlayBakePolicy") or OVERLAY_BAKE_DEFAULT
        payload["overlayAssetId"] = guidance.get("overlayAssetId")
        payload["textLabels"] = guidance.get("textLabels") or []
        payload["numberedMarkers"] = guidance.get("numberedMarkers") or []
        payload["drawingOverlay"] = guidance.get("drawingOverlay")
        payload["guidanceOnly"] = True
    return payload


def _enqueue_ers_edit_hosted(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    prompt: str,
    source_id: str,
    sheet_composite_id: str | None,
    mask_id: str | None,
    src_w: int,
    src_h: int,
    guidance: dict[str, Any],
    provider: str,
    hosted_model_id: str | None,
    fal_image_model_id: str | None,
    kie_image_model_id: str | None,
    wavespeed_image_model_id: str | None,
) -> dict[str, Any]:
    """Canonical hosted edit path via enqueue_imagegen_job (fal/kie/wavespeed). Never T2I."""
    from ..storyboard_jobs import enqueue_imagegen_job

    provider = (provider or "").strip().lower()
    if provider not in {"fal", "kie", "wavespeed"}:
        raise ValueError(f"Unsupported hosted provider for ERS edit: {provider or '(empty)'}")

    body: dict[str, Any] = {
        "prompt": prompt,
        "edit": True,
        "operation": "image.inpaint" if mask_id else "image.edit",
        "edit_op": "modify",
        "sourceAssetId": source_id,
        "source_asset_id": source_id,
        "provider": provider,
        "requested_provider": provider,
        "providerKind": provider,
        "providerPreference": "cloud",
        "hostedModelId": (hosted_model_id or "").strip() or None,
        "tag": f"ers_edit_{(sheet_id or '')[:8] or 'sheet'}",
        "creativeContext": {
            "ersEdit": True,
            "sheetId": sheet_id,
            "frozenCreatorPrompt": prompt,
            "coDirectorRewrite": False,
            "derivativeOnly": True,
            "requested_provider": provider,
            "provider": provider,
            "overlayBakePolicy": guidance.get("overlayBakePolicy") or OVERLAY_BAKE_DEFAULT,
            "sourceWidth": src_w or None,
            "sourceHeight": src_h or None,
        },
    }
    if src_w > 0 and src_h > 0:
        body["width"] = int(src_w)
        body["height"] = int(src_h)
        body["forceWidth"] = int(src_w)
        body["forceHeight"] = int(src_h)
    if mask_id:
        body["masks"] = [{"maskAssetId": mask_id, "maskId": mask_id, "role": "include"}]
    if guidance.get("hasGuidance"):
        body["creativeContext"]["drawingOverlay"] = guidance.get("drawingOverlay")
        body["creativeContext"]["textLabels"] = guidance.get("textLabels") or []
        body["creativeContext"]["numberedMarkers"] = guidance.get("numberedMarkers") or []
        body["creativeContext"]["overlayAssetId"] = guidance.get("overlayAssetId")
        body["creativeContext"]["guidanceModel"] = guidance.get("guidanceModel")
        if guidance.get("overlayAssetId"):
            body["ersOverlayGuidanceAssetId"] = guidance["overlayAssetId"]
            body["ersOverlayBakePolicy"] = OVERLAY_BAKE_DEFAULT

    engine_key = provider
    if provider == "fal":
        endpoint = _fal_edit_endpoint(fal_image_model_id, hosted_model_id)
        body["falImageModelId"] = endpoint
        body["model"] = endpoint
        # Strict: never leave a Kie pin that could win adapter selection.
        body.pop("kieImageModelId", None)
        body.pop("wavespeedImageModelId", None)
        engine_key = f"fal:{endpoint}"
        body["creativeContext"]["engine"] = engine_key
        body["creativeContext"]["falImageModelId"] = endpoint
    elif provider == "wavespeed":
        pin = (wavespeed_image_model_id or hosted_model_id or "").strip()
        if not pin:
            raise ValueError("wavespeed.ai could not start this environment edit (no model selected).")
        body["wavespeedImageModelId"] = pin
        body["model"] = pin
        body.pop("falImageModelId", None)
        body.pop("kieImageModelId", None)
        engine_key = f"wavespeed:{pin}"
        body["creativeContext"]["engine"] = engine_key
    else:  # kie
        pin = (kie_image_model_id or hosted_model_id or "").strip()
        if not pin:
            raise ValueError("kie.ai could not start this environment edit (no model selected).")
        body["kieImageModelId"] = pin
        body["model"] = pin
        body.pop("falImageModelId", None)
        body.pop("wavespeedImageModelId", None)
        engine_key = f"kie:{pin}"
        body["creativeContext"]["engine"] = engine_key

    try:
        job = enqueue_imagegen_job(db, project_id, body)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"ERS edit enqueue failed ({provider}): {exc}. "
            "Sheet composite stays active; no overwrite."
        ) from exc

    job_id = str(getattr(job, "id", "") or "")
    status = str(getattr(job, "status", "") or "queued")
    if status.lower() in {"failed", "error"}:
        raise ValueError(
            f"ERS edit failed ({provider}): {getattr(job, 'message', None) or status}. "
            "Sheet composite stays active; no overwrite."
        )

    enqueue = {
        "queueJobId": job_id,
        "status": status,
        "workflowKey": engine_key,
        "family": provider,
        "operation": body.get("operation") or "image.edit",
        "width": src_w or None,
        "height": src_h or None,
        "resultAssetId": getattr(job, "asset_id", None) or getattr(job, "output_asset_id", None),
        "error": None,
        "provider": provider,
        "requested_provider": provider,
    }
    return _enqueue_payload(
        project_id=project_id,
        sheet_id=sheet_id,
        source_asset_id=source_id,
        mask_asset_id=mask_id,
        sheet_composite_id=sheet_composite_id,
        enqueue=enqueue,
        guidance=guidance,
        engine=engine_key,
    )


def save_ers_edit_annotations(
    project_id: str,
    sheet_id: str,
    *,
    source_asset_id: str | None = None,
    legend: Any = None,
    drawing_overlay: Any = None,
    text_labels: Any = None,
    numbered_markers: Any = None,
    overlay_bake_policy: str | None = None,
) -> dict[str, Any]:
    """Lightweight Legend / spatial-map annotation persist — no image provider.

    Persists guidance overlays (markers, drawing, text) and optional Legend
    snapshot metadata. Does not enqueue inpaint/edit and does not mutate the
    sheet composite pixels.
    """
    from ..image_product.store import project_dir
    from .store import load_sheet

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError("Environment Reference Sheet not found")

    source_id = resolve_source_asset_id(sheet, source_asset_id)
    guidance = _guidance_bundle(
        project_id=project_id,
        sheet_id=sheet_id,
        source_asset_id=source_id,
        drawing_overlay=drawing_overlay,
        text_labels=text_labels,
        numbered_markers=numbered_markers,
        overlay_bake_policy=overlay_bake_policy,
    )

    legend_payload: dict[str, Any] | None = None
    if isinstance(legend, dict):
        legend_payload = legend
    elif legend is not None:
        raise ValueError("legend must be an object when provided")

    has_legend = bool(legend_payload)
    has_guidance = bool(guidance.get("hasGuidance"))
    if not has_legend and not has_guidance:
        raise ValueError("Nothing to save — provide Legend and/or spatial annotations.")

    out_dir = project_dir(project_id) / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_sheet = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (sheet_id or "sheet"))[:64]
    record = {
        "kind": "ers_edit_annotations",
        "projectId": project_id,
        "sheetId": sheet_id,
        "sourceAssetId": source_id,
        "savedAt": datetime.now(timezone.utc).isoformat(),
        "legend": legend_payload,
        "guidance": guidance,
        "imageEditInvoked": False,
    }
    out_path = out_dir / f"ers-annotations-{safe_sheet}.json"
    out_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")

    # Persist structured overlay onto the editable master (pixels unchanged).
    try:
        from .contracts import utc_now as _utc_now
        from .store import save_sheet as _save_sheet

        sheet.overlayState = {
            "sourceAssetId": source_id,
            "savedAt": _utc_now(),
            "legend": legend_payload,
            "guidance": guidance,
        }
        # Persist Direction/Movement on this sheet only (master or current). Never mutates sibling snapshots.
        try:
            from .snapshots import normalize_direction_movement

            move = ""
            if isinstance(legend_payload, dict):
                move = normalize_direction_movement(
                    legend_payload.get("directionMovement")
                    or legend_payload.get("direction_movement")
                    or legend_payload.get("movement")
                )
            if move or (isinstance(legend_payload, dict) and "directionMovement" in legend_payload):
                sheet.directionMovement = move
                if not str(getattr(sheet, "snapshotOfSheetId", "") or "").strip():
                    sheet.movementSequenceIndex = 0
        except Exception:
            pass
        sheet.recordKind = getattr(sheet, "recordKind", None) or "original"
        sheet.isEditableMaster = True if not str(getattr(sheet, "snapshotOfSheetId", "") or "").strip() else False
        sheet.updatedAt = _utc_now()
        _save_sheet(sheet)
    except Exception:
        pass

    return {
        "ok": True,
        "sheetId": sheet_id,
        "sourceAssetId": source_id,
        "path": str(out_path),
        "overlayAssetId": guidance.get("overlayAssetId"),
        "hasGuidance": has_guidance,
        "hasLegend": has_legend,
        "imageEditInvoked": False,
        "message": "Legend and spatial annotations saved.",
    }



def enqueue_ers_edit(
    db: Session,
    project_id: str,
    sheet_id: str,
    *,
    edit_prompt: str,
    mask_asset_id: str | None = None,
    mask_png: str | None = None,
    source_asset_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    drawing_overlay: Any = None,
    text_labels: Any = None,
    numbered_markers: Any = None,
    overlay_bake_policy: str | None = None,
    requested_provider: str | None = None,
    hosted_model_id: str | None = None,
    fal_image_model_id: str | None = None,
    kie_image_model_id: str | None = None,
    wavespeed_image_model_id: str | None = None,
    official_model_id: str | None = None,
    api_model_id: str | None = None,
) -> dict[str, Any]:
    """Enqueue ERS region edit. Hosted EC provider wins; else Certified zimage.inpaint.

    Does not mutate the sheet composite. Creator editPrompt is frozen.
    """
    from .store import load_sheet

    prompt = (edit_prompt or "").strip()
    if not prompt:
        raise ValueError("editPrompt required (frozen creator prompt; will not be rewritten).")

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError("Environment Reference Sheet not found")

    sheet_composite_id = resolve_sheet_composite_id(sheet)
    source_id = resolve_source_asset_id(sheet, source_asset_id)

    source = db.get(Asset, source_id)
    if not source or source.project_id != project_id:
        raise ValueError("Source ERS asset not found in this project.")

    src_w, src_h = _source_pixel_size(source, width, height)

    provider = _normalize_requested_provider(
        requested_provider=requested_provider,
        hosted_model_id=hosted_model_id or api_model_id,
        fal_image_model_id=fal_image_model_id or official_model_id,
        kie_image_model_id=kie_image_model_id or (
            official_model_id if (requested_provider or "").strip().lower() == "kie" else None
        ),
        wavespeed_image_model_id=wavespeed_image_model_id or (
            official_model_id if (requested_provider or "").strip().lower() == "wavespeed" else None
        ),
    )

    has_mask_input = bool((mask_asset_id or "").strip() or (mask_png or "").strip())
    mask_id: str | None = None
    if has_mask_input:
        mask = ensure_mask(
            project_id,
            source_asset_id=source_id,
            mask_asset_id=mask_asset_id,
            mask_png=mask_png,
            width=width or src_w or None,
            height=height or src_h or None,
        )
        mask_id = str(mask.get("maskId") or mask_asset_id or "") or None
        if not src_w or not src_h:
            mw = int((mask.get("dimensions") or {}).get("width") or 0)
            mh = int((mask.get("dimensions") or {}).get("height") or 0)
            if mw and mh:
                src_w, src_h = mw, mh
    elif provider:
        # Hosted prompt-only / draw-guidance edit: no mask required.
        mask_id = None
    else:
        # Local zimage.inpaint: synthesize full-frame include mask for prompt-only.
        if not src_w or not src_h:
            raise ValueError(
                "maskPng or maskAssetId required (white=edit, black=preserve), "
                "or provide source dimensions for a full-frame edit."
            )
        mask = ensure_mask(
            project_id,
            source_asset_id=source_id,
            mask_asset_id=None,
            mask_png=_full_white_mask_png(src_w, src_h),
            width=src_w,
            height=src_h,
        )
        mask_id = str(mask.get("maskId") or "") or None
        if not mask_id:
            raise ValueError("maskPng or maskAssetId required (white=edit, black=preserve).")

    guidance = _guidance_bundle(
        project_id=project_id,
        sheet_id=sheet_id,
        source_asset_id=source_id,
        drawing_overlay=drawing_overlay,
        text_labels=text_labels,
        numbered_markers=numbered_markers,
        overlay_bake_policy=overlay_bake_policy,
    )

    if provider:
        # Strict hosted path — selected provider only; no silent Kie/local substitute.
        return _enqueue_ers_edit_hosted(
            db,
            project_id,
            sheet_id,
            prompt=prompt,
            source_id=source_id,
            sheet_composite_id=sheet_composite_id,
            mask_id=mask_id,
            src_w=int(src_w or 0),
            src_h=int(src_h or 0),
            guidance=guidance,
            provider=provider,
            hosted_model_id=hosted_model_id or api_model_id,
            fal_image_model_id=fal_image_model_id or official_model_id,
            kie_image_model_id=kie_image_model_id,
            wavespeed_image_model_id=wavespeed_image_model_id,
        )

    if not mask_id:
        raise ValueError("maskPng or maskAssetId required (white=edit, black=preserve).")

    from ..image_core.errors import ImageCoreError
    from ..image_core.generate import generate as image_core_generate
    from ..image_core.request import ImageCoreRequest

    creative: dict[str, Any] = {
        "ersEdit": True,
        "sheetId": sheet_id,
        "frozenCreatorPrompt": prompt,
        "coDirectorRewrite": False,
        "derivativeOnly": True,
        "engine": ENGINE,
        "certificationId": ENGINE_CERT_ID,
        "sourceWidth": src_w or None,
        "sourceHeight": src_h or None,
        "overlayBakePolicy": guidance.get("overlayBakePolicy") or OVERLAY_BAKE_DEFAULT,
    }
    if guidance.get("hasGuidance"):
        creative["drawingOverlay"] = guidance.get("drawingOverlay")
        creative["textLabels"] = guidance.get("textLabels") or []
        creative["numberedMarkers"] = guidance.get("numberedMarkers") or []
        creative["overlayAssetId"] = guidance.get("overlayAssetId")
        creative["guidanceModel"] = guidance.get("guidanceModel")
        creative["requestedOverlayBakePolicy"] = guidance.get("requestedOverlayBakePolicy")

    extra: dict[str, Any] = {
        "masks": [
            {
                "maskAssetId": mask_id,
                "maskId": mask_id,
                "role": "include",
            }
        ],
    }
    if src_w > 0 and src_h > 0:
        extra["width"] = int(src_w)
        extra["height"] = int(src_h)
        extra["forceWidth"] = int(src_w)
        extra["forceHeight"] = int(src_h)
    if guidance.get("hasGuidance") and guidance.get("overlayAssetId"):
        extra["ersOverlayGuidanceAssetId"] = guidance["overlayAssetId"]
        extra["ersOverlayBakePolicy"] = OVERLAY_BAKE_DEFAULT

    try:
        result = image_core_generate(
            db,
            ImageCoreRequest(
                project_id=project_id,
                purpose="region_edit",
                operation=ENGINE_OPERATION,
                model_id=ENGINE_FAMILY,
                prompt=prompt,
                source_asset_id=source_id,
                mask_asset_id=mask_id,
                edit_operation=ENGINE_EDIT_OPERATION,
                tag=f"ers_edit_{(sheet_id or '')[:8] or 'sheet'}",
                creative_context=creative,
                extra=extra,
            ),
        )
    except ImageCoreError as exc:
        raise ValueError(
            f"ERS edit failed ({ENGINE}): {exc.message}. "
            "Sheet composite stays active; no overwrite."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"ERS edit enqueue failed ({ENGINE}): {exc}. "
            "Sheet composite stays active; no overwrite."
        ) from exc

    status = str(result.status or "queued")
    if status.lower() in {"failed", "error"}:
        raise ValueError(
            f"ERS edit failed ({ENGINE}): {result.error or status}. "
            "Sheet composite stays active; no overwrite."
        )

    result_asset_id = _job_result_asset_id(result.job)
    enqueue = {
        "queueJobId": str(result.job_id or ""),
        "status": str(result.status or "queued"),
        "workflowKey": str(result.workflow_key or ENGINE),
        "family": str(result.family or ENGINE_FAMILY),
        "operation": str(result.operation or ENGINE_OPERATION),
        "width": int(result.width or 0) or None,
        "height": int(result.height or 0) or None,
        "resultAssetId": result_asset_id,
        "error": str(result.error or "") or None,
    }
    return _enqueue_payload(
        project_id=project_id,
        sheet_id=sheet_id,
        source_asset_id=source_id,
        mask_asset_id=mask_id,
        sheet_composite_id=sheet_composite_id,
        enqueue=enqueue,
        guidance=guidance,
        engine=ENGINE,
    )


def get_ers_edit_job(
    db: Session,
    project_id: str,
    sheet_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Read-only job status. Does not mutate the sheet."""
    from .store import load_sheet

    sheet = load_sheet(project_id, sheet_id)
    if sheet is None:
        raise FileNotFoundError("Environment Reference Sheet not found")
    sheet_composite_id = resolve_sheet_composite_id(sheet)

    job = db.get(Job, job_id)
    if job is None or job.project_id != project_id:
        raise FileNotFoundError("Edit job not found")

    params: dict[str, Any] = {}
    raw = job.params_json or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                params = parsed
        except Exception:
            params = {}
    ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
    result_asset_id = (
        params.get("output_asset_id")
        or params.get("resultAssetId")
        or params.get("derivativeAssetId")
        or getattr(job, "asset_id", None)
        or None
    )
    if result_asset_id:
        result_asset_id = str(result_asset_id)
    workflow_key = str(
        params.get("forceWorkflowKey")
        or ctx.get("workflowKey")
        or ctx.get("imageCoreWorkflowKey")
        or params.get("workflowKey")
        or ENGINE
    )
    source_id = str(params.get("sourceAssetId") or params.get("source_asset_id") or "") or None
    mask_specs = params.get("masks") or []
    mask_id = None
    if mask_specs and isinstance(mask_specs, list):
        m0 = mask_specs[0] if isinstance(mask_specs[0], dict) else {"maskAssetId": mask_specs[0]}
        mask_id = str(m0.get("maskAssetId") or m0.get("maskId") or "") or None

    payload = {
        "jobId": str(job.id),
        "queueJobId": str(job.id),
        "status": str(job.status or ""),
        "progress": float(job.progress or 0),
        "message": str(job.message or ""),
        "workflowKey": workflow_key,
        "derivativeAssetId": result_asset_id,
        "resultAssetId": result_asset_id,
        "sourceAssetId": source_id,
        "sheetId": sheet_id,
        "maskAssetId": mask_id,
        "derivativeOnly": True,
        "ersCompositeAssetId": sheet_composite_id,
        "engine": ENGINE,
        "purpose": "region_edit",
        "previewUrl": _preview_url(project_id, result_asset_id),
        "outputPath": job.output_path,
        "comfyPromptId": job.comfy_prompt_id,
        "overlayBakePolicy": ctx.get("overlayBakePolicy") or OVERLAY_BAKE_DEFAULT,
    }
    if ctx.get("drawingOverlay") is not None or ctx.get("textLabels") or ctx.get("numberedMarkers"):
        payload["drawingOverlay"] = ctx.get("drawingOverlay")
        payload["textLabels"] = ctx.get("textLabels") or []
        payload["numberedMarkers"] = ctx.get("numberedMarkers") or []
        payload["overlayAssetId"] = ctx.get("overlayAssetId")
        payload["guidanceOnly"] = True
    return payload
