"""Capability handler: video.generate — standalone Co-Director video only.

Timeline shot / track / batch generation must not enter this handler.
Uses existing MiniMax / LTX / hosted adapters via ProductionIntent.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ...preferences.resolver import creator_provider_label, resolve_generator_preference
from ...production_intent.execute import IntentExecutionError, enqueue_intent
from ...production_intent.schemas import ProductionIntent
from ...routing.generation_authority import (
    classify_generation_authority,
    resolve_animate_source_asset,
)

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    attachment_asset_ids: list[str] | None = None,
    reference_asset_id: str = "",
    aspect_ratio: str = "16:9",
    user_instructions: str = "",
    original_user_instructions: str = "",
    scene_id: str = "",
    force_enqueue_failure: bool = False,
    **_: Any,
) -> dict[str, Any]:
    speech = user_instructions or prompt
    creative = (original_user_instructions or prompt or user_instructions).strip()
    authority = classify_generation_authority(creative) or classify_generation_authority(speech)
    message = creative or speech
    if authority and authority.owner == "timeline":
        return {
            "error": "This generation belongs to Timeline Suite. Open Timeline to generate that shot.",
            "child_jobs": [],
        }

    resolution = resolve_generator_preference(
        db,
        project_id,
        modality="video",
        message=message,
    )
    if not resolution.ok:
        return {
            "error": resolution.error or "That video generator is not configured.",
            "child_jobs": [],
            "provider": resolution.provider,
            "plan_data": {
                "jobScopedOverride": resolution.job_scoped,
                "preferenceSource": resolution.source,
                "modality": "video",
            },
        }

    source_assets: list[str] = []
    video_mode = authority.video_mode if authority else "t2v"
    if video_mode in {"i2v", "animate"} or (authority and authority.kind == "animate_it"):
        asset_id = reference_asset_id or ((attachment_asset_ids or [None])[0])
        if not asset_id:
            asset_id = resolve_animate_source_asset(db, project_id)
        if not asset_id:
            return {
                "error": "I need the first frame before I can animate it. Generate a still first.",
                "child_jobs": [],
            }
        source_assets = [str(asset_id)]
        video_mode = "i2v"

    intent = ProductionIntent(
        projectId=project_id,
        sceneId=scene_id or None,
        sourceSurface="codirector",
        operation="video.three_frame" if video_mode == "multi_frame" else "video.generate",
        modality="video",
        prompt=prompt or message,
        sourceAssets=source_assets,
        enginePreference=resolution.provider,
        aspectRatio=aspect_ratio,
        metadata={
            "executionId": execution_id,
            "videoMode": video_mode,
            "jobScopedOverride": resolution.job_scoped,
            "preferenceSource": resolution.source,
            "standalone": True,
            "forceEnqueueFailure": bool(force_enqueue_failure),
            "sceneId": scene_id or "",
        },
    )
    try:
        result = enqueue_intent(db, intent)
    except IntentExecutionError as exc:
        raw = str(exc) or "Video generation could not start."
        if resolution.explicit:
            label = creator_provider_label(resolution.provider)
            raw = f"{label} could not start. {raw} I will not switch to another generator."
        elif "no active model" in raw.lower():
            raw = (
                f"{creator_provider_label(resolution.provider)} is the selected video generator, but it is not ready. "
                "I will not switch to another generator."
            )
        return {
            "error": raw,
            "child_jobs": [],
            "provider": resolution.provider,
            "plan_data": {
                "jobScopedOverride": resolution.job_scoped,
                "preferenceSource": resolution.source,
                "modality": "video",
            },
        }

    job_id = str(result.get("jobId") or "")
    if not job_id:
        return {
            "error": result.get("note") or "Video generation did not create a job.",
            "child_jobs": [],
            "provider": resolution.provider,
        }
    if result.get("ok") is False or str(result.get("status") or "").lower() == "failed":
        err = result.get("error") or result.get("note") or "Video generation could not start."
        return {
            "error": err,
            "job_ids": [job_id],
            "child_jobs": [
                {
                    "job_id": job_id,
                    "label": "Video",
                    "status": "failed",
                    "child_index": 0,
                    "error": err,
                }
            ],
            "provider": resolution.provider,
            "plan_data": {
                "jobScopedOverride": resolution.job_scoped,
                "preferenceSource": resolution.source,
                "modality": "video",
            },
        }

    return {
        "job_ids": [job_id],
        "child_jobs": [
            {
                "job_id": job_id,
                "label": "Video",
                "status": "queued",
                "child_index": 0,
                "metadata": {
                    "resolvedProvider": resolution.provider,
                    "preferenceSource": resolution.source,
                    "jobScopedOverride": resolution.job_scoped,
                    "videoMode": video_mode,
                    "sourceAssetId": source_assets[0] if source_assets else "",
                },
            }
        ],
        "surface_type": "video_generation",
        "provider": resolution.provider,
        "model": result.get("workflowKey") or resolution.provider,
        "plan_data": {
            "jobScopedOverride": resolution.job_scoped,
            "preferenceSource": resolution.source,
            "modality": "video",
            "videoMode": video_mode,
        },
    }
