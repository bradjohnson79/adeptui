"""M4.10 Voice Performance persistence and workflow service."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..character_identity.models import CharacterProfileRow, VoiceProfileRow
from ..character_identity.spoken_pronunciation import apply_spoken_pronunciations, entries_from_voice
from ..character_identity.voice_runtime import (
    generate_approved_voice_speech,
    qwen_speech_compatible,
    _register_asset,
)
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
from .mannerism_cues import (
    extract_mannerisms_from_direction,
    merge_structured_cues,
    sanitize_for_tts,
    vocabulary_snapshot as mannerism_vocabulary_snapshot,
)
from .mannerism_events import (
    MANNERISM_FAIL_MESSAGE,
    apply_mannerisms_to_take_audio,
    cue_needs_discrete_event,
)



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


def _profile_visible_in_project(profile: CharacterProfileRow | None, project_id: str) -> bool:
    if profile is None:
        return False
    return profile.project_id == project_id or bool(getattr(profile, "is_global", False))


def require_approved_voice_identity(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    voice_identity_id: str,
) -> VoiceProfileRow:
    profile = db.get(CharacterProfileRow, character_id)
    voice = db.get(VoiceProfileRow, voice_identity_id)
    if (
        not voice
        or not _profile_visible_in_project(profile, project_id)
        or voice.character_profile_id != character_id
    ):
        raise raise_http_error(M410ErrorCode.VOICE_IDENTITY_REQUIRED)
    if (voice.approval_status or "").lower() != "approved":
        raise raise_http_error(M410ErrorCode.VOICE_IDENTITY_REQUIRED)
    return voice


def resolve_canonical_approved_voice(
    db: Session,
    *,
    project_id: str,
    character_id: str,
    voice_identity_id: str | None = None,
) -> VoiceProfileRow:
    profile = db.get(CharacterProfileRow, character_id)
    active_id = str(getattr(profile, "active_voice_profile_id", "") or "").strip() if profile else ""
    chosen_id = active_id or str(voice_identity_id or "").strip()
    if not chosen_id:
        raise raise_http_error(M410ErrorCode.VOICE_IDENTITY_REQUIRED)
    return require_approved_voice_identity(
        db,
        project_id=project_id,
        character_id=character_id,
        voice_identity_id=chosen_id,
    )


def _performance_instruct(plan: dict[str, Any] | None) -> str:
    plan = plan or {}
    return " ".join(
        str(plan.get(key) or "").strip()
        for key in ("summary", "delivery", "notes")
        if str(plan.get(key) or "").strip()
    ).strip()


def _wav_duration_ms(path: str) -> int | None:
    import wave

    try:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate() or 1
            return int(1000 * frames / rate)
    except Exception:
        return None




def _plan_mannerism_cues(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    plan = plan or {}
    raw = plan.get("mannerismCues") or plan.get("mannerisms") or []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return merge_structured_cues(raw, [])


def _attach_mannerisms_to_plan(plan: dict[str, Any] | None, cues: list[dict[str, Any]], notices: list[str] | None = None) -> dict[str, Any]:
    out = dict(plan or {})
    out["mannerismCues"] = cues
    if notices:
        existing = list(out.get("mannerismNotices") or [])
        for n in notices:
            if n not in existing:
                existing.append(n)
        out["mannerismNotices"] = existing
    return out


def _sanitize_record_dialogue(row: VoicePerformanceRecordRow) -> dict[str, Any]:
    plan = _loads(row.performance_plan_json, {})
    structured = _plan_mannerism_cues(plan)
    result = sanitize_for_tts(str(row.dialogue_text or ""), structured_cues=structured)
    # Persist structured cues back onto the active plan so regenerate/compare retain them
    updated = _attach_mannerisms_to_plan(plan, result["mannerismCues"], result.get("notices"))
    row.performance_plan_json = updated
    if row.direction_mode == "manual":
        manual = _loads(row.manual_plan_json, {})
        row.manual_plan_json = _attach_mannerisms_to_plan(manual, result["mannerismCues"], result.get("notices"))
    else:
        cd = _loads(row.codirector_plan_json, {})
        row.codirector_plan_json = _attach_mannerisms_to_plan(cd, result["mannerismCues"], result.get("notices"))
    return result

def _generate_qwen_take(
    db: Session,
    *,
    project_id: str,
    scene_id: str | None,
    record_id: str,
    take_id: str,
    voice: VoiceProfileRow,
    dialogue_text: str,
    performance_plan: dict[str, Any],
    take_number: int,
    label: str,
) -> dict[str, Any]:
    produced = generate_approved_voice_speech(
        db,
        project_id=project_id,
        voice=voice,
        text=dialogue_text,
        seed=take_number,
        performance_instruct=_performance_instruct(performance_plan),
    )
    output_path = str(produced.get("path") or "")
    duration_ms = _wav_duration_ms(output_path) if output_path else None
    audio_asset_id = _register_asset(
        db,
        project_id,
        Path(output_path),
        kind="audio",
        name=label or f"Take {take_number}",
        tag="dialogue",
        extra_meta={
            "source": "voice_performance.m410.qwen3-tts",
            "voiceProfileId": voice.id,
            "recordId": record_id,
            "takeId": take_id,
            "engine": "qwen3-tts",
            "warmWorker": True,
        },
    )
    job = Job(
        id=take_id,
        project_id=project_id,
        scene_id=scene_id,
        kind="voice_performance.qwen3-tts",
        status="completed",
        progress=1.0,
        message="completed",
        preview_json=json.dumps(
            {
                "audioAssetId": audio_asset_id,
                "durationMs": duration_ms,
                "outputPath": output_path,
                "voiceProfileId": voice.id,
                "engine": "qwen3-tts",
                "warmWorker": True,
                "completeMs": produced.get("complete_ms"),
            }
        ),
        params_json=json.dumps(
            {
                "voiceProfileId": voice.id,
                "recordId": record_id,
                "takeId": take_id,
                "engine": "qwen3-tts",
            }
        ),
        output_path=output_path,
        updated_at=_now(),
    )
    db.merge(job)
    db.commit()
    return {
        "ok": True,
        "jobId": take_id,
        "status": "completed",
        "audioAssetId": audio_asset_id,
        "durationMs": duration_ms,
        "providerId": "qwen3-tts",
        "providerVersion": voice.model_id or "Qwen3-TTS-1.7B",
        "modelRevision": voice.model_id,
        "engine": "qwen3-tts",
        "warmWorker": True,
        "voiceProfileId": voice.id,
        "completeMs": produced.get("complete_ms"),
        "outputPath": output_path,
    }


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
    # Structured mannerisms from brackets in dialogue + natural-language CD/parenthetical direction
    direction_blob = " ".join(
        str(x)
        for x in (
            dialogue,
            parenthetical,
            context.get("direction"),
            context.get("instruction"),
            context.get("notes"),
            context.get("performanceDirection"),
        )
        if x
    )
    mannerism_cues = extract_mannerisms_from_direction(direction_blob)
    bracketed = sanitize_for_tts(dialogue)
    mannerism_cues = merge_structured_cues(mannerism_cues, bracketed["mannerismCues"])
    if mannerism_cues:
        labels = ", ".join(c.get("label") or c.get("id") for c in mannerism_cues)
        notes.append(f"Mannerism cues: {labels}.")
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
        "mannerismCues": mannerism_cues,
        "mannerismNotices": bracketed.get("notices") or [],
    }


def create_record(db: Session, body: VoicePerformanceRecordCreate) -> VoicePerformanceRecordOut:
    _project_or_404(db, body.projectId)
    voice = resolve_canonical_approved_voice(
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
    # Normalize typed bracket cues into structured mannerisms; keep original dialogueText for authoring
    _san = sanitize_for_tts(
        body.dialogueText,
        structured_cues=merge_structured_cues(
            _plan_mannerism_cues(performance_plan),
            _plan_mannerism_cues(codirector_plan),
        ),
    )
    performance_plan = _attach_mannerisms_to_plan(performance_plan, _san["mannerismCues"], _san.get("notices"))
    if body.directionMode == "codirector":
        codirector_plan = _attach_mannerisms_to_plan(codirector_plan, _san["mannerismCues"], _san.get("notices"))
    now = _now()
    row = VoicePerformanceRecordRow(
        id=str(uuid.uuid4()),
        project_id=body.projectId,
        scene_id=body.sceneId,
        script_document_id=body.scriptDocumentId,
        script_element_id=body.scriptElementId,
        character_id=body.characterId,
        voice_identity_id=voice.id,
        voice_identity_version=body.voiceIdentityVersion or str(voice.version_number),
        dialogue_text=body.dialogueText,
        language=body.language,
        direction_mode=body.directionMode,
        performance_plan_json=performance_plan,
        emotion_source=body.emotionSource or ("preset" if body.emotionVector else "codirector"),
        emotion_vector_json=body.emotionVector or _loads(codirector_plan.get("emotionVector"), {}),
        emotional_reference_asset_id=body.emotionalReferenceAssetId,
        emotional_reference_strength=body.emotionalReferenceStrength,
        provider_id="qwen3-tts" if qwen_speech_compatible(voice) else body.providerId,
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


def _apply_generated_take(
    take: VoicePerformanceTakeRow,
    row: VoicePerformanceRecordRow,
    queued: dict[str, Any],
    runtime: dict[str, Any],
    *,
    use_qwen: bool,
    mannerism_meta: dict[str, Any] | None = None,
) -> None:
    take.job_id = queued.get("jobId")
    take.status = queued.get("status") or "queued"
    take.error_code = queued.get("errorCode")
    take.error_message = queued.get("errorMessage")
    if queued.get("audioAssetId"):
        take.audio_asset_id = queued["audioAssetId"]
    if queued.get("durationMs") is not None:
        take.duration_ms = int(queued["durationMs"])
    # Persist mannerism event / stitch metadata on the take direction snapshot (one Take player).
    if mannerism_meta:
        snap = dict(_loads(take.direction_snapshot_json, {}) or {})
        snap["mannerismEvents"] = mannerism_meta.get("mannerismEvents") or []
        snap["mannerismSatisfied"] = bool(mannerism_meta.get("mannerismSatisfied", True))
        snap["mannerismFailureMessage"] = mannerism_meta.get("mannerismFailureMessage")
        snap["mannerismStitchedAssetId"] = mannerism_meta.get("mannerismStitchedAssetId")
        snap["mannerismStitchedPath"] = mannerism_meta.get("mannerismStitchedPath")
        snap["mannerismSpeakerMatched"] = bool(mannerism_meta.get("speakerMatched", False))
        snap["mannerismSpeakerMatchNote"] = mannerism_meta.get("speakerMatchNote")
        snap["mannerismGenerator"] = mannerism_meta.get("generator")
        if mannerism_meta.get("mannerismStitchedAssetId"):
            take.audio_asset_id = mannerism_meta["mannerismStitchedAssetId"]
            if (mannerism_meta.get("stitch") or {}).get("durationMs") is not None:
                take.duration_ms = int(mannerism_meta["stitch"]["durationMs"])
        # Honest: if cue requested but event failed, keep dialogue playable but do NOT claim cue satisfied.
        if not snap.get("mannerismSatisfied") and mannerism_meta.get("mannerismFailureMessage"):
            notices = list(snap.get("mannerismNotices") or [])
            msg = str(mannerism_meta.get("mannerismFailureMessage") or MANNERISM_FAIL_MESSAGE)
            if msg not in notices:
                notices.append(msg)
            snap["mannerismNotices"] = notices
        take.direction_snapshot_json = snap
    if take.status in ("completed", "failed", "cancelled"):
        take.generated_at = _now()
    take.updated_at = _now()
    row.provider_id = queued.get("providerId") or ("qwen3-tts" if use_qwen else row.provider_id)
    row.provider_version = queued.get("providerVersion") or runtime.get("providerVersion")
    row.model_revision = queued.get("modelRevision") or runtime.get("modelRevision")


def _generate_elevenlabs_take(
    db: Session,
    *,
    row: VoicePerformanceRecordRow,
    voice: Any,
    body: GenerateTakesBody,
    dialogue_text: str,
) -> dict[str, Any]:
    from ..character_identity.service import provider_voice_binding
    from ..generation_tools.lineage import register_derived_asset
    from ..hosted_providers.adapters.elevenlabs_routed import generate_tts_routed

    binding = provider_voice_binding(voice)
    voice_id = str((binding or {}).get("providerVoiceId") or "").strip()
    if not voice_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CHARACTER_VOICE_NOT_ASSIGNED",
                "error": "CHARACTER_VOICE_NOT_ASSIGNED",
                "message": "This character does not have an ElevenLabs voice yet. Choose a voice, then save it to the character.",
                "silentFallback": False,
                "mock": False,
            },
        )
    model_id = str((binding or {}).get("providerModelId") or getattr(body, "modelId", None) or "").strip() or None
    el = generate_tts_routed(
        text=dialogue_text,
        voice_id=voice_id,
        model_id=model_id,
        surface="voice-studio.generate",
    )
    proven = dict(el.get("provenance") or {})
    asset = register_derived_asset(
        db,
        project_id=row.project_id,
        source_path=el["path"],
        kind="audio",
        tag="voice",
        parent_asset_id=None,
        op="voice_generate_elevenlabs",
        model=str(el.get("model") or proven.get("providerModelId") or ""),
        prompt_meta={
            "prompt": dialogue_text,
            "localProvider": False,
            "cloudPaid": True,
            "libraryClass": "audio",
            "audioRole": "voice",
            **proven,
        },
        library_key="audio.voice",
    )
    return {
        "jobId": asset.id,
        "status": "completed",
        "audioAssetId": asset.id,
        "outputPath": el.get("path"),
        "providerId": "elevenlabs",
        "providerVersion": "direct",
        "modelRevision": el.get("model"),
        "provenance": proven,
    }


def create_takes(db: Session, record_id: str, body: GenerateTakesBody) -> dict[str, Any]:
    preferred = getattr(body, "preferredProvider", None)
    pref = (preferred or "").strip().lower()
    row = _record_or_404(db, record_id)
    voice = resolve_canonical_approved_voice(
        db,
        project_id=row.project_id,
        character_id=row.character_id,
        voice_identity_id=row.voice_identity_id,
    )
    if row.voice_identity_id != voice.id:
        row.voice_identity_id = voice.id
        row.voice_identity_version = str(voice.version_number)
    from ..character_identity.service import provider_voice_binding

    saved_binding = provider_voice_binding(voice)
    active_is_elevenlabs = saved_binding is not None
    asked_elevenlabs = pref in ("elevenlabs", "eleven_labs", "el")
    asked_local = pref in ("local", "kokoro", "index-tts2", "qwen", "qwen3-tts")
    if asked_elevenlabs and not active_is_elevenlabs:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CHARACTER_VOICE_NOT_ASSIGNED",
                "error": "CHARACTER_VOICE_NOT_ASSIGNED",
                "message": "This character does not have a saved ElevenLabs voice. Save one before generating.",
                "silentFallback": False,
                "mock": False,
            },
        )
    if asked_local and active_is_elevenlabs:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VOICE_PROVIDER_MISMATCH",
                "error": "VOICE_PROVIDER_MISMATCH",
                "message": "This character's saved voice is ElevenLabs. Switch Voice Provider to Local before generating a Local take.",
                "silentFallback": False,
                "mock": False,
            },
        )
    use_elevenlabs = active_is_elevenlabs if not asked_local else False
    if asked_elevenlabs:
        use_elevenlabs = True
    use_qwen = False if use_elevenlabs else qwen_speech_compatible(voice)
    runtime = (
        {"providerId": "elevenlabs", "providerVersion": "direct", "modelRevision": getattr(body, "modelId", None)}
        if use_elevenlabs
        else ({} if use_qwen else index_tts2.runtime_status())
    )
    existing = (
        db.query(VoicePerformanceTakeRow)
        .filter(VoicePerformanceTakeRow.record_id == record_id)
        .order_by(VoicePerformanceTakeRow.take_number.desc())
        .first()
    )
    next_take_number = (existing.take_number if existing else 0) + 1
    created: list[VoicePerformanceTakeRow] = []
    # Pre-create all N slots (queued) and commit once so listTakes can show
    # stable Take 1..N order + take-level progress while generation runs.
    batch_id = str(uuid.uuid4())
    batch_total = int(body.count)
    for offset in range(body.count):
        take_number = next_take_number + offset
        label = body.labels[offset] if offset < len(body.labels) else f"Take {take_number}"
        snapshot = dict(_loads(row.performance_plan_json, {}) or {})
        snapshot["_generationBatch"] = {
            "batchId": batch_id,
            "batchIndex": offset + 1,
            "batchTotal": batch_total,
            "takeNumber": take_number,
        }
        take = VoicePerformanceTakeRow(
            id=str(uuid.uuid4()),
            record_id=row.id,
            take_number=take_number,
            label=label,
            status="queued",
            direction_snapshot_json=snapshot,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(take)
        created.append(take)
    db.commit()

    for take in created:
        take_number = int(take.take_number)
        label = take.label or f"Take {take_number}"
        take.status = "running"
        take.updated_at = _now()
        db.commit()
        sanitized = {"mannerismCues": [], "spokenText": row.dialogue_text or "", "notices": [], "emoTextSupplement": ""}
        emotion_ref_path = ""
        if row.emotional_reference_asset_id:
            emo_asset = db.get(Asset, row.emotional_reference_asset_id)
            if emo_asset and emo_asset.path and Path(emo_asset.path).is_file():
                emotion_ref_path = str(emo_asset.path)
        try:
            # Bot1 mannerism path: sanitize brackets → spokenText + structured cues before synth
            sanitized = _sanitize_record_dialogue(row)
            batch_meta = (_loads(take.direction_snapshot_json, {}) or {}).get("_generationBatch")
            snap = _attach_mannerisms_to_plan(
                _loads(row.performance_plan_json, {}),
                sanitized["mannerismCues"],
                sanitized.get("notices"),
            )
            if batch_meta:
                snap = dict(snap or {})
                snap["_generationBatch"] = batch_meta
            take.direction_snapshot_json = snap
            if use_elevenlabs:
                queued = _generate_elevenlabs_take(
                    db,
                    row=row,
                    voice=voice,
                    body=body,
                    dialogue_text=row.dialogue_text or "",
                )
            elif use_qwen:
                queued = _generate_qwen_take(
                    db,
                    project_id=row.project_id,
                    scene_id=row.scene_id,
                    record_id=row.id,
                    take_id=take.id,
                    voice=voice,
                    dialogue_text=sanitized.get("spokenText") or row.dialogue_text,
                    performance_plan=_loads(row.performance_plan_json, {}),
                    take_number=take_number,
                    label=label,
                )
            else:
                spoken_dialogue, _applied = apply_spoken_pronunciations(
                    sanitized.get("spokenText") or row.dialogue_text, entries_from_voice(voice)
                )
                queued = index_tts2.generate_take(
                    db,
                    project_id=row.project_id,
                    scene_id=row.scene_id,
                    record_id=row.id,
                    take_id=take.id,
                    dialogue_text=spoken_dialogue,
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
                    mannerism_cues=sanitized.get("mannerismCues") or [],
                    mannerism_emo_text=sanitized.get("emoTextSupplement") or "",
                )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            queued = {
                "jobId": take.id,
                "status": "failed",
                "errorCode": detail.get("code") or "GENERATION_FAILURE",
                "errorMessage": detail.get("message") or str(exc.detail) or "Voice generation failed.",
                "providerId": "qwen3-tts" if use_qwen else row.provider_id,
            }
        except Exception as exc:
            queued = {
                "jobId": take.id,
                "status": "failed",
                "errorCode": "GENERATION_FAILURE",
                "errorMessage": str(exc) or "Voice generation failed.",
                "providerId": "qwen3-tts" if use_qwen else row.provider_id,
            }
        mannerism_meta = None
        try:
            if str(queued.get("status") or "").lower() in ("completed", "complete", "done", "ready") and (
                queued.get("audioAssetId") or queued.get("outputPath")
            ):
                cues_for_events = sanitized.get("mannerismCues") or []
                if any(cue_needs_discrete_event(str(c.get("id") or "")) for c in cues_for_events):
                    dialogue_path = queued.get("outputPath") or queued.get("path")
                    if not dialogue_path and queued.get("audioAssetId"):
                        asset = db.get(Asset, queued["audioAssetId"])
                        dialogue_path = asset.path if asset else None
                    mannerism_meta = apply_mannerisms_to_take_audio(
                        db=db,
                        project_id=row.project_id,
                        take_id=take.id,
                        dialogue_asset_id=queued.get("audioAssetId"),
                        dialogue_path=dialogue_path,
                        cues=cues_for_events,
                    )
                    # Prefer stitched take as the single playable asset
                    if mannerism_meta.get("mannerismStitchedAssetId"):
                        queued = dict(queued)
                        queued["audioAssetId"] = mannerism_meta["mannerismStitchedAssetId"]
                        if (mannerism_meta.get("stitch") or {}).get("durationMs") is not None:
                            queued["durationMs"] = int(mannerism_meta["stitch"]["durationMs"])
                    elif not mannerism_meta.get("mannerismSatisfied"):
                        # Dialogue may remain playable; cue is NOT satisfied (no silent omit).
                        snap_fail = dict(_loads(take.direction_snapshot_json, {}) or {})
                        notices = list(snap_fail.get("mannerismNotices") or [])
                        msg = str(mannerism_meta.get("mannerismFailureMessage") or MANNERISM_FAIL_MESSAGE)
                        if msg not in notices:
                            notices.append(msg)
                        snap_fail["mannerismNotices"] = notices
                        snap_fail["mannerismSatisfied"] = False
                        take.direction_snapshot_json = snap_fail
        except Exception as exc:  # noqa: BLE001
            mannerism_meta = {
                "mannerismEvents": [],
                "mannerismSatisfied": False,
                "mannerismFailureMessage": MANNERISM_FAIL_MESSAGE,
                "error": str(exc),
                "speakerMatched": False,
                "generator": "local_dsp_vocal_event",
            }
        _apply_generated_take(
            take, row, queued, runtime, use_qwen=use_qwen, mannerism_meta=mannerism_meta
        )
        db.commit()
    row.updated_at = _now()
    db.commit()
    return {
        "ok": True,
        "recordId": row.id,
        "providerId": row.provider_id,
        "providerVersion": row.provider_version,
        "modelRevision": row.model_revision,
        "takes": [_take_out(t).model_dump() for t in created],
        "generationProgress": {
            "source": "take_level",
            "completed": sum(
                1
                for t in created
                if str(t.status or "").lower() in ("completed", "approved", "failed", "cancelled", "rejected")
            ),
            "total": len(created),
            "percent": 100 if created else 0,
            "active": False,
            "label": "Generation complete" if created else "",
        },
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
    # Take-level progress only (completed/total for active generation batch).
    # Never fabricate engine %. Prefer batch metadata stamped at create time.
    def _batch_meta(take_obj):
        snap = getattr(take_obj, "directionSnapshot", None)
        if snap is None:
            snap = getattr(take_obj, "direction_snapshot", None)
        if snap is None and hasattr(take_obj, "model_dump"):
            snap = (take_obj.model_dump() or {}).get("directionSnapshot")
        if isinstance(snap, dict):
            meta = snap.get("_generationBatch")
            if isinstance(meta, dict):
                return meta
        return {}

    def _take_num(take_obj):
        val = getattr(take_obj, "takeNumber", None)
        if val is None:
            val = getattr(take_obj, "take_number", None)
        try:
            return int(val or 0)
        except Exception:
            return 0

    active = [
        take
        for take in takes
        if str(getattr(take, "status", "") or "").lower() in ("queued", "running")
    ]
    batch_id = None
    if active:
        for take in active:
            meta = _batch_meta(take)
            if meta.get("batchId"):
                batch_id = meta.get("batchId")
                break
    batch_takes = []
    if batch_id:
        batch_takes = [t for t in takes if (_batch_meta(t) or {}).get("batchId") == batch_id]
    elif active:
        start_n = min(_take_num(t) for t in active)
        batch_takes = [t for t in takes if _take_num(t) >= start_n]
    total = len(batch_takes)
    terminal = {"completed", "approved", "failed", "cancelled", "rejected"}
    completed = sum(
        1 for take in batch_takes if str(getattr(take, "status", "") or "").lower() in terminal
    )
    in_flight = bool(active)
    percent = int(round((completed / total) * 100)) if total else 0
    current = None
    for take in sorted(active, key=_take_num):
        if str(getattr(take, "status", "") or "").lower() == "running":
            current = take
            break
    if current is None and active:
        current = sorted(active, key=_take_num)[0]
    current_idx = (_batch_meta(current) or {}).get("batchIndex") if current else None
    if current_idx is None and current is not None:
        current_idx = _take_num(current) or (completed + 1)
    generation_progress = {
        "source": "take_level",
        "batchId": batch_id,
        "completed": completed,
        "total": total,
        "percent": percent if in_flight else (100 if total and completed >= total and total > 0 else 0),
        "active": in_flight,
        "currentTakeNumber": (_take_num(current) or None) if current else None,
        "label": (
            f"Generating Take {current_idx} of {total}..."
            if in_flight and total
            else ("Generation complete" if total and completed >= total and not in_flight else "")
        ),
    }
    return {
        "recordId": record_id,
        "approvedTakeId": record.approved_take_id,
        "generationProgress": generation_progress,
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


def save_take_to_library(db: Session, record_id: str, take_id: str) -> dict[str, Any]:
    """Copy a finished take into the project Library. The take audio is not overwritten."""
    record = _record_or_404(db, record_id)
    take = _take_or_404(db, record_id, take_id)
    if take.status not in ("completed", "approved"):
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    if not take.audio_asset_id:
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    source = db.get(Asset, take.audio_asset_id)
    if not source or not source.path or not Path(source.path).is_file():
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    snap = dict(take.direction_snapshot_json or {})
    existing_id = str(snap.get("libraryAssetId") or "")
    if existing_id:
        existing = db.get(Asset, existing_id)
        if existing:
            return {
                "ok": True,
                "assetId": existing.id,
                "takeNumber": take.take_number,
                "alreadySaved": True,
                "mock": False,
            }
    from ..character_identity.service import provider_voice_binding
    from ..generation_tools.lineage import register_derived_asset

    voice = db.get(VoiceProfileRow, record.voice_identity_id) if record.voice_identity_id else None
    binding = provider_voice_binding(voice) if voice else None
    provider = "elevenlabs" if binding else str(getattr(voice, "provider", "") or "local")
    saved = register_derived_asset(
        db,
        project_id=record.project_id,
        source_path=source.path,
        kind="audio",
        tag="voice",
        parent_asset_id=source.id,
        op="voice_take_library",
        model=str((binding or {}).get("providerModelId") or ""),
        prompt_meta={
            "prompt": record.dialogue_text or "",
            "characterId": record.character_id,
            "provider": provider,
            "voiceName": (binding or {}).get("voiceName") or getattr(voice, "name", "") or "",
            "providerModelId": (binding or {}).get("providerModelId") or "",
            "takeNumber": take.take_number,
            "durationMs": take.duration_ms,
            "voicePerformanceRecordId": record.id,
            "takeId": take.id,
            "sourceStudio": "voice-studio-takes",
            "libraryClass": "audio",
            "audioRole": "voice",
            "localProvider": provider != "elevenlabs",
            "cloudPaid": provider == "elevenlabs",
        },
        library_key="audio.voice",
    )
    snap["libraryAssetId"] = saved.id
    take.direction_snapshot_json = snap
    take.updated_at = _now()
    db.commit()
    return {
        "ok": True,
        "assetId": saved.id,
        "takeNumber": take.take_number,
        "alreadySaved": False,
        "mock": False,
    }


def take_download(db: Session, record_id: str, take_id: str) -> tuple[str, str, str]:
    """Resolve a finished take's audio file for browser download.

    Returns (absolute_path, download_filename, media_type). The bytes are the
    exact generated file — no re-encode for download.
    """
    record = _record_or_404(db, record_id)
    take = _take_or_404(db, record_id, take_id)
    if take.status not in ("completed", "approved") or not take.audio_asset_id:
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    source = db.get(Asset, take.audio_asset_id)
    if not source or not source.path or not Path(source.path).is_file():
        raise raise_http_error(M410ErrorCode.TAKE_NOT_READY)
    from ..character_identity.models import CharacterProfileRow

    character = db.get(CharacterProfileRow, record.character_id)
    character_name = str(getattr(character, "name", "") or "Character").strip() or "Character"
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", character_name).strip("_") or "Character"
    ext = Path(source.path).suffix or ".wav"
    filename = f"{safe_name}_Take_{int(take.take_number)}{ext}"
    media_type = "audio/mpeg" if ext.lower() == ".mp3" else "audio/wav" if ext.lower() == ".wav" else "application/octet-stream"
    return str(source.path), filename, media_type


def save_take_as_voice_reference(db: Session, record_id: str, take_id: str) -> dict[str, Any]:
    """Save the take to the Library and make it the character's approved voice reference.

    The character's active Voice Profile then carries only the Library asset id.
    """
    record = _record_or_404(db, record_id)
    saved = save_take_to_library(db, record_id, take_id)
    from ..character_identity.service import set_approved_voice_reference

    reference = set_approved_voice_reference(
        db,
        project_id=record.project_id,
        character_id=record.character_id,
        asset_id=str(saved.get("assetId") or ""),
    )
    return {
        "ok": True,
        "assetId": saved.get("assetId"),
        "takeNumber": saved.get("takeNumber"),
        "alreadySaved": bool(saved.get("alreadySaved")),
        "approvedVoiceReferenceAssetId": reference.get("approvedVoiceReferenceAssetId"),
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
    if not record.scene_id:
        raise raise_http_error(M410ErrorCode.SCENE_NOT_FOUND)
    from ..film_timeline.insertion import add_to_timeline

    clip = proposal["clip"]
    placed = add_to_timeline(
        db,
        record.project_id,
        record.scene_id,
        media_type="voice",
        asset_id=str(clip.get("assetId") or ""),
        target_track_type="voice",
        start_time=float(clip.get("startMs") or 0) / 1000.0,
        duration_sec=float(clip.get("durationMs") or 0) / 1000.0,
        label=clip.get("label") or "Dialogue",
        metadata={"recordId": record.id, "takeId": clip.get("takeId"), "source": "voice-performance"},
    )
    if not placed.get("ok"):
        from fastapi import HTTPException

        raise HTTPException(400, {"error": placed.get("error") or "INSERT_FAILED", "message": placed.get("message")})
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
    from ..character_identity.voice import provider_readiness

    runtime = index_tts2.runtime_status()
    readiness = provider_readiness()
    qwen_clone = readiness.get("qwenVoiceClone") or {}
    qwen_design = readiness.get("qwenVoiceDesign") or {}
    qwen_ready = bool(qwen_clone.get("ready") or qwen_design.get("ready"))
    index_ready = bool(runtime.get("ready"))
    ready = qwen_ready or index_ready
    provider_id = "qwen3-tts" if qwen_ready else runtime.get("providerId")
    if qwen_ready:
        message = (
            "Approved Qwen voices generate on the shared warm local voice worker. "
            "IndexTTS2 stays available for voices that were built on that engine."
        )
    else:
        message = runtime.get("message") or "Voice Performance runtime is not ready yet."
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
    status = "available" if ready else "requires_setup"
    return {
        "ok": True,
        "providerId": provider_id,
        "providerVersion": runtime.get("providerVersion"),
        "status": status,
        "installed": bool(qwen_ready or runtime.get("installed")),
        "ready": ready,
        "supportsLiveGeneration": ready,
        "supportsEmotionVectors": index_ready,
        "supportedEmotionVectors": list(SUPPORTED_VECTORS),
        "directionModes": ["codirector", "manual"],
        "presetsAvailable": len(list_presets()),
        "message": message,
        "language": language,
        "capabilityMetadata": capability_metadata,
        "qwenReady": qwen_ready,
        "indexTts2Ready": index_ready,
        "sharedWarmWorker": qwen_ready,
        "mock": False,
        "mannerismVocabulary": mannerism_vocabulary_snapshot(),
    }


def get_emotion_presets() -> dict[str, Any]:
    return {"ok": True, "presets": list_presets(), "mock": False}
