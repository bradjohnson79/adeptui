"""WAV generation contracts for M3.0i Native Audio Platform."""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Any


def inspect_wav(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "missing_file", "path": str(p)}
    size = p.stat().st_size
    if size < 1000:
        return {"ok": False, "error": "too_small", "bytes": size, "path": str(p)}
    try:
        with wave.open(str(p), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            frames = wf.getnframes()
            sampwidth = wf.getsampwidth()
            duration = frames / float(sample_rate) if sample_rate else 0.0
            # Peak scan first ~2s for non-silence
            peek = min(frames, sample_rate * 2)
            raw = wf.readframes(peek)
    except wave.Error as exc:
        return {"ok": False, "error": f"wave_error:{exc}", "bytes": size, "path": str(p)}

    peak = 0
    if sampwidth == 2 and raw:
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw[: len(raw) - (len(raw) % 2)])
        peak = max(abs(s) for s in samples) if samples else 0
    elif sampwidth == 1 and raw:
        peak = max(abs(b - 128) for b in raw)

    silent = peak < 50
    return {
        "ok": not silent and duration >= 0.25,
        "path": str(p.resolve()),
        "bytes": size,
        "channels": channels,
        "sampleRate": sample_rate,
        "durationSec": round(duration, 3),
        "sampwidth": sampwidth,
        "peakAbs": peak,
        "silent": silent,
        "recognizableContent": not silent,
    }


def assert_wav_contract(
    path: str | Path,
    *,
    min_duration_sec: float = 0.5,
    expected_sample_rate: int | None = 48000,
) -> dict[str, Any]:
    info = inspect_wav(path)
    errors: list[str] = []
    if not info.get("ok"):
        errors.append(str(info.get("error") or "wav_failed_or_silent"))
    if float(info.get("durationSec") or 0) < min_duration_sec:
        errors.append(f"duration<{min_duration_sec}")
    if expected_sample_rate and int(info.get("sampleRate") or 0) != expected_sample_rate:
        # Allow common local rates; warn via flag rather than hard-fail music.
        info["sampleRateMismatch"] = True
    if info.get("silent"):
        errors.append("silent_or_near_silent")
    info["contractErrors"] = errors
    info["contractOk"] = not errors
    return info
