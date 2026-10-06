"""ElevenLabs Direct API capability.

Voice, sound effects, and music resolve only to the configured ElevenLabs API
key. fal.ai, Kie, and WaveSpeed are never selected for these capabilities.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException

from ..secrets_store import get_secret, secret_status

CapabilityId = Literal["elevenlabs.voice", "elevenlabs.sfx", "elevenlabs.music"]

_CAPABILITIES = ("elevenlabs.voice", "elevenlabs.sfx", "elevenlabs.music")
_SECRET = "elevenlabs_api_key"

_DEFAULT_MODELS = {
    "elevenlabs.voice": "eleven_multilingual_v2",
    "elevenlabs.sfx": "eleven_text_to_sound_v2",
    "elevenlabs.music": "",
}


def _status() -> dict[str, Any]:
    """Safe credential state. Never includes the key, hint, or fingerprint."""
    st = secret_status(_SECRET)
    state = str(st.get("state") or "missing")
    present = bool(get_secret(_SECRET))
    if not present or state == "missing":
        status = "unavailable"
    elif state == "invalid":
        status = "invalid"
    elif state == "verified":
        status = "available"
    else:
        status = "configured"
    return {"status": status, "credentialState": state, "present": present}


def resolve_capability(capability: CapabilityId | str) -> dict[str, Any]:
    """Resolve an ElevenLabs capability to the direct API only."""
    cap = (capability or "").strip()
    if cap not in _CAPABILITIES:
        return {
            "ok": False,
            "capability": cap,
            "selected": None,
            "candidates": [],
            "explanation": f"Unknown capability '{cap}'. Expected voice, sound effects, or music.",
            "silentFallback": False,
            "directApi": True,
            "aggregatorsUsed": False,
            "mock": False,
        }

    status = _status()
    model_id = _DEFAULT_MODELS[cap]
    can = status["status"] in ("available", "configured")
    if status["status"] == "invalid":
        reason = "ElevenLabs rejected the saved API key."
    elif status["status"] == "unavailable":
        reason = "ElevenLabs API key not configured."
    elif status["status"] == "configured":
        reason = "ElevenLabs API key is saved. Availability is confirmed after a successful key test."
    else:
        reason = "ElevenLabs direct API is available."

    selected = None
    if can:
        selected = {
            "providerId": "elevenlabs",
            "displayName": "ElevenLabs API",
            "secretName": _SECRET,
            "modelId": model_id,
            "canExecute": True,
            "credentialState": status["credentialState"],
            "directApi": True,
            "reason": reason,
        }
    return {
        "ok": bool(selected),
        "capability": cap,
        "status": status["status"],
        "selected": selected,
        "alternatives": [],
        "candidates": [selected] if selected else [],
        "explanation": reason,
        "silentFallback": False,
        "directApi": True,
        "aggregatorsUsed": False,
        "mock": False,
    }


def require_route_or_raise(*, capability: CapabilityId | str, surface: str = "generate") -> dict[str, Any]:
    """Fail closed on the direct ElevenLabs key. Never returns another provider's key."""
    resolution = resolve_capability(capability)
    status = str(resolution.get("status") or "unavailable")
    if status == "invalid":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_INVALID_CREDENTIALS",
                "error": "ELEVENLABS_INVALID_CREDENTIALS",
                "message": "ElevenLabs credentials are not valid. Check the API key in Settings.",
                "capability": capability,
                "surface": surface,
                "silentFallback": False,
                "mock": False,
            },
        )
    if not resolution.get("ok") or not resolution.get("selected"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_NOT_CONFIGURED",
                "error": "ELEVENLABS_NOT_CONFIGURED",
                "message": "ElevenLabs API key not configured.",
                "capability": capability,
                "surface": surface,
                "silentFallback": False,
                "mock": False,
            },
        )
    key = get_secret(_SECRET)
    if not key:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_NOT_CONFIGURED",
                "error": "ELEVENLABS_NOT_CONFIGURED",
                "message": "ElevenLabs API key not configured.",
                "capability": capability,
                "surface": surface,
                "silentFallback": False,
                "mock": False,
            },
        )
    sel = resolution["selected"]
    return {
        "resolution": {k: v for k, v in resolution.items() if k != "candidates"},
        "providerId": "elevenlabs",
        "modelId": sel.get("modelId") or "",
        "apiKey": key,
        "directApi": True,
        "surface": surface,
        "capability": capability,
    }


def elevenlabs_availability() -> dict[str, Any]:
    """Creator-safe capability contract. Does not include the API key."""
    voice = resolve_capability("elevenlabs.voice")
    sfx = resolve_capability("elevenlabs.sfx")
    music = resolve_capability("elevenlabs.music")
    status = str(voice.get("status") or "unavailable")
    available = status == "available"
    configured = status in ("available", "configured")
    if status == "invalid":
        message = "ElevenLabs credentials are not valid."
    elif status == "unavailable":
        message = "ElevenLabs API key not configured."
    elif status == "configured":
        message = "ElevenLabs API key is saved. Run Test in Settings to confirm access."
    else:
        message = "ElevenLabs API is available."
    return {
        "ok": True,
        "provider": "elevenlabs",
        "displayName": "ElevenLabs API",
        "status": status,
        "configured": configured,
        "available": available,
        "connectionStatus": status,
        "message": message,
        "voice": {"available": bool(voice.get("ok")), "status": voice.get("status")},
        "sfx": {"available": bool(sfx.get("ok")), "status": sfx.get("status")},
        "music": {"available": bool(music.get("ok")), "status": music.get("status")},
        "modelsAvailable": available or configured,
        "voicesAvailable": available or configured,
        "directApi": True,
        "aggregatorsUsed": False,
        "silentFallback": False,
        "setupPath": "Settings > Hosted Providers > ElevenLabs API Key",
        "mock": False,
    }
