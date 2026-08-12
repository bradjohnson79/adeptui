"""Voice Environment business logic."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import Asset, Project, Scene
from ..voice_performance.m410_models import VoicePerformanceRecordRow, VoicePerformanceTakeRow
from .compiler import compile_dsp_plan
from .contracts import (
    ProfileCreateRequest,
    ProfileUpdateRequest,
    VoiceEnvironmentProfile,
    VoiceEnvironmentRender,
    VoiceEnvironmentTiming,
)
from .errors import VoiceEnvironmentError
from .models import VoiceEnvironmentProfileRow, VoiceEnvironmentRenderRow
from .processor import process_environment
from .recommend import recommend_environment


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str:
    if not dt:
        return _now().isoformat()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


def runtime_status() -> dict[str, Any]:
    ready = True
    reasons: list[str] = []
    try:
        import numpy  # noqa: F401
    except Exception:
        ready = False
        reasons.append("numpy unavailable")
    return {
        "ok": ready,
        "status": "Ready" if ready else "Repair Required",
        "processingKind": "deterministic_acoustic",
        "aiGeneration": False,
        "reasons": reasons,
        "capabilities": {
            "preview": ready,
            "render": ready,
            "stems": ready,
            "wallaPlaceholder": ready,
            "roomTonePlaceholder": ready,
        },
    }


def _profile_to_contract(row: VoiceEnvironmentProfileRow) -> VoiceEnvironmentProfile:
    return VoiceEnvironmentProfile(
        id=row.id,
        projectId=row.project_id,
        characterId=row.character_id,
        sceneId=row.scene_id,
        locationId=row.location_id,
        name=row.name,
        spacePreset=row.space_preset,
        customSpacePrompt=row.custom_space_prompt,
        distancePreset=row.distance_preset,
        customDistancePrompt=row.custom_distance_prompt,
        directionPreset=row.direction_preset,
        customDirectionPrompt=row.custom_direction_prompt,
        tonePreset=row.tone_preset,
        customTonePrompt=row.custom_tone_prompt,
        devicePreset=row.device_preset,
        customDevicePrompt=row.custom_device_prompt,
        wallaPreset=row.walla_preset,
        wallaLevel=row.walla_level,  # type: ignore[arg-type]
        wallaDistance=row.walla_distance,  # type: ignore[arg-type]
        wallaBehavior=row.walla_behavior,  # type: ignore[arg-type]
        customWallaPrompt=row.custom_walla_prompt,
        source=row.source,  # type: ignore[arg-type]
        createdAt=_iso(row.created_at),
        updatedAt=_iso(row.updated_at),
    )


def _render_to_contract(row: VoiceEnvironmentRenderRow) -> VoiceEnvironmentRender:
    return VoiceEnvironmentRender(
        id=row.id,
        projectId=row.project_id,
        characterId=row.character_id,
        performanceRecordId=row.performance_record_id,
        performanceTakeId=row.performance_take_id,
        environmentProfileId=row.environment_profile_id,
        dryAudioAssetId=row.dry_audio_asset_id,
        processedAudioAssetId=row.processed_audio_asset_id,
        roomToneAssetId=row.room_tone_asset_id,
        wallaAssetId=row.walla_asset_id,
        timing=VoiceEnvironmentTiming(
            speechStartOffsetMs=row.speech_start_offset_ms or 0.0,
            processingLatencyMs=row.processing_latency_ms or 0.0,
            tailDurationMs=row.tail_duration_ms or 0.0,
            dryDurationMs=row.dry_duration_ms or 0.0,
            processedDurationMs=row.processed_duration_ms or 0.0,
        ),
        status=row.status,  # type: ignore[arg-type]
        approved=bool(row.approved),
        errorCode=row.error_code,
        errorMessage=row.error_message,
        createdAt=_iso(row.created_at),
        updatedAt=_iso(row.updated_at),
        dspPlan=json.loads(row.dsp_plan_json or "{}"),
    )


def create_profile(db: Session, body: ProfileCreateRequest) -> VoiceEnvironmentProfile:
    if not db.get(Project, body.projectId):
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_PROFILE_INVALID", "Project not found.", status_code=404)
    row = VoiceEnvironmentProfileRow(
        id=str(uuid.uuid4()),
        project_id=body.projectId,
        character_id=body.characterId,
        scene_id=body.sceneId,
        location_id=body.locationId,
        name=body.name or "Untitled Environment",
        space_preset=body.spacePreset,
        custom_space_prompt=body.customSpacePrompt,
        distance_preset=body.distancePreset,
        custom_distance_prompt=body.customDistancePrompt,
        direction_preset=body.directionPreset,
        custom_direction_prompt=body.customDirectionPrompt,
        tone_preset=body.tonePreset,
        custom_tone_prompt=body.customTonePrompt,
        device_preset=body.devicePreset,
        custom_device_prompt=body.customDevicePrompt,
        walla_preset=body.wallaPreset,
        walla_level=body.wallaLevel,
        walla_distance=body.wallaDistance,
        walla_behavior=body.wallaBehavior,
        custom_walla_prompt=body.customWallaPrompt,
        source=body.source,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _profile_to_contract(row)


def update_profile(db: Session, profile_id: str, body: ProfileUpdateRequest) -> VoiceEnvironmentProfile:
    row = db.get(VoiceEnvironmentProfileRow, profile_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_PROFILE_INVALID", "Environment profile not found.", status_code=404)
    data = body.model_dump(exclude_unset=True)
    mapping = {
        "name": "name",
        "characterId": "character_id",
        "sceneId": "scene_id",
        "locationId": "location_id",
        "spacePreset": "space_preset",
        "customSpacePrompt": "custom_space_prompt",
        "distancePreset": "distance_preset",
        "customDistancePrompt": "custom_distance_prompt",
        "directionPreset": "direction_preset",
        "customDirectionPrompt": "custom_direction_prompt",
        "tonePreset": "tone_preset",
        "customTonePrompt": "custom_tone_prompt",
        "devicePreset": "device_preset",
        "customDevicePrompt": "custom_device_prompt",
        "wallaPreset": "walla_preset",
        "wallaLevel": "walla_level",
        "wallaDistance": "walla_distance",
        "wallaBehavior": "walla_behavior",
        "customWallaPrompt": "custom_walla_prompt",
        "source": "source",
    }
    for src, dest in mapping.items():
        if src in data:
            setattr(row, dest, data[src])
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _profile_to_contract(row)


def list_profiles(db: Session, project_id: str, character_id: Optional[str] = None) -> list[VoiceEnvironmentProfile]:
    q = db.query(VoiceEnvironmentProfileRow).filter(VoiceEnvironmentProfileRow.project_id == project_id)
    if character_id:
        q = q.filter(VoiceEnvironmentProfileRow.character_id == character_id)
    rows = q.order_by(VoiceEnvironmentProfileRow.updated_at.desc()).all()
    return [_profile_to_contract(r) for r in rows]


def get_profile(db: Session, profile_id: str) -> VoiceEnvironmentProfile:
    row = db.get(VoiceEnvironmentProfileRow, profile_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_PROFILE_INVALID", "Environment profile not found.", status_code=404)
    return _profile_to_contract(row)


def list_renders(
    db: Session,
    project_id: str,
    *,
    character_id: Optional[str] = None,
    performance_take_id: Optional[str] = None,
) -> list[VoiceEnvironmentRender]:
    q = db.query(VoiceEnvironmentRenderRow).filter(VoiceEnvironmentRenderRow.project_id == project_id)
    if character_id:
        q = q.filter(VoiceEnvironmentRenderRow.character_id == character_id)
    if performance_take_id:
        q = q.filter(VoiceEnvironmentRenderRow.performance_take_id == performance_take_id)
    rows = q.order_by(VoiceEnvironmentRenderRow.created_at.desc()).all()
    return [_render_to_contract(r) for r in rows]


def get_render(db: Session, render_id: str) -> VoiceEnvironmentRender:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_RENDER_FAILED", "Environment render not found.", status_code=404)
    return _render_to_contract(row)


def _require_take(
    db: Session, *, character_id: str, record_id: str, take_id: str
) -> tuple[VoicePerformanceRecordRow, VoicePerformanceTakeRow, Asset]:
    if not character_id:
        raise VoiceEnvironmentError("VOICE_STUDIO_CHARACTER_REQUIRED", "Choose a character first.")
    record = db.get(VoicePerformanceRecordRow, record_id)
    if not record or record.character_id != character_id:
        raise VoiceEnvironmentError("VOICE_PERFORMANCE_REQUIRED", "Voice Performance record not found.", status_code=404)
    take = db.get(VoicePerformanceTakeRow, take_id)
    if not take or take.record_id != record.id:
        raise VoiceEnvironmentError("VOICE_PERFORMANCE_REQUIRED", "Voice Performance take not found.", status_code=404)
    if take.status not in {"completed", "approved"} and record.approved_take_id != take.id:
        # Allow completed takes for preview even before approve, but prefer approved.
        if take.status not in {"completed", "approved"}:
            raise VoiceEnvironmentError(
                "VOICE_PERFORMANCE_REQUIRED",
                "Create or approve a Voice Performance before applying an environment.",
            )
    if not take.audio_asset_id:
        raise VoiceEnvironmentError("VOICE_PERFORMANCE_REQUIRED", "This take has no dry audio asset.")
    asset = db.get(Asset, take.audio_asset_id)
    if not asset or not asset.path or not Path(asset.path).exists():
        raise VoiceEnvironmentError("VOICE_PERFORMANCE_REQUIRED", "Dry voice audio file is missing.")
    return record, take, asset


def _register_audio_asset(
    db: Session,
    *,
    project_id: str,
    path: Path,
    tag: str,
    meta: dict[str, Any],
) -> Asset:
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tag=tag,
        kind="audio",
        filename=path.name,
        path=str(path),
        prompt_meta_json=json.dumps(meta),
    )
    db.add(asset)
    return asset


def create_render(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    performance_record_id: str,
    performance_take_id: str,
    environment_profile_id: str,
    preview: bool = False,
) -> VoiceEnvironmentRender:
    status = runtime_status()
    if not status["ok"]:
        raise VoiceEnvironmentError(
            "VOICE_ENVIRONMENT_RUNTIME_NOT_READY",
            "Voice Environment processing is unavailable. Required audio runtime is not ready.",
            details=status,
            status_code=503,
        )

    profile_row = db.get(VoiceEnvironmentProfileRow, environment_profile_id)
    if not profile_row or profile_row.project_id != project_id:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_PROFILE_INVALID", "Environment profile not found.", status_code=404)

    record, take, dry_asset = _require_take(
        db, character_id=character_id, record_id=performance_record_id, take_id=performance_take_id
    )
    profile = _profile_to_contract(profile_row)
    dsp_plan = compile_dsp_plan(profile.model_dump())

    render_id = str(uuid.uuid4())
    dry_path = Path(dry_asset.path)
    out_dir = dry_path.parent / "voice_environment" / render_id
    out_dir.mkdir(parents=True, exist_ok=True)
    processed_path = out_dir / ("preview.wav" if preview else "processed.wav")
    room_path = out_dir / "room_tone.wav"
    walla_path = out_dir / "walla.wav"

    row = VoiceEnvironmentRenderRow(
        id=render_id,
        project_id=project_id,
        character_id=character_id,
        performance_record_id=record.id,
        performance_take_id=take.id,
        environment_profile_id=profile_row.id,
        dry_audio_asset_id=dry_asset.id,
        status="processing",
        approved=False,
        dsp_plan_json=json.dumps(dsp_plan),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()

    try:
        # Preserve dry file immutably — copy into render folder for provenance only.
        dry_copy = out_dir / "dry_source.wav"
        if not dry_copy.exists():
            shutil.copy2(dry_asset.path, dry_copy)
        timing = process_environment(
            Path(dry_asset.path),
            processed_path,
            room_path,
            walla_path if profile.wallaPreset != "none" else None,
            dsp_plan,
        )
        processed_asset = _register_audio_asset(
            db,
            project_id=project_id,
            path=processed_path,
            tag="dialogue",
            meta={
                "source": "voice_environment",
                "role": "processed",
                "renderId": render_id,
                "dryAudioAssetId": dry_asset.id,
                "preview": preview,
            },
        )
        room_asset = _register_audio_asset(
            db,
            project_id=project_id,
            path=room_path,
            tag="room_tone",
            meta={"source": "voice_environment", "role": "room_tone", "renderId": render_id},
        )
        walla_asset = None
        if walla_path.exists():
            walla_asset = _register_audio_asset(
                db,
                project_id=project_id,
                path=walla_path,
                tag="ambience",
                meta={"source": "voice_environment", "role": "walla", "renderId": render_id},
            )
        row.processed_audio_asset_id = processed_asset.id
        row.room_tone_asset_id = room_asset.id
        row.walla_asset_id = walla_asset.id if walla_asset else None
        row.speech_start_offset_ms = timing.speechStartOffsetMs
        row.processing_latency_ms = timing.processingLatencyMs
        row.tail_duration_ms = timing.tailDurationMs
        row.dry_duration_ms = timing.dryDurationMs
        row.processed_duration_ms = timing.processedDurationMs
        row.status = "preview_ready" if preview else "completed"
        row.updated_at = _now()
        # Link on M410 record without mutating dry take.
        linkage = dict(record.timeline_linkage_json or {})
        env_link = {
            "environmentProfileId": profile_row.id,
            "environmentRenderId": render_id,
            "dryAudioAssetId": dry_asset.id,
            "processedAudioAssetId": processed_asset.id,
            "timing": timing.model_dump(),
            "preview": preview,
        }
        linkage["voiceEnvironment"] = env_link
        record.timeline_linkage_json = linkage
        record.updated_at = _now()
        db.commit()
        db.refresh(row)
        return _render_to_contract(row)
    except VoiceEnvironmentError:
        raise
    except Exception as exc:
        row.status = "failed"
        row.error_code = "VOICE_ENVIRONMENT_RENDER_FAILED" if not preview else "VOICE_ENVIRONMENT_PREVIEW_FAILED"
        row.error_message = str(exc)
        row.updated_at = _now()
        db.commit()
        raise VoiceEnvironmentError(
            row.error_code,
            "Environment processing failed. The dry performance was not changed.",
            details={"exception": str(exc)},
            status_code=500,
        )


def approve_render(db: Session, render_id: str, approved: bool = True) -> VoiceEnvironmentRender:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_RENDER_FAILED", "Environment render not found.", status_code=404)
    if row.status not in {"completed", "preview_ready"}:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_RENDER_FAILED", "Only completed or preview-ready renders can be approved.")
    row.approved = bool(approved)
    if approved and row.status == "preview_ready":
        row.status = "completed"
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _render_to_contract(row)


def apply_to_scene(db: Session, render_id: str, scene_id: str) -> dict[str, Any]:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_RENDER_FAILED", "Environment render not found.", status_code=404)
    scene = db.get(Scene, scene_id)
    if not scene or scene.project_id != row.project_id:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_SCENE_NOT_FOUND", "That scene could not be found.", status_code=404)
    profile = db.get(VoiceEnvironmentProfileRow, row.environment_profile_id)
    if profile:
        profile.scene_id = scene_id
        profile.updated_at = _now()
    scene_settings = {}
    # Persist association on profile; scene audio stays dry unless timeline handoff chooses processed.
    db.commit()
    return {
        "ok": True,
        "sceneId": scene_id,
        "environmentProfileId": row.environment_profile_id,
        "environmentRenderId": row.id,
        "sceneSettings": scene_settings,
    }


def prepare_timeline(db: Session, render_id: str, *, scene_id: Optional[str] = None, use_processed: bool = True) -> dict[str, Any]:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_TIMELINE_HANDOFF_FAILED", "Render not found.", status_code=404)
    profile = db.get(VoiceEnvironmentProfileRow, row.environment_profile_id)
    timing = VoiceEnvironmentTiming(
        speechStartOffsetMs=row.speech_start_offset_ms or 0.0,
        processingLatencyMs=row.processing_latency_ms or 0.0,
        tailDurationMs=row.tail_duration_ms or 0.0,
        dryDurationMs=row.dry_duration_ms or 0.0,
        processedDurationMs=row.processed_duration_ms or 0.0,
    )
    asset_id = row.processed_audio_asset_id if use_processed else row.dry_audio_asset_id
    clip = {
        "id": str(uuid.uuid4()),
        "kind": "dialogue",
        "track": "dialogue",
        "recordId": row.performance_record_id,
        "takeId": row.performance_take_id,
        "environmentProfileId": row.environment_profile_id,
        "environmentRenderId": row.id,
        "assetId": asset_id,
        "dryAudioAssetId": row.dry_audio_asset_id,
        "processedAudioAssetId": row.processed_audio_asset_id,
        "roomToneAssetId": row.room_tone_asset_id,
        "wallaAssetId": row.walla_asset_id,
        "characterId": row.character_id,
        "sceneId": scene_id or (profile.scene_id if profile else None),
        # Spoken start preserved; do not offset by processing latency.
        "startMs": 0,
        "speechStartOffsetMs": timing.speechStartOffsetMs,
        "durationMs": int(timing.dryDurationMs),
        "processedDurationMs": int(timing.processedDurationMs),
        "tailDurationMs": int(timing.tailDurationMs),
        "processingLatencyMs": int(timing.processingLatencyMs),
        "label": "Voice Environment mix" if use_processed else "Dry voice",
    }
    return {
        "ok": True,
        "handoff": {
            "projectId": row.project_id,
            "sceneId": clip["sceneId"],
            "characterId": row.character_id,
            "performanceRecordId": row.performance_record_id,
            "performanceTakeId": row.performance_take_id,
            "environmentProfileId": row.environment_profile_id,
            "environmentRenderId": row.id,
            "dryAudioAssetId": row.dry_audio_asset_id,
            "processedAudioAssetId": row.processed_audio_asset_id,
            "roomToneAssetId": row.room_tone_asset_id,
            "wallaAssetId": row.walla_asset_id,
            "timing": timing.model_dump(),
            "distancePreset": profile.distance_preset if profile else None,
            "directionPreset": profile.direction_preset if profile else None,
            "devicePreset": profile.device_preset if profile else None,
            "provenance": {"source": "voice_environment.prepare_timeline", "useProcessedMix": use_processed},
        },
        "clip": clip,
        "stems": {
            "dry": row.dry_audio_asset_id,
            "processed": row.processed_audio_asset_id,
            "roomTone": row.room_tone_asset_id,
            "walla": row.walla_asset_id,
        },
    }


def place_timeline(db: Session, render_id: str, *, scene_id: Optional[str] = None, use_processed: bool = True) -> dict[str, Any]:
    proposal = prepare_timeline(db, render_id, scene_id=scene_id, use_processed=use_processed)
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    assert row
    project = db.get(Project, row.project_id)
    if not project:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_TIMELINE_HANDOFF_FAILED", "Project not found.", status_code=404)
    settings = json.loads(project.settings_json or "{}")
    timeline = settings.setdefault("timeline", {})
    tracks = timeline.setdefault("dialogueTracks", [])
    track = next((t for t in tracks if t.get("id") == "dialogue-main"), None)
    if not track:
        track = {"id": "dialogue-main", "name": "Dialogue", "clips": []}
        tracks.append(track)
    # Replace prior clips for same record/render family without shifting spoken start.
    record_id = row.performance_record_id
    track["clips"] = [
        c
        for c in (track.get("clips") or [])
        if not (c.get("recordId") == record_id and c.get("environmentRenderId"))
    ]
    track["clips"].append(proposal["clip"])
    # Optional stem tracks
    for stem_id, stem_name, asset_key in (
        ("room-tone", "Room Tone", "roomToneAssetId"),
        ("walla", "Walla", "wallaAssetId"),
    ):
        asset_id = proposal["handoff"].get(asset_key) if asset_key.endswith("Id") else None
        # map keys
    room_id = row.room_tone_asset_id
    walla_id = row.walla_asset_id
    for stem_track_id, name, asset_id, duration_key in (
        ("room-tone-main", "Room Tone", room_id, "processedDurationMs"),
        ("walla-main", "Walla", walla_id, "processedDurationMs"),
    ):
        if not asset_id:
            continue
        stem_track = next((t for t in tracks if t.get("id") == stem_track_id), None)
        if not stem_track:
            stem_track = {"id": stem_track_id, "name": name, "clips": []}
            tracks.append(stem_track)
        stem_track["clips"] = [c for c in stem_track.get("clips") or [] if c.get("environmentRenderId") != row.id]
        stem_track["clips"].append(
            {
                "id": str(uuid.uuid4()),
                "kind": "ambience" if stem_track_id.startswith("walla") else "room_tone",
                "assetId": asset_id,
                "environmentRenderId": row.id,
                "startMs": 0,
                "durationMs": int(row.processed_duration_ms or row.dry_duration_ms or 0),
                "speechStartOffsetMs": row.speech_start_offset_ms,
            }
        )
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    project.updated_at = _now()
    record = db.get(VoicePerformanceRecordRow, row.performance_record_id)
    if record:
        linkage = dict(record.timeline_linkage_json or {})
        linkage["voiceEnvironment"] = {
            **(linkage.get("voiceEnvironment") or {}),
            "timelineClipId": proposal["clip"]["id"],
            "placed": True,
            "timing": proposal["handoff"]["timing"],
        }
        record.timeline_linkage_json = linkage
        record.updated_at = _now()
    db.commit()
    return {**proposal, "persisted": True}


def prepare_lipsync(db: Session, render_id: str, *, scene_id: Optional[str] = None) -> dict[str, Any]:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_LIPSYNC_HANDOFF_FAILED", "Render not found.", status_code=404)
    # Always dry timing for mouth sync.
    dry_asset_id = row.dry_audio_asset_id
    timing = {
        "speechStartOffsetMs": row.speech_start_offset_ms or 0.0,
        "processingLatencyMs": row.processing_latency_ms or 0.0,
        "tailDurationMs": row.tail_duration_ms or 0.0,
        "dryDurationMs": row.dry_duration_ms or 0.0,
        "processedDurationMs": row.processed_duration_ms or 0.0,
    }
    target_scene_id = scene_id
    record = db.get(VoicePerformanceRecordRow, row.performance_record_id)
    if not target_scene_id and record:
        target_scene_id = record.scene_id
    scene = db.get(Scene, target_scene_id) if target_scene_id else None
    if scene:
        scene.lipsync_audio_asset_id = dry_asset_id
        scene.lipsync_enabled = 1
        if record:
            record.lipsync_linkage_json = {
                "sceneId": target_scene_id,
                "recordId": record.id,
                "takeId": row.performance_take_id,
                "audioAssetId": dry_asset_id,
                "useDryTiming": True,
                "environmentRenderId": row.id,
                "timing": timing,
                "note": "Lip Sync uses dry voice timing; environment tails are ignored.",
            }
            record.updated_at = _now()
        db.commit()
    return {
        "ok": True,
        "handoff": {
            "projectId": row.project_id,
            "sceneId": target_scene_id,
            "characterId": row.character_id,
            "performanceRecordId": row.performance_record_id,
            "performanceTakeId": row.performance_take_id,
            "dryAudioAssetId": dry_asset_id,
            "timing": timing,
            "useDryTiming": True,
        },
    }


def open_audio_studio_payload(db: Session, render_id: str) -> dict[str, Any]:
    row = db.get(VoiceEnvironmentRenderRow, render_id)
    if not row:
        raise VoiceEnvironmentError("VOICE_ENVIRONMENT_AUDIO_STUDIO_HANDOFF_FAILED", "Render not found.", status_code=404)
    return {
        "ok": True,
        "workspace": "audiostudio",
        "handoff": {
            "projectId": row.project_id,
            "characterId": row.character_id,
            "environmentProfileId": row.environment_profile_id,
            "environmentRenderId": row.id,
            "dryAudioAssetId": row.dry_audio_asset_id,
            "processedAudioAssetId": row.processed_audio_asset_id,
            "roomToneAssetId": row.room_tone_asset_id,
            "wallaAssetId": row.walla_asset_id,
            "timing": {
                "speechStartOffsetMs": row.speech_start_offset_ms or 0.0,
                "processingLatencyMs": row.processing_latency_ms or 0.0,
                "tailDurationMs": row.tail_duration_ms or 0.0,
                "dryDurationMs": row.dry_duration_ms or 0.0,
                "processedDurationMs": row.processed_duration_ms or 0.0,
            },
            "approved": bool(row.approved),
            "provenance": {"source": "voice_environment.open_audio_studio"},
        },
    }


def recommend(db: Session, **kwargs: Any):
    return recommend_environment(db, **kwargs)
