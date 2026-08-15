"""Kie.ai live credential probe via GET /api/v1/chat/credit (no generation job)."""

from __future__ import annotations

import json
from typing import Any

import httpx

_CREDIT_URL = "https://api.kie.ai/api/v1/chat/credit"


async def probe_kie(api_key: str, *, timeout_sec: float = 15.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    out: dict[str, Any] = {
        "providerId": "kie",
        "valid": None,
        "status": "unverified",
        "httpStatus": None,
        "message": "",
        "probeEndpoint": _CREDIT_URL,
        "balance": None,
        "mock": False,
    }
    if not key:
        out.update(valid=False, status="invalid", message="No API key supplied.")
        return out
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(
                _CREDIT_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        out["message"] = f"Could not reach Kie.ai to verify the key: {exc}"
        return out

    out["httpStatus"] = response.status_code
    if response.status_code in (401, 403):
        out.update(
            valid=False,
            status="invalid",
            message="Kie.ai rejected this API key. Check the key at kie.ai/api-key.",
        )
        return out
    if response.status_code >= 500:
        out["message"] = f"Kie.ai returned {response.status_code}; key left unverified."
        return out

    # 200 (and other non-auth client errors that still prove auth) → accepted
    balance = None
    try:
        payload = response.json()
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            for k in ("credit", "credits", "balance", "remaining"):
                if isinstance(data, dict) and data.get(k) is not None:
                    balance = data.get(k)
                    break
    except Exception:
        payload = None

    if response.status_code == 200 or response.status_code < 400:
        out.update(
            valid=True,
            status="verified",
            message="Kie.ai accepted this API key.",
            balance=balance,
        )
        return out

    # e.g. 404 with auth accepted is uncommon; treat non-401 as verified for auth
    out.update(
        valid=True,
        status="verified",
        message=f"Kie.ai authenticated the key (HTTP {response.status_code}).",
        balance=balance,
    )
    return out

_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
_RECORD_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

# Official Market model strings (docs.kie.ai). There is no public models/list.
# Keep existing flux / nano-banana dock ids unchanged.
KIE_IMAGE_T2I_BY_DOCK: dict[str, str] = {
    "flux-kie": "flux",
    "nano-banana-kie": "nano-banana",
    "gpt-image-2-kie": "gpt-image-2-text-to-image",
    "seedream-kie": "seedream/5-pro-text-to-image",
}
KIE_IMAGE_I2I_BY_DOCK: dict[str, str] = {
    "gpt-image-2-kie": "gpt-image-2-image-to-image",
    "seedream-kie": "seedream/5-pro-image-to-image",
}

_KIE_DOCK_ALIASES: dict[str, str] = {
    "nano-banana": "nano-banana-kie",
    "nano-banana-kie": "nano-banana-kie",
    "gpt-image-2": "gpt-image-2-kie",
    "gpt-image-2-kie": "gpt-image-2-kie",
    "gpt-image-2-text-to-image": "gpt-image-2-kie",
    "seedream": "seedream-kie",
    "seedream-kie": "seedream-kie",
    "seedream/5-pro-text-to-image": "seedream-kie",
    "flux": "flux-kie",
    "flux-kie": "flux-kie",
}


def kie_image_model_id_for_dock(dock_model_id: str | None, *, image_to_image: bool = False) -> str | None:
    mid = (dock_model_id or "").strip()
    if not mid:
        return None
    dock = _KIE_DOCK_ALIASES.get(mid, mid)
    if image_to_image:
        mapped = KIE_IMAGE_I2I_BY_DOCK.get(dock)
        if mapped:
            return mapped
    return KIE_IMAGE_T2I_BY_DOCK.get(dock)


def is_kie_image_dock(model_id: str | None) -> bool:
    mid = (model_id or "").strip()
    if not mid:
        return False
    dock = _KIE_DOCK_ALIASES.get(mid, mid)
    return dock in KIE_IMAGE_T2I_BY_DOCK


def extract_kie_image_url(payload: Any) -> str | None:
    """Pull the first http(s) image URL out of a Kie recordInfo payload."""
    import json as _json

    if isinstance(payload, str) and payload.startswith("http"):
        return payload
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None
    blobs: list[Any] = [data]
    for key in ("resultJson", "result_json"):
        raw = data.get(key)
        if isinstance(raw, str):
            try:
                parsed = _json.loads(raw)
            except Exception:
                parsed = None
            if parsed is not None:
                blobs.append(parsed)
        elif isinstance(raw, (dict, list)):
            blobs.append(raw)
    for blob in blobs:
        if isinstance(blob, dict):
            for key in ("resultUrls", "result_urls", "urls", "output", "images"):
                val = blob.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    return val
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, str) and first.startswith("http"):
                        return first
                    if isinstance(first, dict):
                        for uk in ("url", "image_url", "imageUrl"):
                            u = first.get(uk)
                            if isinstance(u, str) and u.startswith("http"):
                                return u
        if isinstance(blob, list) and blob:
            first = blob[0]
            if isinstance(first, str) and first.startswith("http"):
                return first
    return None


async def submit_kie_image_task(
    api_key: str,
    *,
    model: str,
    prompt: str,
    input_urls: list[str] | None = None,
    aspect_ratio: str = "1:1",
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        return {"ok": False, "error": "NO_KEY", "message": "No API key supplied.", "mock": False}
    model_id = (model or "").strip()
    if not model_id:
        return {"ok": False, "error": "NO_MODEL", "message": "No Kie model string supplied.", "mock": False}
    payload: dict[str, Any] = {"model": model_id, "input": {"prompt": prompt or ""}}
    if input_urls:
        payload["input"]["input_urls"] = list(input_urls)
    if aspect_ratio:
        payload["input"]["aspect_ratio"] = aspect_ratio
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                _CREATE_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "mock": False}
    body: Any = None
    try:
        body = response.json()
    except Exception:
        body = None
    task_id = None
    if isinstance(body, dict):
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data, dict):
            task_id = data.get("taskId") or data.get("task_id") or data.get("id")
    return {
        "ok": response.status_code < 400 and bool(task_id),
        "httpStatus": response.status_code,
        "taskId": task_id,
        "payload": body,
        "model": model_id,
        "mock": False,
    }


