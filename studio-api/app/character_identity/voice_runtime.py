"""Character voice design / clone / dialogue execution (M3.3)."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from . import service
from .models import VoiceProfileRow
from .schemas import DialogueGenerateRequest, VoiceConsentCreate, VoiceProfileCreate
from .spoken_pronunciation import apply_spoken_pronunciations, entries_from_voice
from .voice import provider_readiness, validate_generated_wav, validate_voice_reference


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _project_audio_dir(project_id: str) -> Path:
    root = Path(settings.data_dir) / "projects" / project_id / "assets" / "character_voice"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _register_asset(
    db: Session,
    project_id: str,
    path: Path,
    *,
    kind: str,
    name: str,
    tag: str = "character_voice",
    extra_meta: dict[str, Any] | None = None,
) -> str:
    from ..db import Asset

    aid = str(uuid.uuid4())
    meta = {"source": "character_identity", "kind": kind, "label": name}
    if extra_meta:
        meta.update(extra_meta)
    asset = Asset(
        id=aid,
        project_id=project_id,
        kind=kind,
        filename=name if name.endswith(".wav") else f"{name}.wav",
        path=str(path),
        tag=tag,
        prompt_meta_json=json.dumps(meta),
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


ProgressCb = Callable[[dict[str, Any]], None]


def _emit_voice_progress(progress_cb: ProgressCb | None, **payload: Any) -> None:
    if progress_cb is None:
        return
    progress_cb(payload)


def run_voice_design(
    db: Session,
    project_id: str,
    character_id: str,
    body: Any,
    progress_cb: ProgressCb | None = None,
) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    _emit_voice_progress(progress_cb, phase="preparing", sampleIndex=0, completedSamples=0)
    readiness = provider_readiness()
    design = readiness.get("qwenVoiceDesign") or {}
    if not design.get("ready"):
        raise _err(
            "MODEL_NOT_INSTALLED",
            design.get("message")
            or "Qwen3-TTS Voice Design 1.7B is not installed. Install it from Source Manager to generate real voice candidates.",
            503,
        )

    from .voice_preview import DESIGN_VRAM_MIB_REQUIRED, variation_instruct

    candidates: list[str] = []
    errors: list[str] = []
    timings: list[dict[str, Any]] = []
    last_block: HTTPException | None = None
    wanted = max(1, min(int(body.candidate_count), 6))
    _stop_voice_serve("clone")
    _require_voice_vram(DESIGN_VRAM_MIB_REQUIRED, kind="design")
    _emit_voice_progress(progress_cb, phase="preparing_model", sampleIndex=0, completedSamples=0)
    for i in range(wanted):
        _emit_voice_progress(
            progress_cb,
            phase="generating_sample",
            sampleIndex=i + 1,
            completedSamples=i,
        )
        try:
            produced = generate_voice_design_sample(
                project_id=project_id,
                text=body.test_line,
                instruct=variation_instruct(body.voice_design_prompt, i),
                seed=i + 1,
            )
            dest = Path(produced["path"])
            validate_generated_wav(dest)
            aid = _register_asset(db, project_id, dest, kind="audio", name=f"{body.name} candidate {i+1}")
            candidates.append(aid)
            _emit_voice_progress(
                progress_cb,
                phase="generating_sample",
                sampleIndex=i + 1,
                completedSamples=len(candidates),
            )
            timings.append(
                {
                    "index": i,
                    "completeMs": produced.get("complete_ms"),
                    "firstAudioMs": produced.get("first_audio_ms"),
                    "device": produced.get("device"),
                    "warmWorker": True,
                }
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            message = str(detail.get("message") or exc.detail)
            errors.append(message)
            last_block = exc
            if detail.get("code") in {"GPU_MEMORY", "MODEL_NOT_INSTALLED"}:
                break
    if not candidates:
        if last_block is not None:
            raise last_block
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Design produced no samples.", 500)

    _emit_voice_progress(
        progress_cb,
        phase="saving",
        sampleIndex=wanted,
        completedSamples=len(candidates),
    )
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
            "quality": "full",
            "warmWorker": True,
            "timings": timings,
            "candidateErrors": errors,
        }
    )
    db.commit()
    return {
        **service.voice_to_dict(row),
        "candidates": candidates,
        "errors": errors,
        "timings": timings,
        "warmWorker": True,
    }


def resolve_clone_reference_path(db: Session, project_id: str, body: Any) -> Path:
    """Resolve the uploaded recording from asset id first, then filesystem path."""
    asset_id = str(
        getattr(body, "reference_asset_id", "") or getattr(body, "referenceAssetId", "") or ""
    ).strip()
    raw = str(getattr(body, "reference_path", "") or getattr(body, "referencePath", "") or "").strip()
    if asset_id:
        from ..db import Asset

        asset = db.get(Asset, asset_id)
        if asset is None or asset.project_id != project_id:
            raise _err("INVALID_REFERENCE", "The uploaded recording is not in this project.")
        path = Path(str(asset.path or ""))
        if path.is_file():
            return path
        raise _err("INVALID_REFERENCE", "The uploaded recording file is missing from disk.")
    if raw:
        path = Path(raw)
        if path.is_file():
            return path
    raise _err("INVALID_REFERENCE", "Choose a recording to clone. The uploaded file could not be found.")


def studio_clone_consent(consent: VoiceConsentCreate) -> VoiceConsentCreate:
    """One Voice Studio permission checkbox is consent to clone and synthesize."""
    if consent.consent_confirmed and not consent.synthetic_generation_allowed:
        data = consent.model_dump()
        data["synthetic_generation_allowed"] = True
        return VoiceConsentCreate(**data)
    return consent


def _clone_spoken_line(body: Any) -> str:
    return str(getattr(body, "testLine", None) or getattr(body, "test_line", None) or "").strip()


def _clone_wanted_count(body: Any) -> int:
    raw = getattr(body, "sampleCount", None)
    if raw is None:
        raw = getattr(body, "candidateCount", None)
    if raw is None:
        raw = getattr(body, "candidate_count", 4)
    try:
        return max(1, min(int(raw), 6))
    except (TypeError, ValueError):
        return 4


def run_voice_clone(
    db: Session,
    project_id: str,
    character_id: str,
    body: Any,
    progress_cb: ProgressCb | None = None,
) -> dict[str, Any]:
    service.get_profile(db, project_id, character_id)
    _emit_voice_progress(progress_cb, phase="preparing", sampleIndex=0, completedSamples=0)
    if not isinstance(body.consent, VoiceConsentCreate):
        consent = VoiceConsentCreate(**body.consent) if isinstance(body.consent, dict) else body.consent
    else:
        consent = body.consent
    if not consent.consent_confirmed:
        raise _err(
            "CONSENT_MISSING",
            "Confirm you have permission to clone this recording before generating samples.",
        )
    consent = studio_clone_consent(consent)
    spoken = _clone_spoken_line(body)
    if not spoken:
        raise _err(
            "MISSING_SCRIPT",
            "Enter the line the cloned voice should speak. That is new dialogue, not a transcript of the recording.",
        )
    from .voice_preview import DESIGN_VRAM_MIB_REQUIRED

    _stop_voice_serve("design")
    _require_voice_vram(DESIGN_VRAM_MIB_REQUIRED, kind="clone")
    wanted = _clone_wanted_count(body)
    ref_src = resolve_clone_reference_path(db, project_id, body)
    transcript = str(getattr(body, "transcript", "") or "").strip()
    _emit_voice_progress(progress_cb, phase="analyzing_voice", sampleIndex=0, completedSamples=0)
    report = validate_voice_reference(ref_src, transcript=transcript)
    readiness = provider_readiness()
    clone = readiness.get("qwenVoiceClone") or {}

    # Preserve original reference under project assets for later dialogue generation.
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
            reference_transcript=transcript,
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

    _emit_voice_progress(progress_cb, phase="preparing_model", sampleIndex=0, completedSamples=0)
    candidates: list[str] = []
    errors: list[str] = []
    timings: list[dict[str, Any]] = []
    last_block: HTTPException | None = None
    for i in range(wanted):
        _emit_voice_progress(
            progress_cb,
            phase="generating_sample",
            sampleIndex=i + 1,
            completedSamples=i,
        )
        try:
            produced = generate_voice_clone_sample(
                project_id=project_id,
                text=spoken,
                reference_audio=ref_dest,
                reference_transcript=transcript,
                seed=i + 1,
            )
            dest = Path(produced["path"])
            validate_generated_wav(dest)
            aid = _register_asset(db, project_id, dest, kind="audio", name=f"{body.name} clone sample {i + 1}")
            candidates.append(aid)
            _emit_voice_progress(
                progress_cb,
                phase="generating_sample",
                sampleIndex=i + 1,
                completedSamples=len(candidates),
            )
            timings.append(
                {
                    "index": i,
                    "completeMs": produced.get("complete_ms"),
                    "firstAudioMs": produced.get("first_audio_ms"),
                    "device": produced.get("device"),
                    "warmWorker": True,
                }
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
            message = str(detail.get("message") or exc.detail)
            errors.append(message)
            last_block = exc
            if detail.get("code") in {"GPU_MEMORY", "MODEL_NOT_INSTALLED"}:
                break
    if not candidates:
        if last_block is not None:
            raise last_block
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Clone produced no samples.", 500)

    _emit_voice_progress(
        progress_cb,
        phase="saving",
        sampleIndex=wanted,
        completedSamples=len(candidates),
    )
    preview_id = candidates[0]
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
            "test_line": spoken,
            "preview_asset_id": preview_id,
            "reference_asset_id": ref_asset_id,
            "reference_path": str(ref_dest),
            "candidateCount": wanted,
            "warmWorker": True,
            "engine": "qwen3-tts",
            "errors": errors,
            "timings": timings,
        }
    )
    db.commit()
    return {
        **service.voice_to_dict(row),
        "validation": report,
        "preview_asset_id": preview_id,
        "candidates": candidates,
        "errors": errors,
        "timings": timings,
        "warmWorker": True,
    }


def dialogue_style_text(body: DialogueGenerateRequest) -> str:
    """Plain-language delivery notes from generate-dialogue (not spoken words)."""
    parts = [
        str(getattr(body, "emotional_direction", "") or "").strip(),
        str(getattr(body, "performance_instruction", "") or "").strip(),
        str(getattr(body, "pace", "") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def reject_clone_performance_style(voice: VoiceProfileRow, body: DialogueGenerateRequest) -> None:
    """Qwen clone has no instruct/emotion API — refuse style instead of ignoring it."""
    style = dialogue_style_text(body)
    if not style:
        return
    mode = str(voice.source_mode or "").upper()
    if mode != "CLONE":
        return
    raise _err(
        "STYLE_UNSUPPORTED",
        "This cloned voice keeps the recorded performance. Whisper, angry, and other "
        "delivery notes are not applied. Generate the line without those fields, or "
        "use a designed voice when you need a different delivery.",
        400,
    )


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

    source_text = (body.text or "").strip()
    if not source_text:
        raise _err("INVALID_REQUEST", "Dialogue text is required.")
    reject_clone_performance_style(vp, body)
    text, pronunciations_applied = apply_spoken_pronunciations(source_text, entries_from_voice(vp))
    style = dialogue_style_text(body)

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
    if qwen_speech_compatible(vp):
        produced = generate_approved_voice_speech(
            db,
            project_id=project_id,
            voice=vp,
            text=source_text,
            performance_instruct=style,
        )
        src = Path(produced["path"])
        dest = _project_audio_dir(project_id) / f"dialogue_{uuid.uuid4().hex[:10]}.wav"
        shutil.copy2(src, dest)
        validate_generated_wav(dest)
        asset_id = _register_asset(db, project_id, dest, kind="audio", name=f"Dialogue: {source_text[:48]}")
        lineage = {
            "character_id": character_id,
            "character_version_id": profile.active_version_id,
            "voice_profile_id": voice_id,
            "voice_version": vp.version_number,
            "provider": vp.provider,
            "model_id": vp.model_id,
            "engine": "qwen3-tts",
            "warmWorker": True,
            "text": source_text,
            "spokenText": produced.get("spokenText") or text,
            "pronunciationsApplied": produced.get("pronunciationsApplied") or pronunciations_applied,
            "performanceInstruct": style or None,
            "styleApplied": bool(style) and str(vp.source_mode or "").upper() == "DESIGN",
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
            "warmWorker": True,
            "engine": "qwen3-tts",
            "completeMs": produced.get("complete_ms"),
        }
    if vp.source_mode == "DESIGN":
        extra["voiceDescription"] = vp.voice_design_prompt or text
        registry_id = "m2101-voice-design-021"
    elif vp.source_mode == "CLONE":
        registry_id = "m2101-voice-clone-022"
        ref_path = resolve_voice_reference_path(db, vp)
        if ref_path is None:
            raise _err(
                "MISSING_VOICE_REFERENCE",
                "Clone Voice Profile has no usable local reference audio for dialogue generation.",
                400,
            )
        extra["referenceAudioPath"] = str(ref_path)
        extra["referenceTranscript"] = vp.reference_transcript or source_text
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
    asset_id = _register_asset(db, project_id, dest, kind="audio", name=f"Dialogue: {source_text[:48]}")
    lineage = {
        "character_id": character_id,
        "character_version_id": profile.active_version_id,
        "voice_profile_id": voice_id,
        "voice_version": vp.version_number,
        "provider": vp.provider or "kokoro",
        "model_id": model_id,
        "registry_id": registry_id,
        "text": source_text,
        "spokenText": text,
        "pronunciationsApplied": pronunciations_applied,
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


_DESIGN_SERVE_LOCK = threading.Lock()
_DESIGN_SERVE: dict[str, Any] | None = None


def _gpu_free_mib() -> int | None:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode != 0:
            return None
        values = [int(float(part.strip())) for part in (proc.stdout or "").splitlines() if part.strip()]
        return max(values) if values else None
    except Exception:
        return None


def _comfy_queue_busy(queue: dict[str, Any] | None) -> bool:
    if not isinstance(queue, dict):
        return True
    return bool(queue.get("queue_running") or queue.get("queue_pending"))


def release_idle_comfy_models_for_voice() -> bool:
    """Ask the existing Comfy /free path to drop idle models before Qwen voice load.

    Does not restart Comfy. Skips the request when a prompt is queued or running.
    """
    from ..comfy_client import comfy

    async def _go() -> bool:
        try:
            queue = await comfy.get_queue()
        except Exception:
            return False
        if _comfy_queue_busy(queue):
            return False
        await comfy.free_memory(unload_models=True, free_memory=True)
        return True

    try:
        return bool(asyncio.run(_go()))
    except RuntimeError:
        return False


def _stop_voice_serve(slot: str) -> None:
    """Stop the other Adept-owned Qwen voice worker so clone and design do not both stay resident."""
    global _DESIGN_SERVE, _CLONE_SERVE
    if slot not in {"design", "clone"}:
        return
    with _DESIGN_SERVE_LOCK:
        with _CLONE_SERVE_LOCK:
            current = _DESIGN_SERVE if slot == "design" else _CLONE_SERVE
            proc = (current or {}).get("proc") if isinstance(current, dict) else None
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
            if slot == "design":
                _DESIGN_SERVE = None
            else:
                _CLONE_SERVE = None


def _require_voice_vram(required_mib: int, *, kind: str) -> None:
    """Free idle Comfy models when Qwen voice needs room, then refuse if memory is still short."""
    free = _gpu_free_mib()
    if free is None or free >= required_mib:
        return
    release_idle_comfy_models_for_voice()
    time.sleep(0.8)
    free = _gpu_free_mib()
    if free is None or free >= required_mib:
        return
    noun = "Voice cloning" if kind == "clone" else "Voice generation"
    raise _err(
        "GPU_MEMORY",
        (
            f"{noun} needs about 4 GB of free GPU memory for Qwen3-TTS. "
            f"Only {free} MiB is free right now, so generation did not start. "
            "It did not switch to another engine or CPU."
        ),
        503,
    )


def _design_adapter():
    from ..codirector.m210b import registry as m210b_registry

    adapter = m210b_registry.get_adapter("m2101-voice-design-021")
    if adapter is None:
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Design is not registered.", 503)
    return adapter


def _start_design_serve_locked() -> dict[str, Any]:
    from .voice_preview import DESIGN_VRAM_MIB_REQUIRED

    adapter = _design_adapter()
    py = adapter._venv_python()
    models = adapter.sandbox_root / "models"
    worker = Path(__file__).resolve().parents[1] / "codirector" / "native_audio" / "qwen_voice_design_worker.py"
    if not py or not Path(py).is_file():
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Design Python environment is missing.", 503)
    if not models.is_dir():
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Design weights are missing.", 503)
    _require_voice_vram(DESIGN_VRAM_MIB_REQUIRED, kind="design")
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [str(py), str(worker), "--models-dir", str(models), "--serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )
    assert proc.stdout is not None
    deadline = time.time() + 240
    ready: dict[str, Any] | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else "") or ""
            raise _err("GENERATION_FAILURE", f"Qwen3-TTS Voice Design failed to start: {err[:600]}", 503)
        line = proc.stdout.readline()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("type") == "ready":
            ready = payload
            break
        if payload.get("type") == "error":
            raise _err("GENERATION_FAILURE", str(payload.get("message") or "Qwen3-TTS failed to load."), 503)
    if ready is None:
        proc.kill()
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Design did not become ready in time.", 503)
    return {"proc": proc, "ready": ready}


def _design_serve() -> dict[str, Any]:
    global _DESIGN_SERVE
    with _DESIGN_SERVE_LOCK:
        current = _DESIGN_SERVE
        if current and current["proc"].poll() is None:
            return current
        _DESIGN_SERVE = _start_design_serve_locked()
        return _DESIGN_SERVE


def generate_voice_design_sample(
    *,
    project_id: str,
    text: str,
    instruct: str,
    seed: int,
    preview: bool = False,
) -> dict[str, Any]:
    """Generate one full-quality Voice Design WAV on the warm Qwen worker."""
    dest = _project_audio_dir(project_id) / f"design_{uuid.uuid4().hex[:10]}.wav"
    serve = _design_serve()
    proc = serve["proc"]
    if proc.stdin is None or proc.stdout is None:
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Design serve pipes are missing.", 500)
    spoken, _applied = apply_spoken_pronunciations(text)
    job = {
        "id": uuid.uuid4().hex[:10],
        "text": spoken,
        "instruct": instruct,
        "output": str(dest),
        "seed": int(seed),
        "preview": False,
    }
    if preview:
        # Retired product path. Full-quality generate never caps tokens.
        job["preview"] = False
    with _DESIGN_SERVE_LOCK:
        proc.stdin.write(json.dumps(job) + "\n")
        proc.stdin.flush()
        deadline = time.time() + 600
        while time.time() < deadline:
            if proc.poll() is not None:
                raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Design serve exited during generation.", 503)
            line = proc.stdout.readline()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("id") and payload.get("id") != job["id"]:
                continue
            if payload.get("type") == "done":
                validate_generated_wav(dest)
                return {
                    "path": dest,
                    "first_audio_ms": int(payload.get("first_audio_ms") or 0),
                    "complete_ms": int(payload.get("complete_ms") or 0),
                    "streaming": False,
                    "device": payload.get("device") or "cuda:0",
                    "engine": "qwen3-tts",
                    "warm_worker": True,
                }
            if payload.get("type") == "error":
                raise _err("GENERATION_FAILURE", str(payload.get("message") or "Voice generation failed."), 500)
        raise _err("GENERATION_FAILURE", "Voice generation timed out waiting for Qwen3-TTS.", 504)


_CLONE_SERVE_LOCK = threading.Lock()
_CLONE_SERVE: dict[str, Any] | None = None


def _clone_adapter():
    from ..codirector.m210b import registry as m210b_registry

    adapter = m210b_registry.get_adapter("m2101-voice-clone-022")
    if adapter is None:
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Clone is not registered.", 503)
    return adapter


def _start_clone_serve_locked() -> dict[str, Any]:
    from .voice_preview import DESIGN_VRAM_MIB_REQUIRED

    adapter = _clone_adapter()
    py = adapter._venv_python()
    models = adapter.sandbox_root / "models"
    worker = Path(__file__).resolve().parents[1] / "codirector" / "native_audio" / "qwen_voice_clone_worker.py"
    if not py or not Path(py).is_file():
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Clone Python environment is missing.", 503)
    if not models.is_dir():
        raise _err("MODEL_NOT_INSTALLED", "Qwen3-TTS Voice Clone weights are missing.", 503)
    _require_voice_vram(DESIGN_VRAM_MIB_REQUIRED, kind="clone")
    creationflags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [str(py), str(worker), "--models-dir", str(models), "--serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )
    assert proc.stdout is not None
    deadline = time.time() + 240
    ready: dict[str, Any] | None = None
    while time.time() < deadline:
        if proc.poll() is not None:
            err = (proc.stderr.read() if proc.stderr else "") or ""
            raise _err("GENERATION_FAILURE", f"Qwen3-TTS Voice Clone failed to start: {err[:600]}", 503)
        line = proc.stdout.readline()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("type") == "ready":
            ready = payload
            break
        if payload.get("type") == "error":
            raise _err("GENERATION_FAILURE", str(payload.get("message") or "Qwen3-TTS clone failed to load."), 503)
    if ready is None:
        proc.kill()
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Clone did not become ready in time.", 503)
    return {"proc": proc, "ready": ready}


def _clone_serve() -> dict[str, Any]:
    global _CLONE_SERVE
    with _CLONE_SERVE_LOCK:
        current = _CLONE_SERVE
        if current and current["proc"].poll() is None:
            return current
        _CLONE_SERVE = _start_clone_serve_locked()
        return _CLONE_SERVE


def generate_voice_clone_sample(
    *,
    project_id: str,
    text: str,
    reference_audio: Path,
    reference_transcript: str = "",
    seed: int = 1,
) -> dict[str, Any]:
    """Generate one full-quality Voice Clone WAV on the warm Qwen worker."""
    dest = _project_audio_dir(project_id) / f"clone_{uuid.uuid4().hex[:10]}.wav"
    serve = _clone_serve()
    proc = serve["proc"]
    if proc.stdin is None or proc.stdout is None:
        raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Clone serve pipes are missing.", 500)
    spoken, _applied = apply_spoken_pronunciations(text)
    job = {
        "id": uuid.uuid4().hex[:10],
        "text": spoken,
        "reference_audio": str(reference_audio),
        "reference_transcript": reference_transcript or "",
        "output": str(dest),
        "seed": int(seed),
    }
    with _CLONE_SERVE_LOCK:
        proc.stdin.write(json.dumps(job) + "\n")
        proc.stdin.flush()
        deadline = time.time() + 600
        while time.time() < deadline:
            if proc.poll() is not None:
                raise _err("GENERATION_FAILURE", "Qwen3-TTS Voice Clone serve exited during generation.", 503)
            line = proc.stdout.readline()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("id") and payload.get("id") != job["id"]:
                continue
            if payload.get("type") == "done":
                validate_generated_wav(dest)
                return {
                    "path": dest,
                    "first_audio_ms": int(payload.get("first_audio_ms") or 0),
                    "complete_ms": int(payload.get("complete_ms") or 0),
                    "streaming": False,
                    "device": payload.get("device") or "cuda:0",
                    "engine": "qwen3-tts",
                    "warm_worker": True,
                }
            if payload.get("type") == "error":
                raise _err("GENERATION_FAILURE", str(payload.get("message") or "Voice clone generation failed."), 500)
        raise _err("GENERATION_FAILURE", "Voice clone generation timed out waiting for Qwen3-TTS.", 504)


def qwen_speech_compatible(voice: VoiceProfileRow | None) -> bool:
    if voice is None:
        return False
    provider = str(voice.provider or "").lower()
    mode = str(voice.source_mode or "").upper()
    return provider.startswith("qwen") and mode in {"CLONE", "DESIGN"}


def resolve_voice_reference_path(db: Session, voice: VoiceProfileRow) -> Path | None:
    from ..db import Asset

    candidate_ids = [voice.reference_asset_id, voice.approved_preview_asset_id]
    for asset_id in candidate_ids:
        if not asset_id:
            continue
        asset = db.get(Asset, asset_id)
        if asset and asset.path and Path(asset.path).is_file():
            return Path(asset.path)
    if voice.lineage_json:
        try:
            lineage = json.loads(voice.lineage_json)
        except Exception:
            lineage = {}
        for key in ("reference_path", "preview_path"):
            path = Path(str(lineage.get(key) or ""))
            if path.is_file():
                return path
        preview_id = lineage.get("preview_asset_id") or lineage.get("reference_asset_id")
        if preview_id:
            asset = db.get(Asset, str(preview_id))
            if asset and asset.path and Path(asset.path).is_file():
                return Path(asset.path)
    return None


def generate_approved_voice_speech(
    db: Session,
    *,
    project_id: str,
    voice: VoiceProfileRow,
    text: str,
    seed: int = 1,
    performance_instruct: str = "",
) -> dict[str, Any]:
    """Speak a new line with the approved Qwen voice on the warm worker."""
    source = (text or "").strip()
    if not source:
        raise _err("INVALID_REQUEST", "Dialogue text is required.")
    spoken, applied = apply_spoken_pronunciations(source, entries_from_voice(voice))
    if not qwen_speech_compatible(voice):
        raise _err(
            "ENGINE_INCOMPATIBLE",
            "This approved voice is not on the shared Qwen voice worker.",
            409,
        )
    mode = str(voice.source_mode or "").upper()
    if mode == "CLONE":
        ref_path = resolve_voice_reference_path(db, voice)
        if ref_path is None:
            raise _err(
                "MISSING_VOICE_REFERENCE",
                "The approved clone voice has no usable local reference audio.",
                400,
            )
        produced = generate_voice_clone_sample(
            project_id=project_id,
            text=spoken,
            reference_audio=ref_path,
            reference_transcript=str(voice.reference_transcript or ""),
            seed=seed,
        )
        produced["sourceMode"] = "CLONE"
        produced["referencePath"] = str(ref_path)
        produced["sourceText"] = source
        produced["spokenText"] = spoken
        produced["pronunciationsApplied"] = applied
        return produced
    instruct = " ".join(
        part for part in (str(voice.voice_design_prompt or "").strip(), (performance_instruct or "").strip()) if part
    ).strip() or spoken
    produced = generate_voice_design_sample(
        project_id=project_id,
        text=spoken,
        instruct=instruct,
        seed=seed,
    )
    produced["sourceMode"] = "DESIGN"
    produced["instruct"] = instruct
    produced["sourceText"] = source
    produced["spokenText"] = spoken
    produced["pronunciationsApplied"] = applied
    return produced
