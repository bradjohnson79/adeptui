"""Capability handler: storyboard.generate

Handles the `storyboard.generate` capability. Plans N distinct shots,
resolves character references + script context + attachments, then submits
N real imagegen jobs through the existing Image Generator pipeline.

Spec §45 — Schnick Coffee storyboard acceptance case:
1. classify EXECUTION
2. capability storyboard.generate
3. ingest attached character reference sheet
4. retrieve script/story context
5. resolve character/location info
6. plan exactly N distinct shots
7. submit exactly N image jobs
8. right pane switches to Storyboard work surface
9. N placeholders visible immediately
10. live progress updates
11. actual images appear as jobs complete
12. images saved to Library
13. grouped into ordered storyboard collection
14. no generic suggestion cards while running
15. result remains visible
16. user can regenerate any frame
17. user can open collection in Library
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ....character_identity.service import (
    list_profiles,
    resolve_approved_reference,
    resolve_character_by_name,
)
from ..shot_planner import plan_shots, shots_to_prompt_metadata

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    count: int = 4,
    scene_id: str = "",
    scene_context: dict[str, Any] | None = None,
    character_names: list[str] | None = None,
    attachment_asset_ids: list[str] | None = None,
    user_instructions: str = "",
    visual_style: str = "",
    project_style: str = "",
) -> dict[str, Any]:
    """Plan N shots and submit N real imagegen jobs.

    Returns a dict with job_ids, child_jobs, planned_steps, and surface_type.
    The dispatcher wraps this into an ExecutionPlan.
    """
    from ....storyboard_jobs import enqueue_imagegen_job

    # Resolve script scene context if not provided.
    ctx = scene_context or {}
    if not ctx and scene_id:
        ctx = _resolve_scene_context(db, project_id, scene_id)

    # Resolve characters by name (spec §13, §45).
    char_names = character_names or ctx.get("character_names", [])
    character_refs: list[dict[str, Any]] = []
    reference_asset_ids: list[str] = []

    for name in char_names:
        profile = resolve_character_by_name(db, project_id, name)
        if profile:
            character_refs.append({"id": profile.id, "name": profile.name})
            approved = resolve_approved_reference(db, profile.id, "hero_portrait")
            if approved:
                reference_asset_ids.append(approved)

    # User-supplied attachments as additional references (spec §12).
    if attachment_asset_ids:
        reference_asset_ids.extend(attachment_asset_ids)

    # Plan N distinct shots (spec §33).
    shots = plan_shots(
        scene_context=ctx,
        character_refs=character_refs,
        count=count,
        user_instructions=user_instructions,
        project_style=project_style or visual_style,
    )

    shot_metadata = shots_to_prompt_metadata(shots)

    # Submit N real imagegen jobs (spec §45 step 7).
    child_jobs: list[dict[str, Any]] = []
    job_ids: list[str] = []

    primary_reference = reference_asset_ids[0] if reference_asset_ids else None

    for i, shot in enumerate(shots):
        body: dict[str, Any] = {
            "prompt": shot.prompt_fragment,
            "negative_prompt": "",
            "width": 1280,
            "height": 720,
            "tag": f"codirector_storyboard_{execution_id[:8]}_frame{i + 1}",
            "modelFamilyPreference": "zimage",
            "purpose": "codirector_storyboard",
            "aspectRatio": "16:9",
            "batchCount": 1,
            "creativeContext": {
                "objective": "storyboard_frame",
                "executionId": execution_id,
                "frameIndex": i,
                "framing": shot.framing,
                "workflowKey": "zimage.txt2img",
            },
        }

        if primary_reference:
            body["referenceImage"] = primary_reference
            body["reference_image"] = primary_reference

        if visual_style:
            body["creativeContext"]["visualStyle"] = visual_style

        try:
            job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id or None)
            job_id = job.id
        except Exception as exc:
            logger.error("Failed to enqueue storyboard frame %d: %s", i + 1, exc)
            job_id = f"failed_frame_{i}"

        job_ids.append(job_id)
        child_jobs.append({
            "job_id": job_id,
            "label": f"Frame {i + 1} — {shot.framing.title()}",
            "status": "queued",
            "child_index": i,
            "metadata": shot_metadata[i] if i < len(shot_metadata) else {},
        })

    return {
        "job_ids": job_ids,
        "child_jobs": child_jobs,
        "planned_steps": [
            {
                "step_index": i,
                "label": f"Frame {i + 1} — {s.framing.title()}",
                "capability": "image.generate",
                "job_id": job_ids[i] if i < len(job_ids) else None,
                "status": "queued",
                "metadata": shot_metadata[i] if i < len(shot_metadata) else {},
            }
            for i, s in enumerate(shots)
        ],
        "surface_type": "storyboard_generation",
        "character_refs": [{"id": c["id"], "name": c["name"]} for c in character_refs],
        "reference_asset_ids": reference_asset_ids,
        "shot_count": len(shots),
    }


def _resolve_scene_context(db: Session, project_id: str, scene_id: str) -> dict[str, Any]:
    """Read scene context from the scriptwriter store."""
    try:
        from ....scriptwriter.store import list_documents, load_document

        docs = list_documents(db, project_id)
        if not docs:
            return {}
        doc = load_document(db, docs[0].id)
        if not doc or not doc.elements:
            return {}

        # Find the scene heading matching scene_id.
        scene_elements = [e for e in doc.elements if e.type == "scene_heading"]
        for idx, elem in enumerate(scene_elements):
            if elem.scene_id == scene_id or str(elem.scene_number) == scene_id:
                # Collect elements until the next scene heading.
                start = elem.order
                end = scene_elements[idx + 1].order if idx + 1 < len(scene_elements) else len(doc.elements)
                block = [e for e in doc.elements if start <= e.order < end]
                action_text = " ".join(e.text for e in block if e.type == "action")
                dialogue_text = " ".join(e.text for e in block if e.type == "dialogue")
                char_names_in_scene = [e.text for e in block if e.type == "character"]
                return {
                    "scene_number": elem.scene_number,
                    "location": elem.text or "the scene",
                    "action": action_text,
                    "dialogue": dialogue_text,
                    "character_names": list(set(char_names_in_scene)),
                    "emotional_beat": "",
                }
    except Exception as exc:
        logger.warning("Scene context resolution failed: %s", exc)
    return {}
