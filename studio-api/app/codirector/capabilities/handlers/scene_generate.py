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

CDX-085 (Phase 7) — ENGINE OWNERSHIP (canonical decision, no merge):
This handler is the SINGLE shared scene-generation engine for BOTH entry
points: (1) the canonical Scene Creator shot flow
(``POST /scene-creator/projects/{pid}/shots/{shot_id}/generate`` via
scene_creator/service.py) and the Co-Director execution pack path
(scene.generate capability -> codirector/execution/dispatcher.py
``dispatch``/``approve_and_execute``), and (2) the retained-but-gated batch
REST surface (``POST /scene-creator/projects/{pid}/batches``, which calls
this same ``handle`` directly). Every shot compiles through
``entity_resolver.compile_shot_prompt`` and submits one real imagegen job
via ``enqueue_imagegen_job`` (purpose ``scene_shot`` / surface
``scene_generation``). The provenance contract (purpose, surface_type,
modelFamilyPreference, workflowKey) is therefore identical regardless of
which surface initiated the run; parity is locked by
tests/test_engine_ownership.py. NO MERGE of the two surfaces — that is
architectural and out of scope.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _resolve_ers(db: Session, project_id: str, ers_package_id: str) -> Any:
    """Resolve the ERS reference to a real package (CDX-034).

    Accepts a persisted package UUID (existing callers) or the creator-facing
    sheetId. When the id is not found as a package, falls back to
    ``ers_resolver.resolve_ers_for_sheet``; fails loudly (raises
    ``ErsResolveError``) when neither identity resolves — never silently
    compile shots with zero ERS grounding.
    """
    from ....scene_creator.ers_resolver import ErsResolveError, resolve_ers_for_sheet
    from ....spatial_map.ers_persistence import load_ers_package

    ref = (ers_package_id or "").strip()
    if not ref:
        raise ErsResolveError("Select an Environment Reference Sheet first.")

    package = load_ers_package(db, project_id, ref)
    if package is not None:
        return package

    package, _runtime = resolve_ers_for_sheet(db, project_id, ref)
    return package


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
    scene_id: str = "",
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
        parse_shot_requests,
        resolve_shot_request_entities,
    )

    # 1. Parse the free-form shot text into structured ShotRequests.
    parsed_shots = parse_shot_requests(shot_requests_raw)

    # Output count law: never invent extra shots beyond the explicit requests.
    # The dispatcher may pass output_count=None (kwarg present, no value), so
    # coerce defensively instead of crashing on max(1, None) (orchestrator
    # milestone, mission Part 34 - partial failure safety).
    try:
        output_count = int(output_count)
    except (TypeError, ValueError):
        output_count = 4
    effective_count = min(len(parsed_shots), max(1, output_count))
    if not parsed_shots:
        # ZERO-JOBS LAW (scene generation 0/0 loop): no shots parsed is a
        # TERMINAL failure, never a running plan. The frontend must see a
        # failed state with zero jobs, not an indefinite spinner.
        error = "No valid scene-generation jobs were created. Provide explicit shot requests (comma- or newline-separated shot text)."
        try:
            from ....production_events import ACTOR_CODIRECTOR, record_production_event

            record_production_event(
                db,
                project_id=project_id,
                scene_id=scene_id or None,
                event_type="scene_creator.generation_failed",
                actor=ACTOR_CODIRECTOR,
                actor_detail="capability:scene.generate",
                subject_kind="execution",
                subject_id=execution_id,
                summary="Scene Creator generation could not start (no shots parsed)",
                payload={"executionId": execution_id, "accepted": 0, "rejected": 0, "error": error},
            )
        except Exception:  # noqa: BLE001 - event recording never breaks the operation
            pass
        return {
            "job_ids": [],
            "child_jobs": [],
            "surface_type": "scene_generation",
            "ers_package_id": ers_package_id or "",
            "shot_count": 0,
            "purpose": "scene_generation",
            "status": "failed",
            "accepted": 0,
            "rejected": 0,
            "error": error,
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
    # CDX-034: resolve the ERS reference to a real package (package UUID or
    # creator-facing sheetId); unresolvable references fail loudly.
    ers_package = _resolve_ers(db, project_id, ers_package_id)
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
        body["creativeContext"]["ersPackageId"] = ers_package.id if ers_package else ""

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

    accepted = sum(1 for c in child_jobs if c.get("status") == "queued")
    rejected = sum(1 for c in child_jobs if c.get("status") == "failed")
    try:
        from ....production_events import ACTOR_CODIRECTOR, record_production_event

        record_production_event(
            db,
            project_id=project_id,
            scene_id=scene_id or None,
            event_type="scene_creator.generation_started",
            actor=ACTOR_CODIRECTOR,
            actor_detail="capability:scene.generate",
            subject_kind="execution",
            subject_id=execution_id,
            summary=f"Scene Creator generation started ({accepted} accepted / {rejected} rejected)",
            payload={"executionId": execution_id, "jobIds": job_ids, "shotCount": len(shots), "accepted": accepted, "rejected": rejected},

        )
    except Exception:  # noqa: BLE001 - event recording never breaks the operation
        pass

    return {
        "job_ids": job_ids,
        "child_jobs": child_jobs,
        "surface_type": "scene_generation",
        "ers_package_id": ers_package.id if ers_package else (ers_package_id or ""),
        "shot_count": len(shots),
        "purpose": "scene_generation",
        "status": "queued" if accepted > 0 else "failed",
        "accepted": accepted,
        "rejected": rejected,
        "error": None if accepted > 0 else "All scene-generation jobs failed to enqueue.",
    }
