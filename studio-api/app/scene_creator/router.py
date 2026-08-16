"""REST router for Scene Creator — the final image-generation step before
Timeline handoff.

Mounted at ``/api/scene-creator``. Endpoints:

- ``POST /scene-creator/projects/{pid}/parse-shots``
    Parse free-form shot text into ``ShotRequest[]`` (no job submission).
- ``POST /scene-creator/projects/{pid}/batches``
    Create a ``SceneGenerationBatch``, persist it, then call the
    ``scene.generate`` capability handler to submit real imagegen jobs.
- ``GET /scene-creator/projects/{pid}/batches``
    List all batches for the project.
- ``GET /scene-creator/projects/{pid}/batches/{bid}``
    Get one batch.
- ``POST /scene-creator/projects/{pid}/batches/{bid}/regenerate-shot``
    Regenerate one shot of a batch (targeted regen, keep siblings).
- ``POST /scene-creator/projects/{pid}/batches/{bid}/send-to-timeline``
    Hand the batch's result assets off to the W46 Timeline via
    ``magi.timeline_handoff.export_to_timeline``.

Amendment #3 (SPATIAL AUTHORITY): Scene Creator generation never writes
back to spatial map placement state.
Amendment #5 (ENTITY TAGS): @/# tags resolve to stable IDs; the
human-readable tag is not the database identity.

Law #14 (project isolation): every query filters by ``project_id``.
Law #7 (no mock completion): every batch creation calls the real
``scene.generate`` handler, which calls ``enqueue_imagegen_job``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..codirector.entity_resolver import (
    parse_shot_requests,
    resolve_shot_request_entities,
)
from ..db import Project, get_db
from ..spatial_map.ers_contracts import (
    EnvironmentReferencePackage,
    SceneGenerationBatch,
    ShotRequest,
)
from ..spatial_map.ers_persistence import (
    list_scene_batches,
    load_ers_package,
    load_scene_batch,
    save_scene_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scene-creator", tags=["scene-creator-m413"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ParseShotsBody(BaseModel):
    raw_text: str = ""


class CreateBatchBody(BaseModel):
    ers_package_id: str = ""
    shot_requests_raw: str = ""
    output_count: int = 4
    visual_style: str = ""
    character_names: list[str] | None = None
    scene_id: str = ""


class RegenerateShotBody(BaseModel):
    shot_index: int
    new_prompt: str = ""
    visual_style: str = ""


class SendToTimelineBody(BaseModel):
    scene_id: str
    label: str | None = None
    batch_block_id: str | None = None


class CreateShotBody(BaseModel):
    sheet_id: str
    scene_id: str = ""
    shot_id: str = ""
    intent: str = ""
    character_ids: list[str] | None = None
    prop_entity_ids: list[str] | None = None
    camera: dict[str, Any] | None = None
    generator: dict[str, Any] | None = None


class ProductionHandoffBody(BaseModel):
    scene_id: str = ""
    sheet_id: str = ""
    spatial_map_id: str = ""


class GenerateShotBody(BaseModel):
    local_enabled: bool = True
    api_enabled: bool = False
    local_family: str = ""
    api_model: str = ""
    candidate_count: int = 4


class RetakeShotBody(BaseModel):
    correction: str
    local_enabled: bool = True
    api_enabled: bool = False
    local_family: str = ""
    api_model: str = ""


class ApproveCandidateBody(BaseModel):
    candidate_id: str


class SendShotToTimelineBody(BaseModel):
    batch_block_id: str | None = None


class CinematographerCommandBody(BaseModel):
    camera_id: str
    operation_id: str
    character_id: str = ""
    prop_id: str = ""
    shot_id: str = ""
    user_prompt_delta: str | None = None
    orientation3d: dict[str, Any] | None = None


class CinematographerCameraBody(BaseModel):
    camera_id: str
    shot_id: str = ""


class CinematographerDeltaBody(BaseModel):
    camera_id: str
    delta: str = ""


class CinematographerGenerateBody(BaseModel):
    camera_id: str
    shot_id: str
    local_enabled: bool = True
    api_enabled: bool = False
    local_family: str = ""
    api_model: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _batch_or_404(db: Session, project_id: str, batch_id: str) -> SceneGenerationBatch:
    batch = load_scene_batch(db, project_id, batch_id)
    if batch is None:
        raise HTTPException(404, "Scene batch not found")
    return batch


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/projects/{project_id}/parse-shots")
def api_parse_shots(
    project_id: str, body: ParseShotsBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    shots = parse_shot_requests(body.raw_text or "")
    # Resolve entity IDs so callers see real character/prop IDs upfront.
    resolved = [resolve_shot_request_entities(db, project_id, s) for s in shots]
    return {"shots": [s.model_dump() for s in resolved]}


@router.post("/projects/{project_id}/batches")
def api_create_batch(
    project_id: str, body: CreateBatchBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)

    # Parse + resolve the shot requests up front so the batch record carries
    # the structured ShotRequest list (with resolved IDs).
    parsed = parse_shot_requests(body.shot_requests_raw or "")
    resolved = [resolve_shot_request_entities(db, project_id, s) for s in parsed]

    batch = SceneGenerationBatch(
        id=str(uuid.uuid4()),
        project_id=project_id,
        ers_package_id=body.ers_package_id or "",
        shot_requests=resolved,
        output_count=max(1, min(body.output_count or 1, len(resolved) or 1)),
        result_asset_ids=[],
    )
    save_scene_batch(db, project_id, batch)

    # Call the scene.generate capability handler directly (no dispatcher
    # round-trip needed for V1). The handler submits real jobs.
    from ..codirector.capabilities.handlers.scene_generate import handle as scene_generate_handle

    execution_id = f"scene_creator_{batch.id}"
    result = scene_generate_handle(
        db,
        project_id,
        execution_id,
        ers_package_id=body.ers_package_id or "",
        shot_requests_raw=body.shot_requests_raw or "",
        output_count=body.output_count or 4,
        visual_style=body.visual_style or "",
        character_names=body.character_names,
    )

    # Persist the batch with the submitted job_ids for later polling/regen.
    batch.result_asset_ids = list(result.get("job_ids") or [])
    save_scene_batch(db, project_id, batch)

    return {
        "batch": batch.model_dump(),
        "child_jobs": result.get("child_jobs") or [],
        "job_ids": result.get("job_ids") or [],
        "surface_type": result.get("surface_type") or "scene_generation",
    }


@router.get("/projects/{project_id}/batches")
def api_list_batches(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"batches": [b.model_dump() for b in list_scene_batches(db, project_id)]}


@router.get("/projects/{project_id}/batches/{batch_id}")
def api_get_batch(
    project_id: str, batch_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    return {"batch": _batch_or_404(db, project_id, batch_id).model_dump()}


@router.post("/projects/{project_id}/batches/{batch_id}/regenerate-shot")
def api_regenerate_shot(
    project_id: str,
    batch_id: str,
    body: RegenerateShotBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Targeted regeneration: regenerate only one shot, keep siblings intact."""
    _require_project(db, project_id)
    batch = _batch_or_404(db, project_id, batch_id)

    if body.shot_index < 0 or body.shot_index >= len(batch.shot_requests):
        raise HTTPException(400, "shot_index out of range")

    shot = batch.shot_requests[body.shot_index]
    new_prompt = (body.new_prompt or "").strip() or shot.raw_text

    from ..storyboard_jobs import enqueue_imagegen_job

    # Compile a fresh shot body from the existing shot (preserves character/prop refs).
    ers_package = (
        load_ers_package(db, project_id, batch.ers_package_id)
        if batch.ers_package_id
        else None
    )
    # Update the additional_instructions with the new prompt, keep the rest.
    updated_shot = shot.model_copy(update={"additional_instructions": new_prompt})
    from ..codirector.entity_resolver import compile_shot_prompt

    shot_body = compile_shot_prompt(db, project_id, updated_shot, ers_package=ers_package)
    if body.visual_style and isinstance(shot_body.get("creativeContext"), dict):
        shot_body["creativeContext"].setdefault("style_layers", {})["user"] = body.visual_style
    shot_body["tag"] = f"codirector_scene_regen_{batch_id[:8]}_shot{body.shot_index + 1}"
    shot_body["creativeContext"]["executionId"] = f"regen_{batch_id}"
    shot_body["creativeContext"]["ersPackageId"] = batch.ers_package_id or ""

    try:
        job = enqueue_imagegen_job(db, project_id, shot_body)
        job_id = job.id
        status = "queued"
    except Exception as exc:
        logger.error("Scene shot regen failed: %s", exc)
        job_id = f"failed_regen_shot_{body.shot_index}"
        status = "failed"

    # Update the batch's result_asset_ids[shot_index] in place.
    result_ids = list(batch.result_asset_ids)
    while len(result_ids) < len(batch.shot_requests):
        result_ids.append("")
    if body.shot_index < len(result_ids):
        result_ids[body.shot_index] = job_id
    else:
        result_ids.append(job_id)
    batch.result_asset_ids = result_ids
    save_scene_batch(db, project_id, batch)

    return {
        "batch": batch.model_dump(),
        "job_id": job_id,
        "status": status,
        "shot_index": body.shot_index,
    }


