"""Map ProductionIntent → WorkflowResolver request + studio job params."""

from __future__ import annotations

from typing import Any, Optional

from .schemas import ProductionIntent


# Product operation → resolver intent string used by WorkflowResolver.resolve_workflow
_RESOLVER_INTENT: dict[str, Optional[str]] = {
    "video.generate": "scene_i2v",
    "video.shot_render": "shot_render",
    "video.scene_render": "scene_render",
    "video.timeline_render": "timeline_render",
    "video.batch_timeline": "batch_timeline",
    "video.extend": "extend",
    "video.lipsync": "lipsync",
    "video.three_frame": "wan_three_frame",
}

_JOB_KIND: dict[str, Optional[str]] = {
    "video.generate": "render_scene",
    "video.shot_render": "render_scene",
    "video.scene_render": "render_scene",
    "video.timeline_render": "render_timeline",
    "video.batch_timeline": "batch_timeline",
    "video.extend": "video_extend",
    "video.lipsync": "lipsync",
    "video.three_frame": "render_scene",
    "image.generate": "imagegen",
    "image.edit": "imagegen",
}


def resolver_intent_for(operation: str) -> Optional[str]:
    return _RESOLVER_INTENT.get(operation)


def studio_job_kind_for(operation: str) -> Optional[str]:
    return _JOB_KIND.get(operation)


def to_resolver_request(intent: ProductionIntent) -> dict[str, Any]:
    """Public resolve params — never selects raw Comfy graphs."""
    ri = resolver_intent_for(intent.operation)
    engine = (intent.enginePreference or "minimax-h3").lower()
    if intent.operation == "video.three_frame":
        engine = "wan"
    if intent.workflowPreference and "wan" in intent.workflowPreference.lower():
        engine = "wan"
    start = intent.sourceAssets[0] if intent.sourceAssets else None
    middle = intent.sourceAssets[1] if len(intent.sourceAssets) > 1 else None
    end = intent.sourceAssets[2] if len(intent.sourceAssets) > 2 else None
    # Map three-frame refs from references if present
    for ref in intent.references:
        role = str(ref.get("role") or "").lower()
        aid = ref.get("assetId") or ref.get("id")
        if not aid:
            continue
        if role in {"start", "first"} and not start:
            start = str(aid)
        elif role in {"middle", "mid"} and not middle:
            middle = str(aid)
        elif role in {"end", "last"} and not end:
            end = str(aid)
    return {
        "intent": ri or intent.operation,
        "engine": engine,
        "workflowPreference": intent.workflowPreference,
        "projectId": intent.projectId,
        "sceneId": intent.sceneId,
        "shotId": intent.shotId,
        "prompt": intent.prompt,
        "startAssetId": start,
        "middleAssetId": middle,
        "endAssetId": end,
        "duration": intent.duration,
        "aspectRatio": intent.aspectRatio,
        "qualityProfile": intent.qualityProfile,
        "hasAudio": intent.operation == "video.lipsync"
        or bool((intent.metadata or {}).get("audioAssetId")),
        "paidFal": False,
    }


def to_studio_job_params(
    intent: ProductionIntent,
    contract: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Enqueue payload with videoRuntime + provenance. No builder graphs."""
    contract = contract or {}
    start = intent.sourceAssets[0] if intent.sourceAssets else None
    audio_id = (intent.metadata or {}).get("audioAssetId")
    params: dict[str, Any] = {
        "prompt": intent.prompt,
        "duration_sec": intent.duration,
        "aspect_ratio": intent.aspectRatio,
        "engine": intent.enginePreference or contract.get("engine") or "minimax-h3",
        "start_asset_id": start,
        "source_asset_id": start,
        "audio_asset_id": audio_id,
        "cloudPaid": False,
        "productionIntent": {
            "intentId": intent.intentId,
            "operation": intent.operation,
            "toolId": intent.toolId,
            "sourceSurface": intent.sourceSurface,
            "handoffId": intent.handoffId,
            "planId": intent.planId,
            "planStepId": intent.planStepId,
            "creativeContextDigest": (
                intent.creativeContext.digest if intent.creativeContext else None
            ),
        },
        "videoRuntime": {
            "mode": intent.operation,
            "workflow_key": contract.get("workflow_key") or contract.get("workflowKey"),
            "workflow_id": contract.get("workflow_id") or contract.get("workflowId"),
            "workflow_version": contract.get("workflow_version")
            or contract.get("workflowVersion"),
            "provider_kind": contract.get("provider_kind") or contract.get("provider") or "local",
            "engine": contract.get("engine") or intent.enginePreference or "minimax-h3",
            "concurrency_class": contract.get("concurrency_class")
            or contract.get("concurrencyClass")
            or "heavy_local",
            "start_asset_id": start,
            "certification_record_id": contract.get("certificationRecordId")
            or contract.get("certification_record_id"),
            "intent_id": intent.intentId,
        },
    }
    if intent.operation == "video.three_frame":
        params["frame_mode"] = "three_frame"
        params["engine"] = "wan"
        if len(intent.sourceAssets) >= 3:
            params["start_asset_id"] = intent.sourceAssets[0]
            params["middle_asset_id"] = intent.sourceAssets[1]
            params["end_asset_id"] = intent.sourceAssets[2]
    if intent.shotId:
        params["shot_id"] = intent.shotId
    if intent.targetPlacement:
        params["targetPlacement"] = intent.targetPlacement
    return params
