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
                        }
                    )
                else:
                    props.append(
                        {
                            "tag": (placement.get("label") or "prop"),
                            "display_label": placement.get("label") or "Prop",
                            "position_label": _position_summary(placement),
                            "library_asset_id": placement.get("assetId") or placement.get("propId"),
                        }
                    )
        except ErsResolveError as exc:
            resolved = {"error": str(exc)}

    if not characters and not props:
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
                    }
                )
            for p in latest.props or []:
                props.append(
                    {
                        "tag": p.label or "prop",
                        "display_label": p.label or "Prop",
                        "position_label": _position_summary(p.model_dump()),
                        "library_asset_id": p.assetId,
                    }
                )
            if not cameras:
                for index, cam in enumerate(latest.cameras or []):
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
        "api_generation_available": hosted_image_generation_available(),
        "local_families": list_local_generator_families(has_reference=has_reference),
        "has_reference": has_reference,
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
    _apply_cinematic(body_base, shot)

    candidates: list[SceneShotCandidate] = []
    for plan in plans:
        if plan["source"] == "api":
            # Hosted image generation is not Certified/executable. Never fall
            # back to local Comfy under an API provenance label.
            raise SceneCreatorError("API Generation — Not Available")
        index = plan["index"] + index_offset
        body = dict(body_base)
        body["modelFamilyPreference"] = plan["family"]
        body["seed"] = plan["seed"]
        body["sceneId"] = shot.scene_id
        body["shotId"] = shot.id
        body["tag"] = f"scene_shot_{shot.id[:8]}_c{index + 1}"
        ctx = body.setdefault("creativeContext", {})
        if isinstance(ctx, dict):
            ctx["workflowKey"] = f"{plan['family']}.txt2img"
            ctx["candidateIndex"] = index
            ctx["sheetId"] = shot.sheet_id
            ctx["ersPackageId"] = package.id
        try:
            job = enqueue_imagegen_job(db, project_id, body, scene_id=shot.scene_id)
            job_id = job.id
            status = "queued"
            error = ""
        except Exception as exc:
            logger.error("Scene candidate enqueue failed: %s", exc)
            job_id = f"failed_scene_cand_{index}"
            status = "failed"
            error = str(exc)
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
                provenance_label=plan["provenance_label"],
                take_label=f"Take {chr(ord('A') + min(index, 25))}",
                error=error,
            )
        )
    return candidates


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


def _apply_cinematic(body: dict[str, Any], shot: SceneShot) -> None:
    ctx = body.setdefault("creativeContext", {})
    if not isinstance(ctx, dict):
        return
    ctx["sheetId"] = shot.sheet_id
    ctx["sceneId"] = shot.scene_id
    ctx["camera"] = shot.camera.model_dump()
    ctx["cinematic"] = shot.camera.cinematic.model_dump()


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


def _position_summary(p: dict[str, Any]) -> str:
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
