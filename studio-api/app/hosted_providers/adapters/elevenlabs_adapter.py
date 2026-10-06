"""ElevenLabs live credential probe + TTS/SFX generate (server-side xi-api-key only)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

_MODELS_URL = "https://api.elevenlabs.io/v1/models"
_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
_SFX_URL = "https://api.elevenlabs.io/v1/sound-generation"
_MUSIC_URL = "https://api.elevenlabs.io/v1/music"
_VOICES_URL = "https://api.elevenlabs.io/v2/voices"

DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_SFX_MODEL = "eleven_text_to_sound_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


async def probe_elevenlabs(api_key: str, *, timeout_sec: float = 15.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    out: dict[str, Any] = {
        "providerId": "elevenlabs",
        "valid": None,
        "status": "unverified",
        "httpStatus": None,
        "message": "",
        "probeEndpoint": _MODELS_URL,
        "balance": None,
        "mock": False,
    }
    if not key:
        out.update(valid=False, status="invalid", message="No API key supplied.")
        return out
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(
                _MODELS_URL,
                headers={"xi-api-key": key, "Accept": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        out["message"] = f"Could not reach ElevenLabs to verify the key: {exc}"
        return out

    out["httpStatus"] = response.status_code
    if response.status_code in (401, 403):
        out.update(
            valid=False,
            status="invalid",
            message="ElevenLabs rejected this API key. Check the key at elevenlabs.io.",
        )
        return out
    if response.status_code >= 500:
        out["message"] = f"ElevenLabs returned {response.status_code}; key left unverified."
        return out
    if response.status_code == 200 or response.status_code < 400:
        out.update(valid=True, status="verified", message="ElevenLabs accepted this API key.")
        return out
    out.update(valid=False, status="invalid", message=f"ElevenLabs probe HTTP {response.status_code}.")
    return out


def _response_ids(response: httpx.Response) -> dict[str, Any]:
    """Request and cost headers only. Binary responses do not invent an asset id."""
    headers = {str(k).lower(): v for k, v in response.headers.items()}
    request_id = headers.get("request-id") or headers.get("x-request-id") or None
    history_id = headers.get("history-item-id") or None
    cost = headers.get("character-cost") or headers.get("x-character-count") or None
    return {
        "providerRequestId": request_id or history_id,
        "providerAssetId": None,
        "providerMetadata": {
            "requestId": request_id,
            "historyItemId": history_id,
            "characterCost": cost,
        },
    }


def provenance(
    *,
    asset_type: str,
    model_id: str,
    voice_id: str | None = None,
    request_id: str | None = None,
    provider_asset_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "provider": "elevenlabs",
        "providerAssetType": asset_type,
        "providerAssetId": provider_asset_id,
        "providerModelId": model_id,
        "providerRequestId": request_id,
        "providerVoiceId": voice_id,
        "providerMetadata": metadata or {},
    }


def _raise_from_status(status: int, body_text: str = "") -> None:
    lowered = (body_text or "").lower()
    if status in (401,):
        code, msg = "ELEVENLABS_INVALID_CREDENTIALS", "ElevenLabs rejected the API key."
    elif status == 402 or "quota" in lowered or "credit" in lowered:
        code, msg = "ELEVENLABS_QUOTA", "ElevenLabs account does not have enough credits for this request."
    elif status in (403,):
        code, msg = "ELEVENLABS_FORBIDDEN", "This ElevenLabs account cannot use that feature."
    elif status == 404 or "voice_not_found" in lowered or "voice not found" in lowered:
        code, msg = "ELEVENLABS_INVALID_VOICE", "That ElevenLabs voice is not available."
    elif status == 429:
        code, msg = "ELEVENLABS_RATE_LIMITED", "ElevenLabs is rate limiting requests. Try again shortly."
    elif status == 422:
        code, msg = "ELEVENLABS_VALIDATION", "ElevenLabs could not accept that generation request."
    elif status >= 500:
        code, msg = "ELEVENLABS_UNAVAILABLE", "ElevenLabs is unavailable right now."
    else:
        code, msg = "ELEVENLABS_UPSTREAM_ERROR", "ElevenLabs could not complete that request."
    raise HTTPException(
        status_code=502 if status >= 500 else 400,
        detail={
            "code": code,
            "error": code,
            "message": msg,
            "provider": "elevenlabs",
            "silentFallback": False,
            "mock": False,
            "upstreamStatus": status,
        },
    )


def generate_tts_to_file(
    *,
    api_key: str,
    voice_id: str,
    text: str,
    model_id: str = DEFAULT_TTS_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    voice_settings: dict[str, Any] | None = None,
    timeout_sec: float = 120.0,
    dest: Path | None = None,
) -> dict[str, Any]:
    """POST /v1/text-to-speech/{voice_id} → audio file. Sync httpx."""
    key = (api_key or "").strip()
    vid = (voice_id or "").strip()
    prompt = (text or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail={"code": "ELEVENLABS_NOT_CONFIGURED", "error": "ELEVENLABS_NOT_CONFIGURED", "silentFallback": False, "mock": False},
        )
    if not vid:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_VALIDATION",
                "error": "ELEVENLABS_VALIDATION",
                "message": "voiceId is required for ElevenLabs TTS.",
                "silentFallback": False,
                "mock": False,
            },
        )
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_VALIDATION",
                "error": "ELEVENLABS_VALIDATION",
                "message": "text is required for ElevenLabs TTS.",
                "silentFallback": False,
                "mock": False,
            },
        )
    url = _TTS_URL.format(voice_id=vid)
    payload: dict[str, Any] = {"text": prompt, "model_id": model_id or DEFAULT_TTS_MODEL}
    if voice_settings:
        payload["voice_settings"] = voice_settings
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            response = client.post(
                url,
                params={"output_format": output_format or DEFAULT_OUTPUT_FORMAT},
                headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "ELEVENLABS_TIMEOUT",
                "error": "ELEVENLABS_TIMEOUT",
                "message": f"ElevenLabs TTS timed out: {exc}",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ELEVENLABS_UPSTREAM_ERROR",
                "error": "ELEVENLABS_UPSTREAM_ERROR",
                "message": f"ElevenLabs TTS transport error: {exc}",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    if response.status_code >= 400:
        _raise_from_status(response.status_code, response.text)
    out_path = dest or Path(tempfile.mkstemp(prefix="el_tts_", suffix=".mp3")[1])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    ids = _response_ids(response)
    model = model_id or DEFAULT_TTS_MODEL
    return {
        "ok": True,
        "path": str(out_path.resolve()),
        "bytes": out_path.stat().st_size,
        "provider": "elevenlabs",
        "model": model,
        "voiceId": vid,
        "outputFormat": output_format or DEFAULT_OUTPUT_FORMAT,
        "providerRequestId": ids["providerRequestId"],
        "providerAssetId": None,
        "provenance": provenance(
            asset_type="voice",
            model_id=model,
            voice_id=vid,
            request_id=ids["providerRequestId"],
            metadata=ids["providerMetadata"],
        ),
        "mock": False,
    }


def generate_sfx_to_file(
    *,
    api_key: str,
    text: str,
    duration_seconds: float | None = None,
    prompt_influence: float = 0.3,
    loop: bool = False,
    model_id: str = DEFAULT_SFX_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    timeout_sec: float = 120.0,
    dest: Path | None = None,
) -> dict[str, Any]:
    """POST /v1/sound-generation → audio file."""
    key = (api_key or "").strip()
    prompt = (text or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail={"code": "ELEVENLABS_NOT_CONFIGURED", "error": "ELEVENLABS_NOT_CONFIGURED", "silentFallback": False, "mock": False},
        )
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_VALIDATION",
                "error": "ELEVENLABS_VALIDATION",
                "message": "text/prompt is required for ElevenLabs SFX.",
                "silentFallback": False,
                "mock": False,
            },
        )
    dur = None
    if duration_seconds is not None:
        try:
            dur = float(duration_seconds)
        except (TypeError, ValueError):
            dur = None
        if dur is not None:
            if dur < 0.5 or dur > 30.0:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "ELEVENLABS_VALIDATION",
                        "error": "ELEVENLABS_VALIDATION",
                        "message": "ElevenLabs SFX duration_seconds must be between 0.5 and 30.",
                        "silentFallback": False,
                        "mock": False,
                    },
                )
    body: dict[str, Any] = {
        "text": prompt,
        "model_id": model_id or DEFAULT_SFX_MODEL,
        "prompt_influence": float(prompt_influence),
        "loop": bool(loop),
    }
    if dur is not None:
        body["duration_seconds"] = dur
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            response = client.post(
                _SFX_URL,
                params={"output_format": output_format or DEFAULT_OUTPUT_FORMAT},
                headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "ELEVENLABS_TIMEOUT",
                "error": "ELEVENLABS_TIMEOUT",
                "message": f"ElevenLabs SFX timed out: {exc}",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ELEVENLABS_UPSTREAM_ERROR",
                "error": "ELEVENLABS_UPSTREAM_ERROR",
                "message": f"ElevenLabs SFX transport error: {exc}",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    if response.status_code >= 400:
        _raise_from_status(response.status_code, response.text)
    out_path = dest or Path(tempfile.mkstemp(prefix="el_sfx_", suffix=".mp3")[1])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    ids = _response_ids(response)
    model = model_id or DEFAULT_SFX_MODEL
    return {
        "ok": True,
        "path": str(out_path.resolve()),
        "bytes": out_path.stat().st_size,
        "provider": "elevenlabs",
        "model": model,
        "durationSec": dur,
        "loop": bool(loop),
        "outputFormat": output_format or DEFAULT_OUTPUT_FORMAT,
        "providerRequestId": ids["providerRequestId"],
        "providerAssetId": None,
        "provenance": provenance(
            asset_type="sfx",
            model_id=model,
            request_id=ids["providerRequestId"],
            metadata={**ids["providerMetadata"], "prompt": prompt, "durationSec": dur, "loop": bool(loop)},
        ),
        "mock": False,
    }


def generate_music_to_file(
    *,
    api_key: str,
    prompt: str,
    duration_seconds: float | None = None,
    composition_plan: dict[str, Any] | None = None,
    model_id: str | None = None,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    timeout_sec: float = 180.0,
    dest: Path | None = None,
) -> dict[str, Any]:
    """POST /v1/music. Prompt and composition plan are mutually exclusive."""
    key = (api_key or "").strip()
    text = (prompt or "").strip()
    plan = composition_plan if isinstance(composition_plan, dict) and composition_plan else None
    if not key:
        raise HTTPException(
            status_code=400,
            detail={"code": "ELEVENLABS_NOT_CONFIGURED", "error": "ELEVENLABS_NOT_CONFIGURED", "silentFallback": False, "mock": False},
        )
    if plan and text:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_VALIDATION",
                "error": "ELEVENLABS_VALIDATION",
                "message": "Music uses either a prompt or a composition plan.",
                "silentFallback": False,
                "mock": False,
            },
        )
    if not plan and not text:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ELEVENLABS_VALIDATION",
                "error": "ELEVENLABS_VALIDATION",
                "message": "Music needs a prompt or a composition plan.",
                "silentFallback": False,
                "mock": False,
            },
        )
    body: dict[str, Any] = {"composition_plan": plan} if plan else {"prompt": text}
    if model_id:
        body["model_id"] = model_id
    if duration_seconds is not None:
        try:
            ms = int(float(duration_seconds) * 1000)
        except (TypeError, ValueError):
            ms = 0
        if ms <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ELEVENLABS_VALIDATION",
                    "error": "ELEVENLABS_VALIDATION",
                    "message": "Music duration must be greater than zero.",
                    "silentFallback": False,
                    "mock": False,
                },
            )
        body["music_length_ms"] = ms
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            response = client.post(
                _MUSIC_URL,
                params={"output_format": output_format or DEFAULT_OUTPUT_FORMAT},
                headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "code": "ELEVENLABS_TIMEOUT",
                "error": "ELEVENLABS_TIMEOUT",
                "message": "ElevenLabs music timed out.",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ELEVENLABS_UNAVAILABLE",
                "error": "ELEVENLABS_UNAVAILABLE",
                "message": "ElevenLabs music could not be reached.",
                "silentFallback": False,
                "mock": False,
            },
        ) from exc
    if response.status_code >= 400:
        _raise_from_status(response.status_code, response.text)
    out_path = dest or Path(tempfile.mkstemp(prefix="el_music_", suffix=".mp3")[1])
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    ids = _response_ids(response)
    model = model_id or ""
    return {
        "ok": True,
        "path": str(out_path.resolve()),
        "bytes": out_path.stat().st_size,
        "provider": "elevenlabs",
        "model": model,
        "durationSec": duration_seconds,
        "outputFormat": output_format or DEFAULT_OUTPUT_FORMAT,
        "providerRequestId": ids["providerRequestId"],
        "providerAssetId": None,
        "provenance": provenance(
            asset_type="music",
            model_id=model,
            request_id=ids["providerRequestId"],
            metadata={**ids["providerMetadata"], "prompt": text, "durationSec": duration_seconds},
        ),
        "mock": False,
    }


def list_voices(*, api_key: str, timeout_sec: float = 20.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail={"code": "ELEVENLABS_NOT_CONFIGURED", "message": "ElevenLabs API key not configured.", "silentFallback": False, "mock": False},
        )
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(
            _VOICES_URL,
            params={"page_size": 100},
            headers={"xi-api-key": key, "Accept": "application/json"},
        )
    if response.status_code >= 400:
        _raise_from_status(response.status_code, response.text)
    payload = response.json() if response.content else {}
    raw = payload.get("voices") if isinstance(payload, dict) else None
    voices = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        voice_id = str(item.get("voice_id") or "").strip()
        if not voice_id:
            continue
        voices.append({
            "voiceId": voice_id,
            "name": str(item.get("name") or voice_id),
            "category": str(item.get("category") or ""),
            "provider": "elevenlabs",
        })
    return {"ok": True, "provider": "elevenlabs", "voices": voices, "mock": False}


def list_models(*, api_key: str, timeout_sec: float = 20.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail={"code": "ELEVENLABS_NOT_CONFIGURED", "message": "ElevenLabs API key not configured.", "silentFallback": False, "mock": False},
        )
    with httpx.Client(timeout=timeout_sec) as client:
        response = client.get(_MODELS_URL, headers={"xi-api-key": key, "Accept": "application/json"})
    if response.status_code >= 400:
        _raise_from_status(response.status_code, response.text)
    payload = response.json() if response.content else []
    rows = payload if isinstance(payload, list) else payload.get("models") if isinstance(payload, dict) else []
    models = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "").strip()
        if not model_id:
            continue
        models.append({
            "modelId": model_id,
            "name": str(item.get("name") or model_id),
            "canDoTextToSpeech": bool(item.get("can_do_text_to_speech")),
            "provider": "elevenlabs",
        })
    return {"ok": True, "provider": "elevenlabs", "models": models, "mock": False}
