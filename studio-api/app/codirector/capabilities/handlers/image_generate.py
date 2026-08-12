"""Capability handler: image.generate

Handles the `image.generate` capability for the Co-Director execution dispatcher.
Resolves character references, attachments, and style, then submits a real
image generation job through the existing Image Generator pipeline.

Spec §44 — Mieke acceptance case:
1. classify EXECUTION
2. capability image.generate
3. resolve Mieke Character Profile
4. resolve Approved Casting Image/reference
5. resolve style if available
6. create generation request
7. submit real job
8. right pane shows active image-generation surface
9. live progress visible
10. generated image appears
11. asset saved to Library
12. Co-Director can immediately discuss/regenerate it
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ....character_identity.service import resolve_character_by_name, resolve_approved_reference

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    prompt: str = "",
    character_name: str = "",
    character_id: str = "",
    scene_id: str = "",
    visual_style: str = "",
    attachment_asset_ids: list[str] | None = None,
    aspect_ratio: str = "16:9",
    count: int = 1,
) -> dict[str, Any]:
    """Submit a real image generation job.

    Returns a dict with job_ids, child_jobs (for the ExecutionPlan), and
    surface_type. The dispatcher wraps this into an ExecutionPlan.
    """
    from ....storyboard_jobs import enqueue_imagegen_job

    reference_asset_id: str | None = None
    resolved_character_id: str | None = character_id or None
    resolved_character_name = character_name

    # Resolve character by name if given (spec §13, §44).
    if character_name and not resolved_character_id:
        profile = resolve_character_by_name(db, project_id, character_name)
        if profile:
            resolved_character_id = profile.id
            resolved_character_name = profile.name
            reference_asset_id = resolve_approved_reference(db, profile.id, "hero_identity")

    # User-supplied attachment takes precedence as a reference (spec §12).
    if attachment_asset_ids:
        reference_asset_id = attachment_asset_ids[0]

    # Build the generation request.
    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": "",
        "width": 1280,
        "height": 720,
        "tag": f"codirector_image_generate_{execution_id[:8]}",
        "modelFamilyPreference": "zimage",
        "purpose": "codirector_image_generate",
        "aspectRatio": aspect_ratio,
        "batchCount": max(1, min(count, 8)),
        "creativeContext": {
            "objective": "image_generate",
            "executionId": execution_id,
            "characterId": resolved_character_id or "",
            "characterName": resolved_character_name or "",
            "workflowKey": "zimage.txt2img",
        },
    }

    if reference_asset_id:
        body["referenceImage"] = reference_asset_id
        body["reference_image"] = reference_asset_id

    if visual_style:
        body["creativeContext"]["visualStyle"] = visual_style

    # Submit the real job.
    job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id or None)

    child_jobs = []
    for i in range(max(1, min(count, 8))):
        child_jobs.append({
            "job_id": job.id if i == 0 else f"{job.id}_batch{i}",
            "label": f"Image {i + 1}" if count > 1 else "Generated Image",
            "status": "queued",
            "child_index": i,
            "metadata": {
                "character_id": resolved_character_id or "",
                "character_name": resolved_character_name or "",
                "reference_asset_id": reference_asset_id or "",
            },
        })

    return {
        "job_ids": [cj["job_id"] for cj in child_jobs],
        "child_jobs": child_jobs,
        "surface_type": "image_generation",
        "character_id": resolved_character_id,
        "reference_asset_id": reference_asset_id,
    }