@router.post("/projects/{project_id}/batches/{batch_id}/send-to-timeline")
def api_send_to_timeline(
    project_id: str,
    batch_id: str,
    body: SendToTimelineBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Hand the batch's result assets to the W46 Timeline as batch-owned clips."""
    _require_project(db, project_id)
    batch = _batch_or_404(db, project_id, batch_id)

    if not (body.scene_id or "").strip():
        raise HTTPException(400, "Send to Timeline needs a Scene. Create or select one first.")

    # Build clips from the batch's result asset ids (in shot order). Only
    # include slots that actually resolved to real asset ids — skip failed
    # regens (marked "failed_*" or empty).
    clips: list[dict[str, Any]] = []
    for index, asset_id in enumerate(batch.result_asset_ids or []):
        if not asset_id or str(asset_id).startswith("failed_"):
            continue
        shot = batch.shot_requests[index] if index < len(batch.shot_requests) else None
        clips.append(
            {
                "clipId": f"scene_shot_{batch_id}_{index}",
                "assetId": asset_id,
                "name": (
                    f"Shot {shot.index + 1} — {shot.framing or 'scene'}"
                    if shot
                    else f"Shot {index + 1}"
                ),
            }
        )

    if not clips:
        raise HTTPException(
            400,
            "Batch has no completed result assets to send to Timeline.",
        )

    # Manual + agent parity (amendment #54): the REST endpoint and the
    # Co-Director "send to timeline" command both route through the same
    # canonical helper, which delegates to the certified MAGI→Timeline
    # handoff (magi.timeline_handoff.export_to_timeline).
    from .timeline_handoff import send_scene_batch_to_timeline

    result = send_scene_batch_to_timeline(
        db,
        project_id,
        batch_id,
        scene_id=body.scene_id,
        label=body.label,
        batch_block_id=body.batch_block_id,
    )

    if not result.get("ok"):
        error = result.get("error") or "TIMELINE_HANDOFF_FAILED"
        status = 400 if error in {"SCENE_ID_REQUIRED", "NO_COMPLETED_SHOTS", "SCENE_BATCH_NOT_FOUND"} else 502
        raise HTTPException(
            status,
            {
                "error": error,
                "message": result.get("message") or "Timeline handoff failed.",
            },
        )

    return {
        "batch": batch.model_dump(),
        "timeline": result,
        "clips_sent": result.get("clips_sent") or len(clips),
    }


def _service_error(exc: Exception) -> HTTPException:
    from .ers_resolver import ErsResolveError
    from .production_handoff import SceneCreatorHandoffError
    from .service import SceneCreatorError

    if isinstance(exc, (SceneCreatorError, ErsResolveError, SceneCreatorHandoffError, ValueError)):
        return HTTPException(400, str(exc))
    logger.exception("Scene Creator error")
    return HTTPException(500, str(exc))


@router.get("/projects/{project_id}/workspace")
def api_workspace(
    project_id: str,
    sheet_id: str = "",
    scene_id: str = "",
    shot_id: str = "",
    spatial_profile_id: str = "",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import hydrate_workspace

    try:
        return hydrate_workspace(
            db,
            project_id,
            sheet_id=sheet_id,
            scene_id=scene_id,
            shot_id=shot_id,
            spatial_profile_id=spatial_profile_id,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/production-handoff")
def api_production_handoff(
    project_id: str, body: ProductionHandoffBody | None = None, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .production_handoff import synchronize_production_handoff

    payload = body or ProductionHandoffBody()
    try:
        return synchronize_production_handoff(
            db,
            project_id,
            scene_id=payload.scene_id,
            sheet_id=payload.sheet_id,
            spatial_map_id=payload.spatial_map_id,
        )
    except Exception as exc:
        raise _service_error(exc) from exc


@router.get("/projects/{project_id}/spatial-profiles")
def api_list_spatial_profiles(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    from .production_handoff import list_profiles, load_selection

    selection = load_selection(db, project_id)
    return {
        "profiles": [p.model_dump() for p in list_profiles(db, project_id)],
        "selectedProfileId": selection.selectedProfileId,
        "workspaceReset": selection.workspaceReset,
    }


@router.post("/projects/{project_id}/spatial-profiles/{handoff_id}/select")
def api_select_spatial_profile(
    project_id: str, handoff_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .production_handoff import select_profile

    try:
        return select_profile(db, project_id, handoff_id)
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/workspace/reset")
def api_reset_workspace(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_project(db, project_id)
    from .production_handoff import reset_workspace

    try:
        return reset_workspace(db, project_id)
    except Exception as exc:
        raise _service_error(exc) from exc


@router.post("/projects/{project_id}/shots")
def api_upsert_shot(
    project_id: str, body: CreateShotBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import create_or_update_shot

    try:
        shot = create_or_update_shot(
            db,
            project_id,
            shot_id=body.shot_id,
            scene_id=body.scene_id,
            sheet_id=body.sheet_id,
            intent=body.intent,
            character_ids=body.character_ids,
            prop_entity_ids=body.prop_entity_ids,
            camera=body.camera,
            generator=body.generator,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}


@router.get("/projects/{project_id}/shots/{shot_id}")
def api_get_shot(
    project_id: str, shot_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import get_shot

    try:
        shot = get_shot(db, project_id, shot_id)
    except Exception as etc:
        raise _service_error(etc) from etc
    return {"shot": shot.model_dump()}


@router.post("/projects/{project_id}/shots/{shot_id}/generate")
def api_generate_shot(
    project_id: str,
    shot_id: str,
    body: GenerateShotBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import generate_candidates

    try:
        shot = generate_candidates(
            db,
            project_id,
            shot_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
            candidate_count=body.candidate_count,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}


@router.post("/projects/{project_id}/shots/{shot_id}/retake")
def api_retake_shot(
    project_id: str,
    shot_id: str,
    body: RetakeShotBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import retake_shot

    try:
        shot = retake_shot(
            db,
            project_id,
            shot_id,
            correction=body.correction,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}


@router.post("/projects/{project_id}/shots/{shot_id}/approve")
def api_approve_candidate(
    project_id: str,
    shot_id: str,
    body: ApproveCandidateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import approve_candidate

    try:
        shot = approve_candidate(db, project_id, shot_id, body.candidate_id)
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}


@router.delete("/projects/{project_id}/shots/{shot_id}/candidates/{candidate_id}")
def api_delete_shot_candidate(
    project_id: str,
    shot_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import delete_shot_candidate

    try:
        shot = delete_shot_candidate(db, project_id, shot_id, candidate_id)
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"shot": shot.model_dump()}


@router.post("/projects/{project_id}/shots/{shot_id}/send-to-timeline")
def api_send_shot_to_timeline(
    project_id: str,
    shot_id: str,
    body: SendShotToTimelineBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .service import send_approved_to_timeline

    try:
        result = send_approved_to_timeline(
            db, project_id, shot_id, batch_block_id=body.batch_block_id
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    if not result.get("ok"):
        error = result.get("error") or "TIMELINE_HANDOFF_FAILED"
        status = 400 if error in {"SCENE_ID_REQUIRED", "NO_APPROVED_TAKE"} else 502
        raise HTTPException(
            status,
            {"error": error, "message": result.get("message") or "Timeline handoff failed."},
        )
    return {"timeline": result, "clips_sent": result.get("clips_sent") or 1}


@router.get("/projects/{project_id}/scenes/{scene_id}/cinematographer")
def api_get_cinematographer(
    project_id: str, scene_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import hydrate_cinematographer

    try:
        pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/command")
def api_cinematographer_command(
    project_id: str,
    scene_id: str,
    body: CinematographerCommandBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import apply_cinematographer_command

    try:
        pack = apply_cinematographer_command(
            db,
            project_id,
            scene_id=scene_id,
            camera_id=body.camera_id,
            operation_id=body.operation_id,
            character_id=body.character_id,
            prop_id=body.prop_id,
            shot_id=body.shot_id,
            user_prompt_delta=body.user_prompt_delta,
            orientation3d=body.orientation3d,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/undo")
def api_cinematographer_undo(
    project_id: str,
    scene_id: str,
    body: CinematographerCameraBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import undo_cinematographer

    try:
        pack = undo_cinematographer(
            db, project_id, scene_id=scene_id, camera_id=body.camera_id, shot_id=body.shot_id
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/reset")
def api_cinematographer_reset(
    project_id: str,
    scene_id: str,
    body: CinematographerCameraBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import reset_cinematographer

    try:
        pack = reset_cinematographer(
            db, project_id, scene_id=scene_id, camera_id=body.camera_id, shot_id=body.shot_id
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/lock")
def api_cinematographer_lock(
    project_id: str,
    scene_id: str,
    body: CinematographerCameraBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import lock_cinematographer

    try:
        pack = lock_cinematographer(
            db, project_id, scene_id=scene_id, camera_id=body.camera_id, shot_id=body.shot_id
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/prompt-delta")
def api_cinematographer_delta(
    project_id: str,
    scene_id: str,
    body: CinematographerDeltaBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import set_prompt_delta

    try:
        pack = set_prompt_delta(
            db, project_id, scene_id=scene_id, camera_id=body.camera_id, delta=body.delta
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/preview")
def api_cinematographer_preview(
    project_id: str,
    scene_id: str,
    body: CinematographerGenerateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import generate_camera_preview

    try:
        pack, shot = generate_camera_preview(
            db,
            project_id,
            scene_id=scene_id,
            camera_id=body.camera_id,
            shot_id=body.shot_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump(), "shot": shot.model_dump()}


@router.post("/projects/{project_id}/scenes/{scene_id}/cinematographer/final")
def api_cinematographer_final(
    project_id: str,
    scene_id: str,
    body: CinematographerGenerateBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_project(db, project_id)
    from .cinematographer_service import generate_camera_final

    try:
        pack, shot = generate_camera_final(
            db,
            project_id,
            scene_id=scene_id,
            camera_id=body.camera_id,
            shot_id=body.shot_id,
            local_enabled=body.local_enabled,
            api_enabled=body.api_enabled,
            local_family=body.local_family,
            api_model=body.api_model,
        )
    except Exception as exc:
        raise _service_error(exc) from exc
    return {"cinematographer": pack.model_dump(), "shot": shot.model_dump()}
