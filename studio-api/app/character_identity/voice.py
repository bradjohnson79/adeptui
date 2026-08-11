"""Voice reference validation and dialogue generation helpers (M3.3)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Any

from fastapi import HTTPException

MIN_VOICED_SECONDS = 10.0


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def validate_voice_reference(path: str | Path, *, transcript: str = "") -> dict[str, Any]:
    """Validate an uploaded voice reference before cloning."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise _err("INVALID_REFERENCE", "Voice reference file does not exist.")
    suffix = p.suffix.lower()
    if suffix not in {".wav", ".flac", ".mp3", ".m4a"}:
        raise _err("UNSUPPORTED_FORMAT", f"Unsupported audio format: {suffix or '(none)'}")

    duration = 0.0
    sample_rate = 0
    channels = 0
    clipping = False
    silence_ratio = 0.0
    voiced_estimate = 0.0

    if suffix == ".wav":
        try:
            with wave.open(str(p), "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                nframes = wf.getnframes()
                duration = nframes / float(sample_rate or 1)
                sampwidth = wf.getsampwidth()
                raw = wf.readframes(min(nframes, sample_rate * 60 if sample_rate else nframes))
            if sampwidth == 2 and raw:
                samples = struct.unpack("<" + "h" * (len(raw) // 2), raw[: len(raw) - (len(raw) % 2)])
                if samples:
                    peak = max(abs(s) for s in samples)
                    clipping = peak >= 32760
                    silent = sum(1 for s in samples if abs(s) < 200)
                    silence_ratio = silent / len(samples)
                    voiced_estimate = duration * (1.0 - silence_ratio)
        except wave.Error as exc:
            raise _err("INVALID_REFERENCE", f"WAV is not decodable: {exc}") from exc
    else:
        # Non-WAV: require ffmpeg probe when available; else accept file existence with caution.
        try:
            import subprocess
            import json as _json

            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration:stream=sample_rate,channels",
                    "-of",
                    "json",
                    str(p),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0:
                raise _err("INVALID_REFERENCE", "Audio file is not decodable.")
            meta = _json.loads(proc.stdout or "{}")
            duration = float((meta.get("format") or {}).get("duration") or 0)
            streams = meta.get("streams") or []
            if streams:
                sample_rate = int(streams[0].get("sample_rate") or 0)
                channels = int(streams[0].get("channels") or 0)
            voiced_estimate = duration * 0.85
        except HTTPException:
            raise
        except Exception as exc:
            raise _err("INVALID_REFERENCE", f"Unable to probe audio: {exc}") from exc

    if duration <= 0:
        raise _err("INVALID_REFERENCE", "Audio duration is zero or unknown.")
    if voiced_estimate < MIN_VOICED_SECONDS and duration < MIN_VOICED_SECONDS:
        raise _err(
            "INSUFFICIENT_VOICED_DURATION",
            f"Voice reference must contain at least {int(MIN_VOICED_SECONDS)} seconds of speech "
            f"(measured ~{voiced_estimate:.1f}s voiced / {duration:.1f}s total).",
        )
    if not (transcript or "").strip():
        raise _err("EMPTY_TRANSCRIPT", "A transcript is required (provide or review generated transcript).")

    return {
        "ok": True,
        "path": str(p),
        "duration_sec": duration,
        "voiced_duration_sec": voiced_estimate,
        "sample_rate": sample_rate,
        "channels": channels,
        "clipping": clipping,
        "silence_ratio": silence_ratio,
        "format": suffix.lstrip("."),
        "transcript_present": True,
        "min_voiced_seconds": MIN_VOICED_SECONDS,
    }


def validate_generated_wav(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise _err("INVALID_OUTPUT", "Generated audio file does not exist.")
    if p.stat().st_size < 1000:
        raise _err("INVALID_OUTPUT", "Generated audio file is too small.")
    # Prefer soundfile so float32 WAVs are not false-failed as silent int16 PCM.
    try:
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(str(p), always_2d=False)
        arr = np.asarray(data, dtype=float)
        if arr.ndim > 1:
            arr = arr.mean(axis=1)
        dur = float(arr.size) / float(sr or 1)
        if dur <= 0.05:
            raise _err("INVALID_OUTPUT", "Generated audio duration is not usable.")
        peak = float(np.max(np.abs(arr))) if arr.size else 0.0
        if peak < 1e-4:
            raise _err("INVALID_OUTPUT", "Generated audio appears silent.")
        return {"ok": True, "duration_sec": dur, "sample_rate": int(sr), "size": p.stat().st_size, "peak": peak}
    except HTTPException:
        raise
    except Exception:
        pass
    try:
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate()
            n = wf.getnframes()
            dur = n / float(sr or 1)
            raw = wf.readframes(min(n, sr * 5 if sr else n))
        if dur <= 0.05:
            raise _err("INVALID_OUTPUT", "Generated audio duration is not usable.")
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw[: len(raw) - (len(raw) % 2)]) if raw else ()
        if samples and max(abs(s) for s in samples) < 50:
            raise _err("INVALID_OUTPUT", "Generated audio appears silent.")
        return {"ok": True, "duration_sec": dur, "sample_rate": sr, "size": p.stat().st_size}
    except wave.Error as exc:
        raise _err("INVALID_OUTPUT", f"Generated WAV is not decodable: {exc}") from exc


def provider_readiness() -> dict[str, Any]:
    """Honest readiness for Kokoro + Qwen character-voice providers."""
    from ..codirector.m210b import registry as m210b_registry
    from ..codirector.m210b.flags import m210b_audio_sandbox_enabled

    sandbox_on = bool(m210b_audio_sandbox_enabled())
    kokoro = {"registryId": "m2101-dialogue-001", "installed": False, "ready": False, "stub": False}
    qwen_design = {
        "registryId": "m2101-voice-design-021",
        "sourceKey": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "installed": False,
        "ready": False,
        "stub": True,
    }
    qwen_clone = {
        "registryId": "m2101-voice-clone-022",
        "sourceKey": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "installed": False,
        "ready": False,
        "stub": True,
    }
    if sandbox_on:
        try:
            adapter = m210b_registry.get_adapter("m2101-dialogue-001")
            health = adapter.health_check() if adapter else {}
            kokoro["installed"] = bool(getattr(adapter, "is_installed", lambda: False)())
            kokoro["ready"] = bool(health.get("ready") or health.get("ok"))
            kokoro["stub"] = bool(health.get("stub"))
        except Exception as exc:
            kokoro["error"] = str(exc)
        for key, reg_id in (("design", "m2101-voice-design-021"), ("clone", "m2101-voice-clone-022")):
            target = qwen_design if key == "design" else qwen_clone
            try:
                adapter = m210b_registry.get_adapter(reg_id)
                if adapter is None:
                    target["message"] = "Adapter not registered or model not installed."
                    continue
                health = adapter.health_check()
                target["installed"] = bool(getattr(adapter, "is_installed", lambda: False)())
                target["ready"] = bool(health.get("ready") or health.get("ok"))
                target["stub"] = bool(health.get("stub", False))
                if health.get("message"):
                    target["message"] = health["message"]
            except Exception as exc:
                target["error"] = str(exc)
                target["message"] = str(exc)
    return {
        "sandboxEnabled": sandbox_on,
        "kokoro": kokoro,
        "qwenVoiceDesign": qwen_design,
        "qwenVoiceClone": qwen_clone,
    }
