"""Spatial Map Correct Area — Certified zimage.inpaint engine (Brad unlock).

Product contract: source Spatial Map pixels + mask + correction prompt ->
derived corrected asset (non-destructive version chain). Overlays
(characters / cameras / movement) live on the map document and are
preserved by swapping only backgroundAssetId on Accept.

ENGINE (Brad unlock 2026-09-11 ~18:42 PT — Chief relay):
- Correct Area ONLY uses Certified zimage.inpaint (IMG-ZIMAGE-INPAINT-001)
  via the same Image Core path Scene Creator region_edit uses.
- GPT_MASK_BLOCKED_NEED_BRAD / ENGINE_HOLD_PENDING_BRAD removed for Apply.
- Atlas/ERS *generation* stays GPT Image 2 — do NOT change atlas_provider /
  ers generate / ers-law from this module.
- Frozen creator prompt + EDIT ONLY MASKED REGION preservation template;
  no Co-Director silent rewrite.
- Accept uses update_document({ backgroundAssetId }) ONLY — never createMap.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db import Asset, Job
from ..image_product import masks as mask_store
from ..image_product import versions as version_store
from ..image_runtime.certified_registry import get_workflow

ENGINE = "zimage.inpaint"
CERTIFIED_WORKFLOW = "zimage.inpaint"
ENGINE_CERT_ID = "IMG-ZIMAGE-INPAINT-001"
ENGINE_FAMILY = "zimage"
ENGINE_OPERATION = "image.inpaint"
ENGINE_EDIT_OPERATION = "modify"
# Historical labels — removed from Correct Area Apply once zimage path is live.
LEGACY_ENGINE_STATUS_BLOCKED = "GPT_MASK_BLOCKED_NEED_BRAD"
LEGACY_ENGINE_HOLD = "ENGINE_HOLD_PENDING_BRAD"
# Kept for historical draft helper only — Correct Area does NOT enqueue GPT mask edit.
PREFERRED_FAL_MODEL = "openai/gpt-image-2/edit"
PREFERRED_HOSTED_ID = "gpt-image-2-kie"
OP_CORRECT = "spatial_map.correct_area"
BRAD_UNLOCK_AT = "2026-09-11T18:42:00-07:00"  # ~18:42 PT Chief relay of Brad unlock

# Back-compat aliases so older imports do not explode; values no longer gate Apply.
ENGINE_STATUS_BLOCKED = LEGACY_ENGINE_STATUS_BLOCKED  # superseded — Correct Area reports zimage.inpaint
ENGINE_HOLD = LEGACY_ENGINE_HOLD  # legacy label only; live engineHold is None
ENGINE_STATUS_READY = "ZIMAGE_INPAINT_CERTIFIED"

# Frozen preservation wrapper — creator prompt stays identifiable & unchanged.
PRESERVATION_TEMPLATE = (
    "EDIT ONLY MASKED REGION. White mask = edit; black = preserve exactly. "
    "Preserve style, perspective, and lighting outside the mask. "
    "Keep exact output dimensions matching the source Spatial Map. "
    "Do not regenerate the full scene. Do not invent new layout. "
    "Do not rewrite or expand the creator correction prompt."
)

_STORE_FILE = "spatial_map_corrections.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _project_store_path(project_id: str) -> Path:
    from ..image_product.store import project_dir

    d = project_dir(project_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / _STORE_FILE


def _load_store(project_id: str) -> dict[str, Any]:
    path = _project_store_path(project_id)
    if not path.is_file():
        return {"maps": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"maps": {}}
    if not isinstance(data, dict):
        return {"maps": {}}
    data.setdefault("maps", {})
    return data


def _save_store(project_id: str, data: dict[str, Any]) -> None:
    path = _project_store_path(project_id)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _zimage_inpaint_certified() -> bool:
    """True when Certified registry lists zimage.inpaint as Certified.

    get_workflow is imported at module level so a broken certified path
    fails collection/import honestly — no silent fallback.
    """
    wf = get_workflow(CERTIFIED_WORKFLOW)
    if wf is None:
        return False
    return str(getattr(wf, "status", "") or "") == "Certified"


def engine_status() -> dict[str, Any]:
    """Honest Correct Area engine gate — zimage.inpaint after Brad unlock.

    Scope: Spatial Map Correct Area Apply ONLY. Atlas/ERS generation remains
    GPT Image 2 and is not selected or swapped here.
    """
    # Legacy GPT env is informational only — Correct Area no longer gates on it.
    allow = str(os.environ.get("ADEPT_SPATIAL_MAP_GPT_MASK_ENGINE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    certified = _zimage_inpaint_certified()
    executable = certified
    reason = (
        f"ENGINE={ENGINE} (Correct Area only). Certified workflow {ENGINE_CERT_ID}. "
        f"Brad unlock {BRAD_UNLOCK_AT}. "
        "correct() enqueues via Image Core purpose=region_edit → zimage.inpaint "
        "(same path as Scene Creator region_edit_shot). "
        "Atlas/ERS generation stays GPT Image 2 (untouched). "
        f"{'Executable.' if executable else 'Not executable: zimage.inpaint missing or not Certified in registry.'}"
    )
    return {
        "engine": ENGINE,
        "engineStatus": ENGINE_STATUS_READY if executable else "ENGINE_NOT_CERTIFIED",
        "engineHold": None,
        "executable": executable,
        "preferredModel": CERTIFIED_WORKFLOW,
        "preferredHostedId": None,
        "workflowKey": CERTIFIED_WORKFLOW,
        "certificationId": ENGINE_CERT_ID,
        "family": ENGINE_FAMILY,
        "zimageWired": True,
        "providerCalled": False,
        "reason": reason,
        "allowEnv": allow,
        "certified": certified,
        "bradUnlockAt": BRAD_UNLOCK_AT,
        "scope": "spatial_map.correct_area_only",
        "atlasErsGeneration": "gpt-image-2",
        "atlasGenerationUnchanged": True,
        "legacyHoldsRemoved": [LEGACY_ENGINE_STATUS_BLOCKED, LEGACY_ENGINE_HOLD],
    }


def compose_frozen_prompt(
    creator_prompt: str,
    *,
    preserve_style: bool = True,
    preserve_perspective: bool = True,
    preserve_lighting: bool = True,
) -> dict[str, str]:
    """Frozen correction prompt: preservation wrapper + identifiable creator text."""
    creator = (creator_prompt or "").strip()
    if not creator:
        raise ValueError("Correction prompt is required.")
    flags = []
    if preserve_style:
        flags.append("preserveStyle=true")
    if preserve_perspective:
        flags.append("preservePerspective=true")
    if preserve_lighting:
        flags.append("preserveLighting=true")
    flag_line = "; ".join(flags) if flags else "preserve defaults off"
    composed = f"{creator}\n\n{PRESERVATION_TEMPLATE}\n({flag_line})"
    return {
        "creatorPrompt": creator,
        "preservationTemplate": PRESERVATION_TEMPLATE,
        "composedPrompt": composed,
        "preserveStyle": str(preserve_style).lower(),
        "preservePerspective": str(preserve_perspective).lower(),
        "preserveLighting": str(preserve_lighting).lower(),
    }


def build_gpt_mask_edit_arguments(
    *,
    source_image_url: str,
    mask_url: str,
    composed_prompt: str,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Draft-only fal openai/gpt-image-2/edit payload (NOT enqueued).

    Vendor docs: mask_image_url (product page) / mask_url (llms.txt).
    Adept adapters do not pass either today — draft for Primary review only.
    """
    args: dict[str, Any] = {
        "prompt": composed_prompt,
        "image_urls": [source_image_url],
        # Prefer documented product-page name; keep mask_url alias for honesty.
        "mask_image_url": mask_url,
        "mask_url": mask_url,
        "output_format": "png",
        "num_images": 1,
        "quality": "high",
    }
    if width and height and width > 0 and height > 0:
        args["image_size"] = {"width": int(width), "height": int(height)}
    return args


