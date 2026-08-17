"""Enqueue through existing Image Product / storyboard job path."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .capability import ADD_INSERT_DOCK, ADD_INSERT_FAL_MODEL, is_add_insert_family
from .errors import ImageCoreError, UNSUPPORTED_OPERATION, WORKFLOW_FAILED
from .preflight import REFERENCES_UNSUPPORTED_MESSAGE, preflight, request_has_identity_refs
from .request import ImageCoreRequest, NormalizedEnqueue


def idempotency_key(request: ImageCoreRequest) -> str:
    ctx = request.creative_context or {}
    cine = ctx.get("cinematographer") if isinstance(ctx.get("cinematographer"), dict) else {}
    camera_hash = str(cine.get("cameraStateHash") or ctx.get("cameraStateHash") or "")
    return "|".join(
        [
            request.purpose or "",
            request.source_asset_id or "",
            camera_hash,
            request.model_id or "",
            request.operation or "",
            request.edit_operation or "",
            request.mask_asset_id or "",
        ]
    )


def _to_body(request: ImageCoreRequest, decision) -> dict[str, Any]:
    if request_has_identity_refs(request) and (decision.runtime_operation or "") in {
        "image.generate",
        "text_to_image",
        "txt2img",
    }:
        # Preflight refuses this combination; honor the refusal so references are
        # never silently dropped from the enqueue body (CDX-079).
        raise ImageCoreError(UNSUPPORTED_OPERATION, REFERENCES_UNSUPPORTED_MESSAGE)
    body = dict(request.extra or {})
    body["purpose"] = request.purpose
    body["operation"] = decision.runtime_operation
    body["prompt"] = request.prompt or body.get("prompt") or ""
    if request.negative_prompt:
        body["negativePrompt"] = request.negative_prompt
    body["model"] = request.model_id or decision.family
    body["modelFamilyPreference"] = decision.family
    body["lockModelFamily"] = request.lock_model_family
    body["providerPreference"] = "cloud" if request.provider == "cloud" else "local"
    if is_add_insert_family(decision.family) and (request.edit_operation or "").strip().lower() == "add":
        body["providerPreference"] = "cloud"
        body["source"] = "api"
        body["falImageModelId"] = ADD_INSERT_FAL_MODEL
        body["hostedModelId"] = ADD_INSERT_DOCK
        body["model"] = ADD_INSERT_FAL_MODEL
        body["aspect"] = request.aspect_ratio or "16:9"
        body["aspectRatio"] = request.aspect_ratio or "16:9"
    if request.hosted_model_id:
        body["hostedModelId"] = request.hosted_model_id
        body["model"] = request.hosted_model_id
    if request.seed is not None:
        body["seed"] = request.seed
    if request.scene_id:
        body["sceneId"] = request.scene_id
    if request.shot_id:
        body["shotId"] = request.shot_id
    if request.tag:
        body["tag"] = request.tag
    if decision.width:
        body["width"] = decision.width
    if decision.height:
        body["height"] = decision.height
    if request.source_asset_id:
        body["sourceAssetId"] = request.source_asset_id
        body["source_asset_id"] = request.source_asset_id
        body["edit"] = True
    elif decision.runtime_operation in {"image.edit", "image.reference"}:
        extra = request.extra or {}
        primary = str(extra.get("referenceImage") or extra.get("reference_image") or "").strip()
        if not primary:
            ids = extra.get("referenceIds") or extra.get("referenceAssetIds") or []
            if not ids:
                ctx = request.creative_context or {}
                ids = ctx.get("reference_image_ids") if isinstance(ctx, dict) else []
            if ids:
                primary = str(ids[0] or "").strip()
        if primary:
            body["sourceAssetId"] = primary
            body["source_asset_id"] = primary
            body["referenceImage"] = primary
            body["reference_image"] = primary
            if not body.get("referenceIds"):
                body["referenceIds"] = [primary]
    if request.mask_asset_id:
        body["masks"] = [
            {
                "maskAssetId": request.mask_asset_id,
                "maskId": request.mask_asset_id,
                "role": "replace" if request.edit_operation == "replace" else "include",
            }
        ]
    if decision.denoise is not None:
        body["denoise"] = decision.denoise
    if decision.grow_mask_by is not None:
        body["grow_mask_by"] = decision.grow_mask_by
    if request.purpose in {"scene_shot_preview"}:
        body["quality"] = "draft"
        body["allowDraft"] = True
    if request.aspect_ratio:
        body["aspect"] = request.aspect_ratio
        body["aspectRatio"] = request.aspect_ratio
    ctx = dict(request.creative_context or {})
    if isinstance(body.get("creativeContext"), dict):
        merged = dict(body["creativeContext"])
        merged.update(ctx)
        ctx = merged
    # Core records the resolved key for provenance. Scene must not choose it.
    if decision.workflow_key:
        ctx["workflowKey"] = decision.workflow_key
        ctx["imageCoreWorkflowKey"] = decision.workflow_key
        body["forceWorkflowKey"] = decision.workflow_key
        body["allow_force_workflow_key"] = True
    if request.edit_operation:
        ctx["editOperation"] = request.edit_operation
    ctx["purpose"] = request.purpose
    ctx["imageCoreIdempotencyKey"] = idempotency_key(request)
    body["creativeContext"] = ctx
    return body


def _reuse_live_job(db: Session, request: ImageCoreRequest):
    key = idempotency_key(request)
    if not key.strip("|") or not request.project_id:
        return None
    try:
        from ..db import Job
    except Exception:
        return None
    wanted = {"queued", "pending", "running", "generating", "processing"}
    try:
        rows = (
            db.query(Job)
            .filter(Job.project_id == request.project_id)
            .order_by(Job.created_at.desc())
            .limit(24)
            .all()
        )
    except Exception:
        return None
    for job in rows:
        status = str(getattr(job, "status", "") or "").lower()
        if status not in wanted:
            continue
        raw = getattr(job, "params_json", None) or getattr(job, "params", None)
        params: dict[str, Any] = {}
        if isinstance(raw, dict):
            params = raw
        elif isinstance(raw, str) and raw:
            try:
                import json

                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    params = parsed
            except Exception:
                params = {}
        ctx = params.get("creativeContext") if isinstance(params.get("creativeContext"), dict) else {}
        if str(ctx.get("imageCoreIdempotencyKey") or "") == key:
            return job
    return None


def generate(db: Session, request: ImageCoreRequest) -> NormalizedEnqueue:
    decision = preflight(request)
    if not decision.ok:
        raise ImageCoreError(decision.code or UNSUPPORTED_OPERATION, decision.message or "Unsupported operation")
    reused = _reuse_live_job(db, request)
    if reused is not None:
        return NormalizedEnqueue(
            job_id=str(getattr(reused, "id", "") or ""),
            status="queued",
            workflow_key=decision.workflow_key,
            family=decision.family,
            operation=decision.runtime_operation,
            width=decision.width,
            height=decision.height,
            fallback_applied=False,
            job=reused,
            decision=decision,
        )
    body = _to_body(request, decision)
    try:
        from ..storyboard_jobs import enqueue_imagegen_job

        job = enqueue_imagegen_job(db, request.project_id, body, scene_id=request.scene_id or None)
    except ImageCoreError:
        raise
    except Exception as exc:
        msg = str(exc)
        low = msg.lower()
        code = WORKFLOW_FAILED
        if "not installed" in low:
            from .errors import MODEL_NOT_INSTALLED

            code = MODEL_NOT_INSTALLED
        elif "offline" in low or "not running" in low:
            from .errors import RUNTIME_OFFLINE

            code = RUNTIME_OFFLINE
        elif "api key" in low or "auth" in low:
            from .errors import PROVIDER_AUTH_FAILED

            code = PROVIDER_AUTH_FAILED
        raise ImageCoreError(code, msg) from exc

    job_id = str(getattr(job, "id", "") or "")
    job_status = str(getattr(job, "status", "") or "").lower()
    status = "failed" if job_status in {"failed", "error"} else "queued"
    error = str(getattr(job, "message", "") or "")
    return NormalizedEnqueue(
        job_id=job_id,
        status=status,
        workflow_key=decision.workflow_key,
        family=decision.family,
        operation=decision.runtime_operation,
        width=decision.width,
        height=decision.height,
        fallback_applied=False,
        error=error,
        job=job,
        decision=decision,
    )
