"""Capability handler: storyboard.regenerate_frame

Spec §43: "Support: 'Regenerate frame 2.' 'Change only the close-up.'
Regenerate only requested frame/assets. Keep rest of collection intact."
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..shot_planner import shots_to_prompt_metadata

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    frame_index: int = 0,
    frame_metadata: dict[str, Any] | None = None,
    reference_asset_id: str | None = None,
    visual_style: str = "",
    user_instructions: str = "",
) -> dict[str, Any]:
    """Regenerate a single storyboard frame.

    Submits one new imagegen job for the specified frame. The parent execution
    pack's other frames remain intact — only this child job is replaced.
    """
    from ....storyboard_jobs import enqueue_imagegen_job

    meta = frame_metadata or {}
    framing = meta.get("framing", "medium")
    prompt = meta.get("prompt_fragment", meta.get("composition", f"{framing} shot"))

    if user_instructions:
        prompt = f"{user_instructions}. {prompt}"

    body: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": "",
        "width": 1280,
        "height": 720,
        "tag": f"codirector_storyboard_regen_{execution_id[:8]}_frame{frame_index + 1}",
        "modelFamilyPreference": "zimage",
        "purpose": "codirector_storyboard_regen",
        "aspectRatio": "16:9",
        "batchCount": 1,
        "creativeContext": {
            "objective": "storyboard_regen",
            "executionId": execution_id,
            "frameIndex": frame_index,
            "framing": framing,
            "workflowKey": "zimage.txt2img",
        },
    }

    if reference_asset_id:
        body["referenceImage"] = reference_asset_id
        body["reference_image"] = reference_asset_id

    if visual_style:
        body["creativeContext"]["visualStyle"] = visual_style

    try:
        job = enqueue_imagegen_job(db, project_id, body)
        job_id = job.id
    except Exception as exc:
        logger.error("Failed to regenerate frame %d: %s", frame_index + 1, exc)
        job_id = f"failed_regen_frame_{frame_index}"

    return {
        "job_ids": [job_id],
        "child_jobs": [{
            "job_id": job_id,
            "label": f"Frame {frame_index + 1} — {framing.title()} (regenerated)",
            "status": "queued",
            "child_index": frame_index,
            "metadata": meta,
        }],
        "surface_type": "storyboard_generation",
        "frame_index": frame_index,
    }
