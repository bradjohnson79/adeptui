"""WaveSpeed.ai live credential probe + official generation / LLM enqueue."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

_PROBE_URL = "https://api.wavespeed.ai/api/v3/predictions/{task_id}/result"
_GEN_BASE = "https://api.wavespeed.ai/api/v3"
_LLM_CHAT_URL = "https://llm.wavespeed.ai/v1/chat/completions"


async def probe_wavespeed(api_key: str, *, timeout_sec: float = 15.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    task_id = f"adept-probe-{uuid.uuid4().hex}"
    url = _PROBE_URL.format(task_id=task_id)
    out: dict[str, Any] = {
        "providerId": "wavespeed",
        "valid": None,
        "status": "unverified",
        "httpStatus": None,
        "message": "",
        "probeEndpoint": url,
        "balance": None,
        "mock": False,
    }
    if not key:
        out.update(valid=False, status="invalid", message="No API key supplied.")
        return out
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        out["message"] = f"Could not reach WaveSpeed.ai to verify the key: {exc}"
        return out

    out["httpStatus"] = response.status_code
    if response.status_code in (401, 403):
        out.update(
            valid=False,
            status="invalid",
            message=(
                "WaveSpeed.ai rejected this API key. Confirm the key at wavespeed.ai/accesskey "
                "and that the account has been topped up (keys require a top-up to activate)."
            ),
        )
        return out
    if response.status_code >= 500:
        out["message"] = f"WaveSpeed.ai returned {response.status_code}; key left unverified."
        return out

    out.update(
        valid=True,
        status="verified",
        message="WaveSpeed.ai accepted this API key (auth probe; no generation job submitted).",
    )
    return out


async def enqueue_wavespeed(
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    *,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """POST official WaveSpeed generation API: /api/v3/{model_id}."""
    key = (api_key or "").strip()
    mid = (model_id or "").strip().lstrip("/")
    if not key:
        return {"ok": False, "error": "NO_KEY", "message": "No WaveSpeed.ai API key.", "mock": False}
    if not mid:
        return {"ok": False, "error": "NO_MODEL", "message": "providerModelId is required.", "mock": False}
    url = f"{_GEN_BASE}/{mid}"
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload if isinstance(payload, dict) else {},
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "mock": False}
    data: Any = None
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:800]}
    pred_id = None
    if isinstance(data, dict):
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        pred_id = (inner or {}).get("id") or (inner or {}).get("prediction_id") or data.get("id")
    ok = response.status_code < 400 and pred_id is not None
    return {
        "ok": ok,
        "providerId": "wavespeed",
        "modelId": mid,
        "httpStatus": response.status_code,
        "predictionId": pred_id,
        "result": data,
        "message": None if ok else (data.get("message") if isinstance(data, dict) else response.text[:400]),
        "mock": False,
    }


async def chat_wavespeed(
    api_key: str,
    *,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float = 0.55,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """Official OpenAI-compatible WaveSpeed LLM API."""
    key = (api_key or "").strip()
    mid = (model_id or "").strip() or "deepseek/deepseek-v4-flash"
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                _LLM_CHAT_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": mid, "messages": messages, "temperature": temperature, "stream": False},
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "mock": False}
    data: Any = None
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:800]}
    output = ""
    if isinstance(data, dict):
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(msg, dict):
                output = str(msg.get("content") or "")
    ok = response.status_code < 400 and bool(output)
    return {
        "ok": ok,
        "providerId": "wavespeed",
        "modelId": mid,
        "httpStatus": response.status_code,
        "output": output,
        "raw": data,
        "mock": False,
    }
