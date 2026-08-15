"""Enqueue through existing Image Product / storyboard job path."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .errors import ImageCoreError, UNSUPPORTED_OPERATION, WORKFLOW_FAILED
from .preflight import preflight
from .request import ImageCoreRequest, NormalizedEnqueue


def _to_body(request: ImageCoreRequest, decision) -> dict[str, Any]:
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
    body["creativeContext"] = ctx
    return body


def generate(db: Session, request: ImageCoreRequest) -> NormalizedEnqueue:
    decision = preflight(request)
    if not decision.ok:
        raise ImageCoreError(decision.code or UNSUPPORTED_OPERATION, decision.message or "Unsupported operation")
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
