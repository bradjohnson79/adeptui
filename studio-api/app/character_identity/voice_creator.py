"""Character Voice Creator workspace — design/clone/candidates/audition/refine/approve.

Uses existing Qwen adapters via voice_runtime (no direct provider calls from UI).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import service
from .models import VoiceProfileRow
from .prompt_package import generate_prompt_package
from .schemas import DialogueGenerateRequest, VoiceConsentCreate, VoiceProfileCreate
from .voice import provider_readiness, validate_voice_reference
from .voice_runtime import run_generate_dialogue, run_voice_clone, run_voice_design

KORRI_DESIGN_BRIEF = {
    "perceivedAge": "Young adult",
    "vocalRegister": "Mid to upper-mid",
    "pitchRange": "Moderately bright",
    "timbre": "Clear with a slight playful edge",
    "texture": "Clear, light",
    "resonance": "Forward",
    "brightness": "High",
    "warmth": "Moderate beneath teasing exterior",
    "breathiness": "Low",
    "clarity": "High",
    "gender": "Female",
    "language": "English",
    "accent": "Neutral contemporary English",
    "speakingPace": "Fast and reactive",
    "energy": "High",
    "vocalWeight": "Light-medium",
    "confidence": "High",
    "playfulness": "High",
    "sarcasm": "High",
    "tenderness": "Low-moderate (rare)",
    "authority": "Low public / accepts private guidance",
    "rebelliousness": "High",
    "emotionalVolatility": "Moderate-high",
    "comedicTiming": "Sharp",
    "intensity": "Quick spikes",
    "restraint": "Low until serious stillness",
    "delivery": "Sarcastic, sharp, playful",
    "additionalDirection": "",
}

KORRI_AUDITION_LINES = [
    {"id": "neutral", "category": "Neutral introduction", "text": "Hey. I'm Korri. Don't make it weird."},
    {"id": "fast", "category": "Fast dialogue", "text": "Yeah I already know — move, talk, keep up."},
    {
        "id": "sarcastic",
        "category": "Sarcastic line",
        "text": "Oh sure, that plan is flawless. What could possibly go wrong?",
    },
    {"id": "playful", "category": "Playful insult", "text": "Cute. You're almost clever today."},
    {"id": "annoyed", "category": "Annoyance", "text": "Stop explaining. I got it the first time."},
    {"id": "defiant", "category": "Defiance", "text": "I'm not following that order. Try again."},
    {
        "id": "sincere",
        "category": "Warm sincerity",
        "text": "Hey… I've got you. I'm not going anywhere.",
    },
    {
        "id": "vulnerable",
        "category": "Quiet vulnerability",
        "text": "Just… give me a second. Okay?",
    },
]

KORRI_REACTIONS = [
    {"id": "laugh", "label": "short amused laugh", "text": "*short amused laugh*"},
    {"id": "scoff", "label": "sarcastic scoff", "text": "*sarcastic scoff*"},
    {"id": "exhale", "label": "annoyed exhale", "text": "*annoyed exhale*"},
    {"id": "gasp", "label": "surprised gasp", "text": "*surprised gasp*"},
    {"id": "breath", "label": "quiet sincere breath", "text": "*quiet sincere breath*"},
    {"id": "grunt", "label": "effort grunt", "text": "*effort grunt*"},
]

DEFAULT_DESIGN_BRIEF = {
    "perceivedAge": "",
    "vocalRegister": "",
    "pitchRange": "",
    "timbre": "",
    "texture": "",
    "resonance": "",
    "brightness": "",
    "warmth": "",
    "breathiness": "",
    "clarity": "",
    "gender": "",
    "language": "English",
    "accent": "",
    "speakingPace": "",
    "energy": "",
    "vocalWeight": "",
    "confidence": "",
    "playfulness": "",
    "sarcasm": "",
    "tenderness": "",
    "authority": "",
    "rebelliousness": "",
    "emotionalVolatility": "",
    "comedicTiming": "",
    "intensity": "",
    "restraint": "",
    "delivery": "",
    "additionalDirection": "",
}

DEFAULT_AUDITION_LINES = [
    {"id": "neutral", "category": "Neutral introduction", "text": "Hello. I'm a character in this story."},
    {"id": "fast", "category": "Fast dialogue", "text": "Let's go — there's no time to waste."},
    {"id": "serious", "category": "Serious line", "text": "This is important. We need to get it right."},
    {"id": "warm", "category": "Warm line", "text": "Don't worry. I'll be right here."},
]

DEFAULT_REACTIONS = [
    {"id": "laugh", "label": "short amused laugh", "text": "*short amused laugh*"},
    {"id": "sigh", "label": "thoughtful sigh", "text": "*thoughtful sigh*"},
    {"id": "exhale", "label": "frustrated exhale", "text": "*frustrated exhale*"},
    {"id": "gasp", "label": "surprised gasp", "text": "*surprised gasp*"},
    {"id": "breath", "label": "quiet breath", "text": "*quiet breath*"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _save_lineage(row: VoiceProfileRow, lineage: dict[str, Any]) -> None:
    row.lineage_json = json.dumps(lineage, ensure_ascii=False)
    row.updated_at = _now()


def compile_design_prompt(brief: dict[str, Any], *, character_name: str = "Character") -> str:
    """Compile structured design brief into provider voiceDescription — no conflicting baritone defaults."""
    parts = [
        f"Character voice for {character_name}.",
        f"Gender presentation: {brief.get('gender') or brief.get('vocalGender') or ''}.",
        f"Accent / dialect: {brief.get('accent') or ''}.",
        f"Spoken language: {brief.get('language') or 'English'}.",
        f"Perceived age: {brief.get('perceivedAge') or ''}.",
        f"Register: {brief.get('vocalRegister') or ''}.",
        f"Pitch: {brief.get('pitchRange') or ''}.",
        f"Timbre: {brief.get('timbre') or ''}.",
        f"Texture: {brief.get('texture') or ''}.",
        f"Pace: {brief.get('speakingPace') or ''}.",
        f"Energy: {brief.get('energy') or ''}.",
        f"Delivery: {brief.get('delivery') or ''}.",
        f"Warmth: {brief.get('warmth') or ''}.",
        f"Sarcasm: {brief.get('sarcasm') or ''}.",
        f"Playfulness: {brief.get('playfulness') or ''}.",
        f"Breathiness: {brief.get('breathiness') or ''}.",
        f"Clarity: {brief.get('clarity') or ''}.",
    ]
    extra = (brief.get("additionalDirection") or "").strip()
    if extra:
        parts.append(f"Additional direction: {extra}.")
    parts.append(
        "Do not invent conflicting gender, age, accent, or register identity. "
        "Match the structured brief only — never substitute an unrelated adult male register."
    )
    return " ".join(p for p in parts if p and not p.endswith(": ."))


def _profile_row(db: Session, character_id: str):
    from .models import CharacterProfileRow

    return db.get(CharacterProfileRow, character_id)


def _get_studio_draft(db: Session, character_id: str) -> dict[str, Any]:
    prow = _profile_row(db, character_id)
    if not prow:
        return {}
    cont = _loads(prow.continuity_json, {})
    draft = cont.get("voiceStudioDraft") if isinstance(cont, dict) else None
    return dict(draft) if isinstance(draft, dict) else {}


def _save_studio_draft(db: Session, character_id: str, draft: dict[str, Any]) -> dict[str, Any]:
    from .models import CharacterProfileRow

    prow = db.get(CharacterProfileRow, character_id)
    if not prow:
        raise _err("NOT_FOUND", "Character Profile not found.", 404)
    cont = _loads(prow.continuity_json, {})
    if not isinstance(cont, dict):
        cont = {}
    cleaned = {k: v for k, v in draft.items() if v is not None}
    cleaned["updatedAt"] = _now()
    cont["voiceStudioDraft"] = cleaned
    prow.continuity_json = json.dumps(cont, ensure_ascii=False)
    prow.updated_at = _now()
    db.commit()
    return cleaned


def _aggregate_batches(voices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    for v in voices:
        lineage = v.get("lineage") or {}
        for b in lineage.get("candidateBatches") or []:
            if isinstance(b, dict):
                batches.append({**b, "voiceProfileId": v.get("id")})
    batches.sort(key=lambda b: str(b.get("createdAt") or ""), reverse=True)
    return batches


def get_voice_workspace(db: Session, project_id: str, character_id: str) -> dict[str, Any]:
    profile = service.get_profile(db, project_id, character_id)
    voices = service.list_voice_profiles(db, project_id, character_id)
    readiness = provider_readiness()
    active = None
    if profile.active_voice_profile_id:
        active = next((v for v in voices if v["id"] == profile.active_voice_profile_id), None)
    methods = _methods_catalog(readiness)
    design_brief = KORRI_DESIGN_BRIEF if (profile.slug or "").lower() == "korri" else dict(DEFAULT_DESIGN_BRIEF)
    prompt_document = None
    # Prefer stored brief from latest DESIGN voice
    for v in reversed(voices):
        lineage = v.get("lineage") or {}
        brief = lineage.get("designBrief")
        if brief:
            design_brief = brief
            if lineage.get("promptDocument"):
                prompt_document = lineage.get("promptDocument")
            break
    draft = _get_studio_draft(db, character_id)
    batches = _aggregate_batches(voices)
    testing = {
        "voiceProfileId": draft.get("testingVoiceProfileId") or "",
        "candidateId": draft.get("testingCandidateId") or "",
        "approved": bool(active and active.get("approval_status") == "approved"),
    }
    return {
        "characterId": character_id,
        "characterName": profile.name,
        "slug": profile.slug,
        "activeVoiceProfileId": profile.active_voice_profile_id,
        "activeVoice": active,
        "voices": voices,
        "providers": readiness,
        "methods": methods,
        "designBrief": design_brief,
        "promptDocument": prompt_document,
        "compiledDesignPrompt": compile_design_prompt(design_brief, character_name=profile.name),
        "performanceAttached": bool(profile.performance),
        "emotionAttached": bool(profile.emotion),
        "personality": getattr(profile, "personality", None),
        "performance": getattr(profile, "performance", None),
        "emotion": getattr(profile, "emotion", None),
        "auditionLines": KORRI_AUDITION_LINES if (profile.slug or "").lower() == "korri" else DEFAULT_AUDITION_LINES,
        "reactionCatalog": KORRI_REACTIONS if (profile.slug or "").lower() == "korri" else DEFAULT_REACTIONS,
        "candidateBatches": batches,
        "voiceStudioDraft": draft,
        "testingSelection": testing,
        "prefillSource": "character_profile",
        "mock": False,
    }


def save_voice_studio_draft(
    db: Session, project_id: str, character_id: str, draft: dict[str, Any]
) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    existing = _get_studio_draft(db, character_id)
    merged = {**existing, **draft}
    saved = _save_studio_draft(db, character_id, merged)
    return {"ok": True, "voiceStudioDraft": saved, "mock": False}


def select_testing_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    voice_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    """Bind a candidate for performance testing — does NOT approve the canonical voice."""
    row = _voice(db, project_id, character_id, voice_id)
    lineage = _loads(row.lineage_json, {})
    meta = list(lineage.get("candidatesMeta") or [])
    cand = next((c for c in meta if c.get("id") == candidate_id), None)
    if not cand:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    if cand.get("status") == "rejected":
        raise _err("INVALID_STATUS", "Cannot select a rejected candidate for testing.")
    lineage["testingCandidateId"] = candidate_id
    lineage["testingSelectedAt"] = _now()
    row.approved_preview_asset_id = cand.get("assetId") or row.approved_preview_asset_id
    _save_lineage(row, lineage)
    db.commit()
    draft = save_voice_studio_draft(
        db,
        project_id,
        character_id,
        {
            "phase": "performance",
            "testingVoiceProfileId": voice_id,
            "testingCandidateId": candidate_id,
            "selectedVoiceProfileId": voice_id,
            "selectedCandidateId": candidate_id,
        },
    )
    return {
        "ok": True,
        "approved": False,
        "testing": True,
        "voiceProfileId": voice_id,
        "candidateId": candidate_id,
        "voiceStudioDraft": draft.get("voiceStudioDraft"),
        "mock": False,
    }


def _methods_catalog(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    design = readiness.get("qwenVoiceDesign") or {}
    clone = readiness.get("qwenVoiceClone") or {}
    kokoro = readiness.get("kokoro") or {}
    return [
        {
            "id": "DESIGN",
            "title": "Qwen Voice Design",
            "provider": "qwen3-tts",
            "ready": bool(design.get("ready")),
            "message": design.get("message") or "",
            "consentRequired": False,
            "stages": ["brief", "generate", "audition", "refine", "approve"],
            "limitations": "Requires Qwen3-TTS Voice Design installed via Source Manager.",
        },
        {
            "id": "CLONE",
            "title": "Qwen Voice Clone",
            "provider": "qwen3-tts",
            "ready": bool(clone.get("ready")),
            "message": clone.get("message") or "",
            "consentRequired": True,
            "stages": ["consent", "reference", "validate", "generate", "audition", "approve"],
            "limitations": "Requires valid consent + ≥10s reference audio + Qwen Clone model.",
        },
        {
            "id": "UPLOAD",
            "title": "Upload Voice",
            "provider": "external",
            "ready": True,
            "message": "Register externally produced voice samples as a draft profile.",
            "consentRequired": True,
            "stages": ["upload", "consent", "approve"],
            "limitations": "Does not synthesize; registers provided audio only.",
        },
        {
            "id": "PRESET",
            "title": "Preset Voice",
            "provider": "kokoro",
            "ready": bool(kokoro.get("ready")),
            "message": kokoro.get("message") or "",
            "consentRequired": False,
            "stages": ["select", "preview", "approve"],
            "limitations": "Generic preset — weaker character identity fit than Qwen Design.",
        },
    ]


def preview_voice_design(
    db: Session, project_id: str, character_id: str, *, brief: dict[str, Any] | None = None
) -> dict[str, Any]:
    profile = service.get_profile(db, project_id, character_id)
    b = brief or (KORRI_DESIGN_BRIEF if (profile.slug or "").lower() == "korri" else DEFAULT_DESIGN_BRIEF)
    prompt = compile_design_prompt(b, character_name=profile.name)
    readiness = provider_readiness()
    design = readiness.get("qwenVoiceDesign") or {}
    return {
        "ok": True,
        "character": profile.name,
        "method": "Qwen Voice Design",
        "provider": "qwen3-tts",
        "providerReady": bool(design.get("ready")),
        "providerMessage": design.get("message") or "",
        "designBrief": b,
        "compiledVoiceDescription": prompt,
        "performanceAttached": bool(profile.performance),
        "emotionAttached": bool(profile.emotion),
        "testScript": "Korri Core Audition v1" if (profile.slug or "").lower() == "korri" else "Core Audition v1",
        "candidateCountDefault": 3,
        "mock": False,
    }


def generate_voice_candidates(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    brief: dict[str, Any] | None = None,
    candidate_count: int = 3,
    test_line: str | None = None,
    name: str | None = None,
    master_prompt: str | None = None,
    prompt_document: dict[str, Any] | None = None,
    method: str = "design",
    parent_candidate_id: str | None = None,
    append_to_voice_id: str | None = None,
) -> dict[str, Any]:
    profile = service.get_profile(db, project_id, character_id)
    is_korri = (profile.slug or "").lower() == "korri"
    b = brief or (KORRI_DESIGN_BRIEF if is_korri else DEFAULT_DESIGN_BRIEF)
    prompt = (master_prompt or "").strip() or compile_design_prompt(b, character_name=profile.name)
    line = test_line or (KORRI_AUDITION_LINES[2]["text"] if is_korri else DEFAULT_AUDITION_LINES[0]["text"])
    wanted = max(1, min(int(candidate_count), 6))
    body = type(
        "Body",
        (),
        {
            "name": name or f"{profile.name} Voice Draft",
            "voice_design_prompt": prompt,
            "test_line": line,
            "candidate_count": wanted,
            "language": "en",
        },
    )()
    result = run_voice_design(db, project_id, character_id, body)
    produced = db.get(VoiceProfileRow, result["id"])
    assert produced
    row = produced
    append_mode = False
    # Optionally append candidates onto an existing draft voice (Generate 3 More / Similar)
    if append_to_voice_id and append_to_voice_id != produced.id:
        try:
            existing = _voice(db, project_id, character_id, append_to_voice_id)
            if existing.approval_status != "approved":
                row = existing
                append_mode = True
        except Exception:
            append_mode = False
    lineage = _loads(row.lineage_json, {})
    prior_meta = list(lineage.get("candidatesMeta") or []) if append_mode else []
    candidates_meta = list(prior_meta)
    batch_candidate_ids: list[str] = []
    aids = list(result.get("candidates") or [])
    errors = list(result.get("errors") or result.get("candidateErrors") or [])
    for i in range(wanted):
        aid = aids[i] if i < len(aids) else None
        cid = str(uuid.uuid4())
        batch_candidate_ids.append(cid)
        if aid:
            candidates_meta.append(
                {
                    "id": cid,
                    "name": f"Voice {len(candidates_meta) + 1}",
                    "assetId": aid,
                    "status": "ready",
                    "method": "DESIGN",
                    "provider": "qwen3-tts",
                    "parentCandidateId": parent_candidate_id,
                    "createdAt": _now(),
                    "notes": "",
                }
            )
        else:
            err = errors[i] if i < len(errors) else "Generation failed for this candidate"
            candidates_meta.append(
                {
                    "id": cid,
                    "name": f"Voice {len(candidates_meta) + 1}",
                    "assetId": None,
                    "status": "failed",
                    "error": str(err),
                    "method": "DESIGN",
                    "provider": "qwen3-tts",
                    "parentCandidateId": parent_candidate_id,
                    "createdAt": _now(),
                    "notes": "",
                }
            )
    batch = {
        "id": str(uuid.uuid4()),
        "projectId": project_id,
        "characterId": character_id,
        "method": method if method in ("design", "clone", "similar") else "design",
        "designBriefSnapshot": b,
        "masterPrompt": prompt,
        "promptDocument": prompt_document,
        "candidateIds": batch_candidate_ids,
        "parentCandidateId": parent_candidate_id,
        "createdAt": _now(),
        "requestedCount": wanted,
        "readyCount": sum(1 for c in candidates_meta if c.get("id") in batch_candidate_ids and c.get("status") == "ready"),
        "failedCount": sum(1 for c in candidates_meta if c.get("id") in batch_candidate_ids and c.get("status") == "failed"),
    }
    batches = list(lineage.get("candidateBatches") or [])
    batches.append(batch)
    lineage.update(
        {
            "designBrief": b,
            "compiledPrompt": prompt,
            "promptDocument": prompt_document or lineage.get("promptDocument"),
            "candidatesMeta": candidates_meta,
            "candidateBatches": batches,
            "workspace": "voice_studio",
        }
    )
    # Mirror timbre fields onto row for SoT
    row.perceived_age = str(b.get("perceivedAge") or "")
    row.pitch_description = str(b.get("pitchRange") or "")
    row.pace_description = str(b.get("speakingPace") or "")
    row.tone_description = str(b.get("delivery") or "")
    row.warmth = str(b.get("warmth") or "")
    row.breathiness = str(b.get("breathiness") or "")
    row.energy = str(b.get("energy") or "")
    cids = [c.get("assetId") for c in candidates_meta if c.get("assetId")]
    row.candidate_asset_ids_json = json.dumps(cids)
    _save_lineage(row, lineage)
    db.commit()
    save_voice_studio_draft(
        db,
        project_id,
        character_id,
        {
            "phase": "select",
            "selectedVoiceProfileId": row.id,
            "latestBatchId": batch["id"],
            "promptDocument": prompt_document,
            "designBrief": b,
            "masterPrompt": prompt,
        },
    )
    return {
        **service.voice_to_dict(row),
        "candidates": [c for c in candidates_meta if c.get("id") in batch_candidate_ids],
        "allCandidates": candidates_meta,
        "batch": batch,
        "candidateBatches": _aggregate_batches(
            [{**service.voice_to_dict(row), "lineage": lineage}]
        ),
        "compiledPrompt": prompt,
        "capabilityNote": result.get("capabilityNote"),
        "mock": False,
    }


def retry_failed_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    candidate_id: str,
    *,
    test_line: str | None = None,
) -> dict[str, Any]:
    """Retry a single failed candidate slot without destroying the batch."""
    row = _voice(db, project_id, character_id, voice_id)
    lineage = _loads(row.lineage_json, {})
    meta = list(lineage.get("candidatesMeta") or [])
    cand = next((c for c in meta if c.get("id") == candidate_id), None)
    if not cand:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    profile = service.get_profile(db, project_id, character_id)
    is_korri = (profile.slug or "").lower() == "korri"
    brief = dict(lineage.get("designBrief") or (KORRI_DESIGN_BRIEF if is_korri else DEFAULT_DESIGN_BRIEF))
    prompt = str(lineage.get("compiledPrompt") or compile_design_prompt(brief, character_name=profile.name))
    readiness = provider_readiness()
    if not (readiness.get("qwenVoiceDesign") or {}).get("ready"):
        raise _err("MODEL_NOT_INSTALLED", "Qwen Voice Design not ready.", 503)
    from .voice_runtime import _register_asset, _try_m210b_generate, _project_audio_dir
    import shutil

    line = test_line or (KORRI_AUDITION_LINES[2]["text"] if is_korri else DEFAULT_AUDITION_LINES[0]["text"])
    try:
        src = _try_m210b_generate(
            registry_id="m2101-voice-design-021",
            text=line,
            project_id=project_id,
            extra={"voiceDescription": prompt, "seed": abs(hash(candidate_id + _now())) % 10000},
        )
        dest = _project_audio_dir(project_id) / f"retry_{uuid.uuid4().hex[:10]}.wav"
        shutil.copy2(src, dest)
        from .voice import validate_generated_wav

        validate_generated_wav(dest)
        aid = _register_asset(db, project_id, dest, kind="audio", name=f"{row.name} retry")
        cand["assetId"] = aid
        cand["status"] = "ready"
        cand["error"] = None
        cand["retriedAt"] = _now()
        cids = _loads(row.candidate_asset_ids_json, [])
        if aid not in cids:
            cids.append(aid)
            row.candidate_asset_ids_json = json.dumps(cids)
    except Exception as exc:
        cand["status"] = "failed"
        cand["error"] = str(exc)
        cand["retriedAt"] = _now()
    lineage["candidatesMeta"] = meta
    _save_lineage(row, lineage)
    db.commit()
    return {"ok": True, "candidate": cand, "candidates": meta, "mock": False}


def register_upload_voice(
    db: Session,
    project_id: str,
    character_id: str,
    *,
    asset_id: str,
    upload_kind: str,
    name: str | None = None,
    consent_confirmed: bool = False,
) -> dict[str, Any]:
    """Register an uploaded audio asset with explicit semantic kind.

    Only reusable_character_voice may become a selectable Character Voice Version
    without further processing. Dialogue performances never silently become identity.
    """
    kind = (upload_kind or "").strip()
    allowed = {
        "reusable_character_voice",
        "voice_reference",
        "audition_sample",
        "finished_dialogue_performance",
    }
    if kind not in allowed:
        raise _err("INVALID_UPLOAD_KIND", f"Unknown upload kind: {upload_kind}")
    if kind == "reusable_character_voice" and not consent_confirmed:
        raise _err("CONSENT_REQUIRED", "Consent is required to register a reusable character voice.")
    profile = service.get_profile(db, project_id, character_id)
    if kind == "reusable_character_voice":
        vp = service.create_voice_profile(
            db,
            project_id,
            character_id,
            VoiceProfileCreate(
                name=name or f"{profile.name} Uploaded Voice",
                source_mode="UPLOAD",
                provider="external",
                reference_asset_id=asset_id,
            ),
        )
        row = db.get(VoiceProfileRow, str(vp["id"]))
        assert row
        cid = str(uuid.uuid4())
        meta = [
            {
                "id": cid,
                "name": "Uploaded voice",
                "assetId": asset_id,
                "status": "ready",
                "method": "UPLOAD",
                "provider": "external",
                "parentCandidateId": None,
                "createdAt": _now(),
            }
        ]
        batch = {
            "id": str(uuid.uuid4()),
            "projectId": project_id,
            "characterId": character_id,
            "method": "design",
            "designBriefSnapshot": {},
            "masterPrompt": "",
            "candidateIds": [cid],
            "createdAt": _now(),
            "uploadKind": kind,
        }
        lineage = _loads(row.lineage_json, {})
        lineage.update(
            {
                "candidatesMeta": meta,
                "candidateBatches": [batch],
                "uploadKind": kind,
                "workspace": "voice_studio",
            }
        )
        row.approved_preview_asset_id = asset_id
        row.candidate_asset_ids_json = json.dumps([asset_id])
        _save_lineage(row, lineage)
        db.commit()
        return {
            "ok": True,
            "uploadKind": kind,
            "becomesVoiceVersion": True,
            "voice": service.voice_to_dict(row),
            "candidates": meta,
            "batch": batch,
            "mock": False,
        }
    # Non-identity uploads — register as draft artifact only
    draft = save_voice_studio_draft(
        db,
        project_id,
        character_id,
        {
            "uploadKind": kind,
            "uploadAssetId": asset_id,
            "phase": "create" if kind == "voice_reference" else "performance",
        },
    )
    return {
        "ok": True,
        "uploadKind": kind,
        "becomesVoiceVersion": False,
        "assetId": asset_id,
        "voiceStudioDraft": draft.get("voiceStudioDraft"),
        "message": {
            "voice_reference": "Saved as a voice reference. Use Clone from Recording to create a reusable voice.",
            "audition_sample": "Saved as an audition sample for listening only.",
            "finished_dialogue_performance": "Saved as a finished dialogue performance — not a reusable character voice.",
        }.get(kind, "Upload recorded."),
        "mock": False,
    }


def list_candidates(db: Session, project_id: str, character_id: str, voice_id: str) -> dict[str, Any]:
    row = _voice(db, project_id, character_id, voice_id)
    lineage = _loads(row.lineage_json, {})
    meta = lineage.get("candidatesMeta") or []
    if not meta:
        meta = [
            {
                "id": str(uuid.uuid4()),
                "name": f"Candidate {i + 1}",
                "assetId": aid,
                "status": "ready",
                "method": row.source_mode,
                "provider": row.provider,
                "parentCandidateId": None,
                "createdAt": row.created_at,
            }
            for i, aid in enumerate(_loads(row.candidate_asset_ids_json, []))
        ]
    return {"voiceProfileId": voice_id, "candidates": meta, "mock": False}


def update_candidate_status(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    candidate_id: str,
    *,
    status: str,
    notes: str = "",
) -> dict[str, Any]:
    if status not in ("ready", "rejected", "shortlisted", "approved", "archived"):
        raise _err("INVALID_STATUS", f"Invalid candidate status: {status}")
    row = _voice(db, project_id, character_id, voice_id)
    if row.approval_status == "approved" and status == "approved":
        pass
    lineage = _loads(row.lineage_json, {})
    meta = list(lineage.get("candidatesMeta") or [])
    found = False
    for c in meta:
        if c.get("id") == candidate_id:
            c["status"] = status
            if notes:
                c["notes"] = notes
            c["updatedAt"] = _now()
            if status == "shortlisted":
                row.approved_preview_asset_id = c.get("assetId")
            found = True
            break
    if not found:
        raise _err("NOT_FOUND", "Candidate not found.", 404)
    lineage["candidatesMeta"] = meta
    _save_lineage(row, lineage)
    db.commit()
    return {"ok": True, "candidates": meta}


def refine_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    candidate_id: str,
    *,
    refinement: str,
    test_line: str | None = None,
) -> dict[str, Any]:
    """Create a child candidate via new design generation — does not overwrite parent."""
    row, forked = service.fork_draft_voice_profile(
        db,
        project_id,
        character_id,
        voice_id,
        reason="Regenerate / refine after approved voice",
    )
    lineage = _loads(row.lineage_json, {})
    meta = list(lineage.get("candidatesMeta") or [])
    parent = next((c for c in meta if c.get("id") == candidate_id), None)
    if not parent:
        raise _err("NOT_FOUND", "Parent candidate not found.", 404)
    profile = service.get_profile(db, project_id, character_id)
    is_korri = (profile.slug or "").lower() == "korri"
    brief = dict(lineage.get("designBrief") or (KORRI_DESIGN_BRIEF if is_korri else DEFAULT_DESIGN_BRIEF))
    brief["additionalDirection"] = (
        f"{brief.get('additionalDirection') or ''} Refinement: {refinement}".strip()
    )
    prompt = compile_design_prompt(brief, character_name=profile.name)
    from .voice_runtime import _register_asset, _try_m210b_generate, _project_audio_dir
    import shutil
    from pathlib import Path

    readiness = provider_readiness()
    if not (readiness.get("qwenVoiceDesign") or {}).get("ready"):
        raise _err("MODEL_NOT_INSTALLED", "Qwen Voice Design not ready.", 503)
    line = test_line or (KORRI_AUDITION_LINES[2]["text"] if is_korri else DEFAULT_AUDITION_LINES[0]["text"])
    src = _try_m210b_generate(
        registry_id="m2101-voice-design-021",
        text=line,
        project_id=project_id,
        extra={"voiceDescription": prompt, "seed": abs(hash(refinement)) % 10000},
    )
    dest = _project_audio_dir(project_id) / f"refine_{uuid.uuid4().hex[:10]}.wav"
    shutil.copy2(src, dest)
    from .voice import validate_generated_wav

    validate_generated_wav(dest)
    aid = _register_asset(db, project_id, dest, kind="audio", name=f"{row.name} refinement")
    child = {
        "id": str(uuid.uuid4()),
        "name": f"{parent.get('name')} · refined",
        "assetId": aid,
        "status": "ready",
        "method": "DESIGN",
        "provider": "qwen3-tts",
        "parentCandidateId": candidate_id,
        "refinement": refinement,
        "createdAt": _now(),
        "notes": "",
    }
    meta.append(child)
    cids = _loads(row.candidate_asset_ids_json, [])
    cids.append(aid)
    row.candidate_asset_ids_json = json.dumps(cids)
    lineage["candidatesMeta"] = meta
    lineage["designBrief"] = brief
    lineage["compiledPrompt"] = prompt
    _save_lineage(row, lineage)
    db.commit()
    return {
        "ok": True,
        "parent": parent,
        "child": child,
        "candidates": meta,
        "voiceId": row.id,
        "forked": forked,
        "mock": False,
    }


def audition_line(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    *,
    text: str,
    category: str = "",
) -> dict[str, Any]:
    body = DialogueGenerateRequest(text=text, language="en")
    result = run_generate_dialogue(db, project_id, character_id, voice_id, body)
    row = _voice(db, project_id, character_id, voice_id)
    lineage = _loads(row.lineage_json, {})
    history = list(lineage.get("auditionHistory") or [])
    history.append(
        {
            "id": str(uuid.uuid4()),
            "category": category,
            "text": text,
            "assetId": result.get("assetId"),
            "createdAt": _now(),
        }
    )
    lineage["auditionHistory"] = history[-50:]
    _save_lineage(row, lineage)
    db.commit()
    return {**result, "category": category, "mock": False}


def generate_reactions(
    db: Session, project_id: str, character_id: str, voice_id: str
) -> dict[str, Any]:
    # Reaction packs are production metadata — allowed on approved voices (voice identity stays locked).
    row = _voice(db, project_id, character_id, voice_id)
    results = []
    for r in DEFAULT_REACTIONS:
        try:
            out = run_generate_dialogue(
                db,
                project_id,
                character_id,
                voice_id,
                DialogueGenerateRequest(text=r["text"], language="en"),
            )
            results.append(
                {
                    "id": r["id"],
                    "label": r["label"],
                    "assetId": out.get("assetId"),
                    "status": "ready",
                    "path": out.get("path"),
                }
            )
        except Exception as exc:
            results.append({"id": r["id"], "label": r["label"], "status": "failed", "error": str(exc)})
    lineage = _loads(row.lineage_json, {})
    lineage["reactions"] = results
    _save_lineage(row, lineage)
    db.commit()
    missing = [r["id"] for r in results if r.get("status") != "ready"]
    return {
        "ok": True,
        "reactions": results,
        "missing": missing,
        "voiceId": row.id,
        "forked": False,
        "mock": False,
    }


def upsert_pronunciations(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    # Pronunciation dictionary is production metadata — allowed on approved voices.
    # Voice identity regeneration (refine/redesign) remains locked and must fork.
    row = _voice(db, project_id, character_id, voice_id)
    cleaned = []
    for e in entries:
        word = str(e.get("word") or "").strip()
        if not word:
            continue
        cleaned.append(
            {
                "id": e.get("id") or str(uuid.uuid4()),
                "word": word,
                "phonetic": str(e.get("phonetic") or ""),
                "language": str(e.get("language") or "en"),
                "stress": str(e.get("stress") or ""),
                "notes": str(e.get("notes") or ""),
                "status": e.get("status") or "draft",
                "audioAssetId": e.get("audioAssetId"),
            }
        )
    notes = "; ".join(f"{c['word']}={c['phonetic']}" for c in cleaned if c.get("phonetic"))
    row.pronunciation_notes = notes
    lineage = _loads(row.lineage_json, {})
    lineage["pronunciations"] = cleaned
    _save_lineage(row, lineage)
    db.commit()
    return {
        "ok": True,
        "pronunciations": cleaned,
        "voiceId": row.id,
        "forked": False,
        "mock": False,
    }


def test_pronunciation(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    *,
    word: str,
    phonetic: str = "",
) -> dict[str, Any]:
    text = f"{word}." if not phonetic else f"{word} ({phonetic})."
    out = run_generate_dialogue(
        db,
        project_id,
        character_id,
        voice_id,
        DialogueGenerateRequest(text=f"The word is {text}", language="en"),
    )
    return {"ok": True, "word": word, "phonetic": phonetic, "assetId": out.get("assetId"), "mock": False}


def approve_voice_candidate(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    *,
    candidate_id: str | None = None,
    approved_by: str = "owner",
) -> dict[str, Any]:
    row = _voice(db, project_id, character_id, voice_id)
    lineage = _loads(row.lineage_json, {})
    meta = list(lineage.get("candidatesMeta") or [])
    if candidate_id:
        cand = next((c for c in meta if c.get("id") == candidate_id), None)
        if not cand:
            raise _err("NOT_FOUND", "Candidate not found.", 404)
        if cand.get("status") == "rejected":
            raise _err("INVALID_STATUS", "Cannot approve a rejected candidate.")
        row.approved_preview_asset_id = cand.get("assetId")
        for c in meta:
            c["status"] = "approved" if c.get("id") == candidate_id else (
                "archived" if c.get("status") == "shortlisted" else c.get("status")
            )
        lineage["candidatesMeta"] = meta
        lineage["approvedCandidateId"] = candidate_id
        lineage["approvedBy"] = approved_by
        lineage["approvedAt"] = _now()
        _save_lineage(row, lineage)
        db.commit()
    approved = service.approve_voice_profile(db, project_id, character_id, voice_id)
    # Refresh Prompt Package with voice fields
    profile = service.get_profile(db, project_id, character_id)
    row = _voice(db, project_id, character_id, voice_id)
    pkg = generate_prompt_package(
        {**profile.model_dump(), "active_voice": service.voice_to_dict(row)},
        character_version_id=profile.active_version_id or "",
    )
    from .models import CharacterProfileRow

    prow = db.get(CharacterProfileRow, character_id)
    if prow:
        prow.prompt_package_json = json.dumps(pkg, ensure_ascii=False)
        prow.updated_at = _now()
        db.commit()
    return {
        "ok": True,
        "voice": approved,
        "promptPackageUpdated": True,
        "approvedBy": approved_by,
        "mock": False,
    }


def clone_with_workspace(
    db: Session,
    project_id: str,
    character_id: str,
    body: Any,
) -> dict[str, Any]:
    """Clone via existing runtime; enrich lineage for workspace candidates."""
    result = run_voice_clone(db, project_id, character_id, body)
    row = db.get(VoiceProfileRow, result["id"])
    assert row
    lineage = _loads(row.lineage_json, {})
    preview = result.get("preview_asset_id")
    meta = []
    if preview:
        meta.append(
            {
                "id": str(uuid.uuid4()),
                "name": "Clone preview",
                "assetId": preview,
                "status": "ready",
                "method": "CLONE",
                "provider": "qwen3-tts",
                "parentCandidateId": None,
                "createdAt": _now(),
            }
        )
    batch = {
        "id": str(uuid.uuid4()),
        "projectId": project_id,
        "characterId": character_id,
        "method": "clone",
        "designBriefSnapshot": {},
        "masterPrompt": "",
        "candidateIds": [c["id"] for c in meta],
        "createdAt": _now(),
    }
    lineage["candidatesMeta"] = meta
    lineage["candidateBatches"] = list(lineage.get("candidateBatches") or []) + ([batch] if meta else [])
    lineage["workspace"] = "voice_studio"
    _save_lineage(row, lineage)
    row.candidate_asset_ids_json = json.dumps([preview] if preview else [])
    db.commit()
    save_voice_studio_draft(
        db,
        project_id,
        character_id,
        {"phase": "select", "selectedVoiceProfileId": row.id, "latestBatchId": batch["id"] if meta else None},
    )
    return {
        **service.voice_to_dict(row),
        "candidates": meta,
        "batch": batch if meta else None,
        "validation": result.get("validation"),
        "mock": False,
    }


def _voice(db: Session, project_id: str, character_id: str, voice_id: str) -> VoiceProfileRow:
    service.get_profile(db, project_id, character_id)
    row = db.get(VoiceProfileRow, voice_id)
    if not row or row.project_id != project_id or row.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)
    return row
