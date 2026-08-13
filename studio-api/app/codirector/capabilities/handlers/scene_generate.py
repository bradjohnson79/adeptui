"""Capability handler: scene.generate

Generates N scene images from shot requests + ERS package + character and
prop references. This is the final image-generation step before Timeline
handoff.

Amendment #1 (ATLAS ORDER): Scene Creator sits AFTER ERS and BEFORE
Timeline. Workflow: Character Creator → Atlas Shot / Master Environment →
Spatial Map → ERS → Scene Creator → Timeline.

Amendment #3 (SPATIAL AUTHORITY): generated scene images are visual
interpretations and may NEVER silently update grid coordinates, entity
assignments, mini-prompts, orientation, or placement state.

Amendment #5 (ENTITY TAGS): @ references support real character names;
# props use normalized tags. Tags resolve to stable IDs; the
human-readable tag is not the database identity.

Output count law: generate exactly the number of explicit shot requests.
If 4 requests and ``output_count=8``, generate 4 (do NOT silently invent
4 more). If ``output_count > len(shots)``, use ``len(shots)``.

Law #18: scene shots go through the canonical image gen pipeline
(``enqueue_imagegen_job``) — no silent provider/model substitution.
Law #7: this handler submits REAL jobs (no mock completion).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def handle(
    db: Session,
    project_id: str,
    execution_id: str,
    *,
    ers_package_id: str = "",
    shot_requests_raw: str = "",
    output_count: int = 4,
    visual_style: str = "",
    character_names: list[str] | None = None,
) -> dict[str, Any]:
    """Generate N scene images from parsed shot requests.

    Uses ``entity_resolver.parse_shot_requests`` + ``compile_shot_prompt``
    to compile each shot, then submits one real imagegen job per shot
    (purpose ``scene_shot``).

    Output count law: the number of generated jobs is
    ``min(len(shots), output_count)`` — we never silently invent extra
    shots.
    """
    from ....storyboard_jobs import enqueue_imagegen_job
    from ...entity_resolver import (
        compile_shot_prompt,
        get_ers_package,
        parse_shot_requests,
        resolve_shot_request_entities,
    )

    # 1. Parse the free-form shot text into structured ShotRequests.
    parsed_shots = parse_shot_requests(shot_requests_raw)

    # Output count law: never invent extra shots beyond the explicit requests.
    effective_count = min(len(parsed_shots), max(1, output_count))
    if not parsed_shots:
        # No explicit shots — return an empty plan. Do NOT silently fabricate.
        return {
            "job_ids": [],
            "child_jobs": [],
            "surface_type": "scene_generation",
            "ers_package_id": ers_package_id or "",
            "shot_count": 0,
            "purpose": "scene_generation",
            "note": "No shot requests provided. Pass explicit comma- or newline-separated shot text.",
        }

    # If character_names were explicitly supplied (creator-typed), add them as
    # a shared context for each shot (entity_resolver will resolve them).
    if character_names:
        # Prepend the @-tagged names to the raw text on a best-effort basis
        # so each shot inherits them. parse_shot_requests already ran, so we
        # merge names into each shot's ``characters`` list (still names here;
        # resolved to IDs below).
        names_to_add = [n for n in character_names if n]
        if names_to_add:
            for shot in parsed_shots:
                for name in names_to_add:
                    if name not in shot.characters:
                        shot.characters.append(name)

    shots = parsed_shots[:effective_count]

    # 2. Resolve entity IDs per shot + compile the imagegen body.
    ers_package = get_ers_package(db, project_id, ers_package_id) if ers_package_id else None

    child_jobs: list[dict[str, Any]] = []
    job_ids: list[str] = []

    for shot in shots:
        resolved = resolve_shot_request_entities(db, project_id, shot)
        body = compile_shot_prompt(
            db,
            project_id,
            resolved,
            ers_package=ers_package,
        )

        # Layer the caller's visual_style into the style_layers.user slot.
        if visual_style and isinstance(body.get("creativeContext"), dict):
            style_layers = body["creativeContext"].setdefault("style_layers", {})
            style_layers["user"] = visual_style
            # Re-resolve the model family when the user style is anime/animation
            # AND no reference is attached (Reference Law: reference-conditioned
            # shots keep the reference-capable zimage engine). This lets the
            # creator's explicit visual_style drive style→engine routing.
            if not body.get("referenceImage") and not body.get("reference_image"):
                try:
                    from ....image_product.recommend import recommend_image_family

                    rec = recommend_image_family(
                        prompt=str(body.get("prompt") or ""),
                        purpose="scene_shot",
                        operation="image.generate",
                        style=visual_style or None,
                    )
                    fam = rec.get("executionFamily") or "zimage"
                    body["modelFamilyPreference"] = fam
                    body["creativeContext"]["workflowKey"] = f"{fam}.txt2img"
                except Exception:
                    pass
        body["tag"] = f"codirector_scene_{execution_id[:8]}_shot{resolved.index + 1}"
        body["creativeContext"]["executionId"] = execution_id
        body["creativeContext"]["ersPackageId"] = ers_package_id or ""

        try:
            job = enqueue_imagegen_job(db, project_id, body)
            job_id = job.id
            status = "queued"
        except Exception as exc:
            logger.error("Scene shot enqueue failed for shot %d: %s", resolved.index, exc)
            job_id = f"failed_scene_shot_{resolved.index}"
            status = "failed"

        job_ids.append(job_id)
        child_jobs.append(
            {
                "job_id": job_id,
                "label": f"Shot {resolved.index + 1}",
                "status": status,
                "child_index": resolved.index,
                "metadata": {
                    "shot_request": resolved.raw_text,
                    "characters": resolved.characters,
                    "props": resolved.prop_entities,
                    "framing": resolved.framing,
                    "angle": resolved.angle,
                    "orientation": resolved.orientation,
                },
            }
        )

    return {
        "job_ids": job_ids,
        "child_jobs": child_jobs,
        "surface_type": "scene_generation",
        "ers_package_id": ers_package_id or "",
        "shot_count": len(shots),
        "purpose": "scene_generation",
    }
