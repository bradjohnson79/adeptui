"""Objective WAV checks for Audio Studio takes.

Semantic audio classification is not available. This only rejects corrupt,
silent, empty, or wildly wrong-duration files — it does not claim the
event identity is correct.

Studio API may not have soundfile installed. Missing optional decoders must
not fail a real take.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Any


def validate_sfx_wav(
    path: str | Path,
    *,
    expected_duration_sec: float | None = None,
) -> dict[str, Any]:
    p = Path(path) if path else Path()
    if not p.is_file():
        return {"ok": False, "reason": "Generated audio file is missing."}
    size = p.stat().st_size
    if size < 1000:
        return {"ok": False, "reason": "Generated audio file is too small to be a real take."}

    try:
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(str(p), always_2d=True)
        arr = np.asarray(data, dtype=float)
        if arr.size == 0:
            return {"ok": False, "reason": "Generated audio has no samples."}
        duration = float(arr.shape[0]) / float(sr or 1)
        peak = float(np.max(np.abs(arr)))
        rms = float(np.sqrt(np.mean(np.square(arr))))
        clipped_frac = float(np.mean(np.abs(arr) >= 0.999))
        if duration <= 0.08:
            return {"ok": False, "reason": "Generated audio is too short to use."}
        if peak < 1e-4 or rms < 1e-5:
            return {"ok": False, "reason": "Generated audio appears silent."}
        if clipped_frac > 0.35:
            return {"ok": False, "reason": "Generated audio is heavily clipped or corrupt."}
        if expected_duration_sec and expected_duration_sec > 0:
            if duration < max(0.4, expected_duration_sec * 0.35):
                return {
                    "ok": False,
                    "reason": (
                        f"Generated audio is {duration:.2f}s, much shorter than the "
                        f"requested {expected_duration_sec:.1f}s."
                    ),
                }
        return {
            "ok": True,
            "durationSec": duration,
            "sampleRate": int(sr),
            "peak": peak,
            "rms": rms,
            "clippedFraction": clipped_frac,
            "bytes": size,
            "semanticClassification": False,
            "note": "Objective WAV checks only. Event identity still needs human review.",
        }
    except Exception:
        pass

    try:
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate() or 1
            n = wf.getnframes()
            duration = n / float(sr)
            raw = wf.readframes(min(n, sr * 4))
        if duration <= 0.08:
            return {"ok": False, "reason": "Generated audio is too short to use."}
        if len(raw) >= 4:
            samples = struct.unpack("<" + "h" * (len(raw) // 2), raw[: len(raw) - (len(raw) % 2)])
            peak = max((abs(s) for s in samples), default=0)
            if peak < 40:
                return {"ok": False, "reason": "Generated audio appears silent."}
        if expected_duration_sec and duration < max(0.4, expected_duration_sec * 0.35):
            return {
                "ok": False,
                "reason": (
                    f"Generated audio is {duration:.2f}s, much shorter than the "
                    f"requested {expected_duration_sec:.1f}s."
                ),
            }
        return {
            "ok": True,
            "durationSec": duration,
            "sampleRate": int(sr),
            "bytes": size,
            "decoder": "wave",
            "semanticClassification": False,
        }
    except Exception:
        # Float32 WAVs often fail stdlib wave. A real-size file still stands.
        return {
            "ok": True,
            "bytes": size,
            "decoder": "size-only",
            "semanticClassification": False,
            "note": "Accepted by size because a full decoder is not installed in Studio API.",
        }
