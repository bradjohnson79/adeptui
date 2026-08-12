"""Audio metadata helpers for MiniMax H3 provenance."""

from __future__ import annotations

from typing import Any


def detect_native_stereo_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    payload = metadata or {}
    channels = payload.get("channels", payload.get("audioChannels"))
    sample_rate = payload.get("sampleRateHz", payload.get("sampleRate"))
    stereo = channels == 2 or bool(payload.get("stereo"))
    return {
        "stereoDetected": bool(stereo),
        "channels": int(channels) if isinstance(channels, int) else None,
        "sampleRateHz": int(sample_rate) if isinstance(sample_rate, int) else None,
    }


def register_native_audio_provenance(provenance: dict[str, Any], metadata: dict[str, Any] | None) -> dict[str, Any]:
    audio = detect_native_stereo_metadata(metadata)
    next_provenance = dict(provenance or {})
    next_provenance["audio"] = {
        "nativeStereoDetected": audio["stereoDetected"],
        "channels": audio["channels"],
        "sampleRateHz": audio["sampleRateHz"],
        "stemsDetected": False,
        "note": "Stereo metadata is recorded only when it is present in the source.",
    }
    return next_provenance
