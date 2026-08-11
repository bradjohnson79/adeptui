"""Character voice design / clone / dialogue execution (M3.3)."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from . import service
from .models import VoiceProfileRow
from .schemas import DialogueGenerateRequest, VoiceConsentCreate, VoiceProfileCreate
from .voice import provider_readiness, validate_generated_wav, validate_voice_reference


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _project_audio_dir(project_id: str) -> Path:
    root = Path(settings.data_dir) / "projects" / project_id / "assets" / "character_voice"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _register_asset(db: Session, project_id: str, path: Path, *, kind: str, name: str) -> str:
    from ..db import Asset

    aid = str(uuid.uuid4())
    asset = Asset(
        id=aid,
        project_id=project_id,
        kind=kind,
        filename=name if name.endswith(".wav") else f"{name}.wav",
        path=str(path),
        tag="character_voice",
        prompt_meta_json=json.dumps({"source": "character_identity", "kind": kind, "label": name}),
    )
    db.add(asset)
    db.commit()
    return aid


def _try_m210b_generate(
    *,
    registry_id: str,
    text: str,
    project_id: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    from ..codirector.m210b import registry as m210b_registry
    from ..codirector.m210b.flags import m210b_audio_sandbox_enabled
    from ..codirector.m210b.schemas import AudioGenerateRequest

    if not m210b_audio_sandbox_enabled():
        raise _err("PROVIDER_UNAVAILABLE", "M2.10b audio sandbox is disabled.", 503)
    adapter = m210b_registry.get_adapter(registry_id)
    if adapter is None:
        raise _err(
            "MODEL_NOT_INSTALLED",
            f"Provider {registry_id} is not registered. Install the model via Source Manager.",
            503,
        )
    health = adapter.health_check()
    if health.get("stub") or not (health.get("ready") or health.get("ok") or getattr(adapter, "is_installed", lambda: False)()):
        raise _err(
            "MODEL_NOT_INSTALLED",
            health.get("message")
            or f"{registry_id} is not installed or not ready. Install Qwen3-TTS / Kokoro via Source Manager.",
            503,
        )
    req = AudioGenerateRequest(
        capabilityId="audio.dialogue.generate",
        projectId=project_id,
        prompt=text,
        format="wav",
        kind="dialogue",
        registryId=registry_id,
    )
    if extra:
        for k, v in extra.items():
            try:
                setattr(req, k, v)
            except Exception:
                pass
    result = adapter.generate(req)
    payload = result.to_dict() if hasattr(result, "to_dict") else (result if isinstance(result, dict) else {})
    out = Path(str(payload.get("assetPath") or payload.get("outputPath") or payload.get("path") or ""))
    if not out.exists():
        raise _err("GENERATION_FAILURE", "Provider returned no output file.", 500)
    return out


def run_voice_design(db: Session, project_id: str, character_id: str, body: Any) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    readiness = provider_readiness()
    design = readiness.get("qwenVoiceDesign") or {}
    if not design.get("ready"):
        raise _err(
            "MODEL_NOT_INSTALLED",
            design.get("message")
            or "Qwen3-TTS Voice Design 1.7B is not installed. Install it from Source Manager to generate real voice candidates.",
            503,
        )

    candidates: list[str] = []
    out_dir = _project_audio_dir(project_id)
    for i in range(int(body.candidate_count)):
        src = _try_m210b_generate(
            registry_id="m2101-voice-design-021",
            text=body.test_line,
            project_id=project_id,
            extra={"voiceDescription": body.voice_design_prompt, "seed": i + 1},
        )
        dest = out_dir / f"design_{uuid.uuid4().hex[:10]}.wav"
        shutil.copy2(src, dest)
        validate_generated_wav(dest)
        aid = _register_asset(db, project_id, dest, kind="audio", name=f"{body.name} candidate {i+1}")
        candidates.append(aid)

    vp = service.create_voice_profile(
        db,
        project_id,
        character_id,
        VoiceProfileCreate(
            name=body.name,
            source_mode="DESIGN",
            provider="qwen3-tts",
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            voice_design_prompt=body.voice_design_prompt,
            language=body.language,
        ),
    )
    row = db.get(VoiceProfileRow, vp["id"])
    assert row
    row.candidate_asset_ids_json = json.dumps(candidates)
    row.status = "REVIEW"
    row.lineage_json = json.dumps(
        {
            "provider": "qwen3-tts",
            "model": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "test_line": body.test_line,
            "candidates": candidates,
        }
    )
    db.commit()
    return {**service.voice_to_dict(row), "candidates": candidates}


def run_voice_clone(db: Session, project_id: str, character_id: str, body: Any) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    if not isinstance(body.consent, VoiceConsentCreate):
        consent = VoiceConsentCreate(**body.consent) if isinstance(body.consent, dict) else body.consent
    else:
        consent = body.consent
    report = validate_voice_reference(body.reference_path, transcript=body.transcript)
    readiness = provider_readiness()
    clone = readiness.get("qwenVoiceClone") or {}

    # Preserve original reference under project assets for later dialogue generation.
    ref_src = Path(body.reference_path)
    ref_dest = _project_audio_dir(project_id) / f"clone_ref_{uuid.uuid4().hex[:10]}{ref_src.suffix or '.wav'}"
    shutil.copy2(ref_src, ref_dest)
    ref_asset_id = _register_asset(db, project_id, ref_dest, kind="audio", name=f"{body.name} reference")

    vp = service.create_voice_profile(
        db,
        project_id,
        character_id,
        VoiceProfileCreate(
            name=body.name,
            source_mode="CLONE",
            provider="qwen3-tts",
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            reference_transcript=body.transcript,
            reference_asset_id=ref_asset_id,
            language="en",
        ),
    )
    service.record_consent(db, project_id, character_id, vp["id"], consent)

    if not clone.get("ready"):
        raise _err(
            "MODEL_NOT_INSTALLED",
            clone.get("message")
            or "Qwen3-TTS Voice Clone 1.7B is not installed. Install it from Source Manager to clone voices.",
            503,
        )

    src = _try_m210b_generate(
        registry_id="m2101-voice-clone-022",
        text=body.test_line,
        project_id=project_id,
        extra={"referenceAudioPath": str(ref_dest), "referenceTranscript": body.transcript},
    )
    dest = _project_audio_dir(project_id) / f"clone_preview_{uuid.uuid4().hex[:10]}.wav"
    shutil.copy2(src, dest)
    validate_generated_wav(dest)
    preview_id = _register_asset(db, project_id, dest, kind="audio", name=f"{body.name} clone preview")
    row = db.get(VoiceProfileRow, vp["id"])
    assert row
    row.reference_asset_id = ref_asset_id
    row.approved_preview_asset_id = preview_id
    row.status = "REVIEW"
    row.lineage_json = json.dumps(
        {
            "provider": "qwen3-tts",
            "model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            "validation": report,
            "test_line": body.test_line,
            "preview_asset_id": preview_id,
            "reference_asset_id": ref_asset_id,
            "reference_path": str(ref_dest),
        }
    )
    db.commit()
    return {**service.voice_to_dict(row), "validation": report, "preview_asset_id": preview_id}


def run_generate_dialogue(
    db: Session,
    project_id: str,
    character_id: str,
    voice_id: str,
    body: DialogueGenerateRequest,
) -> dict[str, Any]:
    profile = service.get_profile(db, project_id, character_id)
    vp = db.get(VoiceProfileRow, voice_id)
    if not vp or vp.project_id != project_id or vp.character_profile_id != character_id:
        raise _err("NOT_FOUND", "Voice Profile not found.", 404)

    text = (body.text or "").strip()
    if not text:
        raise _err("INVALID_REQUEST", "Dialogue text is required.")

    registry_id = None
    model_id = vp.model_id
    if vp.source_mode in ("DESIGN", "CLONE") and vp.provider.startswith("qwen"):
        registry_id = "m2101-voice-clone-022" if vp.source_mode == "CLONE" else "m2101-voice-design-021"
    elif vp.source_mode == "PRESET" or vp.provider in ("kokoro", "kokoro-82m", ""):
        registry_id = "m2101-dialogue-001"
        model_id = model_id or "hexgrad/Kokoro-82M"
    else:
        registry_id = "m2101-dialogue-001"

    readiness = provider_readiness()
    extra: dict[str, Any] = {}
    if vp.source_mode == "DESIGN":
        extra["voiceDescription"] = vp.voice_design_prompt or text
        registry_id = "m2101-voice-design-021"
    elif vp.source_mode == "CLONE":
        registry_id = "m2101-voice-clone-022"
        ref_path = ""
        if vp.reference_asset_id:
            from ..db import Asset

            asset = db.get(Asset, vp.reference_asset_id)
            if asset and asset.path:
                ref_path = str(asset.path)
        if not ref_path and vp.lineage_json:
            try:
                lineage_meta = json.loads(vp.lineage_json)
                preview_id = lineage_meta.get("preview_asset_id")
                if preview_id:
                    from ..db import Asset

                    asset = db.get(Asset, preview_id)
                    if asset and asset.path:
                        ref_path = str(asset.path)
            except Exception:
                pass
        # Fall back to approved preview asset as reference carrier when original missing.
        if not ref_path and vp.approved_preview_asset_id:
            from ..db import Asset

            asset = db.get(Asset, vp.approved_preview_asset_id)
            if asset and asset.path:
                ref_path = str(asset.path)
        if not ref_path or not Path(ref_path).is_file():
            raise _err(
                "MISSING_VOICE_REFERENCE",
                "Clone Voice Profile has no usable local reference audio for dialogue generation.",
                400,
            )
        extra["referenceAudioPath"] = ref_path
        extra["referenceTranscript"] = vp.reference_transcript or text
    try:
        src = _try_m210b_generate(
            registry_id=registry_id, text=text, project_id=project_id, extra=extra
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("code") == "MODEL_NOT_INSTALLED" and body.allow_kokoro_fallback:
            if registry_id != "m2101-dialogue-001" and readiness.get("kokoro", {}).get("ready"):
                # Explicit user-approved fallback only
                src = _try_m210b_generate(registry_id="m2101-dialogue-001", text=text, project_id=project_id)
                model_id = "hexgrad/Kokoro-82M"
                registry_id = "m2101-dialogue-001"
            else:
                raise
        else:
            # Never silent fallback to a different identity
            raise

    dest = _project_audio_dir(project_id) / f"dialogue_{uuid.uuid4().hex[:10]}.wav"
    shutil.copy2(src, dest)
    validate_generated_wav(dest)
    asset_id = _register_asset(db, project_id, dest, kind="audio", name=f"Dialogue: {text[:48]}")
    lineage = {
        "character_id": character_id,
        "character_version_id": profile.active_version_id,
        "voice_profile_id": voice_id,
        "voice_version": vp.version_number,
        "provider": vp.provider or "kokoro",
        "model_id": model_id,
        "registry_id": registry_id,
        "text": text,
        "consent_record_id": vp.consent_record_id,
        "asset_id": asset_id,
        "path": str(dest),
    }
    return {
        "assetId": asset_id,
        "path": str(dest),
        "lineage": lineage,
        "voiceProfileId": voice_id,
        "characterId": character_id,
    }
