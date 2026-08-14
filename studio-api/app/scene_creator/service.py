"""Scene Creator shared backend — SceneShot, candidates, approval, Re-Take, Timeline.

Express and Standard share this service. Do not add a second Scene Creator backend.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from ..db import Asset, Job, Scene
from ..spatial_map.ers_contracts import (
    GeneratorSourceSelection,
    SceneCreatorCamera,
    SceneShot,
    SceneShotCandidate,
    SceneShotTakeMemory,
    ShotRequest,
)
from ..spatial_map.ers_persistence import (
    list_scene_shots,
    load_prop_entity_by_id,
    load_scene_shot,
    save_scene_shot,
)
from .ers_resolver import ErsResolveError, resolve_ers_for_sheet
from .generation import (
    build_candidate_plans,
    hosted_image_generation_available,
    list_local_generator_families,
)

logger = logging.getLogger(__name__)

CINEMATIC_SIZE_LABELS = {
    "wide": "Wide",
    "medium_wide": "Medium Wide",
    "medium": "Medium",
    "close_up": "Close-Up",
    "extreme_close_up": "Extreme Close-Up",
}
CINEMATIC_MOTION_LABELS = {
    "static": "Static",
    "pan": "Pan",
    "tilt": "Tilt",
    "dolly": "Dolly",
    "handheld": "Handheld",
}
CINEMATIC_FRAMING_LABELS = {
    "single": "Single",
    "two_shot": "Two Shot",
    "group": "Group",
    "over_shoulder": "Over Shoulder",
    "pov": "Point of View",
}


class SceneCreatorError(ValueError):
    pass


def ensure_scene_id(db: Session, project_id: str, scene_id: str = "") -> Scene:
    """Bind to an authoritative Studio Scene row. Never return an empty id."""
    from ..services.scene_service import SceneService

    wanted = (scene_id or "").strip()
    if wanted:
        scene = db.get(Scene, wanted)
        if scene is None or scene.project_id != project_id:
            raise SceneCreatorError("Scene not found in this project.")
        return scene
    existing = SceneService.list_for_project(db, project_id)
    if existing:
        return existing[0]
    return SceneService.create(db, project_id, {"name": "Scene 1"})


def hydrate_workspace(
    db: Session,
    project_id: str,
    *,
    sheet_id: str = "",
    scene_id: str = "",
    shot_id: str = "",
) -> dict[str, Any]:
    from ..environment_reference_sheet.store import list_sheets, load_sheet
    from ..spatial_map.service import list_documents

    sheets = list_sheets(project_id)
    sheet_summaries = [
        {
            "sheetId": s.sheetId,
            "name": s.name,
            "status": s.status,
            "sceneId": s.sceneId,
            "approvedDirections": [
                v.direction for v in (s.directionalViews or []) if v.approvedAssetId
            ],
        }
        for s in sheets
    ]
    selected_sheet_id = (sheet_id or "").strip()
    if not selected_sheet_id and sheets:
        selected_sheet_id = sheets[0].sheetId

    sheet = load_sheet(project_id, selected_sheet_id) if selected_sheet_id else None
    preferred_scene = (scene_id or "").strip() or (sheet.sceneId if sheet and sheet.sceneId else "")

    resolved = None
    cameras: list[dict[str, Any]] = []
    characters: list[dict[str, Any]] = []
    props: list[dict[str, Any]] = []
    if selected_sheet_id:
        try:
            package, runtime = resolve_ers_for_sheet(db, project_id, selected_sheet_id)
            cameras = list((package.metadata or {}).get("cameras") or [])
            resolved = {
                "sheet_id": selected_sheet_id,
                "package_id": package.id,
                "runtime": runtime,
                "directional_assets": package.directional_assets,
                "atlas_asset_id": package.atlas_asset_id,
                "ers_composite_asset_id": package.ers_composite_asset_id,
                "style_context": package.style_context,
            }
            for placement in package.placements or []:
                if not isinstance(placement, dict):
                    continue
                if placement.get("characterId"):
                    characters.append(
                        {
                            "character_id": placement.get("characterId"),
                            "name": placement.get("label") or placement.get("characterId"),
                            "position_label": _position_summary(placement),
                            "slot_index": placement.get("slotIndex"),
                        }
                    )
                else:
                    leftover_prop_id = str(placement.get("propId") or placement.get("prop_id") or "").strip()
                    if not leftover_prop_id:
                        # Leftover character-as-prop rows (e.g. {prop_id:null, tag:"Korri"})
                        # are not PropEntities. Skip; Spatial Map union adds real ids.
                        continue
                    props.append(
                        _hydrate_prop(
                            db,
                            project_id,
                            prop_id=leftover_prop_id,
                            asset_id=str(placement.get("assetId") or placement.get("asset_id") or ""),
                            label=str(placement.get("label") or placement.get("tag") or "Prop"),
                            position_label=_position_summary(placement),
                            placement=placement,
                        )
                    )
        except ErsResolveError as exc:
            resolved = {"error": str(exc)}

    if not characters:
        try:
            maps = list_documents(db, project_id)
        except Exception:
            maps = []
        if maps:
            latest = maps[0]
            for c in latest.characters or []:
                    characters.append(
                        {
                            "character_id": c.characterId,
                            "name": c.label or c.characterId,
                            "position_label": _position_summary(c.model_dump()),
                            "slot_index": getattr(c, "slotIndex", None),
                        }
                    )

    # Always union Spatial Map PropEntity rows so attached project props appear
    # even when leftover ERS placements already filled workspace.props.
    _union_spatial_map_project_props(db, project_id, props)

    if not cameras:
        try:
            from ..spatial_map.service import list_documents as _list_maps_for_cameras
            maps_for_cameras = _list_maps_for_cameras(db, project_id)
        except Exception:
            maps_for_cameras = []
        if maps_for_cameras:
            latest_map = maps_for_cameras[0]
            for index, cam in enumerate(latest_map.cameras or []):
                slot = cam.cameraSlot if cam.cameraSlot is not None and cam.cameraSlot >= 0 else index
                cameras.append(
                    {
                        "id": cam.id,
                        "label": cam.label or f"C{slot + 1}",
                        "cameraSlot": int(slot),
                        "orientation": cam.orientation or "",
                        "fovPreset": cam.fovPreset or "",
                        "yawDegrees": cam.yawDegrees,
                        "lensMm": cam.lensMm,
                        "hero": bool(cam.hero),
                        "visible": bool(getattr(cam, "visible", True)),
                        "gridColumn": getattr(cam, "gridColumn", -1),
                        "gridRow": getattr(cam, "gridRow", -1),
                        "normalizedX": getattr(cam, "normalizedX", None),
                        "normalizedY": getattr(cam, "normalizedY", None),
                        "heightMeters": getattr(cam, "heightMeters", None),
                        "pitchDegrees": getattr(cam, "pitchDegrees", None),
                        "targetCharacterIds": list(getattr(cam, "targetCharacterIds", None) or []),
                    }
                )

    scene = ensure_scene_id(db, project_id, preferred_scene)
    from ..services.scene_service import SceneService

    scenes = [
        {"id": s.id, "name": s.name, "index": s.index}
        for s in SceneService.list_for_project(db, project_id)
    ]
    shots = list_scene_shots(db, project_id, scene_id=scene.id)
    for shot in shots:
        _sync_candidate_jobs(db, project_id, shot)
    selected_shot = None
    wanted_shot = (shot_id or "").strip()
    if wanted_shot:
        selected_shot = next((s for s in shots if s.id == wanted_shot), None)
    if selected_shot is None and shots:
        selected_shot = shots[-1]

    has_reference = bool(
        resolved
        and isinstance(resolved, dict)
        and any((resolved.get("directional_assets") or {}).values())
    )

    cinematographer = None
    api_models: list[dict[str, Any]] = []
    try:
        from ..hosted_providers.discovery import dock_api_models

        payload = dock_api_models("image")
        api_models = [m for m in (payload.get("models") or []) if isinstance(m, dict)]
    except Exception:
        api_models = []
    try:
        from .cinematographer_service import hydrate_cinematographer

        pack = hydrate_cinematographer(db, project_id, scene_id=scene.id)
        cinematographer = pack.model_dump()
    except Exception:
        logger.exception("Cinematographer hydrate failed")

    return {
        "sheets": sheet_summaries,
        "selected_sheet_id": selected_sheet_id,
        "sheet_name": sheet.name if sheet else "",
        "resolved_ers": resolved,
        "scenes": scenes,
        "selected_scene_id": scene.id,
        "shots": [s.model_dump() for s in shots],
        "selected_shot": selected_shot.model_dump() if selected_shot else None,
        "cameras": cameras,
        "characters": characters,
        "props": props,
        "api_generation_available": hosted_image_generation_available() or bool(api_models),
        "api_models": api_models,
        "local_families": list_local_generator_families(has_reference=has_reference),
        "has_reference": has_reference,
        "cinematographer": cinematographer,
        "preview_capabilities": _workspace_preview_capabilities(bool(api_models)),
    }


def create_or_update_shot(
    db: Session,
    project_id: str,
    *,
    shot_id: str = "",
    scene_id: str = "",
    sheet_id: str = "",
    intent: str = "",
    character_ids: list[str] | None = None,
    prop_entity_ids: list[str] | None = None,
    camera: dict[str, Any] | None = None,
    generator: dict[str, Any] | None = None,
) -> SceneShot:
    scene = ensure_scene_id(db, project_id, scene_id)
    sheet_id = (sheet_id or "").strip()
    if not sheet_id:
        raise SceneCreatorError("Select an Environment Reference Sheet first.")
    package, runtime = resolve_ers_for_sheet(db, project_id, sheet_id)

    existing = load_scene_shot(db, project_id, shot_id) if shot_id else None
    shot = existing or SceneShot(
        project_id=project_id,
        scene_id=scene.id,
        sheet_id=sheet_id,
    )
    if shot.project_id != project_id:
        raise SceneCreatorError("Shot not found in this project.")
    shot.scene_id = scene.id
    shot.sheet_id = sheet_id
    shot.ers_package_id = package.id
    shot.ers_runtime = runtime
    if intent:
        shot.intent = intent.strip()
        shot.prompt = intent.strip()
    if character_ids is not None:
        shot.character_ids = list(character_ids)
    if prop_entity_ids is not None:
        shot.prop_entity_ids = list(prop_entity_ids)
    if not shot.prop_entity_ids:
        shot.prop_entity_ids = _placed_project_prop_ids(db, project_id, sheet_id)
    if camera:
        shot.camera = SceneCreatorCamera.model_validate(camera)
    if generator:
        shot.generator = GeneratorSourceSelection.model_validate(generator)
    save_scene_shot(db, project_id, shot)
    return shot


def _enqueue_shot_candidates(
    db: Session,
    project_id: str,
    shot: SceneShot,
    *,
    local_enabled: bool,
    api_enabled: bool,
    local_family: str,
    api_model: str,
    candidate_count: int,
    index_offset: int = 0,
    quality_profile: str = "final",
    camera_record: Any = None,
) -> list[SceneShotCandidate]:
    package, runtime = resolve_ers_for_sheet(db, project_id, shot.sheet_id)
    shot.ers_package_id = package.id
    shot.ers_runtime = runtime
    shot.generator = GeneratorSourceSelection(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
    )

    has_reference = bool(any((package.directional_assets or {}).values()) or shot.character_ids)
    shot.prop_entity_ids = _ensure_placed_project_props(db, project_id, shot)
    if any(shot.prop_entity_ids):
        has_reference = True
    plans = build_candidate_plans(
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        has_reference=has_reference,
        candidate_count=candidate_count,
    )

    from ..codirector.entity_resolver import compile_shot_prompt
    from ..storyboard_jobs import enqueue_imagegen_job

    parsed = _shot_request_from_scene_shot(shot)
    body_base = compile_shot_prompt(db, project_id, parsed, ers_package=package)
    _apply_cinematic(body_base, shot, camera_record=camera_record, db=db, project_id=project_id)
    draft = (quality_profile or "final").lower() == "draft"
    if draft:
        body_base["purpose"] = "scene_shot_preview"
        body_base["quality"] = "draft"
        body_base["width"] = 512
        body_base["height"] = 288
        body_base["allowDraft"] = True

    candidates: list[SceneShotCandidate] = []
    for plan in plans:
        index = plan["index"] + index_offset
        body = dict(body_base)
        body["modelFamilyPreference"] = plan["family"]
        body["seed"] = plan["seed"]
        body["sceneId"] = shot.scene_id
        body["shotId"] = shot.id
        tag_prefix = "scene_preview" if draft else "scene_shot"
        body["tag"] = f"{tag_prefix}_{shot.id[:8]}_c{index + 1}"
        ctx = body.setdefault("creativeContext", {})
        if isinstance(ctx, dict):
            ctx["workflowKey"] = f"{plan['family']}.txt2img"
            ctx["candidateIndex"] = index
            ctx["sheetId"] = shot.sheet_id
            ctx["ersPackageId"] = package.id
            ctx["qualityProfile"] = "draft" if draft else "final"
            if camera_record is not None:
                ctx["cinematographer"] = {
                    "cameraId": getattr(camera_record, "cameraId", ""),
                    "cameraSlot": getattr(camera_record, "cameraSlot", None),
                    "cameraStateVersion": getattr(camera_record, "cameraStateVersion", None),
                    "cameraStateHash": getattr(camera_record, "cameraStateHash", ""),
                    "locked": bool(getattr(getattr(camera_record, "lineage", None), "locked", False)),
                }
                pose = getattr(camera_record, "current", None)
                if pose is not None:
                    ctx["cinematographer"]["pose"] = pose.model_dump() if hasattr(pose, "model_dump") else dict(pose)
        if plan["source"] == "api":
            hosted = (api_model or plan.get("model") or "").strip()
            if not hosted:
                raise SceneCreatorError("API Generation — Not Available")
            body["providerPreference"] = "cloud"
            body["hostedModelId"] = hosted
            body["model"] = hosted
            body["lockModelFamily"] = True
        elif plan["source"] == "local" and plan.get("family"):
            body["lockModelFamily"] = True
            body["model"] = plan["family"]
        try:
            job = enqueue_imagegen_job(db, project_id, body, scene_id=shot.scene_id)
            if plan["source"] == "api":
                job = _pin_hosted_image_job(db, job, hosted=hosted)
            job_id = job.id
            job_status = str(getattr(job, "status", "") or "").lower()
            status = "failed" if job_status in {"failed", "error"} else "queued"
            error = str(getattr(job, "message", "") or "")
        except Exception as exc:
            logger.error("Scene candidate enqueue failed: %s", exc)
            job_id = f"failed_scene_cand_{index}"
            status = "failed"
            error = str(exc)
        provenance = plan["provenance_label"]
        if draft:
            provenance = f"PREVIEW — {provenance}"
        candidates.append(
            SceneShotCandidate(
                shot_id=shot.id,
                index=index,
                job_id=job_id,
                status=status,  # type: ignore[arg-type]
                source=plan["source"],
                family=plan["family"],
                model=plan["model"],
                seed=plan["seed"],
                provenance_label=provenance,
                take_label="Preview" if draft else f"Take {chr(ord('A') + min(index, 25))}",
                error=error,
                camera_state_version=getattr(camera_record, "cameraStateVersion", None),
                camera_state_hash=getattr(camera_record, "cameraStateHash", "") or "",
                source_camera_id=getattr(camera_record, "cameraId", "") or "",
                quality_profile="draft" if draft else "final",
            )
        )
    return candidates


def _pin_hosted_image_job(db: Session, job: Any, *, hosted: str) -> Any:
    """Pin Fal/hosted still-image dispatch. Never silently substitute Comfy."""
    try:
        from ..character_identity.visual_sheet import _fal_image_model_id
    except Exception:
        _fal_image_model_id = None  # type: ignore[assignment]
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    fal_id = _fal_image_model_id(hosted) if _fal_image_model_id else None
    if fal_id:
        params["cloudPaid"] = True
        params["falImageModelId"] = fal_id
        params["hostedModelId"] = hosted
        params["providerPreference"] = "cloud"
        job.params_json = json.dumps(params)
        db.commit()
        db.refresh(job)
        return job
    runtime_key = str((params.get("imageRuntime") or {}).get("workflowKey") or "")
    cloud_paid = bool(params.get("cloudPaid"))
    if not cloud_paid and not runtime_key.startswith("imagen."):
        job.status = "failed"
        job.message = (
            f"API model {hosted} resolved to local workflow {runtime_key or 'unknown'}; "
            "refusing silent Comfy substitute."
        )
        db.commit()
        db.refresh(job)
    return job


def generate_candidates(
    db: Session,
    project_id: str,
    shot_id: str,
    *,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
    candidate_count: int = 4,
) -> SceneShot:
    shot = _require_shot(db, project_id, shot_id)
    if _approved_candidate(shot) is not None:
        raise SceneCreatorError("Use Re-Take to change an approved look.")
    package, _runtime = resolve_ers_for_sheet(db, project_id, shot.sheet_id)
    candidates = _enqueue_shot_candidates(
        db,
        project_id,
        shot,
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        candidate_count=candidate_count,
    )
    shot.candidates = candidates
    shot.take_memory = _seed_take_memory(shot, package, user_correction={})
    save_scene_shot(db, project_id, shot)
    return shot


def retake_shot(
    db: Session,
    project_id: str,
    shot_id: str,
    *,
    correction: str,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
) -> SceneShot:
    """Non-destructive Re-Take. Take A stays until Take B is approved."""
    shot = _require_shot(db, project_id, shot_id)
    approved = _approved_candidate(shot)
    if approved is None:
        raise SceneCreatorError("Approve a take before Re-Take.")
    delta = (correction or "").strip()
    if not delta:
        raise SceneCreatorError("Describe what to change. Re-Take is a correction, not a full rewrite.")

    prior = list(shot.candidates)
    approved_id = shot.approved_candidate_id

    memory = shot.take_memory or SceneShotTakeMemory()
    memory.userCorrection = {
        "text": delta,
        "parent_candidate_id": approved.id,
        "parent_take_label": approved.take_label,
    }
    shot.take_memory = memory
    if shot.intent and delta not in shot.intent:
        shot.prompt = f"{shot.intent}. Correction: {delta}"
    else:
        shot.prompt = shot.intent or delta

    new_cands = _enqueue_shot_candidates(
        db,
        project_id,
        shot,
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family or shot.generator.local_family,
        api_model=api_model or shot.generator.api_model,
        candidate_count=1,
        index_offset=len(prior),
        camera_record=_camera_record_for_shot(db, project_id, shot),
    )
    shot.candidates = prior + new_cands
    shot.approved_candidate_id = approved_id
    shot.take_memory = memory
    save_scene_shot(db, project_id, shot)
    return shot


def approve_candidate(
    db: Session,
    project_id: str,
    shot_id: str,
    candidate_id: str,
) -> SceneShot:
    shot = _require_shot(db, project_id, shot_id)
    _sync_candidate_jobs(db, project_id, shot)
    candidate = next((c for c in shot.candidates if c.id == candidate_id), None)
    if candidate is None:
        raise SceneCreatorError("Candidate not found.")
    if not candidate.asset_id or candidate.status != "complete":
        raise SceneCreatorError("That look is still generating. Wait for it to finish.")

    prev_id = shot.approved_candidate_id
    if prev_id and prev_id != candidate.id:
        prev = next((c for c in shot.candidates if c.id == prev_id), None)
        if prev and prev.asset_id:
            _set_asset_approval(db, project_id, prev.asset_id, approved=False)

    shot.approved_candidate_id = candidate.id
    shot.take_memory.takeState = {
        "approved_candidate_id": candidate.id,
        "approved_asset_id": candidate.asset_id,
        "take_label": candidate.take_label,
        "family": candidate.family,
        "source": candidate.source,
        "sourceCameraId": candidate.source_camera_id or shot.camera.camera_id,
        "cameraStateVersion": candidate.camera_state_version,
        "cameraStateHash": candidate.camera_state_hash,
    }
    _set_asset_approval(db, project_id, candidate.asset_id, approved=True)
    save_scene_shot(db, project_id, shot)
    return shot


def send_approved_to_timeline(
    db: Session,
    project_id: str,
    shot_id: str,
    *,
    batch_block_id: str | None = None,
) -> dict[str, Any]:
    shot = _require_shot(db, project_id, shot_id)
    _sync_candidate_jobs(db, project_id, shot)
    candidate = _approved_candidate(shot)
    if candidate is None or not candidate.asset_id:
        raise SceneCreatorError("Approve a take before sending to Timeline.")
    scene_id = (shot.scene_id or "").strip()
    if not scene_id:
        raise SceneCreatorError("This shot is not bound to a Scene.")
    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        raise SceneCreatorError("Scene not found in this project.")

    from .timeline_handoff import send_approved_shot_to_timeline

    return send_approved_shot_to_timeline(
        db,
        project_id,
        shot,
        candidate,
        batch_block_id=batch_block_id,
    )


def get_shot(db: Session, project_id: str, shot_id: str) -> SceneShot:
    shot = _require_shot(db, project_id, shot_id)
    _sync_candidate_jobs(db, project_id, shot)
    save_scene_shot(db, project_id, shot)
    return shot


def _require_shot(db: Session, project_id: str, shot_id: str) -> SceneShot:
    shot = load_scene_shot(db, project_id, shot_id)
    if shot is None or shot.project_id != project_id:
        raise SceneCreatorError("Shot not found.")
    return shot


def _approved_candidate(shot: SceneShot) -> SceneShotCandidate | None:
    if not shot.approved_candidate_id:
        return None
    return next((c for c in shot.candidates if c.id == shot.approved_candidate_id), None)


def _sync_candidate_jobs(db: Session, project_id: str, shot: SceneShot) -> None:
    for candidate in shot.candidates:
        if candidate.status in {"complete", "failed"} and candidate.asset_id:
            continue
        job_id = candidate.job_id
        if not job_id or job_id.startswith("failed_"):
            candidate.status = "failed"
            continue
        job = db.get(Job, job_id)
        if job is None or job.project_id != project_id:
            continue
        status = (job.status or "").lower()
        if status in {"done", "completed", "complete", "success"}:
            asset_id = _job_asset_id(job)
            candidate.asset_id = asset_id or candidate.asset_id
            candidate.status = "complete" if candidate.asset_id else "generating"
        elif status in {"failed", "error", "cancelled"}:
            candidate.status = "failed"
            candidate.error = job.message or candidate.error
        elif status in {"running", "preview"}:
            candidate.status = "generating"
        else:
            candidate.status = "queued"


def _job_asset_id(job: Job) -> str | None:
    try:
        params = json.loads(job.params_json or "{}")
    except Exception:
        params = {}
    asset_id = params.get("output_asset_id")
    if asset_id:
        return str(asset_id)
    return None


def _set_asset_approval(db: Session, project_id: str, asset_id: str, *, approved: bool) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.project_id != project_id:
        return
    asset.production_approval = "approved" if approved else "none"
    try:
        labels = json.loads(asset.labels_json or "[]")
    except Exception:
        labels = []
    if not isinstance(labels, list):
        labels = []
    labels = [str(x) for x in labels if x]
    for tag in ("scene_shot", "scene_creator"):
        if tag not in labels:
            labels.append(tag)
    if approved and "approved_take" not in labels:
        labels.append("approved_take")
    if not approved:
        labels = [x for x in labels if x != "approved_take"]
    asset.labels_json = json.dumps(labels)
    db.commit()


def _shot_request_from_scene_shot(shot: SceneShot) -> ShotRequest:
    cine = shot.camera.cinematic
    size = CINEMATIC_SIZE_LABELS.get(cine.shot_size, cine.shot_size.replace("_", " ").title())
    motion = CINEMATIC_MOTION_LABELS.get(cine.motion, cine.motion.title())
    framing = CINEMATIC_FRAMING_LABELS.get(cine.framing, cine.framing.replace("_", " ").title())
    where = ""
    if shot.camera.label:
        parts = [shot.camera.label]
        if shot.camera.orientation:
            parts.append(shot.camera.orientation)
        if shot.camera.fov_preset:
            parts.append(f"{shot.camera.fov_preset} FOV")
        where = " ".join(parts)
    extra = shot.prompt or shot.intent
    if where:
        extra = f"{extra}. Camera: {where}".strip(". ")
    orientation = ""
    ori = (shot.camera.orientation or "").upper()
    compass = {"N": "north", "E": "east", "S": "south", "W": "west"}
    if ori in compass:
        orientation = compass[ori]
    elif ori[:1] in compass:
        orientation = compass[ori[:1]]
    return ShotRequest(
        index=0,
        raw_text=shot.intent or shot.prompt,
        characters=list(shot.character_ids),
        prop_entities=list(shot.prop_entity_ids),
        framing=framing,
        angle=f"{size}, {motion}",
        orientation=orientation,
        additional_instructions=extra,
    )


def _workspace_preview_capabilities(api_discovered: bool) -> dict[str, Any]:
    from .cinematographer import api_preview_capability, local_preview_capability

    api_cap = api_preview_capability(api_enabled=False, api_model="")
    api_cap["discovered"] = bool(api_discovered)
    api_cap["noneLabel"] = "API Generation — Not Available"
    if api_discovered:
        api_cap["status"] = "standard_cost"
        api_cap["label"] = "Standard-Cost Preview Only"
    else:
        api_cap["status"] = "none"
        api_cap["label"] = "API Generation — Not Available"
    return {"local": local_preview_capability(), "api": api_cap}


def _camera_record_for_shot(db: Session, project_id: str, shot: SceneShot) -> Any:
    try:
        from .cinematographer import get_camera, load_pack

        pack = load_pack(db, project_id, shot.scene_id)
        if pack is None:
            return None
        approved = _approved_candidate(shot)
        cam_id = str(getattr(approved, "source_camera_id", "") or "") if approved else ""
        if not cam_id:
            locked = next((c for c in pack.cameras if lock_is_valid_safe(c)), None)
            cam_id = locked.cameraId if locked else ""
        if not cam_id:
            cam_id = str(getattr(shot.camera, "camera_id", "") or "")
        if not cam_id:
            return None
        return get_camera(pack, cam_id)
    except Exception:
        return None


def lock_is_valid_safe(record: Any) -> bool:
    try:
        from .cinematographer import lock_is_valid

        return bool(lock_is_valid(record))
    except Exception:
        return False


def _apply_cinematic(
    body: dict[str, Any],
    shot: SceneShot,
    camera_record: Any = None,
    *,
    db: Session | None = None,
    project_id: str = "",
) -> None:
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        return
    ctx["sheetId"] = shot.sheet_id
    ctx["sceneId"] = shot.scene_id
    ctx["camera"] = shot.camera.model_dump()
    ctx["cinematic"] = shot.camera.cinematic.model_dump()
    if camera_record is not None:
        try:
            from .cinematographer import association_for, compile_camera_context

            pose = getattr(camera_record, "current", None)
            held = ""
            char_id = ""
            prop_id = ""
            if pose is not None:
                if getattr(pose, "targetEntityType", "") == "character":
                    char_id = str(getattr(pose, "targetEntityId", "") or "")
                elif getattr(pose, "targetEntityType", "") == "prop":
                    prop_id = str(getattr(pose, "targetEntityId", "") or "")
                prop_id = str(getattr(pose, "inclusionPropId", "") or prop_id or "")
            if db is not None and project_id and (char_id or prop_id):
                held = association_for(db, project_id, character_id=char_id, prop_id=prop_id)
            compiled = compile_camera_context(
                camera_record,
                held_association=held,
            )
            ctx["cinematographer"] = compiled
            extra = compiled.get("prose") or ""
            if extra:
                prompt = str(body.get("prompt") or "")
                delta = str(getattr(camera_record, "userCameraPromptDelta", "") or "")
                parts = [prompt, extra]
                if delta:
                    parts.append(delta)
                body["prompt"] = " ".join(p for p in parts if p).strip()
        except Exception:
            logger.exception("Failed to compile cinematographer context")


def _seed_take_memory(shot: SceneShot, package: Any, user_correction: dict[str, Any]) -> SceneShotTakeMemory:
    return SceneShotTakeMemory(
        originalTakeIntent={
            "intent": shot.intent,
            "prompt": shot.prompt,
            "cinematic": shot.camera.cinematic.model_dump(),
        },
        sceneErsState={
            "sheet_id": shot.sheet_id,
            "package_id": getattr(package, "id", ""),
            "runtime": shot.ers_runtime,
            "directional_assets": getattr(package, "directional_assets", {}),
        },
        characterIdentity={"character_ids": list(shot.character_ids)},
        blocking={"prop_entity_ids": list(shot.prop_entity_ids)},
        camera=shot.camera.model_dump(),
        takeState={
            "approved_candidate_id": shot.approved_candidate_id,
        },
        userCorrection=dict(user_correction or {}),
    )


def _ensure_placed_project_props(db: Session, project_id: str, shot: SceneShot) -> list[str]:
    """Union placed approved PropEntity ids onto the shot so Scene Creator consumes them."""
    placed = _placed_project_prop_ids(db, project_id, shot.sheet_id)
    merged = list(dict.fromkeys([*(shot.prop_entity_ids or []), *placed]))
    shot.prop_entity_ids = merged
    return merged


def _placed_project_prop_ids(db: Session, project_id: str, sheet_id: str = "") -> list[str]:
    ids: list[str] = []
    placements: list[dict[str, Any]] = []
    if (sheet_id or "").strip():
        try:
            package, _runtime = resolve_ers_for_sheet(db, project_id, sheet_id)
            placements.extend([p for p in (package.placements or []) if isinstance(p, dict)])
        except Exception:
            placements = []
    if not placements:
        try:
            from ..spatial_map.service import list_documents

            maps = list_documents(db, project_id)
        except Exception:
            maps = []
        if maps:
            placements.extend(p.model_dump() for p in (maps[0].props or []))
    for placement in placements:
        prop_id = str(placement.get("propId") or placement.get("prop_id") or "").strip()
        if not prop_id or prop_id in ids:
            continue
        entity = load_prop_entity_by_id(db, project_id, prop_id)
        if entity is None:
            continue
        if not (entity.approved_asset_id or "").strip():
            continue
        ids.append(entity.id)
    return ids



def _union_spatial_map_project_props(db: Session, project_id: str, props: list[dict[str, Any]]) -> None:
    """Add Spatial Map PropEntity placements into workspace.props (same store).

    Attached rows use PropEntity.id. Leftover ERS {prop_id:null} rows are not
    a second registry and are dropped once a real propId is present.
    """
    from ..spatial_map.service import list_documents

    try:
        maps = list_documents(db, project_id)
    except Exception:
        maps = []
    if not maps:
        return
    seen = {str(p.get("prop_id") or "").strip() for p in props if str(p.get("prop_id") or "").strip()}
    for placement in maps[0].props or []:
        pid = str(getattr(placement, "propId", None) or "").strip()
        if not pid or pid in seen:
            continue
        dumped = placement.model_dump()
        props.append(
            _hydrate_prop(
                db,
                project_id,
                prop_id=pid,
                asset_id=getattr(placement, "assetId", None) or "",
                label=getattr(placement, "label", None) or getattr(placement, "tag", None) or "Prop",
                position_label=_position_summary(dumped),
                placement=dumped,
            )
        )
        seen.add(pid)
    if seen:
        props[:] = [p for p in props if str(p.get("prop_id") or "").strip()]


def _hydrate_prop(
    db: Session,
    project_id: str,
    *,
    prop_id: str = "",
    asset_id: str = "",
    label: str = "Prop",
    position_label: str = "",
    placement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a Spatial Map / ERS placement to an approved PropEntity when possible."""
    entity = load_prop_entity_by_id(db, project_id, prop_id) if (prop_id or "").strip() else None
    visual = ""
    description = ""
    tag = (label or "prop").strip() or "prop"
    display = (label or "Prop").strip() or "Prop"
    resolved_id = (prop_id or "").strip() or None
    approved = None
    if entity:
        approved = (entity.approved_asset_id or "").strip() or None
        visual = approved or (entity.library_asset_id or "").strip()
        description = (entity.description or entity.notes or "").strip()
        tag = entity.tag or tag
        display = entity.display_label or display
        resolved_id = entity.id
    else:
        visual = (asset_id or "").strip()
    result = {
        "prop_id": resolved_id,
        "tag": tag,
        "display_label": display,
        "position_label": position_label,
        "approved_asset_id": approved,
        "library_asset_id": visual,
        "description": description,
        "slot_index": (placement or {}).get("slotIndex"),
    }
    src = placement or {}
    if src.get("placementMode") == "attached":
        result["placementMode"] = "attached"
        result["attachedCharacterSlot"] = src.get("attachedCharacterSlot")
        result["attachedCharacterId"] = src.get("attachedCharacterId")
        result["relationship"] = src.get("relationship")
        result["attachmentPoint"] = src.get("attachmentPoint")
        result["position_label"] = ""
    elif src.get("placementMode"):
        result["placementMode"] = src.get("placementMode")
    return result


def _position_summary(p: dict[str, Any]) -> str:
    if str(p.get("placementMode") or "") == "attached":
        return ""
    try:
        x = float(p.get("x") or 0)
        z = float(p.get("z") or 0)
    except Exception:
        return ""
    lateral = "center"
    if x <= -1.5:
        lateral = "left"
    elif x >= 1.5:
        lateral = "right"
    depth = "midground"
    if z <= -1.5:
        depth = "foreground"
    elif z >= 1.5:
        depth = "background"
    return f"{depth} {lateral}".strip()
