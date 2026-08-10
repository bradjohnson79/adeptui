"""Voice Performance service — plans, generation, assembly, timeline placement."""

from __future__ import annotations

import json
import shutil
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..character_identity.schemas import DialogueGenerateRequest
from ..character_identity.voice_runtime import _project_audio_dir, _register_asset, run_generate_dialogue
from ..codirector.tools.ownership import find_owned_segment_plan
from ..config import settings
from ..db import Asset, Project
from .compiler import character_readiness, compile_performance, resolve_character_context
from .models import PerformanceAssemblyRow, PerformancePlanRow
from .provider_capabilities import classify_feature, list_capabilities
from .provider_translation import translate_plan
from .schemas import (
    CreatePlanBody,
    PerformanceSegmentOut,
    PlanOut,
    ValidationIssue,
)
from .tag_registry import registry_snapshot


def ensure_tables() -> None:
    from ..db import Base, engine
    from . import models as _m  # noqa: F401
    from . import m410_models as _m410  # noqa: F401

    Base.metadata.create_all(
        bind=engine,
        tables=[
            _m.PerformancePlanRow.__table__,
            _m.PerformanceAssemblyRow.__table__,
            _m410.VoicePerformanceRecordRow.__table__,
            _m410.VoicePerformanceTakeRow.__table__,
        ],
    )


