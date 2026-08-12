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
) -> dict[str, Any]:
    """Submit a real Atlas Shot image generation job.

    Returns a dict with ``job_ids``, ``child_jobs`` (single Atlas Shot job),
    and ``surface_type``. The dispatcher wraps this into an ExecutionPlan.
    """
    from ....storyboard_jobs import enqueue_imagegen_job

    user_prompt = (prompt or "").strip()
    atlas_prompt = _ATLAS_PREFIX + user_prompt

    # Atlas Shot aspect is square by default (1:1) for clean floor-plan coverage.
    # Respect the caller's aspect ratio if they override (e.g. 16:16 for wide sets).
    body: dict[str, Any] = {
        "prompt": atlas_prompt,
        "negative_prompt": (
            "characters, people, moveable props, perspective distortion, "
            "horizon line, sky, dramatic angle, dutch tilt, fish-eye"
        ),
        "width": 1280,
        "height": 1280,
        "tag": f"codirector_atlas_{execution_id[:8]}",
        "modelFamilyPreference": "zimage",
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
            "workflowKey": "zimage.txt2img",
        },
    }

    job = enqueue_imagegen_job(db, project_id, body)

    child_jobs = [
        {
            "job_id": job.id,
            "label": "Atlas Shot",
            "status": "queued",
            "child_index": 0,
            "metadata": {
                "purpose": "atlas_shot",
                "aspect_ratio": aspect_ratio or "1:1",
                "scene_context": scene_context or "",
            },
        }
    ]

    return {
        "job_ids": [job.id],
        "child_jobs": child_jobs,
        "surface_type": "atlas_shot_generation",
        "purpose": "atlas_shot",
        "aspect_ratio": aspect_ratio or "1:1",
    }
