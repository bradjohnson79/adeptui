"""Scene Creator cinematographer persistence + preview/final generation."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from .cinematographer import (
    CinematographerError,
    SceneCinematographerPack,
    api_preview_capability,
    apply_command_to_pack,
    association_for,
    bind_pack_from_spatial,
    can_lock,
    compile_camera_context,
    get_camera,
    list_spatial_cameras,
    load_pack,
    local_preview_capability,
    lock_camera,
    lock_is_valid,
    reset_camera,
    save_pack,
    undo_camera,
)
from .service import (
    SceneCreatorError,
    _enqueue_shot_candidates,
    _job_asset_id,
    _require_shot,
    approved_look_blocks_final,
    ensure_scene_id,
)

logger = logging.getLogger(__name__)


def hydrate_cinematographer(
    db: Session,
    project_id: str,
    *,
    scene_id: str = "",
) -> SceneCinematographerPack:
    scene = ensure_scene_id(db, project_id, scene_id)
    cams, density, grid_scale = list_spatial_cameras(db, project_id)
    existing = load_pack(db, project_id, scene.id)
    pack = bind_pack_from_spatial(
        existing,
        project_id=project_id,
        scene_id=scene.id,
        spatial_cameras=cams,
        density=density,
        grid_scale=grid_scale,
    )
    _sync_preview_jobs(db, project_id, pack)
    save_pack(db, project_id, pack)
    return pack


def sync_final_assets_from_shots(pack: SceneCinematographerPack, shots: list[Any]) -> bool:
    """Point lineage.finalAssetId at the completed final candidate asset."""
    changed = False
    for rec in pack.cameras:
        job_id = rec.lineage.finalJobId
        if not job_id:
            continue
        for shot in shots or []:
            for cand in getattr(shot, "candidates", None) or []:
                if cand.job_id == job_id and cand.asset_id and rec.lineage.finalAssetId != cand.asset_id:
                    rec.lineage.finalAssetId = cand.asset_id
                    changed = True
    return changed


def apply_cinematographer_command(
    db: Session,
    project_id: str,
    *,
    scene_id: str,
    camera_id: str,
    operation_id: str,
    character_id: str = "",
    prop_id: str = "",
    shot_id: str = "",
    user_prompt_delta: str | None = None,
    orientation3d: dict[str, Any] | None = None,
) -> SceneCinematographerPack:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    char_name, char_slot = _entity_label(db, project_id, character_id, kind="character")
    prop_name, prop_slot = _entity_label(db, project_id, prop_id, kind="prop")
    held = association_for(db, project_id, character_id=character_id, prop_id=prop_id)
    pack = apply_command_to_pack(
        pack,
        camera_id=camera_id,
        operation_id=operation_id,
        character_id=character_id,
        prop_id=prop_id,
        character_name=char_name,
        prop_name=prop_name,
        character_slot=char_slot,
        prop_slot=prop_slot,
        held_by_character_id=character_id if held else "",
        orientation_patch=orientation3d,
    )
    if user_prompt_delta is not None:
        rec = get_camera(pack, camera_id)
        rec.userCameraPromptDelta = user_prompt_delta
    save_pack(db, project_id, pack)
    _mirror_shot_camera(db, project_id, pack, shot_id=shot_id, camera_id=camera_id)
    return pack


def undo_cinematographer(
    db: Session, project_id: str, *, scene_id: str, camera_id: str, shot_id: str = ""
) -> SceneCinematographerPack:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    pack = undo_camera(pack, camera_id)
    save_pack(db, project_id, pack)
    _mirror_shot_camera(db, project_id, pack, shot_id=shot_id, camera_id=camera_id)
    return pack


def reset_cinematographer(
    db: Session, project_id: str, *, scene_id: str, camera_id: str, shot_id: str = ""
) -> SceneCinematographerPack:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    pack = reset_camera(pack, camera_id)
    save_pack(db, project_id, pack)
    _mirror_shot_camera(db, project_id, pack, shot_id=shot_id, camera_id=camera_id)
    return pack


def lock_cinematographer(
    db: Session, project_id: str, *, scene_id: str, camera_id: str, shot_id: str = ""
) -> SceneCinematographerPack:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    rec = get_camera(pack, camera_id)
    if not can_lock(rec):
        raise CinematographerError("Generate a preview of this camera setup before locking it.")
    pack = lock_camera(pack, camera_id)
    save_pack(db, project_id, pack)
    _mirror_shot_camera(db, project_id, pack, shot_id=shot_id, camera_id=camera_id)
    return pack


def set_prompt_delta(
    db: Session,
    project_id: str,
    *,
    scene_id: str,
    camera_id: str,
    delta: str,
) -> SceneCinematographerPack:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    rec = get_camera(pack, camera_id)
    rec.userCameraPromptDelta = delta or ""
    save_pack(db, project_id, pack)
    return pack


def generate_camera_preview(
    db: Session,
    project_id: str,
    *,
    scene_id: str,
    camera_id: str,
    shot_id: str,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
) -> tuple[SceneCinematographerPack, Any]:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    rec = get_camera(pack, camera_id)
    if api_enabled and not local_enabled:
        cap = api_preview_capability(api_enabled=True, api_model=api_model)
        if cap["status"] == "unsupported":
            raise CinematographerError("Preview Unsupported for this cloud generator.")
    shot = _require_shot(db, project_id, shot_id)
    _apply_record_to_shot(shot, rec)
    from ..spatial_map.ers_persistence import save_scene_shot

    save_scene_shot(db, project_id, shot)
    try:
        cands = _enqueue_shot_candidates(
            db,
            project_id,
            shot,
            local_enabled=local_enabled,
            api_enabled=api_enabled,
            local_family=local_family,
            api_model=api_model,
            candidate_count=1,
            quality_profile="draft",
            camera_record=rec,
        )
    except SceneCreatorError as exc:
        rec.lineage.previewStatus = "failed"
        rec.lineage.previewError = str(exc)
        save_pack(db, project_id, pack)
        raise
    cand = cands[0] if cands else None
    rec.lineage.previewJobId = cand.job_id if cand else ""
    rec.lineage.previewAssetId = cand.asset_id or "" if cand else ""
    rec.lineage.previewStateVersion = rec.cameraStateVersion
    rec.lineage.previewStateHash = rec.cameraStateHash
    rec.lineage.previewStatus = "failed" if cand and cand.status == "failed" else "generating"
    rec.lineage.previewError = cand.error if cand else ""
    rec.lineage.cameraId = rec.cameraId
    rec.lineage.cameraStateVersion = rec.cameraStateVersion
    rec.lineage.cameraStateHash = rec.cameraStateHash
    save_pack(db, project_id, pack)
    return pack, shot


def generate_camera_final(
    db: Session,
    project_id: str,
    *,
    scene_id: str,
    camera_id: str,
    shot_id: str,
    local_enabled: bool = True,
    api_enabled: bool = False,
    local_family: str = "",
    api_model: str = "",
) -> tuple[SceneCinematographerPack, Any]:
    pack = hydrate_cinematographer(db, project_id, scene_id=scene_id)
    rec = get_camera(pack, camera_id)
    if not lock_is_valid(rec):
        raise CinematographerError("Lock this camera before the final quality render.")
    shot = _require_shot(db, project_id, shot_id)
    if approved_look_blocks_final(shot):
        raise SceneCreatorError("Use Re-Take to change an approved look.")
    _apply_record_to_shot(shot, rec)
    from ..spatial_map.ers_persistence import save_scene_shot

    save_scene_shot(db, project_id, shot)
    cands = _enqueue_shot_candidates(
        db,
        project_id,
        shot,
        local_enabled=local_enabled,
        api_enabled=api_enabled,
        local_family=local_family,
        api_model=api_model,
        candidate_count=1,
        quality_profile="final",
        camera_record=rec,
        index_offset=len(shot.candidates or []),
    )
    shot.candidates = list(shot.candidates or []) + list(cands)
    rec.lineage.finalJobId = cands[0].job_id if cands else rec.lineage.finalJobId
    rec.lineage.finalStateVersion = rec.cameraStateVersion
    save_pack(db, project_id, pack)
    save_scene_shot(db, project_id, shot)
    return pack, shot


def preview_capabilities(*, local_enabled: bool, api_enabled: bool, api_model: str = "") -> dict[str, Any]:
    return {
        "local": local_preview_capability() if local_enabled else {"status": "none", "label": ""},
        "api": api_preview_capability(api_enabled=api_enabled, api_model=api_model),
    }


def _sync_preview_jobs(db: Session, project_id: str, pack: SceneCinematographerPack) -> None:
    from ..db import Job

    for rec in pack.cameras:
        lin = rec.lineage
        job_id = lin.previewJobId
        if not job_id or job_id.startswith("failed_"):
            if lin.previewStatus == "generating":
                lin.previewStatus = "failed"
        else:
            job = db.get(Job, job_id)
            if job is not None and job.project_id == project_id:
                status = (job.status or "").lower()
                if status in {"done", "completed", "complete", "success"}:
                    asset_id = _job_asset_id(job)
                    lin.previewAssetId = asset_id or lin.previewAssetId
                    lin.previewStatus = "ready" if lin.previewAssetId else "generating"
                    lin.previewError = ""
                elif status in {"failed", "error", "cancelled"}:
                    lin.previewStatus = "failed"
                    lin.previewError = job.message or lin.previewError or "Preview failed."
                elif status in {"running", "preview", "queued"}:
                    lin.previewStatus = "generating"
        final_id = lin.finalJobId
        if final_id and not final_id.startswith("failed_"):
            final_job = db.get(Job, final_id)
            if final_job is not None and final_job.project_id == project_id:
                st = (final_job.status or "").lower()
                if st in {"done", "completed", "complete", "success"}:
                    asset_id = _job_asset_id(final_job)
                    if asset_id:
                        lin.finalAssetId = asset_id


def _apply_record_to_shot(shot: Any, rec: Any) -> None:
    from ..spatial_map.ers_contracts import SceneCreatorCamera

    pose = rec.current
    cine_size = {
        "extreme_close_up": "extreme_close_up",
        "close_up": "close_up",
        "medium_close_up": "close_up",
        "medium": "medium",
        "cowboy": "medium",
        "full": "medium_wide",
        "wide": "wide",
        "extreme_wide": "wide",
    }.get(pose.shotType, "medium")
    shot.camera = SceneCreatorCamera.model_validate(
        {
            "camera_id": rec.cameraId,
            "camera_slot": rec.cameraSlot,
            "label": rec.label or f"C{rec.cameraSlot + 1}",
            "orientation": pose.orientation,
            "fov_preset": pose.fovPreset,
            "yaw_degrees": pose.yawDegrees,
            "lens_mm": pose.lensMm,
            "cinematic": {
                "shot_size": cine_size,
                "motion": "static",
                "framing": "single",
            },
        }
    )
    if pose.targetEntityType == "character" and pose.targetEntityId:
        if pose.targetEntityId not in (shot.character_ids or []):
            shot.character_ids = list(shot.character_ids or []) + [pose.targetEntityId]
    if pose.targetEntityType == "prop" and pose.targetEntityId:
        if pose.targetEntityId not in (shot.prop_entity_ids or []):
            shot.prop_entity_ids = list(shot.prop_entity_ids or []) + [pose.targetEntityId]
    if pose.inclusionPropId and pose.inclusionPropId not in (shot.prop_entity_ids or []):
        shot.prop_entity_ids = list(shot.prop_entity_ids or []) + [pose.inclusionPropId]


def _mirror_shot_camera(
    db: Session,
    project_id: str,
    pack: SceneCinematographerPack,
    *,
    shot_id: str,
    camera_id: str,
) -> None:
    if not (shot_id or "").strip():
        return
    try:
        shot = _require_shot(db, project_id, shot_id)
    except Exception:
        return
    rec = get_camera(pack, camera_id)
    _apply_record_to_shot(shot, rec)
    from ..spatial_map.ers_persistence import save_scene_shot

    save_scene_shot(db, project_id, shot)


def _entity_label(db: Session, project_id: str, entity_id: str, *, kind: str) -> tuple[str, int | None]:
    if not (entity_id or "").strip():
        return "", None
    try:
        from ..spatial_map.service import list_documents

        maps = list_documents(db, project_id)
    except Exception:
        return "", None
    if not maps:
        return "", None
    doc = maps[0]
    if kind == "character":
        for index, ch in enumerate(doc.characters or []):
            cid = str(getattr(ch, "characterId", "") or "")
            if cid != entity_id:
                continue
            slot = getattr(ch, "slotIndex", None)
            slot_n = int(slot) + 1 if slot is not None and int(slot) >= 0 else index + 1
            return str(getattr(ch, "label", None) or cid), slot_n
    else:
        for index, prop in enumerate(doc.props or []):
            pid = str(getattr(prop, "propId", "") or "")
            if pid != entity_id:
                continue
            slot = getattr(prop, "slotIndex", None)
            slot_n = int(slot) + 1 if slot is not None and int(slot) >= 0 else index + 1
            return str(getattr(prop, "label", None) or pid), slot_n
    return "", None


def camera_context_for_shot(db: Session, project_id: str, pack: SceneCinematographerPack, camera_id: str) -> dict[str, Any]:
    rec = get_camera(pack, camera_id)
    char_name = ""
    prop_name = ""
    if rec.current.targetEntityType == "character":
        char_name, _ = _entity_label(db, project_id, rec.current.targetEntityId, kind="character")
    if rec.current.targetEntityType == "prop" or rec.current.inclusionPropId:
        pid = rec.current.inclusionPropId or rec.current.targetEntityId
        prop_name, _ = _entity_label(db, project_id, pid, kind="prop")
    held = association_for(
        db,
        project_id,
        character_id=rec.current.targetEntityId if rec.current.targetEntityType == "character" else "",
        prop_id=rec.current.inclusionPropId
        or (rec.current.targetEntityId if rec.current.targetEntityType == "prop" else ""),
    )
    return compile_camera_context(rec, character_name=char_name, prop_name=prop_name, held_association=held)
