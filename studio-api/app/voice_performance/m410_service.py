"""M4.10 Voice Performance persistence and workflow service."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..character_identity.models import VoiceProfileRow
from ..db import Asset, Job, Project, Scene
from ..scriptwriter.store import load_document
from .emotion_presets import SUPPORTED_VECTORS, get_preset, list_presets, normalize_mix
from .m410_errors import M410ErrorCode, raise_http_error
from .m410_models import M410_TABLES, VoicePerformanceRecordRow, VoicePerformanceTakeRow
from .m410_schemas import (
    DirectionMode,
    GenerateTakesBody,
    SceneBatchBody,
    VoicePerformanceRecordCreate,
    VoicePerformanceRecordOut,
    VoicePerformanceTakeOut,
)
from .runtime import index_tts2


def ensure_m410_tables() -> None:
    from ..db import Base, engine

    Base.metadata.create_all(bind=engine, tables=M410_TABLES)


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise raise_http_error(M410ErrorCode.PROJECT_NOT_FOUND)
    return project


def _record_or_404(db: Session, record_id: str) -> VoicePerformanceRecordRow:
    row = db.get(VoicePerformanceRecordRow, record_id)
    if not row:
        raise raise_http_error(M410ErrorCode.RECORD_NOT_FOUND)
    return row


def _take_or_404(db: Session, record_id: str, take_id: str) -> VoicePerformanceTakeRow:
    row = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id, VoicePerformanceTakeRow.id == take_id)
        .first()
    )
    if not row:
        raise raise_http_error(M410ErrorCode.TAKE_NOT_FOUND)
    return row


def _take_out(row: VoicePerformanceTakeRow) -> VoicePerformanceTakeOut:
    return VoicePerformanceTakeOut(
        id=row.id,
        recordId=row.record_id,
        takeNumber=row.take_number,
        label=row.label,
        jobId=row.job_id,
        audioAssetId=row.audio_asset_id,
        durationMs=row.duration_ms,
        status=row.status,  # type: ignore[arg-type]
        directionSnapshot=_loads(row.direction_snapshot_json, {}),
        generatedAt=_iso(row.generated_at),
        errorCode=row.error_code,
        errorMessage=row.error_message,
        createdAt=_iso(row.created_at) or "",
        updatedAt=_iso(row.updated_at) or "",
    )


def _record_out(db: Session, row: VoicePerformanceRecordRow, *, include_takes: bool = True) -> VoicePerformanceRecordOut:
    takes: list[VoicePerformanceTakeOut] = []
    if include_takes:
        take_rows = (
            db.query(VoicePerformanceTakeRow)
            .filter(VoicePerformanceTakeRow.record_id == row.id)
            .order_by(VoicePerformanceTakeRow.take_number.asc(), VoicePerformanceTakeRow.created_at.asc())
            .all()
        )
        takes = [_take_out(t) for t in take_rows]
    return VoicePerformanceRecordOut(
        id=row.id,
        projectId=row.project_id,
        sceneId=row.scene_id,
        scriptDocumentId=row.script_document_id,
        scriptElementId=row.script_element_id,
        characterId=row.character_id,
        voiceIdentityId=row.voice_identity_id,
        voiceIdentityVersion=row.voice_identity_version,
        dialogueText=row.dialogue_text,
        language=row.language,
        directionMode=row.direction_mode,  # type: ignore[arg-type]
        performancePlan=_loads(row.performance_plan_json, {}),
        emotionSource=row.emotion_source,
        emotionVector=_loads(row.emotion_vector_json, {}),
        emotionalReferenceAssetId=row.emotional_reference_asset_id,
        emotionalReferenceStrength=row.emotional_reference_strength,
        providerId=row.provider_id,
        providerVersion=row.provider_version,
        modelRevision=row.model_revision,
        approvedTakeId=row.approved_take_id,
        manualPlan=_loads(row.manual_plan_json, {}),
        codirectorPlan=_loads(row.codirector_plan_json, {}),
        sceneArcId=row.scene_arc_id,
        timelineLinkage=_loads(row.timeline_linkage_json, {}),
        lipsyncLinkage=_loads(row.lipsync_linkage_json, {}),
        consentAck=_loads(row.consent_ack_json, {}),
        createdAt=_iso(row.created_at) or "",
        updatedAt=_iso(row.updated_at) or "",
        takes=takes,
    )


def require_approved_voice_identity(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    voice_identity_id: str,
) -> VoiceProfileRow:
    voice = db.get(VoiceProfileRow, voice_identity_id)
    if not voice or voice.project_id != project_id or voice.character_profile_id != character_id:
        raise raise_http_error(M410ErrorCode.VOICE_IDENTITY_REQUIRED)
    if (voice.approval_status or "").lower() != "approved":
        raise raise_http_error(M410ErrorCode.VOICE_IDENTITY_REQUIRED)
    return voice


def _keyword_mix(dialogue: str, cues: str) -> dict[str, float]:
    text = f"{dialogue} {cues}".lower()
    weights = {
        "joy": 0.0,
        "sadness": 0.0,
        "anger": 0.0,
        "fear": 0.0,
        "surprise": 0.0,
        "disgust": 0.0,
        "contempt": 0.0,
    }
    keyword_map = {
        "joy": ("laugh", "smile", "grateful", "relief", "love", "delighted", "hope"),
        "sadness": ("cry", "miss", "sorry", "lost", "grief", "hurt", "goodbye"),
        "anger": ("damn", "furious", "angry", "snaps", "growls", "stop", "enough"),
        "fear": ("afraid", "panic", "please", "don't", "run", "terrified", "shaken"),
        "surprise": ("what", "wait", "suddenly", "whoa", "how", "why", "?"),
        "disgust": ("gross", "disgust", "filthy", "nasty", "revolting"),
        "contempt": ("pathetic", "ridiculous", "sure", "obviously", "hate", "beneath"),
    }
    for emotion, words in keyword_map.items():
        for word in words:
            if word in text:
                weights[emotion] += 1.0
    if "!" in dialogue:
        weights["anger"] += 0.5
        weights["surprise"] += 0.4
    if "..." in dialogue:
        weights["sadness"] += 0.4
    if dialogue.strip().endswith("?"):
        weights["surprise"] += 0.5
        weights["fear"] += 0.2
    if not any(weights.values()):
        weights["joy"] = 0.18
        weights["sadness"] = 0.18
        weights["fear"] = 0.12
        weights["surprise"] = 0.1
    return normalize_mix(weights)


def build_codirector_performance_plan(dialogue: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    parenthetical = str(context.get("parenthetical") or "")
    preset_id = str(context.get("presetId") or "").strip().lower()
    preset = get_preset(preset_id) if preset_id else None
    emotion_vector = preset.get("emotionVector") if preset else _keyword_mix(dialogue, parenthetical)
    pace = "steady"
    delivery = "grounded and cinematic"
    breath = "natural, unobtrusive breaths"
    notes: list[str] = []

    lowered = f"{dialogue} {parenthetical}".lower()
    if any(token in lowered for token in ("whisper", "quiet", "softly")):
        delivery = "intimate and restrained"
        breath = "close-mic soft breath"
        pace = "slower"
    elif any(token in lowered for token in ("shout", "yell", "snaps", "furious")):
        delivery = "forceful with sharper consonants"
        breath = "compressed breath between phrases"
        pace = "faster"
    elif any(token in lowered for token in ("pleading", "begging", "please")):
        delivery = "vulnerable and reaching"
        breath = "audible intake before key appeals"
        pace = "slower with emotional lift at line ends"

    if "..." in dialogue:
        notes.append("Let unfinished thoughts trail naturally.")
    if "!" in dialogue:
        notes.append("Land the strongest word at the end of each urgent phrase.")
    if re.search(r"\b[A-Z]{3,}\b", dialogue):
        notes.append("One emphasized word may peak slightly harder than the rest.")
    if parenthetical:
        notes.append(f"Honor parenthetical guidance: {parenthetical.strip()}.")
    if context.get("sceneProgression"):
        notes.append(f"Scene progression cue: {context['sceneProgression']}.")

    primary = max(emotion_vector.items(), key=lambda item: item[1])[0] if emotion_vector else "joy"
    return {
        "source": "codirector",
        "summary": f"Play the line with {primary}-led intention while keeping it editable.",
        "emotionVector": emotion_vector,
        "intensity": preset.get("intensity") if preset else ("medium" if "!" in dialogue else "low"),
        "delivery": preset.get("delivery") if preset else delivery,
        "pacing": preset.get("pacing") if preset else pace,
        "breath": preset.get("breath") if preset else breath,
        "notes": preset.get("notes") if preset else " ".join(notes).strip() or "Keep it natural and specific to the line.",
        "editable": True,
    }


def create_record(db: Session, body: VoicePerformanceRecordCreate) -> VoicePerformanceRecordOut:
    _project_or_404(db, body.projectId)
    voice = require_approved_voice_identity(
        db,
        project_id=body.projectId,
        character_id=body.characterId,
        voice_identity_id=body.voiceIdentityId,
    )
    if body.scriptDocumentId:
        doc = load_document(db, body.scriptDocumentId)
        if not doc or doc.projectId != body.projectId:
            raise raise_http_error(M410ErrorCode.SCRIPT_DOCUMENT_NOT_FOUND)
        if body.scriptElementId and not any(el.id == body.scriptElementId for el in doc.elements):
            raise raise_http_error(M410ErrorCode.SCRIPT_ELEMENT_NOT_FOUND)
    if body.sceneId:
        scene = db.get(Scene, body.sceneId)
        if not scene or scene.project_id != body.projectId:
            raise raise_http_error(M410ErrorCode.SCENE_NOT_FOUND)
    codirector_plan = body.codirectorPlan or build_codirector_performance_plan(
        body.dialogueText,
        {
            "sceneId": body.sceneId,
            "scriptElementId": body.scriptElementId,
            "characterId": body.characterId,
            "sceneArcId": body.sceneArcId,
        },
    )
    performance_plan = body.performancePlan or (
        codirector_plan if body.directionMode == "codirector" else body.manualPlan or {}
    )
    now = _now()
    row = VoicePerformanceRecordRow(
        id=str(uuid.uuid4()),
        project_id=body.projectId,
        scene_id=body.sceneId,
        script_document_id=body.scriptDocumentId,
        script_element_id=body.scriptElementId,
        character_id=body.characterId,
        voice_identity_id=body.voiceIdentityId,
        voice_identity_version=body.voiceIdentityVersion or str(voice.version_number),
        dialogue_text=body.dialogueText,
        language=body.language,
        direction_mode=body.directionMode,
        performance_plan_json=performance_plan,
        emotion_source=body.emotionSource or ("preset" if body.emotionVector else "codirector"),
        emotion_vector_json=body.emotionVector or _loads(codirector_plan.get("emotionVector"), {}),
        emotional_reference_asset_id=body.emotionalReferenceAssetId,
        emotional_reference_strength=body.emotionalReferenceStrength,
        provider_id=body.providerId,
        provider_version=body.providerVersion,
        model_revision=body.modelRevision,
        approved_take_id=body.approvedTakeId,
        manual_plan_json=body.manualPlan,
        codirector_plan_json=codirector_plan,
        scene_arc_id=body.sceneArcId,
        timeline_linkage_json=body.timelineLinkage,
        lipsync_linkage_json=body.lipsyncLinkage,
        consent_ack_json=body.consentAck,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _record_out(db, row)


def get_record(db: Session, record_id: str) -> VoicePerformanceRecordOut:
    return _record_out(db, _record_or_404(db, record_id))


def list_records(db: Session, project_id: str) -> list[VoicePerformanceRecordOut]:
    _project_or_404(db, project_id)
    rows = (
        db.query(VoicePerformanceRecordRow)
        .filter(VoicePerformanceRecordRow.project_id == project_id)
        .order_by(VoicePerformanceRecordRow.updated_at.desc(), VoicePerformanceRecordRow.created_at.desc())
        .all()
    )
    return [_record_out(db, row) for row in rows]


def apply_performance_plan(
    db: Session,
    record_id: str,
    performance_plan: dict[str, Any],
    *,
    mode: DirectionMode | None = None,
    emotion_source: str | None = None,
    emotion_vector: dict[str, float] | None = None,
) -> VoicePerformanceRecordOut:
    row = _record_or_404(db, record_id)
    active_mode = mode or row.direction_mode
    row.performance_plan_json = performance_plan
    if active_mode == "manual":
        row.manual_plan_json = performance_plan
    else:
        row.codirector_plan_json = performance_plan
    if mode:
        row.direction_mode = mode
    if emotion_source is not None:
        row.emotion_source = emotion_source
    if emotion_vector is not None:
        row.emotion_vector_json = emotion_vector
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _record_out(db, row)


def set_direction_mode(
    db: Session,
    record_id: str,
    direction_mode: DirectionMode,
    *,
    performance_plan: dict[str, Any] | None = None,
) -> VoicePerformanceRecordOut:
    row = _record_or_404(db, record_id)
    if direction_mode not in ("codirector", "manual"):
        raise raise_http_error(M410ErrorCode.INVALID_DIRECTION_MODE)
    row.direction_mode = direction_mode
    if performance_plan:
        row.performance_plan_json = performance_plan
        if direction_mode == "manual":
            row.manual_plan_json = performance_plan
        else:
            row.codirector_plan_json = performance_plan
    else:
        row.performance_plan_json = (
            _loads(row.manual_plan_json, {})
            if direction_mode == "manual"
            else _loads(row.codirector_plan_json, {}) or _loads(row.performance_plan_json, {})
        )
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _record_out(db, row)


def create_takes(db: Session, record_id: str, body: GenerateTakesBody) -> dict[str, Any]:
    row = _record_or_404(db, record_id)
    voice = require_approved_voice_identity(
        db,
        project_id=row.project_id,
        character_id=row.character_id,
        voice_identity_id=row.voice_identity_id,
    )
    runtime = index_tts2.runtime_status()
    existing = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id)
        .order_by(VoicePerformanceTakeRow.take_number.desc())
        .first()
    )
    next_take_number = (existing.take_number if existing else 0) + 1
    created: list[VoicePerformanceTakeRow] = []
    for offset in range(body.count):
        take_number = next_take_number + offset
        label = body.labels[offset] if offset < len(body.labels) else f"Take {take_number}"
        take = VoicePerformanceTakeRow(
            id=str(uuid.uuid4()),
            record_id=row.id,
            take_number=take_number,
            label=label,
            status="queued",
            direction_snapshot_json=_loads(row.performance_plan_json, {}),
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(take)
        db.flush()
        emotion_ref_path = ""
        if row.emotional_reference_asset_id:
            emo_asset = db.get(Asset, row.emotional_reference_asset_id)
            if emo_asset and emo_asset.path and Path(emo_asset.path).is_file():
                emotion_ref_path = str(emo_asset.path)
        queued = index_tts2.generate_take(
            db,
            project_id=row.project_id,
            scene_id=row.scene_id,
            record_id=row.id,
            take_id=take.id,
            dialogue_text=row.dialogue_text,
            language=row.language,
            voice_identity_id=voice.id,
            performance_plan=_loads(row.performance_plan_json, {}),
            direction_snapshot=_loads(row.performance_plan_json, {}),
            take_number=take_number,
            label=label,
            emotion_source=row.emotion_source,
            emotion_vector=_loads(row.emotion_vector_json, {}),
            emotion_audio_path=emotion_ref_path or None,
            emotional_reference_strength=row.emotional_reference_strength,
        )
        take.job_id = queued.get("jobId")
        take.status = queued.get("status") or "queued"
        take.error_code = queued.get("errorCode")
        take.error_message = queued.get("errorMessage")
        if queued.get("audioAssetId"):
            take.audio_asset_id = queued["audioAssetId"]
        if queued.get("durationMs") is not None:
            take.duration_ms = int(queued["durationMs"])
        if take.status in ("completed", "failed", "cancelled"):
            take.generated_at = _now()
        take.updated_at = _now()
        row.provider_version = queued.get("providerVersion") or runtime.get("providerVersion")
        row.model_revision = queued.get("modelRevision") or runtime.get("modelRevision")
        created.append(take)
    row.updated_at = _now()
    db.commit()
    return {
        "ok": True,
        "recordId": row.id,
        "providerId": row.provider_id,
        "providerVersion": row.provider_version,
        "modelRevision": row.model_revision,
        "takes": [_take_out(t).model_dump() for t in created],
        "mock": False,
    }


def poll_take_status(db: Session, record_id: str) -> list[VoicePerformanceTakeOut]:
    _record_or_404(db, record_id)
    take_rows = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id)
        .order_by(VoicePerformanceTakeRow.take_number.asc(), VoicePerformanceTakeRow.created_at.asc())
        .all()
    )
    dirty = False
    for take in take_rows:
        if not take.job_id or take.status in ("approved", "rejected"):
            continue
        job = db.get(Job, take.job_id)
        if not job:
            continue
        take_dirty = False
        result = _loads(job.preview_json, {})
        new_status = str(job.status or take.status).lower()
        if new_status in ("queued", "running", "completed", "failed", "cancelled") and take.status != new_status:
            take.status = new_status
            dirty = True
            take_dirty = True
        audio_asset_id = result.get("audioAssetId") or result.get("outputAssetId")
        if audio_asset_id and take.audio_asset_id != audio_asset_id:
            take.audio_asset_id = audio_asset_id
            dirty = True
            take_dirty = True
        duration_ms = result.get("durationMs")
        if duration_ms is not None and take.duration_ms != int(duration_ms):
            take.duration_ms = int(duration_ms)
            dirty = True
            take_dirty = True
        error_code = result.get("errorCode")
        error_message = result.get("errorMessage") or (job.message if new_status == "failed" else None)
        if error_code != take.error_code:
            take.error_code = error_code
            dirty = True
            take_dirty = True
        if error_message != take.error_message:
            take.error_message = error_message
            dirty = True
            take_dirty = True
        if new_status in ("completed", "failed", "cancelled") and not take.generated_at:
            take.generated_at = job.updated_at or _now()
            dirty = True
            take_dirty = True
        if take_dirty:
            take.updated_at = _now()
    if dirty:
        db.commit()
    return [_take_out(t) for t in take_rows]


def list_takes(db: Session, record_id: str) -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    takes = poll_take_status(db, record_id)
    return {
        "recordId": record_id,
        "approvedTakeId": record.approved_take_id,
        "takes": [take.model_dump() for take in takes],
        "mock": False,
    }


def approve_take(db: Session, record_id: str, take_id: str, *, approved_by: str = "owner") -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    target = _take_or_404(db, record_id, take_id)
    if target.status not in ("completed", "approved"):
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    rows = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id)
        .order_by(VoicePerformanceTakeRow.take_number.asc())
        .all()
    )
    for row in rows:
        if row.id == take_id:
            row.status = "approved"
        elif row.status == "approved":
            row.status = "completed"
        row.updated_at = _now()
    record.approved_take_id = take_id
    record.updated_at = _now()
    db.commit()
    return {
        "ok": True,
        "recordId": record_id,
        "takeId": take_id,
        "approvedBy": approved_by,
        "approvedTakeId": take_id,
        "takes": [_take_out(row).model_dump() for row in rows],
        "mock": False,
    }


def compare_takes(db: Session, record_id: str, take_ids: list[str] | None = None) -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    rows = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id)
        .order_by(VoicePerformanceTakeRow.take_number.asc())
        .all()
    )
    if take_ids:
        wanted = set(take_ids)
        rows = [row for row in rows if row.id in wanted]
    return {
        "ok": True,
        "recordId": record_id,
        "approvedTakeId": record.approved_take_id,
        "comparison": {
            "dialogueText": record.dialogue_text,
            "takeCount": len(rows),
            "takes": [
                {
                    "id": row.id,
                    "takeNumber": row.take_number,
                    "label": row.label,
                    "status": row.status,
                    "durationMs": row.duration_ms,
                    "audioAssetId": row.audio_asset_id,
                    "isApproved": row.id == record.approved_take_id,
                }
                for row in rows
            ],
        },
        "mock": False,
    }


def _approved_take_and_asset(db: Session, record: VoicePerformanceRecordRow) -> tuple[VoicePerformanceTakeRow, Asset | None]:
    if not record.approved_take_id:
        raise raise_http_error(M410ErrorCode.APPROVED_TAKE_REQUIRED)
    take = _take_or_404(db, record.id, record.approved_take_id)
    asset = db.get(Asset, take.audio_asset_id) if take.audio_asset_id else None
    return take, asset


def _existing_dialogue_clips(track: dict[str, Any], record: VoicePerformanceRecordRow) -> list[dict[str, Any]]:
    clips = track.get("clips") or []
    return [
        clip
        for clip in clips
        if clip.get("recordId") == record.id
        or (
            record.scene_id
            and clip.get("sceneId") == record.scene_id
            and clip.get("scriptElementId") == record.script_element_id
            and clip.get("characterId") == record.character_id
        )
    ]


def prepare_timeline_dialogue(
    db: Session,
    record_id: str,
    *,
    track_id: str = "dialogue-main",
    start_ms: int = 0,
) -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    project = _project_or_404(db, record.project_id)
    take, _asset = _approved_take_and_asset(db, record)
    settings = _loads(project.settings_json or "{}", {})
    timeline = settings.setdefault("timeline", {})
    tracks = timeline.setdefault("dialogueTracks", [])
    track = next((t for t in tracks if t.get("id") == track_id), None) or {
        "id": track_id,
        "name": "Dialogue",
        "clips": [],
    }
    existing = _existing_dialogue_clips(track, record)
    duration_ms = int(take.duration_ms or 0)
    clip = {
        "id": str(uuid.uuid4()),
        "kind": "dialogue",
        "track": "dialogue",
        "recordId": record.id,
        "takeId": take.id,
        "assetId": take.audio_asset_id,
        "characterId": record.character_id,
        "voiceIdentityId": record.voice_identity_id,
        "sceneId": record.scene_id,
        "scriptDocumentId": record.script_document_id,
        "scriptElementId": record.script_element_id,
        "startMs": int(start_ms),
        "durationMs": duration_ms,
        "label": take.label,
    }
    return {
        "ok": True,
        "recordId": record_id,
        "approvedTakeId": take.id,
        "trackId": track_id,
        "wouldReplace": bool(existing),
        "existingClipIds": [clip_row.get("id") for clip_row in existing],
        "clip": clip,
        "mock": False,
    }


def place_timeline_dialogue(
    db: Session,
    record_id: str,
    *,
    track_id: str = "dialogue-main",
    start_ms: int = 0,
    confirm_replace: bool = False,
) -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    proposal = prepare_timeline_dialogue(db, record_id, track_id=track_id, start_ms=start_ms)
    if proposal["wouldReplace"] and not confirm_replace:
        raise raise_http_error(M410ErrorCode.TIMELINE_REPLACE_CONFIRM_REQUIRED)
    project = _project_or_404(db, record.project_id)
    settings = _loads(project.settings_json or "{}", {})
    timeline = settings.setdefault("timeline", {})
    tracks = timeline.setdefault("dialogueTracks", [])
    track = next((t for t in tracks if t.get("id") == track_id), None)
    if not track:
        track = {"id": track_id, "name": "Dialogue", "clips": []}
        tracks.append(track)
    existing = _existing_dialogue_clips(track, record)
    if existing:
        existing_ids = {clip["id"] for clip in existing if clip.get("id")}
        track["clips"] = [clip for clip in track.get("clips") or [] if clip.get("id") not in existing_ids]
    track.setdefault("clips", []).append(proposal["clip"])
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    project.updated_at = _now()
    record.timeline_linkage_json = {
        "trackId": track_id,
        "clipIds": [proposal["clip"]["id"]],
        "approvedTakeId": proposal["approvedTakeId"],
        "existingClipIdsReplaced": proposal["existingClipIds"] if confirm_replace else [],
    }
    record.updated_at = _now()
    db.commit()
    return {
        **proposal,
        "persisted": True,
        "timelineLinkage": _loads(record.timeline_linkage_json, {}),
    }


def prepare_lipsync(
    db: Session,
    record_id: str,
    *,
    confirm: bool = True,
    set_scene_audio_asset: bool = True,
) -> dict[str, Any]:
    record = _record_or_404(db, record_id)
    take, _asset = _approved_take_and_asset(db, record)
    scene = db.get(Scene, record.scene_id) if record.scene_id else None
    if record.scene_id and not scene:
        raise raise_http_error(M410ErrorCode.SCENE_NOT_FOUND)
    would_replace = False
    if scene:
        if scene.lipsync_audio_asset_id and scene.lipsync_audio_asset_id != take.audio_asset_id:
            would_replace = True
        if set_scene_audio_asset and scene.audio_asset_id and scene.audio_asset_id != take.audio_asset_id:
            would_replace = True
    if would_replace and not confirm:
        raise raise_http_error(M410ErrorCode.CONFIRM_REQUIRED)
    linkage = {
        "sceneId": record.scene_id,
        "recordId": record.id,
        "takeId": take.id,
        "audioAssetId": take.audio_asset_id,
        "setSceneAudioAsset": bool(scene and set_scene_audio_asset),
        "updatedScene": bool(scene),
        "wouldReplace": would_replace,
    }
    if scene:
        scene.lipsync_audio_asset_id = take.audio_asset_id
        scene.lipsync_enabled = 1
        if set_scene_audio_asset:
            scene.audio_asset_id = take.audio_asset_id
        record.lipsync_linkage_json = linkage
        record.updated_at = _now()
        db.commit()
    return {"ok": True, "recordId": record.id, "lipsyncLinkage": linkage, "mock": False}


def _scene_progression_plan(index: int, total: int, scene_arc_id: str | None) -> dict[str, Any]:
    if total <= 1:
        label = "standalone beat"
    else:
        ratio = index / max(total - 1, 1)
        if ratio <= 0.2:
            label = "opening pressure"
        elif ratio <= 0.5:
            label = "rising complication"
        elif ratio <= 0.8:
            label = "turning pressure"
        else:
            label = "late-scene payoff"
    return {"index": index + 1, "total": total, "sceneProgression": label, "sceneArcId": scene_arc_id}


def create_scene_batch(db: Session, body: SceneBatchBody) -> dict[str, Any]:
    _project_or_404(db, body.projectId)
    created = []
    progression = []
    total = len(body.items)
    for index, item in enumerate(body.items):
        progression_plan = _scene_progression_plan(index, total, item.sceneArcId)
        progression.append(progression_plan)
        generated_plan = build_codirector_performance_plan(
            item.dialogueText,
            {**item.context, **progression_plan, "sceneId": item.sceneId, "scriptElementId": item.scriptElementId},
        )
        created.append(
            create_record(
                db,
                VoicePerformanceRecordCreate(
                    projectId=body.projectId,
                    sceneId=item.sceneId,
                    scriptDocumentId=item.scriptDocumentId,
                    scriptElementId=item.scriptElementId,
                    characterId=item.characterId,
                    voiceIdentityId=item.voiceIdentityId,
                    voiceIdentityVersion=item.voiceIdentityVersion,
                    dialogueText=item.dialogueText,
                    language=item.language,
                    directionMode=item.directionMode,
                    performancePlan=generated_plan if item.directionMode == "codirector" else {},
                    codirectorPlan=generated_plan,
                    sceneArcId=item.sceneArcId,
                ),
            )
        )
    return {
        "ok": True,
        "projectId": body.projectId,
        "sceneProgressionPlans": progression,
        "records": [record.model_dump() for record in created],
        "mock": False,
    }


def get_runtime_status() -> dict[str, Any]:
    return index_tts2.runtime_status()


def install_runtime(*, confirm: bool, confirm_download_models: bool = False) -> dict[str, Any]:
    if not confirm:
        raise raise_http_error(M410ErrorCode.CONFIRM_REQUIRED)
    return index_tts2.install_runtime(
        confirm=confirm,
        confirm_download_models=confirm_download_models,
    )


def verify_runtime() -> dict[str, Any]:
    return index_tts2.verify_runtime()


def get_capabilities() -> dict[str, Any]:
    runtime = index_tts2.runtime_status()
    try:
        capability_metadata = index_tts2.get_index_tts2_runtime().capability_metadata()
    except Exception:
        capability_metadata = {
            "language": {
                "english": "recommended",
                "chinese": "recommended",
                "accent": "experimental",
                "mixed_language": "not_recommended",
            },
            "performance": {"emotion": "strong", "voice_cloning": "strong"},
        }
    language = capability_metadata.get("language") or {}
    status = "available" if runtime.get("ready") else "requires_setup"
    return {
        "ok": True,
        "providerId": runtime["providerId"],
        "providerVersion": runtime["providerVersion"],
        "status": status,
        "installed": bool(runtime.get("installed")),
        "ready": bool(runtime.get("ready")),
        "supportsLiveGeneration": bool(runtime.get("ready")),
        "supportsEmotionVectors": True,
        "supportedEmotionVectors": list(SUPPORTED_VECTORS),
        "directionModes": ["codirector", "manual"],
        "presetsAvailable": len(list_presets()),
        "message": runtime["message"],
        "language": language,
        "capabilityMetadata": capability_metadata,
        "mock": False,
    }


def get_emotion_presets() -> dict[str, Any]:
    return {"ok": True, "presets": list_presets(), "mock": False}
