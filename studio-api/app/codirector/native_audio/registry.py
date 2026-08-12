"""Capability-specific native audio provider registry (no generic audio.generate)."""

from __future__ import annotations

from typing import Any

# Role-specific capabilities — do not collapse into a single audio.generate.
PROVIDER_CAPS: dict[str, dict[str, Any]] = {
    "ace-step": {
        "registryId": "m2101-music-045",
        "capabilities": ["music.generate"],
        "route": "isolated_worker_subprocess",
    },
    "mmaudio": {
        "registryId": "m2101-sfx-031",
        "capabilities": ["sfx.generate", "ambience.generate", "foley.generate"],
        "route": "isolated_worker_subprocess",
    },
    "stable-audio-tools": {
        "registryId": "m2101-sfx-021",
        "capabilities": ["sfx.generate", "ambience.generate", "foley.generate"],
        "route": "isolated_worker_subprocess",
        "fallbackFor": "mmaudio",
    },
    "kokoro": {
        "registryId": "m2101-dialogue-001",
        "capabilities": ["speech.generate", "audio.dialogue.generate"],
        "route": "isolated_worker_subprocess",
    },
}


def capability_for_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k == "music":
        return "music.generate"
    if k in ("sfx", "foley"):
        return "sfx.generate"
    if k == "ambience":
        return "ambience.generate"
    if k in ("dialogue", "speech", "tts"):
        return "speech.generate"
    raise ValueError(f"unsupported audio kind: {kind}")


def resolve_native_audio_provider(kind: str) -> dict[str, Any]:
    """Pick preferred local provider for kind; disclose fallbacks."""
    cap = capability_for_kind(kind)
    if cap == "music.generate":
        return {
            "requestedCapability": cap,
            "preferredProvider": "ace-step",
            "selectedProvider": "ace-step",
            "fallbackUsed": False,
            "registryId": PROVIDER_CAPS["ace-step"]["registryId"],
        }
    if cap in ("sfx.generate", "ambience.generate", "foley.generate"):
        # Prefer MMAudio; caller may flip to stable-audio-tools when install fails.
        return {
            "requestedCapability": cap,
            "preferredProvider": "mmaudio",
            "selectedProvider": "mmaudio",
            "fallbackUsed": False,
            "registryId": PROVIDER_CAPS["mmaudio"]["registryId"],
        }
    return {
        "requestedCapability": cap,
        "preferredProvider": "kokoro",
        "selectedProvider": "kokoro",
        "fallbackUsed": False,
        "registryId": PROVIDER_CAPS["kokoro"]["registryId"],
    }
