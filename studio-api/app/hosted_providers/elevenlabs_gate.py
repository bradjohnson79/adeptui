"""ElevenLabs Direct API gate.

A selected ElevenLabs provider uses the saved ElevenLabs API key only.
Failure stays on ElevenLabs. Local, fal, Kie, and WaveSpeed are not substitutes.
"""
from __future__ import annotations

from typing import Any

from ..secrets_store import secret_status
from .elevenlabs_capability import require_route_or_raise, resolve_capability

# Kept for status reporting only — not Adept subsidy primary.
SECRET_NAME = "elevenlabs_api_key"
PROVIDER_ID = "elevenlabs"


def normalize_provider(value: str | None) -> str:
    raw = (value or "local").strip().lower()
    if raw in ("", "local", "mmaudio", "index-tts2", "index_tts2"):
        return "local"
    if raw in ("elevenlabs", "eleven_labs", "el"):
        return "elevenlabs"
    return raw


def elevenlabs_configured() -> bool:
    """True when the direct ElevenLabs key can execute voice, SFX, or music."""
    return bool(resolve_capability("elevenlabs.voice").get("ok"))


def elevenlabs_api_key_status() -> dict[str, Any]:
    """Credential state only. The raw key is not included."""
    status = secret_status(SECRET_NAME)
    return {
        "configured": bool(status.get("configured")),
        "state": status.get("state") or "missing",
        "verified": status.get("verified"),
        "message": status.get("message") or "",
    }


def elevenlabs_route_status() -> dict[str, Any]:
    voice = resolve_capability("elevenlabs.voice")
    sfx = resolve_capability("elevenlabs.sfx")
    music = resolve_capability("elevenlabs.music")
    return {
        "configured": bool(voice.get("ok")),
        "voice": voice,
        "sfx": sfx,
        "music": music,
        "directApi": True,
        "aggregatorsUsed": False,
        "primaryPath": "elevenlabs direct API",
        "mock": False,
    }


def require_elevenlabs_or_raise(*, surface: str = "generate", capability: str | None = None) -> str:
    """Return the direct ElevenLabs API key, or fail closed."""
    cap = capability or (
        "elevenlabs.sfx" if "audio-studio" in (surface or "") or "sfx" in (surface or "").lower()
        else "elevenlabs.voice"
    )
    route = require_route_or_raise(capability=cap, surface=surface)
    return route["apiKey"]


def require_elevenlabs_route(*, surface: str = "generate", capability: str | None = None) -> dict[str, Any]:
    cap = capability or (
        "elevenlabs.sfx" if "audio-studio" in (surface or "") or "sfx" in (surface or "").lower()
        else "elevenlabs.voice"
    )
    return require_route_or_raise(capability=cap, surface=surface)


def gate_preferred_provider(preferred: str | None, *, surface: str, capability: str | None = None) -> str:
    """Normalize preferred provider. ElevenLabs without a direct key fails closed."""
    provider = normalize_provider(preferred)
    if provider == "elevenlabs":
        require_elevenlabs_or_raise(surface=surface, capability=capability)
    return provider