def reconcile_dimensions(
    *,
    source_width: int,
    source_height: int,
    output_width: int | None = None,
    output_height: int | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Exact source WxH gate - refuse mismatch; never silent-resize to conceal.

    Contract (REVIEW NO-GO #3): Correct Area output must match source natural
    pixels exactly. LANCZOS / any silent resize is forbidden.
    """
    sw, sh = int(source_width or 0), int(source_height or 0)
    ow, oh = output_width, output_height
    if output_path and (ow is None or oh is None):
        try:
            from PIL import Image

            with Image.open(output_path) as im:
                ow, oh = im.size
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "matched": False,
                "sourceWidth": sw,
                "sourceHeight": sh,
                "outputWidth": ow,
                "outputHeight": oh,
                "resized": False,
                "error": str(exc),
            }
    ow = int(ow or 0)
    oh = int(oh or 0)
    if sw <= 0 or sh <= 0:
        return {
            "ok": False,
            "matched": False,
            "sourceWidth": sw,
            "sourceHeight": sh,
            "outputWidth": ow,
            "outputHeight": oh,
            "resized": False,
            "error": "Source dimensions required.",
        }
    if ow == sw and oh == sh:
        return {
            "ok": True,
            "matched": True,
            "sourceWidth": sw,
            "sourceHeight": sh,
            "outputWidth": ow,
            "outputHeight": oh,
            "resized": False,
        }
    return {
        "ok": False,
        "matched": False,
        "sourceWidth": sw,
        "sourceHeight": sh,
        "outputWidth": ow,
        "outputHeight": oh,
        "resized": False,
        "error": (
            f"Dimension mismatch: output {ow}x{oh} != source {sw}x{sh}. "
            "Silent resize is forbidden - refuse Accept until engine returns exact source WxH."
        ),
    }


def _map_bucket(store: dict[str, Any], document_id: str) -> dict[str, Any]:
    maps = store.setdefault("maps", {})
    bucket = maps.get(document_id)
    if not isinstance(bucket, dict):
        bucket = {
            "documentId": document_id,
            "sessions": [],
            "jobs": [],
            "activeSessionId": None,
            "activeJobId": None,
            "acceptedChain": [],
            "currentBackgroundAssetId": None,
            "originalBackgroundAssetId": None,
            "tokens": {},
        }
        maps[document_id] = bucket
    bucket.setdefault("sessions", [])
    bucket.setdefault("jobs", [])
    bucket.setdefault("acceptedChain", [])
    bucket.setdefault("tokens", {})
    return bucket


def _mint_accept_token(job_id: str, result_asset_id: str | None) -> str:
    raw = f"{job_id}:{result_asset_id or ''}:{secrets.token_hex(16)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _chain_labels(accepted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(accepted or []):
        label = "Original" if i == 0 and entry.get("label") == "Original" else f"Correction v{i}" if i else "Original"
        # Prefer stored label; otherwise derive Original → Correction v1 → v2
        stored = entry.get("label")
        if not stored:
            stored = "Original" if i == 0 and not entry.get("fromAssetId") else f"Correction v{max(1, i)}"
        row = dict(entry)
        row["label"] = stored
        out.append(row)
    return out


def _job_output_asset_id(job: "Job") -> str | None:
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    if isinstance(params, dict):
        asset_id = params.get("output_asset_id") or params.get("outputAssetId")
        if asset_id:
            return str(asset_id)
    try:
        preview = json.loads(job.preview_json or "{}")
    except Exception:
        preview = {}
    if isinstance(preview, dict):
        for key in ("assetId", "asset_id", "output_asset_id", "outputAssetId"):
            if preview.get(key):
                return str(preview[key])
    return None


def _preview_url_for(project_id: str, asset_id: str | None) -> str | None:
    if not asset_id:
        return None
    return f"/api/projects/{project_id}/assets/{asset_id}/file"


def _mark_preview_ready(
    bucket: dict[str, Any],
    *,
    project_id: str,
    session_id: str,
    output_asset_id: str,
    dimension_check: dict[str, Any] | None = None,
) -> str:
    """Bind completed queue job pixels into correction store for Accept ungating."""
    accept_token = _mint_accept_token(session_id, output_asset_id)
    preview = _preview_url_for(project_id, output_asset_id)
    session = next((s for s in bucket["sessions"] if s.get("sessionId") == session_id), None)
    job = next((j for j in bucket["jobs"] if j.get("jobId") == session_id), None)
    if session:
        session["outputAssetId"] = output_asset_id
        session["resultAssetId"] = output_asset_id
        session["status"] = "preview_ready"
        session["previewUrl"] = preview
        session["modifiedAt"] = _now()
        session["engineStatus"] = ENGINE_STATUS_READY
        session["executable"] = True
        session["zimageWired"] = True
        session["engineHold"] = None
        session["acceptToken"] = accept_token
        if dimension_check is not None:
            session["dimensionCheck"] = dimension_check
    if job:
        job["resultAssetId"] = output_asset_id
        job["outputAssetId"] = output_asset_id
        job["status"] = "preview_ready"
        job["previewUrl"] = preview
        job["acceptToken"] = accept_token
        job["modifiedAt"] = _now()
        job["engineStatus"] = ENGINE_STATUS_READY
        job["executable"] = True
        job["zimageWired"] = True
        job["engineHold"] = None
        job["providerCalled"] = True
        if dimension_check is not None:
            job["dimensionCheck"] = dimension_check
    bucket.setdefault("tokens", {})[accept_token] = {
        "jobId": session_id,
        "resultAssetId": output_asset_id,
        "mapId": bucket.get("documentId") or (job or session or {}).get("documentId"),
        "createdAt": _now(),
    }
    bucket["activeSessionId"] = session_id
    bucket["activeJobId"] = session_id
    return accept_token


def _sync_provider_jobs(db: Session | None, project_id: str, document_id: str) -> None:
    """Bridge queueJobId completion -> resultAssetId / preview_ready (Accept ungates)."""
    if db is None:
        return
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    bucket["documentId"] = document_id
    dirty = False
    for job_rec in list(bucket.get("jobs") or []):
        if job_rec.get("resultAssetId") and str(job_rec.get("status") or "") == "preview_ready":
            continue
        provider_job_id = str(
            job_rec.get("queueJobId") or job_rec.get("providerJobId") or ""
        ).strip()
        if not provider_job_id:
            continue
        session_id = str(job_rec.get("jobId") or "")
        job = db.get(Job, provider_job_id)
        if job is None:
            # Not visible yet — leave queued; do not invent failure.
            continue
        if getattr(job, "project_id", None) != project_id:
            if job_rec.get("status") not in {"failed", "preview_ready", "accepted"}:
                job_rec["status"] = "failed"
                job_rec["reason"] = "Provider job project mismatch."
                dirty = True
            continue
        status = (job.status or "").lower()
        if status in {"done", "completed", "complete", "success"}:
            out_id = _job_output_asset_id(job)
            if not out_id:
                job_rec["status"] = "failed"
                job_rec["reason"] = "Generation finished without a usable image."
                dirty = True
                continue
            out_asset = db.get(Asset, out_id)
            dim = reconcile_dimensions(
                source_width=int(job_rec.get("width") or 0),
                source_height=int(job_rec.get("height") or 0),
                output_path=getattr(out_asset, "path", None) if out_asset else None,
            )
            if not dim.get("matched") and int(job_rec.get("width") or 0) > 0 and int(job_rec.get("height") or 0) > 0:
                job_rec["dimensionCheck"] = dim
                job_rec["status"] = "dimension_mismatch"
                job_rec["rejectedAssetId"] = out_id
                job_rec["reason"] = dim.get("error") or "Dimension mismatch"
                session = next((s for s in bucket["sessions"] if s.get("sessionId") == session_id), None)
                if session:
                    session["status"] = "dimension_mismatch"
                    session["rejectedAssetId"] = out_id
                    session["reason"] = job_rec["reason"]
                    session["dimensionCheck"] = dim
                    session["modifiedAt"] = _now()
                dirty = True
                continue
            version_id = job_rec.get("versionId")
            if version_id:
                try:
                    data = version_store._load(project_id)  # noqa: SLF001
                    for v in data.get("versions") or []:
                        if v.get("versionId") == version_id:
                            v["outputAssetId"] = out_id
                            v["modifiedAt"] = _now()
                            v["state"] = "Draft"
                    version_store._save(project_id, data)  # noqa: SLF001
                except Exception:
                    pass
            _mark_preview_ready(
                bucket,
                project_id=project_id,
                session_id=session_id,
                output_asset_id=out_id,
                dimension_check=dim if dim.get("ok") else None,
            )
            dirty = True
        elif status in {"failed", "error", "cancelled"}:
            job_rec["status"] = "failed"
            job_rec["reason"] = job.message or f"{ENGINE} job failed"
            job_rec["modifiedAt"] = _now()
            session = next((s for s in bucket["sessions"] if s.get("sessionId") == session_id), None)
            if session:
                session["status"] = "failed"
                session["reason"] = job_rec["reason"]
                session["modifiedAt"] = _now()
            dirty = True
        elif status in {"running", "preview", "generating", "processing"}:
            if job_rec.get("status") != "running":
                job_rec["status"] = "running"
                dirty = True
        else:
            if job_rec.get("status") not in {"queued", "running", "preview_ready", "accepted"}:
                job_rec["status"] = "queued"
                dirty = True
    if dirty:
        _save_store(project_id, store)


def get_correction_state(
    project_id: str,
    document_id: str,
    db: Session | None = None,
) -> dict[str, Any]:
    """Correct Area UI state. Router passes db= for queueJobId -> preview_ready sync."""
    _sync_provider_jobs(db, project_id, document_id)
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    eng = engine_status()
    active = None
    sid = bucket.get("activeSessionId")
    if sid:
        active = next((s for s in bucket["sessions"] if s.get("sessionId") == sid), None)
    job = None
    jid = bucket.get("activeJobId")
    if jid:
        job = next((j for j in bucket["jobs"] if j.get("jobId") == jid), None)
    result_id = (
        (job or {}).get("resultAssetId")
        or (active or {}).get("outputAssetId")
        or (active or {}).get("resultAssetId")
    )
    preview = (
        (job or {}).get("previewUrl")
        or (active or {}).get("previewUrl")
        or _preview_url(project_id, result_id)
    )
    preview_ready = (job or {}).get("status") == "preview_ready" or (active or {}).get("status") == "preview_ready"
    return {
        **eng,
        "documentId": document_id,
        "activeSession": deepcopy(active) if active else None,
        "activeJob": deepcopy(job) if job else None,
        "acceptedChain": _chain_labels(list(bucket.get("acceptedChain") or [])),
        "originalBackgroundAssetId": bucket.get("originalBackgroundAssetId"),
        "currentBackgroundAssetId": bucket.get("currentBackgroundAssetId"),
        "canUndo": bool(bucket.get("acceptedChain")),
        "sessions": list(bucket.get("sessions") or []),
        "jobs": list(bucket.get("jobs") or []),
        "resultAssetId": result_id,
        "previewUrl": preview,
        "previewReady": preview_ready,
        "acceptToken": (job or {}).get("acceptToken") or (active or {}).get("acceptToken"),
        "queueJobId": (job or {}).get("queueJobId") or (active or {}).get("queueJobId"),
    }



def _resolve_source_asset(
    db: Session,
    project_id: str,
    *,
    source_asset_id: str | None,
    map_id: str | None,
) -> tuple[Asset, str, str | None]:
    """Return (asset, asset_id, document_id)."""
    document_id = map_id
    bg = (source_asset_id or "").strip() or None
    if not bg and document_id:
        from .service import get_document

        document = get_document(db, project_id, document_id)
        bg = getattr(document, "backgroundAssetId", None) or None
    if not bg:
        raise ValueError(
            "sourceAssetId / backgroundAssetId required (or mapId with an Atlas background)."
        )
    source = db.get(Asset, bg)
    if not source or source.project_id != project_id:
        raise ValueError("Source Spatial Map asset not found in this project.")
    return source, bg, document_id


def _ensure_mask(
    project_id: str,
    *,
    source_asset_id: str,
    mask_asset_id: str | None,
    mask_png: str | None,
    width: int | None,
    height: int | None,
) -> dict[str, Any]:
    mid = (mask_asset_id or "").strip()
    if mid:
        mask = mask_store.get_mask(project_id, mid)
        if not mask:
            raise ValueError("Mask not found. Paint a region and save the mask first.")
        return mask
    if not mask_png:
        raise ValueError("maskPng or maskAssetId required (white=edit, black=preserve).")
    dims = {}
    if width and height:
        dims = {"width": int(width), "height": int(height)}
    return mask_store.save_mask(
        project_id,
        source_asset_id=source_asset_id,
        png_base64=mask_png,
        role="include",
        dimensions=dims or None,
        creator="spatial_map.correct",
        metadata={"white": "edit", "black": "preserve"},
    )



def _preview_url(project_id: str, asset_id: str | None) -> str | None:
    aid = (asset_id or "").strip()
    if not aid:
        return None
    return f"/api/projects/{project_id}/assets/{aid}/file"


def _source_pixel_size(source: Asset, width: int | None, height: int | None) -> tuple[int, int]:
    """Best-effort source WxH for dimension reconcile authority."""
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
    meta = getattr(source, "meta_json", None) or getattr(source, "metadata", None)
    if isinstance(meta, str) and meta:
        try:
            meta = json.loads(meta)
        except Exception:
            meta = None
    if isinstance(meta, dict):
        try:
            mw = int(meta.get("width") or meta.get("w") or 0)
            mh = int(meta.get("height") or meta.get("h") or 0)
            if mw > 0 and mh > 0:
                return mw, mh
        except (TypeError, ValueError):
            pass
    return sw, sh


def _enqueue_zimage_inpaint(
    db: Session,
    *,
    project_id: str,
    source_asset_id: str,
    mask_asset_id: str,
    composed_prompt: str,
    creator_prompt: str,
    document_id: str,
    source_width: int,
    source_height: int,
) -> dict[str, Any]:
    """Enqueue Certified zimage.inpaint via Image Core (SC region_edit pattern).

    Raises ValueError with a clear creator-facing message on failure.
    Does not invent pixels or silently fall back to GPT / Atlas engines.
    """
    from ..image_core.errors import ImageCoreError
    from ..image_core.generate import generate as image_core_generate
    from ..image_core.request import ImageCoreRequest

    creative: dict[str, Any] = {
        "spatialMapCorrect": True,
        "op": OP_CORRECT,
        "mapId": document_id,
        "frozenCreatorPrompt": creator_prompt,
        "coDirectorRewrite": False,
        "preservationTemplate": PRESERVATION_TEMPLATE,
        "sourceWidth": source_width or None,
        "sourceHeight": source_height or None,
        "engine": ENGINE,
        "certificationId": ENGINE_CERT_ID,
    }
    extra: dict[str, Any] = {
        "masks": [
            {
                "maskAssetId": mask_asset_id,
                "maskId": mask_asset_id,
                "role": "include",
            }
        ],
    }
    # Prefer exact source dims when known; Image Core may still resolve registry
    # size — reconcile_dimensions remains the Accept-time safety net.
    if source_width > 0 and source_height > 0:
        extra["width"] = int(source_width)
        extra["height"] = int(source_height)
        extra["forceWidth"] = int(source_width)
        extra["forceHeight"] = int(source_height)

    try:
        result = image_core_generate(
            db,
            ImageCoreRequest(
                project_id=project_id,
                purpose="region_edit",
                operation=ENGINE_OPERATION,
                model_id=ENGINE_FAMILY,
                prompt=composed_prompt,
                source_asset_id=source_asset_id,
                mask_asset_id=mask_asset_id,
                edit_operation=ENGINE_EDIT_OPERATION,
                tag=f"spatial_map_correct_{(document_id or '')[:8] or 'map'}",
                creative_context=creative,
                extra=extra,
            ),
        )
    except ImageCoreError as exc:
        raise ValueError(
            f"Spatial Map Correct Area failed ({ENGINE}): {exc.message}. "
            "Original Spatial Map stays active; no partial replace."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"Spatial Map Correct Area enqueue failed ({ENGINE}): {exc}. "
            "Original Spatial Map stays active; no partial replace."
        ) from exc

    job_obj = result.job
    result_asset_id = None
    if job_obj is not None:
        result_asset_id = (
            getattr(job_obj, "asset_id", None)
            or getattr(job_obj, "output_asset_id", None)
            or None
        )
        if result_asset_id is not None:
            result_asset_id = str(result_asset_id) or None
    status = str(result.status or "queued")
    if result.error:
        raise ValueError(
            f"Spatial Map Correct Area failed ({ENGINE}): {result.error}. "
            "Original Spatial Map stays active; no partial replace."
        )
    return {
        "queueJobId": str(result.job_id or ""),
        "status": status,
        "workflowKey": str(result.workflow_key or ENGINE),
        "family": str(result.family or ENGINE_FAMILY),
        "operation": str(result.operation or ENGINE_OPERATION),
        "width": int(result.width or 0) or None,
        "height": int(result.height or 0) or None,
        "resultAssetId": result_asset_id,
        "previewUrl": _preview_url(project_id, result_asset_id),
        "providerCalled": True,
        "error": str(result.error or "") or None,
        "decision": result.decision,
    }


def correct(
    db: Session,
    project_id: str,
    *,
    source_asset_id: str | None = None,
    background_asset_id: str | None = None,
    mask_png: str | None = None,
    mask_asset_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    correction_prompt: str = "",
    preserve_style: bool = True,
    preserve_perspective: bool = True,
    preserve_lighting: bool = True,
    current_spatial_map_asset_id: str | None = None,
    map_id: str | None = None,
) -> dict[str, Any]:
    """POST /api/spatial-map/correct — enqueue Certified zimage.inpaint.

    Frozen creator prompt + preservation template; no Co-Director rewrite.
    On enqueue/run failure: original stays active; clear error; no partial replace.
    Atlas/ERS generation is never selected from this path.
    """
    eng = engine_status()
    if not eng.get("executable"):
        raise ValueError(
            f"Spatial Map Correct Area engine not executable: {eng.get('reason')}. "
            "Original Spatial Map stays active."
        )

    src_id = (
        (source_asset_id or "").strip()
        or (background_asset_id or "").strip()
        or (current_spatial_map_asset_id or "").strip()
        or None
    )
    source, bg, document_id = _resolve_source_asset(
        db, project_id, source_asset_id=src_id, map_id=map_id
    )
    if not document_id and map_id:
        document_id = map_id
    if not document_id:
        # Persistence bucket key — require mapId for Accept overlay-safe path.
        document_id = f"orphan-{bg}"

    mask = _ensure_mask(
        project_id,
        source_asset_id=bg,
        mask_asset_id=mask_asset_id,
        mask_png=mask_png,
        width=width,
        height=height,
    )
    mask_id = str(mask.get("maskId") or mask_asset_id or "")

    src_w, src_h = _source_pixel_size(source, width, height)
    if not src_w or not src_h:
        mw = int((mask.get("dimensions") or {}).get("width") or 0)
        mh = int((mask.get("dimensions") or {}).get("height") or 0)
        if mw and mh:
            src_w, src_h = mw, mh

    dim_note = None
    if width and height and mask.get("dimensions"):
        mw = int((mask.get("dimensions") or {}).get("width") or 0)
        mh = int((mask.get("dimensions") or {}).get("height") or 0)
        if mw and mh and (mw != int(width) or mh != int(height)):
            dim_note = (
                f"Mask dimensions {mw}x{mh} differ from requested {width}x{height}; "
                "exact source dimensions remain the Accept authority."
            )

    frozen = compose_frozen_prompt(
        correction_prompt,
        preserve_style=preserve_style,
        preserve_perspective=preserve_perspective,
        preserve_lighting=preserve_lighting,
    )

    # Historical GPT draft retained for Primary evidence only — NOT enqueued.
    draft_args = build_gpt_mask_edit_arguments(
        source_image_url=f"asset://{bg}",
        mask_url=f"mask://{mask_id}",
        composed_prompt=frozen["composedPrompt"],
        width=src_w or None,
        height=src_h or None,
    )

    # Lineage stub via existing image_product.versions (CDX-074 — no third table).
    version = version_store.create_version(
        project_id,
        source_asset_id=bg,
        parent_version_id=None,
        name="Spatial Map Correction",
        state="Draft",
        output_asset_id=None,
    )

    # Live engine: Image Core → Certified zimage.inpaint (SC region_edit path).
    enqueue = _enqueue_zimage_inpaint(
        db,
        project_id=project_id,
        source_asset_id=bg,
        mask_asset_id=mask_id,
        composed_prompt=frozen["composedPrompt"],
        creator_prompt=frozen["creatorPrompt"],
        document_id=document_id,
        source_width=src_w,
        source_height=src_h,
    )

    queue_job_id = str(enqueue.get("queueJobId") or "")
    job_id = queue_job_id or f"smc-job-{uuid4().hex[:12]}"
    result_asset_id = enqueue.get("resultAssetId")
    preview_url = enqueue.get("previewUrl")
    run_status = str(enqueue.get("status") or "queued")
    accept_token = _mint_accept_token(job_id, result_asset_id)

    version_meta = {
        "label": "Correction v?" if not result_asset_id else "Correction (preview)",
        "sourceAssetId": bg,
        "maskAssetId": mask_id,
        "correctionPrompt": frozen["creatorPrompt"],
        "composedPrompt": frozen["composedPrompt"],
        "preservationTemplate": frozen["preservationTemplate"],
        "provider": "local",
        "model": ENGINE,
        "workflowKey": enqueue.get("workflowKey") or ENGINE,
        "certificationId": ENGINE_CERT_ID,
        "createdAt": _now(),
        "versionId": version.get("versionId"),
        "queueJobId": queue_job_id or None,
    }

    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    if not bucket.get("originalBackgroundAssetId"):
        bucket["originalBackgroundAssetId"] = bg
    bucket["currentBackgroundAssetId"] = bg
    chain = _chain_labels(list(bucket.get("acceptedChain") or []))
    if not chain:
        chain = [
            {
                "label": "Original",
                "assetId": bg,
                "toAssetId": bg,
                "fromAssetId": None,
            }
        ]

    job = {
        "jobId": job_id,
        "queueJobId": queue_job_id or None,
        "documentId": document_id,
        "projectId": project_id,
        "sourceAssetId": bg,
        "parentAssetId": bg,
        "maskAssetId": mask_id,
        "resultAssetId": result_asset_id,
        "previewUrl": preview_url,
        "creatorPrompt": frozen["creatorPrompt"],
        "preservationTemplate": frozen["preservationTemplate"],
        "composedPrompt": frozen["composedPrompt"],
        "frozen": True,
        "coDirectorRewrite": False,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "executable": True,
        "providerCalled": True,
        "preferredModel": ENGINE,
        "workflowKey": enqueue.get("workflowKey") or ENGINE,
        "certificationId": ENGINE_CERT_ID,
        "zimageWired": True,
        "draftFalArguments": draft_args,  # evidence only — not submitted
        "version": version_meta,
        "versionId": version.get("versionId"),
        "acceptToken": accept_token,
        "undoToAssetId": bg,
        "width": src_w or None,
        "height": src_h or None,
        "dimensionNote": dim_note,
        "status": run_status,
        "reason": eng["reason"],
        "createdAt": _now(),
        "modifiedAt": _now(),
    }
    bucket["jobs"].append(job)
    bucket["activeJobId"] = job_id
    bucket["tokens"][accept_token] = {
        "jobId": job_id,
        "resultAssetId": result_asset_id,
        "mapId": document_id,
        "createdAt": _now(),
    }
    # Mirror session shape for Correct Area UI compat.
    session = {
        "sessionId": job_id,
        "documentId": document_id,
        "projectId": project_id,
        "sourceAssetId": bg,
        "maskAssetId": mask_id,
        "creatorPrompt": frozen["creatorPrompt"],
        "preservationTemplate": frozen["preservationTemplate"],
        "composedPrompt": frozen["composedPrompt"],
        "frozen": True,
        "coDirectorRewrite": False,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "executable": True,
        "preferredModel": ENGINE,
        "workflowKey": enqueue.get("workflowKey") or ENGINE,
        "zimageWired": True,
        "providerCalled": True,
        "queueJobId": queue_job_id or None,
        "versionId": version.get("versionId"),
        "outputAssetId": result_asset_id,
        "status": run_status,
        "reason": eng["reason"],
        "createdAt": _now(),
        "modifiedAt": _now(),
    }
    bucket["sessions"].append(session)
    bucket["activeSessionId"] = job_id
    _save_store(project_id, store)

    # If pixels already present (rare sync complete), stamp version output.
    if result_asset_id:
        try:
            version_store.set_state(project_id, version.get("versionId"), "Draft")
            data = version_store._load(project_id)  # noqa: SLF001
            for v in data.get("versions") or []:
                if v.get("versionId") == version.get("versionId"):
                    v["outputAssetId"] = result_asset_id
                    v["modifiedAt"] = _now()
            version_store._save(project_id, data)  # noqa: SLF001
        except Exception:
            pass
        version_meta["label"] = "Correction (preview)"
        version_meta["outputAssetId"] = result_asset_id

    message = (
        f"Correct Area enqueued on {ENGINE} ({ENGINE_CERT_ID}). "
        f"queueJobId={queue_job_id or job_id}. "
        "Original Spatial Map stays active until Accept."
        if not result_asset_id
        else (
            f"Correct Area produced preview via {ENGINE} ({ENGINE_CERT_ID}). "
            "Original Spatial Map stays active until Accept."
        )
    )

    return {
        "jobId": job_id,
        "queueJobId": queue_job_id or None,
        "resultAssetId": result_asset_id,
        "previewUrl": preview_url,
        "parentAssetId": bg,
        "version": version_meta,
        "chain": chain,
        "acceptToken": accept_token,
        "undoToAssetId": bg,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "executable": True,
        "providerCalled": True,
        "zimageWired": True,
        "preferredModel": ENGINE,
        "workflowKey": enqueue.get("workflowKey") or ENGINE,
        "certificationId": ENGINE_CERT_ID,
        "status": run_status,
        "reason": eng["reason"],
        "documentId": document_id,
        "mapId": document_id,
        "overlaysPreserved": True,
        "originalRemainsActive": True,
        "dimensionReconcile": {
            "requiredExactSource": True,
            "sourceWidth": src_w or None,
            "sourceHeight": src_h or None,
            "note": dim_note,
        },
        "message": message,
        "session": session,
        **{k: eng[k] for k in ("allowEnv", "certified", "bradUnlockAt", "scope", "atlasErsGeneration") if k in eng},
    }



def start_correction(
    db: Session,
    project_id: str,
    document_id: str,
    *,
    mask_asset_id: str,
    prompt: str,
    source_asset_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    preserve_style: bool = True,
    preserve_perspective: bool = True,
    preserve_lighting: bool = True,
) -> dict[str, Any]:
    """Compat wrapper for Correct Area UI -> same zimage.inpaint path as correct()."""
    return correct(
        db,
        project_id,
        source_asset_id=source_asset_id,
        mask_asset_id=mask_asset_id,
        correction_prompt=prompt,
        map_id=document_id,
        width=width,
        height=height,
        preserve_style=preserve_style,
        preserve_perspective=preserve_perspective,
        preserve_lighting=preserve_lighting,
    )


def accept_correction(
    db: Session,
    project_id: str,
    document_id: str,
    *,
    session_id: str | None = None,
    output_asset_id: str | None = None,
    result_asset_id: str | None = None,
    accept_token: str | None = None,
) -> dict[str, Any]:
    """Accept a corrected asset as the new map background.

    OVERLAY_GUARD: update_document(SpatialMapUpdateBody(backgroundAssetId=...))
    ONLY — never create_document / createMap. Characters/cameras/movement untouched.
    """
    from .schemas import SpatialMapUpdateBody
    from .service import get_document, update_document

    _sync_provider_jobs(db, project_id, document_id)
    document = get_document(db, project_id, document_id)
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)

    out_id = (result_asset_id or output_asset_id or "").strip() or None
    token = (accept_token or "").strip() or None

    if token:
        tok = (bucket.get("tokens") or {}).get(token)
        if not tok:
            raise ValueError("Invalid or expired acceptToken.")
        if tok.get("mapId") and tok.get("mapId") != document_id:
            raise ValueError("acceptToken mapId mismatch.")
        out_id = out_id or tok.get("resultAssetId")
        session_id = session_id or tok.get("jobId")

    sid = session_id or bucket.get("activeSessionId") or bucket.get("activeJobId")
    session = next((s for s in bucket["sessions"] if s.get("sessionId") == sid), None)
    job = next((j for j in bucket["jobs"] if j.get("jobId") == sid), None)
    if not session and not job:
        raise ValueError("No active Correct Area session/job to accept.")

    if not out_id:
        out_id = (session or {}).get("outputAssetId") or (job or {}).get("resultAssetId")
    if not out_id:
        raise ValueError(
            f"No corrected asset to accept yet. Wait for {ENGINE} job to finish "
            "(or attach-preview), then Accept. Original Spatial Map stays active."
        )
    out = db.get(Asset, out_id)
    if not out or out.project_id != project_id:
        raise ValueError("Corrected asset not found in this project.")

    # Exact dimension gate — refuse mismatch; never silent-resize.
    src_w = int((job or session or {}).get("width") or 0)
    src_h = int((job or session or {}).get("height") or 0)
    if src_w <= 0 or src_h <= 0:
        src_probe_id = (
            (job or {}).get("sourceAssetId")
            or (session or {}).get("sourceAssetId")
            or getattr(document, "backgroundAssetId", None)
            or ""
        )
        prev_probe = db.get(Asset, src_probe_id) if src_probe_id else None
        if prev_probe and getattr(prev_probe, "path", None):
            try:
                from PIL import Image

                with Image.open(prev_probe.path) as im:
                    src_w, src_h = int(im.size[0]), int(im.size[1])
            except Exception:
                pass
    dim = reconcile_dimensions(
        source_width=src_w,
        source_height=src_h,
        output_path=out.path,
    )
    if src_w > 0 and src_h > 0 and not dim.get("ok"):
        raise ValueError(
            dim.get("error")
            or f"Corrected asset dimensions must match source {src_w}x{src_h} exactly. Original stays active."
        )

    prev_bg = getattr(document, "backgroundAssetId", None)
    try:
        from ..asset_graph import add_edge, add_version

        if prev_bg:
            add_edge(db, prev_bg, out_id, "derived_from", {"op": OP_CORRECT})
        add_version(
            db,
            asset_id=out_id,
            op=OP_CORRECT,
            path=out.path or "",
            prompt={
                "creatorPrompt": (session or job or {}).get("creatorPrompt"),
                "preservationTemplate": PRESERVATION_TEMPLATE,
                "frozen": True,
            },
            model=(session or job or {}).get("preferredModel") or ENGINE,
        )
        if not out.parent_asset_id and prev_bg:
            out.parent_asset_id = prev_bg
            db.add(out)
        db.commit()
    except Exception:
        db.rollback()

    version_id = (session or job or {}).get("versionId")
    if version_id:
        try:
            version_store.set_state(project_id, version_id, "Approved")
            data = version_store._load(project_id)  # noqa: SLF001
            for v in data.get("versions") or []:
                if v.get("versionId") == version_id:
                    v["outputAssetId"] = out_id
                    v["modifiedAt"] = _now()
            version_store._save(project_id, data)  # noqa: SLF001
        except Exception:
            pass

    # OVERLAY_GUARD: backgroundAssetId PATCH only — never create_document / createMap.
    updated = update_document(
        db,
        project_id,
        document_id,
        SpatialMapUpdateBody(backgroundAssetId=out_id),
    )

    n = len(bucket.get("acceptedChain") or []) + 1
    chain_entry = {
        "label": f"Correction v{n}",
        "sessionId": sid,
        "jobId": sid,
        "fromAssetId": prev_bg,
        "toAssetId": out_id,
        "assetId": out_id,
        "creatorPrompt": (session or job or {}).get("creatorPrompt"),
        "acceptedAt": _now(),
    }
    bucket.setdefault("acceptedChain", []).append(chain_entry)
    if not bucket.get("originalBackgroundAssetId"):
        bucket["originalBackgroundAssetId"] = prev_bg
    bucket["currentBackgroundAssetId"] = out_id
    if session:
        session["outputAssetId"] = out_id
        session["status"] = "accepted"
        session["modifiedAt"] = _now()
    if job:
        job["resultAssetId"] = out_id
        job["status"] = "accepted"
        job["modifiedAt"] = _now()
    bucket["activeSessionId"] = sid
    bucket["activeJobId"] = sid
    if token and token in bucket.get("tokens", {}):
        bucket["tokens"][token]["consumedAt"] = _now()
        bucket["tokens"][token]["resultAssetId"] = out_id
    _save_store(project_id, store)

    return {
        "document": updated.model_dump(),
        "session": session,
        "job": job,
        "acceptedChain": _chain_labels(list(bucket["acceptedChain"])),
        "overlaysPreserved": True,
        "backgroundAssetId": out_id,
        "previousBackgroundAssetId": prev_bg,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "acceptUsedUpdateDocumentOnly": True,
        "createMapCalled": False,
    }


def undo_correction(
    db: Session,
    project_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Undo last accepted correction — restore prior backgroundAssetId. Overlays untouched."""
    from .schemas import SpatialMapUpdateBody
    from .service import get_document, update_document

    get_document(db, project_id, document_id)
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    chain = list(bucket.get("acceptedChain") or [])
    if not chain:
        raise ValueError("Nothing to undo — no accepted Spatial Map corrections.")
    last = chain.pop()
    restore_id = last.get("fromAssetId") or bucket.get("originalBackgroundAssetId")
    if not restore_id:
        raise ValueError("Cannot undo — prior background asset missing.")

    updated = update_document(
        db,
        project_id,
        document_id,
        SpatialMapUpdateBody(backgroundAssetId=restore_id),
    )
    bucket["acceptedChain"] = chain
    bucket["currentBackgroundAssetId"] = restore_id
    if bucket.get("activeSessionId") == last.get("sessionId") or bucket.get("activeJobId") == last.get(
        "jobId"
    ):
        bucket["activeSessionId"] = chain[-1].get("sessionId") if chain else None
        bucket["activeJobId"] = chain[-1].get("jobId") if chain else None
    for s in bucket["sessions"]:
        if s.get("sessionId") in {last.get("sessionId"), last.get("jobId")}:
            s["status"] = "undone"
            s["modifiedAt"] = _now()
    for j in bucket["jobs"]:
        if j.get("jobId") in {last.get("jobId"), last.get("sessionId")}:
            j["status"] = "undone"
            j["modifiedAt"] = _now()
    _save_store(project_id, store)

    return {
        "document": updated.model_dump(),
        "restoredBackgroundAssetId": restore_id,
        "undone": last,
        "acceptedChain": _chain_labels(chain),
        "overlaysPreserved": True,
        "canUndo": bool(chain),
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "acceptUsedUpdateDocumentOnly": True,
        "createMapCalled": False,
    }


def reset_correction(
    db: Session,
    project_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Reset to original backgroundAssetId. Overlays untouched. Not a map Reset wipe."""
    from .schemas import SpatialMapUpdateBody
    from .service import get_document, update_document

    get_document(db, project_id, document_id)
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    original = bucket.get("originalBackgroundAssetId")
    if not original:
        # No correction history — nothing to reset; leave active as-is.
        doc = get_document(db, project_id, document_id)
        return {
            "document": doc.model_dump(),
            "restoredBackgroundAssetId": getattr(doc, "backgroundAssetId", None),
            "reset": False,
            "reason": "No recorded original background for this map.",
            "overlaysPreserved": True,
            "engine": ENGINE,
            "engineStatus": ENGINE,
            "engineHold": None,
        }
    updated = update_document(
        db,
        project_id,
        document_id,
        SpatialMapUpdateBody(backgroundAssetId=original),
    )
    for entry in list(bucket.get("acceptedChain") or []):
        for s in bucket["sessions"]:
            if s.get("sessionId") in {entry.get("sessionId"), entry.get("jobId")}:
                s["status"] = "reset"
                s["modifiedAt"] = _now()
        for j in bucket["jobs"]:
            if j.get("jobId") in {entry.get("jobId"), entry.get("sessionId")}:
                j["status"] = "reset"
                j["modifiedAt"] = _now()
    bucket["acceptedChain"] = []
    bucket["currentBackgroundAssetId"] = original
    bucket["activeSessionId"] = None
    bucket["activeJobId"] = None
    _save_store(project_id, store)
    return {
        "document": updated.model_dump(),
        "restoredBackgroundAssetId": original,
        "reset": True,
        "acceptedChain": [],
        "overlaysPreserved": True,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "acceptUsedUpdateDocumentOnly": True,
        "createMapCalled": False,
    }


def attach_preview_output(
    project_id: str,
    document_id: str,
    *,
    session_id: str,
    output_asset_id: str,
) -> dict[str, Any]:
    """Brad / Primary test hook: attach a real corrected asset after supervised run.

    Does not call a provider. Only links an already-existing asset id.
    """
    store = _load_store(project_id)
    bucket = _map_bucket(store, document_id)
    session = next((s for s in bucket["sessions"] if s.get("sessionId") == session_id), None)
    job = next((j for j in bucket["jobs"] if j.get("jobId") == session_id), None)
    if not session and not job:
        raise ValueError("Correction session/job not found.")
    accept_token = _mint_accept_token(session_id, output_asset_id)
    if session:
        session["outputAssetId"] = output_asset_id
        session["status"] = "preview_ready"
        session["modifiedAt"] = _now()
    if job:
        job["resultAssetId"] = output_asset_id
        job["status"] = "preview_ready"
        job["acceptToken"] = accept_token
        job["modifiedAt"] = _now()
    bucket["tokens"][accept_token] = {
        "jobId": session_id,
        "resultAssetId": output_asset_id,
        "mapId": document_id,
        "createdAt": _now(),
    }
    bucket["activeSessionId"] = session_id
    bucket["activeJobId"] = session_id
    _save_store(project_id, store)
    return {
        "session": session,
        "job": job,
        "acceptToken": accept_token,
        "engine": ENGINE,
        "engineStatus": ENGINE,
        "engineHold": None,
        "providerCalled": False,
        "previewUrl": _preview_url(project_id, output_asset_id),
        "resultAssetId": output_asset_id,
    }