def _now() -> datetime:
    return datetime.utcnow()


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _loads(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except Exception:
        return default


def _dump_seg(s: PerformanceSegmentOut | dict) -> dict:
    if isinstance(s, PerformanceSegmentOut):
        return s.model_dump()
    return dict(s)


def _plan_out(row: PerformancePlanRow) -> PlanOut:
    segs = [_loads(json.dumps(s), s) if isinstance(s, dict) else s for s in _loads(row.segments_json, [])]
    segments = [PerformanceSegmentOut(**s) if isinstance(s, dict) else s for s in segs]
    issues_raw = _loads(row.issues_json, [])
    issues = [ValidationIssue(**i) if isinstance(i, dict) else i for i in issues_raw]
    return PlanOut(
        id=row.id,
        projectId=row.project_id,
        sceneId=row.scene_id,
        characterId=row.character_id,
        characterProfileVersionId=row.character_profile_version_id or "",
        voiceVersionId=row.voice_version_id or "",
        performanceBibleVersionId=row.performance_bible_version_id,
        emotionProfileVersionId=row.emotion_profile_version_id,
        pronunciationProfileVersionId=row.pronunciation_profile_version_id,
        reactionLibraryVersionId=row.reaction_library_version_id,
        sourceText=row.source_text,
        segments=segments,
        providerPreferences=_loads(row.provider_preferences_json, []),
        status=row.status,
        compilerVersion=row.compiler_version,
        schemaVersion=row.schema_version,
        createdBy=row.created_by,
        createdAt=row.created_at.isoformat() if row.created_at else "",
        issues=issues,
        appliedDefaults=_loads(row.applied_defaults_json, {}),
        immutable=bool(row.immutable),
        mock=False,
    )


def create_plan(db: Session, body: CreatePlanBody, request=None) -> PlanOut:
    if not db.get(Project, body.projectId):
        raise _err("NOT_FOUND", "Project not found.", 404)
    compiled = compile_performance(
        db,
        project_id=body.projectId,
        character_id=body.characterId,
        source_text=body.sourceText,
        scene_id=body.sceneId,
        voice_version_id=body.voiceVersionId,
        request=request,
    )
    if compiled.status == "blocked":
        raise _err("PLAN_BLOCKED", "Performance plan blocked by validation.", 400)
    ctx = resolve_character_context(db, body.projectId, body.characterId, body.voiceVersionId)
    voice = ctx.get("voice") or {}
    pid = str(uuid.uuid4())
    now = _now()
    row = PerformancePlanRow(
        id=pid,
        project_id=body.projectId,
        scene_id=body.sceneId,
        shot_id=None,
        timeline_id=body.timelineId,
        character_id=body.characterId,
        character_profile_version_id=str(ctx["profile"].active_version_id or ""),
        voice_version_id=str(voice.get("id") or ""),
        performance_bible_version_id="performance" if ctx.get("performance") else None,
        emotion_profile_version_id="emotion" if ctx.get("emotion") else None,
        pronunciation_profile_version_id="pronunciation" if voice.get("pronunciations") else None,
        reaction_library_version_id="reactions" if voice.get("reactions") else None,
        script_source_id=body.scriptSourceId,
        source_text=body.sourceText,
        segments_json=json.dumps([_dump_seg(s) for s in compiled.segments], ensure_ascii=False),
        provider_preferences_json=json.dumps(body.providerPreferences),
        applied_defaults_json=json.dumps(compiled.appliedDefaults),
        issues_json=json.dumps([i.model_dump() for i in compiled.issues]),
        status="draft",
        immutable=0,
        version=1,
        compiler_version="w44.1",
        schema_version=1,
        created_by=body.createdBy,
        created_at=now,
        updated_at=now,
        provenance_json=json.dumps(
            {
                "characterId": body.characterId,
                "voiceVersionId": voice.get("id"),
                "voiceApproval": voice.get("approval_status"),
                "testingMode": bool(getattr(body, "testingMode", False)),
                "compilerVersion": "w44.1",
            }
        ),
    )
    db.add(row)
    db.commit()
    return _plan_out(row)


def get_plan(db: Session, plan_id: str, request=None, *, project_id: str | None = None) -> PlanOut:
    row = db.get(PerformancePlanRow, plan_id)
    if not row:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    from .compiler import _locked_project_guard

    _locked_project_guard(db, row.project_id, request)
    return _plan_out(row)


def submit_plan(db: Session, plan_id: str) -> PlanOut:
    row = db.get(PerformancePlanRow, plan_id)
    if not row:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    if row.immutable:
        raise _err("IMMUTABLE", "Plan is immutable. Create a new version.", 409)
    row.immutable = 1
    row.status = "submitted"
    row.updated_at = _now()
    db.commit()
    return _plan_out(row)


def provider_translation_for_plan(
    db: Session, plan_id: str, provider_key: str | None = None, *, project_id: str | None = None
) -> dict[str, Any]:
    plan = get_plan(db, plan_id, project_id=project_id)
    row = db.get(PerformancePlanRow, plan_id)
    assert row
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    ctx = resolve_character_context(db, row.project_id, row.character_id, row.voice_version_id)
    prefs = plan.providerPreferences or ["qwen3-tts"]
    key = provider_key or prefs[0]
    return translate_plan(provider_key=key, voice=ctx.get("voice"), segments=list(plan.segments))


def _silence_wav(path: Path, duration_ms: int, sample_rate: int = 24000) -> None:
    n = max(0, int(sample_rate * (duration_ms / 1000.0)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n)


def generate_segments(
    db: Session,
    plan_id: str,
    *,
    allow_kokoro_fallback: bool = False,
    allow_testing_voice: bool = False,
    request=None,
    project_id: str | None = None,
) -> PlanOut:
    row = db.get(PerformancePlanRow, plan_id)
    if not row:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Performance plan not found.", 404)
    from .compiler import _locked_project_guard

    _locked_project_guard(db, row.project_id, request)
    if not row.immutable:
        row.immutable = 1
        row.status = "submitted"
    if not row.voice_version_id:
        raise _err("VOICE_REQUIRED", "Character Voice Version is required.", 400)
    ctx = resolve_character_context(db, row.project_id, row.character_id, row.voice_version_id)
    voice = ctx.get("voice")
    prov = _loads(row.provenance_json, {})
    testing_ok = bool(allow_testing_voice or prov.get("testingMode"))
    if not voice:
        raise _err("VOICE_NOT_APPROVED", "Character voice must be selected before generation.", 400)
    if voice.get("approval_status") != "approved" and not testing_ok:
        raise _err("VOICE_NOT_APPROVED", "Character voice must be approved before generation.", 400)

    segments = [PerformanceSegmentOut(**s) for s in _loads(row.segments_json, [])]
    provider = "qwen3-tts" if (voice.get("provider") or "").startswith("qwen") else "kokoro"
    translation = translate_plan(provider_key=provider, voice=voice, segments=segments)
    updated: list[dict[str, Any]] = []
    any_failed = False

    for seg in segments:
        data = seg.model_dump()
        data["provider"] = provider
        if seg.segmentType in ("pause", "silence"):
            ms = int(seg.pauseMs or seg.expectedDurationMs or 250)
            dest = _project_audio_dir(row.project_id) / f"vp_pause_{uuid.uuid4().hex[:10]}.wav"
            _silence_wav(dest, ms)
            aid = _register_asset(db, row.project_id, dest, kind="audio", name=f"pause_{ms}ms")
            data["outputAssetId"] = aid
            data["status"] = "ready"
            data["supportMode"] = "Translated"
            data["expectedDurationMs"] = ms
        elif seg.segmentType == "reaction":
            if seg.outputAssetId:
                data["status"] = "ready"
                data["supportMode"] = "Pre-rendered asset"
            else:
                # Prompt-guided short vocalization
                try:
                    text = f"*{(seg.reactionKey or 'breath')}*"
                    out = run_generate_dialogue(
                        db,
                        row.project_id,
                        row.character_id,
                        row.voice_version_id,
                        DialogueGenerateRequest(text=text, language="en", allow_kokoro_fallback=allow_kokoro_fallback),
                    )
                    data["outputAssetId"] = out.get("assetId")
                    data["status"] = "ready" if out.get("assetId") else "failed"
                    data["supportMode"] = "Prompt-guided"
                    if not out.get("assetId"):
                        any_failed = True
                        data["error"] = "Reaction generation produced no asset"
                except Exception as exc:
                    data["status"] = "failed"
                    data["error"] = str(exc)
                    any_failed = True
        elif seg.segmentType == "beat":
            ms = 500
            dest = _project_audio_dir(row.project_id) / f"vp_beat_{uuid.uuid4().hex[:10]}.wav"
            _silence_wav(dest, ms)
            aid = _register_asset(db, row.project_id, dest, kind="audio", name=f"beat_{seg.beatType or 'beat'}")
            data["outputAssetId"] = aid
            data["status"] = "ready"
            data["supportMode"] = "Translated"
            data["expectedDurationMs"] = ms
        elif seg.segmentType == "speech":
            text = (seg.text or "").strip()
            if not text:
                data["status"] = "failed"
                data["error"] = "Empty speech segment"
                any_failed = True
            else:
                # Append prompt guidance without mutating stored source_text
                guidance = []
                if seg.emotion:
                    guidance.append(f"[{seg.emotion.get('primary')}]")
                if seg.delivery and seg.delivery.get("style"):
                    guidance.append(f"({seg.delivery.get('style')})")
                spoken = text
                try:
                    data["status"] = "generating"
                    out = run_generate_dialogue(
                        db,
                        row.project_id,
                        row.character_id,
                        row.voice_version_id,
                        DialogueGenerateRequest(
                            text=spoken,
                            language="en",
                            emotional_direction=(seg.emotion or {}).get("primary") or "",
                            performance_instruction=(seg.delivery or {}).get("style") or "",
                            pace=str(seg.pace or ""),
                            allow_kokoro_fallback=allow_kokoro_fallback,
                        ),
                    )
                    data["outputAssetId"] = out.get("assetId")
                    data["status"] = "ready" if out.get("assetId") else "failed"
                    data["supportMode"] = classify_feature(provider, "emotion") if seg.emotion else "Native"
                    if guidance:
                        data["supportMode"] = "Prompt-guided"
                    if not out.get("assetId"):
                        any_failed = True
                        data["error"] = "No asset registered"
                except Exception as exc:
                    data["status"] = "failed"
                    data["error"] = str(exc)
                    any_failed = True
                    # Honest failure — no fake asset
        else:
            data["status"] = "ready"
        updated.append(data)

    row.segments_json = json.dumps(updated, ensure_ascii=False)
    row.status = "failed" if any_failed else "generated"
    row.updated_at = _now()
    prov = _loads(row.provenance_json, {})
    prov["lastTranslation"] = {
        "provider": provider,
        "unsupported": translation.get("unsupported_features"),
        "fallbacks": translation.get("fallback_directives"),
    }
    row.provenance_json = json.dumps(prov)
    db.commit()
    return _plan_out(row)


def retry_segment(
    db: Session,
    segment_id: str,
    *,
    allow_kokoro_fallback: bool = False,
    project_id: str | None = None,
) -> PlanOut:
    if project_id is not None:
        plan_id, _seg = find_owned_segment_plan(db, project_id, segment_id)
        target_row = db.get(PerformancePlanRow, plan_id)
        assert target_row is not None
        segs = _loads(target_row.segments_json, [])
        target_seg = next((s for s in segs if isinstance(s, dict) and s.get("id") == segment_id), None)
    else:
        rows = db.query(PerformancePlanRow).order_by(PerformancePlanRow.created_at.desc()).limit(200).all()
        target_row = None
        target_seg = None
        segs: list[dict] = []
        for row in rows:
            segs = _loads(row.segments_json, [])
            for s in segs:
                if s.get("id") == segment_id:
                    target_row, target_seg = row, s
                    break
            if target_row:
                break
    if not target_row or not target_seg:
        raise _err("NOT_FOUND", "Segment not found.", 404)
    parent_id = target_seg.get("id")
    child = dict(target_seg)
    child["id"] = str(uuid.uuid4())
    child["retryOf"] = parent_id
    child["version"] = int(target_seg.get("version") or 1) + 1
    child["status"] = "pending"
    child["error"] = None
    child["outputAssetId"] = None
    # Keep parent; append child
    segs.append(child)
    target_row.segments_json = json.dumps(segs, ensure_ascii=False)
    target_row.updated_at = _now()
    db.commit()
    # Generate only the child by temporarily filtering — reuse generate on a synthetic pass
    plan_id = target_row.id
    # Direct generate child speech
    if child.get("segmentType") == "speech" and child.get("text"):
        try:
            out = run_generate_dialogue(
                db,
                target_row.project_id,
                target_row.character_id,
                target_row.voice_version_id,
                DialogueGenerateRequest(
                    text=child["text"],
                    language="en",
                    allow_kokoro_fallback=allow_kokoro_fallback,
                ),
            )
            child["outputAssetId"] = out.get("assetId")
            child["status"] = "ready" if out.get("assetId") else "failed"
            if not out.get("assetId"):
                child["error"] = "No asset"
        except Exception as exc:
            child["status"] = "failed"
            child["error"] = str(exc)
        # update last segment in list
        segs[-1] = child
        target_row.segments_json = json.dumps(segs, ensure_ascii=False)
        target_row.status = "generated" if child["status"] == "ready" else "failed"
        target_row.updated_at = _now()
        db.commit()
    return _plan_out(target_row)


def approve_segment(
    db: Session,
    segment_id: str,
    *,
    approved: bool = True,
    project_id: str | None = None,
) -> dict[str, Any]:
    if project_id is not None:
        plan_id, _seg = find_owned_segment_plan(db, project_id, segment_id)
        row = db.get(PerformancePlanRow, plan_id)
        assert row is not None
        segs = _loads(row.segments_json, [])
        for s in segs:
            if isinstance(s, dict) and s.get("id") == segment_id:
                s["status"] = "approved" if approved else "rejected"
                row.segments_json = json.dumps(segs, ensure_ascii=False)
                row.updated_at = _now()
                db.commit()
                return {"ok": True, "segmentId": segment_id, "status": s["status"], "mock": False}
        raise _err("NOT_FOUND", "Segment not found.", 404)
    rows = db.query(PerformancePlanRow).order_by(PerformancePlanRow.created_at.desc()).limit(200).all()
    for row in rows:
        segs = _loads(row.segments_json, [])
        for s in segs:
            if s.get("id") == segment_id:
                s["status"] = "approved" if approved else "rejected"
                row.segments_json = json.dumps(segs, ensure_ascii=False)
                row.updated_at = _now()
                db.commit()
                return {"ok": True, "segmentId": segment_id, "status": s["status"], "mock": False}
    raise _err("NOT_FOUND", "Segment not found.", 404)


def assemble_plan(db: Session, plan_id: str, *, project_id: str | None = None) -> dict[str, Any]:
    row = db.get(PerformancePlanRow, plan_id)
    if not row:
        raise _err("NOT_FOUND", "Plan not found.", 404)
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Plan not found.", 404)
    segs = _loads(row.segments_json, [])
    # Prefer approved speech/reaction; allow ready if none approved yet
    usable = [s for s in segs if s.get("status") in ("approved", "ready") and s.get("outputAssetId")]
    failed = [s for s in segs if s.get("status") == "failed" and not s.get("retryOf")]
    # If a failed segment has a successful retry child, OK
    failed_ids = {s["id"] for s in failed}
    retries_ok = {
        s.get("retryOf")
        for s in segs
        if s.get("retryOf") in failed_ids and s.get("status") in ("ready", "approved")
    }
    blocking = [s for s in failed if s["id"] not in retries_ok]
    if blocking:
        raise _err(
            "ASSEMBLY_BLOCKED",
            f"Cannot assemble while {len(blocking)} segment(s) failed without successful retry.",
            409,
        )
    if not usable:
        raise _err("ASSEMBLY_EMPTY", "No ready segments to assemble.", 400)

    # Concatenate WAVs in order (simple PCM concat for same format)
    paths: list[Path] = []
    timing = []
    cursor = 0
    for s in sorted(usable, key=lambda x: int(x.get("orderIndex") or 0)):
        # skip superseded parents when retry exists
        if any(c.get("retryOf") == s.get("id") and c.get("status") in ("ready", "approved") for c in segs):
            continue
        asset = db.get(Asset, s["outputAssetId"])
        if not asset or not asset.path:
            continue
        p = Path(asset.path)
        if not p.is_file():
            continue
        paths.append(p)
        dur_ms = int(s.get("expectedDurationMs") or _wav_duration_ms(p) or 0)
        timing.append(
            {
                "segmentId": s["id"],
                "assetId": s["outputAssetId"],
                "startMs": cursor,
                "durationMs": dur_ms,
                "overlapGroup": s.get("overlapGroup"),
                "characterId": row.character_id,
            }
        )
        cursor += dur_ms

    if not paths:
        raise _err("ASSEMBLY_EMPTY", "No readable segment audio files.", 400)

    dest = _project_audio_dir(row.project_id) / f"vp_assembly_{uuid.uuid4().hex[:10]}.wav"
    _concat_wavs(paths, dest)
    aid = _register_asset(db, row.project_id, dest, kind="audio", name=f"dialogue_assembly_{plan_id[:8]}")
    assembly_id = str(uuid.uuid4())
    db.add(
        PerformanceAssemblyRow(
            id=assembly_id,
            plan_id=plan_id,
            project_id=row.project_id,
            composite_asset_id=aid,
            segment_asset_ids_json=json.dumps([t["assetId"] for t in timing]),
            timeline_clip_ids_json="[]",
            status="assembled",
            timing_json=json.dumps({"clips": timing, "totalMs": cursor}),
            created_at=_now(),
        )
    )
    row.status = "assembled"
    row.updated_at = _now()
    db.commit()
    return {
        "ok": True,
        "assemblyId": assembly_id,
        "compositeAssetId": aid,
        "timing": timing,
        "totalMs": cursor,
        "mock": False,
    }


def _wav_duration_ms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return int(1000 * frames / rate)
    except Exception:
        return 0


def _concat_wavs(paths: list[Path], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    params = None
    frames = []
    for p in paths:
        with wave.open(str(p), "rb") as w:
            if params is None:
                params = w.getparams()
            frames.append(w.readframes(w.getnframes()))
    assert params
    with wave.open(str(dest), "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)


def approve_assembly(
    db: Session,
    assembly_id: str,
    *,
    approved_by: str = "owner",
    project_id: str | None = None,
) -> dict[str, Any]:
    row = db.get(PerformanceAssemblyRow, assembly_id)
    if not row:
        raise _err("NOT_FOUND", "Assembly not found.", 404)
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Assembly not found.", 404)
    row.status = "approved"
    row.approved_at = _now()
    row.approved_by = approved_by
    plan = db.get(PerformancePlanRow, row.plan_id)
    if plan:
        plan.status = "approved"
        plan.updated_at = _now()
    db.commit()
    return {"ok": True, "assemblyId": assembly_id, "status": "approved", "mock": False}


def place_on_timeline(
    db: Session,
    assembly_id: str,
    *,
    timeline_id: str | None = None,
    start_ms: int = 0,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Persist dialogue clips into project settings_json timeline dialogue track (canonical project state)."""
    row = db.get(PerformanceAssemblyRow, assembly_id)
    if not row:
        raise _err("NOT_FOUND", "Assembly not found.", 404)
    if project_id is not None and row.project_id != project_id:
        raise _err("NOT_FOUND", "Assembly not found.", 404)
    if row.status not in ("assembled", "approved"):
        raise _err("NOT_READY", "Assembly must be assembled/approved before Timeline placement.", 409)
    project = db.get(Project, row.project_id)
    if not project:
        raise _err("NOT_FOUND", "Project not found.", 404)
    plan = db.get(PerformancePlanRow, row.plan_id)
    timing = _loads(row.timing_json, {})
    clips = []
    for c in timing.get("clips") or []:
        clip_id = str(uuid.uuid4())
        clips.append(
            {
                "id": clip_id,
                "kind": "dialogue",
                "assetId": c.get("assetId"),
                "segmentId": c.get("segmentId"),
                "characterId": (plan.character_id if plan else None),
                "voiceVersionId": (plan.voice_version_id if plan else None),
                "planId": row.plan_id,
                "assemblyId": assembly_id,
                "startMs": int(start_ms) + int(c.get("startMs") or 0),
                "durationMs": int(c.get("durationMs") or 0),
                "overlapGroup": c.get("overlapGroup"),
                "track": "dialogue",
            }
        )
    settings = _loads(getattr(project, "settings_json", None) or "{}", {})
    tl = settings.setdefault("timeline", {})
    dialogue = tl.setdefault("dialogueTracks", [])
    track = next((t for t in dialogue if t.get("id") == (timeline_id or "dialogue-main")), None)
    if not track:
        track = {"id": timeline_id or "dialogue-main", "name": "Dialogue", "clips": []}
        dialogue.append(track)
    track.setdefault("clips", []).extend(clips)
    project.settings_json = json.dumps(settings, ensure_ascii=False)
    project.updated_at = _now()
    row.timeline_clip_ids_json = json.dumps([c["id"] for c in clips])
    row.status = "placed"
    db.commit()
    return {
        "ok": True,
        "assemblyId": assembly_id,
        "clips": clips,
        "trackId": track["id"],
        "persisted": True,
        "mock": False,
    }


def get_registry() -> dict[str, Any]:
    return registry_snapshot()


def get_provider_caps() -> dict[str, Any]:
    return {"providers": list_capabilities(), "mock": False}
