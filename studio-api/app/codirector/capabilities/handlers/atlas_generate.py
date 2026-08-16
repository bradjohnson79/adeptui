"""Capability handler: atlas.generate

Generates an Atlas Shot — a roofless top-down orthographic environment
reference used as the background/master reference for a Spatial Map.

Amendment #1 (ATLAS ORDER): the Atlas Shot is an INPUT to the Spatial Map.
The workflow is Character Creator → Atlas Shot / Master Environment →
Spatial Map → ERS → Scene Creator → Timeline.

Amendment #4 (ORIENTATION): Atlas North = the top edge of the approved
Atlas Shot. N/E/S/W are scene-relative, not literal compass headings.

Law #18 (Model/Provider): we use the canonical image gen pipeline
(``enqueue_imagegen_job``) — no silent provider/model substitution.
Law #7 (No mock completion): this handler submits a REAL job.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


_ATLAS_PREFIX = (
    "Roofless top-down orthographic environment reference, viewed from directly above. "
    "Clear floor plan with minimal perspective distortion. Complete environment coverage. "
    "Architectural layout, furniture, and fixed fixtures visible from above. "
    "No characters and no moveable props unless explicitly requested. "
    "Consistent lighting and material palette throughout. "
)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    visual_style: str = "",
    scene_context: str | None = None,
    aspect_ratio: str = "1:1",
    attachment_asset_ids: list[str] | None = None,
    scene_description: str = "",
    scene_intent: dict[str, Any] | None = None,
    hosted_model_id: str = "",
    hostedModelId: str = "",
    kie_image_model_id: str = "",
    kieImageModelId: str = "",
    model: str = "",
    model_family_preference: str = "",
    source: str = "",
    forceWorkflowKey: str = "",
) -> dict[str, Any]:
    """Submit a real Atlas Shot image generation job.

    Returns a dict with ``job_ids``, ``child_jobs`` (single Atlas Shot job),
    and ``surface_type``. The dispatcher wraps this into an ExecutionPlan.

    Atlas Scene Intent law: every Atlas Shot carries a compact SceneIntent
    snapshot (semantic anchor) plus the original environment reference asset
    IDs, so ERS generation never has to re-infer why the Atlas exists.
    """
    from ....db import Project
    from ....spatial_map.scene_intent import (
        build_scene_intent,
        coerce_scene_intent,
    )
    from ....storyboard_jobs import enqueue_imagegen_job

    user_prompt = (prompt or "").strip()
    atlas_prompt = _ATLAS_PREFIX + user_prompt

    source_ref_ids = [
        str(a).strip() for a in (attachment_asset_ids or []) if str(a or "").strip()
    ]

    # Snapshot Scene Intent at creation time (never re-infer at ERS time).
    intent = coerce_scene_intent(scene_intent)
    intent_error = ""
    if intent is None:
        description = (scene_description or "").strip() or user_prompt
        try:
            project = db.get(Project, project_id)
            intent = build_scene_intent(
                description,
                project_name=str(getattr(project, "name", "") or ""),
                source_reference_asset_ids=source_ref_ids,
                originating_prompt=user_prompt,
            )
        except ValueError as exc:
            # No usable intent text at all — record honestly, do not invent.
            intent = None
            intent_error = str(exc)
    if intent is not None and source_ref_ids and not intent.sourceReferenceAssetIds:
        intent.sourceReferenceAssetIds = source_ref_ids

    # Atlas Shot aspect is square by default (1:1) for clean floor-plan coverage.
    body: dict[str, Any] = {
        "prompt": atlas_prompt,
        "negative_prompt": (
            "characters, people, moveable props, perspective distortion, "
            "horizon line, sky, dramatic angle, dutch tilt, fish-eye"
        ),
        "width": 1280,
        "height": 1280,
        "tag": f"codirector_atlas_{execution_id[:8]}",
        "purpose": "atlas_shot",
        "aspectRatio": aspect_ratio or "1:1",
        "batchCount": 1,
        "creativeContext": {
            "objective": "atlas_shot",
            "executionId": execution_id,
            "visualStyle": visual_style or "",
            "sceneContext": scene_context or "",
            "orientationNote": (
                "North = top edge of the approved Atlas Shot (scene-relative)."
            ),
        },
    }
    source_asset = source_ref_ids[0] if source_ref_ids else ""
    gpt_blob = " ".join(
        str(v)
        for v in (
            hosted_model_id,
            hostedModelId,
            kie_image_model_id,
            kieImageModelId,
            model,
        )
        if v
    ).lower()
    wants_gpt = "gpt-image-2" in gpt_blob or "gpt_image_2" in gpt_blob
    if source_asset:
        # Continuity mode: source pixels + instruction. Never zimage.txt2img.
        body["sourceAssetId"] = source_asset
        body["source_asset_id"] = source_asset
        body["referenceImage"] = source_asset
        body["creativeContext"]["authoritativeSourceAssetId"] = source_asset
        body["operation"] = "image.generate"
        if wants_gpt:
            from .ers_generate import _gpt_i2i_official_id, _public_asset_url

            url = _public_asset_url(source_asset)
            if not url:
                raise RuntimeError(
                    "Atlas continuity requires a public URL for the source environment "
                    "image when using GPT Image 2. Text-to-image is not allowed."
                )
            body["hostedModelId"] = "gpt-image-2-kie"
            body["kieImageModelId"] = _gpt_i2i_official_id()
            body["input_urls"] = [url]
            body["source"] = "api"
            body["lockModelFamily"] = True
            body["creativeContext"]["workflowKey"] = _gpt_i2i_official_id()
            body["creativeContext"]["operationIntent"] = "image.generate"
        else:
            from .ers_generate import _ers_i2i_workflow_key

            wf = _ers_i2i_workflow_key()
            if not wf:
                raise RuntimeError(
                    "Atlas continuity requires Qwen image-to-image (qwen2512.ref) or "
                    "GPT Image 2 image-to-image. Text-to-image is not allowed once a "
                    "source environment image exists."
                )
            body["modelFamilyPreference"] = "qwen2512"
            body["model"] = "qwen2512"
            body["forceWorkflowKey"] = wf
            body["allow_force_workflow_key"] = True
            body["lockModelFamily"] = True
            body["source"] = "local"
            body["creativeContext"]["workflowKey"] = wf
            body["creativeContext"]["operationIntent"] = "image_to_image_reference"
    else:
        # Brand-new environment with no source image: T2I creation mode.
        body["modelFamilyPreference"] = "zimage"
        body["creativeContext"]["workflowKey"] = "zimage.txt2img"
        body["creativeContext"]["operationIntent"] = "text_to_image"
    if intent is not None:
        body["creativeContext"]["sceneIntent"] = intent.model_dump()
    if source_ref_ids:
        body["creativeContext"]["originalEnvironmentReferenceAssetIds"] = source_ref_ids

    job = enqueue_imagegen_job(db, project_id, body)

    child_metadata: dict[str, Any] = {
        "purpose": "atlas_shot",
        "aspect_ratio": aspect_ratio or "1:1",
        "scene_context": scene_context or "",
    }
    if intent is not None:
        child_metadata["scene_intent"] = intent.model_dump()
    if source_ref_ids:
        child_metadata["original_environment_reference_asset_ids"] = source_ref_ids
        child_metadata["authoritative_source_asset_id"] = source_ref_ids[0]

    child_jobs = [
        {
            "job_id": job.id,
            "label": "Atlas Shot",
            "status": "queued",
            "child_index": 0,
            "metadata": child_metadata,
        }
    ]

    result: dict[str, Any] = {
        "job_ids": [job.id],
        "child_jobs": child_jobs,
        "surface_type": "atlas_shot_generation",
        "purpose": "atlas_shot",
        "aspect_ratio": aspect_ratio or "1:1",
    }
    if intent is not None:
        result["scene_intent"] = intent.model_dump()
    if intent_error:
        result["scene_intent_warning"] = intent_error
    return result
