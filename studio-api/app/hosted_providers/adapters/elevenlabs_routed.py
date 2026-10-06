"""ElevenLabs generation entry points.

Public generate_* functions call the ElevenLabs API directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..elevenlabs_capability import require_route_or_raise
from . import elevenlabs_adapter as direct_el


def _direct_key(capability: str, surface: str) -> tuple[str, str]:
    route = require_route_or_raise(capability=capability, surface=surface)
    if route.get("providerId") != "elevenlabs" or not route.get("directApi"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_DIRECT_ONLY",
                "error": "ELEVENLABS_DIRECT_ONLY",
                "message": "ElevenLabs generation uses the ElevenLabs API directly.",
                "silentFallback": False,
                "mock": False,
            },
        )
    return str(route["apiKey"]), str(route.get("modelId") or "")


def generate_tts_routed(
    *,
    text: str,
    voice_id: str,
    surface: str = "voice-performance.generate-takes",
    dest: Path | None = None,
    voice_settings: dict[str, Any] | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    key, default_model = _direct_key("elevenlabs.voice", surface)
    result = direct_el.generate_tts_to_file(
        api_key=key,
        voice_id=voice_id,
        text=text,
        model_id=model_id or default_model or direct_el.DEFAULT_TTS_MODEL,
        dest=dest,
        voice_settings=voice_settings,
    )
    return {**result, "routeProviderId": "elevenlabs", "directApi": True}


def generate_sfx_routed(
    *,
    text: str,
    duration_seconds: float | None = None,
    prompt_influence: float = 0.3,
    loop: bool = False,
    surface: str = "audio-studio.generate",
    dest: Path | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    key, default_model = _direct_key("elevenlabs.sfx", surface)
    result = direct_el.generate_sfx_to_file(
        api_key=key,
        text=text,
        duration_seconds=duration_seconds,
        prompt_influence=prompt_influence,
        loop=loop,
        model_id=model_id or default_model or direct_el.DEFAULT_SFX_MODEL,
        dest=dest,
    )
    return {**result, "routeProviderId": "elevenlabs", "directApi": True}


def generate_music_routed(
    *,
    prompt: str,
    duration_seconds: float | None = None,
    composition_plan: dict[str, Any] | None = None,
    surface: str = "audio-studio.generate",
    dest: Path | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    key, _default_model = _direct_key("elevenlabs.music", surface)
    result = direct_el.generate_music_to_file(
        api_key=key,
        prompt=prompt,
        duration_seconds=duration_seconds,
        composition_plan=composition_plan,
        model_id=model_id or None,
        dest=dest,
    )
    return {**result, "routeProviderId": "elevenlabs", "directApi": True}
