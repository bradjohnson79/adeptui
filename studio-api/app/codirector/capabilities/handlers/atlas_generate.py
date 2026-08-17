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
import re
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


# CDX-030: the Co-Director chat atlas path forwards the ENTIRE user message as
# the execution prompt, so the routing phrase ("create an atlas shot of ...")
# must never become the canonical SceneIntent summary. These patterns strip the
# leading capability phrase (matching the router vocabulary in
# ``codirector.routing``) so only the location description remains.
_ATLAS_ROUTING_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "create an atlas shot of X" / "make an atlas of X" / "generate atlas of X"
    re.compile(
        r"^(?:create|generate|make|render|build)\s+(?:an?\s+)?atlas(?:\s+shot)?"
        r"(?:\s+(?:of|for|featuring|showing|with)\s+)?",
        re.IGNORECASE,
    ),
    # "create a roofless shot of X" / "roofless shot of X" / "roofless view of X"
    re.compile(
        r"^(?:(?:create|generate|make|render|build)\s+)?(?:an?\s+)?roofless\s+(?:shot|map|view)"
        r"(?:\s+(?:of|for|featuring|showing|with)\s+)?",
        re.IGNORECASE,
    ),
)


def strip_atlas_routing_prefix(text: str) -> str:
    """CDX-030: strip the Atlas capability routing phrase from a description.

    Only a leading, verb-led capability phrase is removed. A genuine location
    description ("A neighborhood coffee shop.") or a non-routed phrase
    ("Atlas of the city streets") is returned unchanged. An empty remainder
    (e.g. a bare "create an atlas shot") keeps the original text so the
    SceneIntent validation layer reports the honest problem instead of
    silently inventing a description.
    """
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return cleaned
    for pattern in _ATLAS_ROUTING_PREFIX_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            remainder = cleaned[match.end():].strip()
            if remainder:
                return remainder
            return cleaned
    return cleaned


def _atlas_pixels(aspect_ratio: str) -> tuple[int, int]:
    """Derive Atlas Shot pixel dimensions from the requested aspect ratio (CDX-031).

    Uses the same aspect table as image_product.compile (1:1 base 1024x1024,
    scaled by the 2K factor 1.25) so the default square Atlas stays 1280x1280
    (unchanged behavior) while wide/tall requests (16:9, 9:16, 21:9, ...) produce
    genuinely non-square bodies instead of a fixed 1280x1280. Results are rounded
    down to multiples of 8 for model compatibility.
    """
    from ....image_product.compile import _ASPECT, _RES_SCALE

    key = (aspect_ratio or "1:1").strip() or "1:1"
    w, h = _ASPECT.get(key, (1024, 1024))
    scale = float(_RES_SCALE.get("2K", 1.25))
    return max(64, int(w * scale / 8) * 8), max(64, int(h * scale / 8) * 8)


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
        # CDX-030: the chat path forwards the entire user message (routing
        # phrase included) as the fallback description. Strip the capability
        # prefix so SceneIntent.summary carries the location description only.
        description = strip_atlas_routing_prefix(
            (scene_description or "").strip() or user_prompt
        )
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

    # Atlas Shot dimensions derive from the requested aspect ratio (CDX-031):
    # same table as image_product.compile, scaled so the default 1:1 stays
    # 1280x1280 while wide/tall requests produce genuinely non-square bodies.
    width, height = _atlas_pixels(aspect_ratio)
    body: dict[str, Any] = {
        "prompt": atlas_prompt,
        "negative_prompt": (
            "characters, people, moveable props, perspective distortion, "
            "horizon line, sky, dramatic angle, dutch tilt, fish-eye"
        ),
        "width": width,
        "height": height,
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
    # CDX-032 lineage contract (payload-only; queue_worker.py is a concurrent
    # workstream, so no worker edits): the PRIMARY reference rides
    # source_asset_id/sourceAssetId/referenceImage so _imagegen_commit_asset
    # records parent_asset_id + derived_from/reference_of edges; ALL reference
    # ids ride creativeContext.originalEnvironmentReferenceAssetIds (persisted
    # into prompt_meta) for the full lineage chain.
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
