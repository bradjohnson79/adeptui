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
from ..shot_planner import (
    plan_four_panel_storyboard_sheets,
    plan_shots,
    shots_to_prompt_metadata,
)

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
    plan_only: bool = False,
    plan_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan N shots and submit N real imagegen jobs.

    When ``plan_only=True``, plans shots and returns plan_data but does NOT
    enqueue any GPU jobs. The caller (dispatcher) stores the plan_data in the
    ExecutionPlan for later approval.

    When ``plan_data`` is provided (from an approved plan), uses the stored
    shot descriptions/prompts to enqueue jobs without re-planning.

    When neither flag is active, behaves as before: plan + enqueue.

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
            approved = resolve_approved_reference(db, profile.id, "hero_identity")
            if approved:
                reference_asset_ids.append(approved)

    # User-supplied attachments as additional references (spec §12).
    if attachment_asset_ids:
        reference_asset_ids.extend(attachment_asset_ids)

    # Detect four-panel storyboard mode from user instructions / project style.
    combined_text = (user_instructions + " " + (project_style or visual_style or "")).lower()
    user_wants_four_panel = any(
        phrase in combined_text
        for phrase in ["four-panel", "4 panel", "four panel", "storyboard sheet", "2x2", "\u00d72"]
    )

    if user_wants_four_panel and not plan_data:
        sheets = plan_four_panel_storyboard_sheets(
            scene_context=ctx,
            character_refs=character_refs,
            count=count,
            user_instructions=user_instructions,
            project_style=project_style or visual_style,
        )

        if plan_only:
            sheet_outputs = _build_four_panel_sheet_outputs(sheets)
            plan_data_result = {
                "output_count": len(sheets),
                "output_mode": "four_panel_storyboard",
                "outputs": sheet_outputs,
                "references": {
                    "character_refs": [
                        {"id": c["id"], "name": c["name"]} for c in character_refs
                    ],
                    "reference_asset_ids": reference_asset_ids,
                },
                "style_context": project_style or visual_style or "",
                "scene_context": {
                    "location": ctx.get("location", ""),
                    "action": ctx.get("action", ""),
                    "dialogue": ctx.get("dialogue", ""),
                },
            }
            return {
                "child_jobs": [],
                "planned_steps": [],
                "surface_type": "storyboard_generation",
                "plan_data": plan_data_result,
                "shot_count": len(sheets),
            }

        primary_reference = reference_asset_ids[0] if reference_asset_ids else None
        child_jobs: list[dict[str, Any]] = []
        job_ids: list[str] = []

        for i, sheet in enumerate(sheets):
            body: dict[str, Any] = {
                "prompt": sheet["compiled_prompt"],
                "negative_prompt": "",
                "width": 1280,
                "height": 720,
                "tag": f"codirector_storyboard_{execution_id[:8]}_sheet{i + 1}",
                "modelFamilyPreference": "zimage",
                "purpose": "codirector_storyboard",
                "aspectRatio": "16:9",
                "batchCount": 1,
                "creativeContext": {
                    "objective": "storyboard_sheet",
                    "executionId": execution_id,
                    "outputIndex": i,
                    "frameCount": len(sheet["panels"]),
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
                logger.error("Failed to enqueue storyboard sheet %d: %s", i + 1, exc)
                job_id = f"failed_sheet_{i}"
            job_ids.append(job_id)
            child_jobs.append({
                "job_id": job_id,
                "label": f"Output {i + 1} \u2014 4-Panel Storyboard",
                "status": "queued",
                "child_index": i,
                "metadata": {
                    "output_index": sheet["output_index"],
                    "output_type": "four_panel_storyboard",
                    "framing_slots": sheet["framing_slots"],
                    "compiled_prompt": sheet["compiled_prompt"][:300],
                },
            })

        return {
            "job_ids": job_ids,
            "child_jobs": child_jobs,
            "planned_steps": [
                {
                    "step_index": i,
                    "label": f"Output {i + 1} \u2014 4-Panel Storyboard",
                    "capability": "image.generate",
                    "job_id": job_ids[i] if i < len(job_ids) else None,
                    "status": "queued",
                    "metadata": {
                        "output_index": s["output_index"],
                        "output_type": "four_panel_storyboard",
                        "framing_slots": s["framing_slots"],
                        "compiled_prompt": s["compiled_prompt"][:300],
                    },
                }
                for i, s in enumerate(sheets)
            ],
            "surface_type": "storyboard_generation",
            "character_refs": [
                {"id": c["id"], "name": c["name"]} for c in character_refs
            ],
            "reference_asset_ids": reference_asset_ids,
            "shot_count": len(sheets),
        }

    # Plan N distinct shots (spec §33) — single_frame mode.
    shots = plan_shots(
        scene_context=ctx,
        character_refs=character_refs,
        count=count,
        user_instructions=user_instructions,
        project_style=project_style or visual_style,
    )

    shot_metadata = shots_to_prompt_metadata(shots)

    # --- PLAN-ONLY MODE ---
    if plan_only:
        plan_data_result = _build_plan_data(
            shots=shots,
            character_refs=character_refs,
            reference_asset_ids=reference_asset_ids,
            ctx=ctx,
            project_style=project_style,
            visual_style=visual_style,
        )
        return {
            "child_jobs": [],
            "planned_steps": [],
            "surface_type": "storyboard_generation",
            "plan_data": plan_data_result,
            "shot_count": len(shots),
        }

    # --- EXECUTE FROM APPROVED PLAN DATA ---
    # Use the stored shot plan outputs to drive job creation.
    if plan_data:
        outputs = plan_data.get("outputs", [])
        refs = plan_data.get("references", {})
        style_context = plan_data.get("style_context", visual_style or project_style)
        stored_char_refs = refs.get("character_refs", [])
        stored_ref_asset_ids = refs.get("reference_asset_ids", [])
        primary_reference = (
            stored_ref_asset_ids[0]
            if stored_ref_asset_ids
            else (reference_asset_ids[0] if reference_asset_ids else None)
        )
        child_jobs: list[dict[str, Any]] = []
        job_ids: list[str] = []
        for i, output in enumerate(outputs):
            output_type = output.get("output_type", "single_frame")

            if output_type == "four_panel_storyboard":
                prompt = output.get("compiled_prompt", "")
                label = output.get("label", f"Output {i + 1} \u2014 4-Panel Storyboard")
                body: dict[str, Any] = {
                    "prompt": prompt,
                    "negative_prompt": "",
                    "width": 1280,
                    "height": 720,
                    "tag": f"codirector_storyboard_{execution_id[:8]}_sheet{i + 1}",
                    "modelFamilyPreference": "zimage",
                    "purpose": "codirector_storyboard",
                    "aspectRatio": "16:9",
                    "batchCount": 1,
                    "creativeContext": {
                        "objective": "storyboard_sheet",
                        "executionId": execution_id,
                        "outputIndex": i,
                        "frameCount": len(output.get("panels", [])),
                        "framing_slots": output.get("framing_slots", []),
                        "workflowKey": "zimage.txt2img",
                    },
                }
            else:
                prompt = output.get("prompt_summary") or output.get("description", "")
                framing = output.get("framing", "medium")
                label = f"Frame {i + 1} \u2014 {framing.title()}"
                body: dict[str, Any] = {
                    "prompt": prompt,
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
                        "framing": framing,
                        "workflowKey": "zimage.txt2img",
                    },
                }

            if primary_reference:
                body["referenceImage"] = primary_reference
                body["reference_image"] = primary_reference
            if style_context:
                body["creativeContext"]["visualStyle"] = style_context
            try:
                job = enqueue_imagegen_job(db, project_id, body, scene_id=scene_id or None)
                job_id = job.id
            except Exception as exc:
                logger.error("Failed to enqueue storyboard output %d from plan: %s", i + 1, exc)
                job_id = f"failed_output_{i}"
            job_ids.append(job_id)
            child_jobs.append({
                "job_id": job_id,
                "label": label,
                "status": "queued",
                "child_index": i,
                "metadata": output,
            })
        return {
            "job_ids": job_ids,
            "child_jobs": child_jobs,
            "planned_steps": [
                {
                    "step_index": i,
                    "label": child_jobs[i]["label"] if i < len(child_jobs) else f"Output {i + 1}",
                    "capability": "image.generate",
                    "job_id": job_ids[i] if i < len(job_ids) else None,
                    "status": "queued",
                    "metadata": output,
                }
                for i, output in enumerate(outputs)
            ],
            "surface_type": "storyboard_generation",
            "character_refs": stored_char_refs,
            "reference_asset_ids": stored_ref_asset_ids,
            "shot_count": len(outputs),
        }

    # --- NORMAL MODE (backward compatible) ---
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


def _build_plan_data(
    shots: list[Any],
    character_refs: list[dict[str, Any]],
    reference_asset_ids: list[str],
    ctx: dict[str, Any],
    project_style: str = "",
    visual_style: str = "",
) -> dict[str, Any]:
    """Build the plan_data dict from planned shots for approval preview.

    Used for ``single_frame`` output mode. For ``four_panel_storyboard``
    mode, the caller branches to ``_build_four_panel_sheet_outputs``
    before reaching this function.
    """
    return {
        "output_count": len(shots),
        "output_mode": "single_frame",
        "outputs": [
            {
                "index": i,
                "output_type": "single_frame",
                "framing": shot.framing,
                "description": shot.prompt_fragment[:200],
                "prompt_summary": shot.prompt_fragment[:300],
                "character_names": shot.character_names,
                "location": shot.location,
                "action_beat": shot.action_beat,
                "emotional_beat": shot.emotional_beat,
            }
            for i, shot in enumerate(shots)
        ],
        "references": {
            "character_refs": [{"id": c["id"], "name": c["name"]} for c in character_refs],
            "reference_asset_ids": reference_asset_ids,
        },
        "style_context": project_style or visual_style or "",
        "scene_context": {
            "location": ctx.get("location", ""),
            "action": ctx.get("action", ""),
            "dialogue": ctx.get("dialogue", ""),
        },
    }


def _build_four_panel_sheet_outputs(
    sheets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert four-panel storyboard sheets to plan output dicts.

    Each output corresponds to one GPU job (one image containing 4 panels).
    """
    return [
        {
            "index": sheet["output_index"],
            "output_type": "four_panel_storyboard",
            "framing": "storyboard_sheet",
            "compiled_prompt": sheet["compiled_prompt"],
            "framing_slots": sheet["framing_slots"],
            "panels": [
                {
                    "framing": p.framing,
                    "shot_size": p.shot_size,
                    "composition": p.composition,
                    "prompt_fragment": p.prompt_fragment,
                    "character_names": p.character_names,
                    "location": p.location,
                    "action_beat": p.action_beat,
                    "emotional_beat": p.emotional_beat,
                }
                for p in sheet["panels"]
            ],
            "description": sheet["compiled_prompt"][:200],
            "prompt_summary": sheet["compiled_prompt"][:300],
            "character_names": [
                n for p in sheet["panels"] for n in p.character_names
            ] if sheet["panels"] else [],
            "location": sheet["panels"][0].location if sheet["panels"] else "",
            "action_beat": sheet["panels"][0].action_beat if sheet["panels"] else "",
            "emotional_beat": sheet["panels"][0].emotional_beat if sheet["panels"] else "",
            "label": f"Output {sheet['output_index'] + 1} \u2014 4-Panel Storyboard",
        }
        for sheet in sheets
    ]


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