async def poll_kie_task(api_key: str, task_id: str, *, timeout_sec: float = 15.0) -> dict[str, Any]:
    key = (api_key or "").strip()
    tid = (task_id or "").strip()
    if not key or not tid:
        return {"ok": False, "error": "BAD_ARGS", "mock": False}
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.get(
                _RECORD_URL,
                params={"taskId": tid},
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "mock": False}
    body: Any = None
    try:
        body = response.json()
    except Exception:
        body = None
    state = None
    if isinstance(body, dict):
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data, dict):
            state = data.get("state") or data.get("status")
    return {
        "ok": response.status_code < 400,
        "httpStatus": response.status_code,
        "taskId": tid,
        "state": state,
        "payload": body,
        "mock": False,
    }



# Restored Market enqueue + Gemini chat so adapters.__init__ imports stay valid.
_KIE_CHAT_ENDPOINTS: dict[str, str] = {
    "gemini-3-pro": "https://api.kie.ai/gemini-3-pro/v1/chat/completions",
    "gemini-3.1-pro": "https://api.kie.ai/gemini-3-pro/v1/chat/completions",
    "gemini-2.5-pro": "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions",
    "gemini-2.5-flash": "https://api.kie.ai/gemini-2.5-flash/v1/chat/completions",
    "gemini-3-flash": "https://api.kie.ai/gemini-3-flash/v1/chat/completions",
}


async def enqueue_kie(
    api_key: str,
    model_id: str,
    payload: dict[str, Any],
    *,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """POST official Market createTask. Dock ids resolve via KIE_IMAGE_T2I_BY_DOCK."""
    key = (api_key or "").strip()
    raw_mid = (model_id or "").strip()
    mid = KIE_IMAGE_T2I_BY_DOCK.get(raw_mid, raw_mid)
    if not key:
        return {"ok": False, "error": "NO_KEY", "message": "No Kie.ai API key.", "mock": False}
    if not mid:
        return {"ok": False, "error": "NO_MODEL", "message": "providerModelId is required.", "mock": False}
    body = {"model": mid, "input": payload if isinstance(payload, dict) else {}}
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                _CREATE_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "NETWORK", "message": str(exc), "mock": False}
    data: Any = None
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:800]}
    task_id = None
    if isinstance(data, dict):
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        task_id = (inner or {}).get("taskId") or (inner or {}).get("task_id")
    ok = response.status_code < 400 and bool(task_id)
    return {
        "ok": ok,
        "providerId": "kie",
        "modelId": mid,
        "httpStatus": response.status_code,
        "taskId": task_id,
        "result": data,
        "pollUrl": f"{_RECORD_URL}?taskId={task_id}" if task_id else None,
        "message": None if ok else (data.get("msg") if isinstance(data, dict) else response.text[:400]),
        "mock": False,
    }


async def chat_kie(
    api_key: str,
    *,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float = 0.55,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """OpenAI-compatible Kie chat (Gemini family). Other chat families use different paths."""
    key = (api_key or "").strip()
    mid = (model_id or "").strip() or "gemini-3-pro"
    url = _KIE_CHAT_ENDPOINTS.get(mid)
    if not url:
        return {
            "ok": False,
            "error": "REQUIRES_ADAPTER",
            "message": f"Kie chat path not wired for {mid}. Use gemini-3-pro.",
            "mock": False,
        }
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(
                url,
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
        "providerId": "kie",
        "modelId": mid,
        "httpStatus": response.status_code,
        "output": output,
        "raw": data,
        "mock": False,
    }
