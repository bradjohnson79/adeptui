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
    "nano-banana-kie": "nano-banana-2",
    "gpt-image-2-kie": "gpt-image-2-text-to-image",
    "seedream-kie": "seedream/5-pro-text-to-image",
}
KIE_IMAGE_I2I_BY_DOCK: dict[str, str] = {
    "gpt-image-2-kie": "gpt-image-2-image-to-image",
    "seedream-kie": "seedream/5-pro-image-to-image",
}

_KIE_DOCK_ALIASES: dict[str, str] = {
    "nano-banana": "nano-banana-kie",
    "nano-banana-2": "nano-banana-kie",
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



# Kie createTask aspect_ratio enums (docs.kie.ai). Never send raw pixel pairs.
KIE_IMAGE_ASPECTS: tuple[str, ...] = (
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "21:9",
)
KIE_ALLOWED_ASPECTS: frozenset[str] = frozenset(KIE_IMAGE_ASPECTS + ("auto",))


def kie_aspect_from_pixels(
    width: int | float | None,
    height: int | float | None,
    *,
    default: str = "16:9",
) -> str:
    """Nearest Kie aspect enum for pixel dims. Never returns raw pixels."""
    try:
        w = float(width or 0)
        h = float(height or 0)
    except (TypeError, ValueError):
        return default
    if w <= 0 or h <= 0:
        return default
    ratio = w / h
    best = default
    best_delta: float | None = None
    for label in KIE_IMAGE_ASPECTS:
        aw_s, ah_s = label.split(":")
        ar = float(aw_s) / float(ah_s)
        delta = abs(ratio - ar)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best = label
    return best


def normalize_kie_aspect(
    aspect_ratio: str | None = None,
    *,
    width: int | float | None = None,
    height: int | float | None = None,
    default: str = "16:9",
) -> str:
    """Accept a Kie enum, or map pixel-like '1920:1080' / dims to the nearest enum."""
    raw = (aspect_ratio or "").strip()
    if raw in KIE_ALLOWED_ASPECTS:
        return raw
    if raw:
        sep = None
        if ":" in raw:
            sep = ":"
        elif "x" in raw.lower():
            sep = "x" if "x" in raw else "X"
            if "X" in raw and "x" not in raw:
                sep = "X"
        if sep:
            parts = raw.split(sep)
            if len(parts) == 2:
                try:
                    return kie_aspect_from_pixels(float(parts[0]), float(parts[1]), default=default)
                except ValueError:
                    pass
    if width is not None or height is not None:
        return kie_aspect_from_pixels(width, height, default=default)
    return default


def strengthen_kie_character_sheet_prompt(prompt: str, *, model: str | None = None) -> str:
    """Nano Banana / GPT Image 2 / Seedream 5 Pro four-panel turnaround strengthen."""
    from ...character_identity.four_view_sheet import strengthen_four_view_prompt

    return strengthen_four_view_prompt(prompt)


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


def resolve_official_kie_image_model(
    model_id: str | None,
    params: dict | None = None,
    *,
    image_to_image: bool = False,
) -> str:
    """Official Market id from kieImageModelId / dock map / model_id. Always a string."""
    src = params if isinstance(params, dict) else {}
    pinned = str(src.get("kieImageModelId") or src.get("kie_image_model_id") or "").strip()
    mapped = kie_image_model_id_for_dock(pinned or model_id, image_to_image=image_to_image)
    return mapped or pinned or str(model_id or "").strip()


def is_kie_image_dock(model_id: str | None) -> bool:
    mid = (model_id or "").strip()
    if not mid:
        return False
    dock = _KIE_DOCK_ALIASES.get(mid, mid)
    return dock in KIE_IMAGE_T2I_BY_DOCK


KIE_POLL_ATTEMPTS = 90
KIE_POLL_INTERVAL_SEC = 2.0
KIE_GENERATING_STATES: frozenset[str] = frozenset(
    {"waiting", "queuing", "queued", "pending", "generating", "running", "processing"}
)
KIE_FAIL_STATES: frozenset[str] = frozenset({"fail", "failed", "error"})


def _first_http_url(val: Any) -> str | None:
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("http://") or s.startswith("https://"):
            return s
        if s.startswith("{") or s.startswith("["):
            try:
                parsed = json.loads(s)
            except Exception:
                return None
            return _first_http_url(parsed)
        return None
    if isinstance(val, list):
        for item in val:
            found = _first_http_url(item)
            if found:
                return found
        return None
    if isinstance(val, dict):
        for key in ("url", "image_url", "imageUrl", "resultUrl"):
            found = _first_http_url(val.get(key))
            if found:
                return found
    return None


def extract_kie_image_url(payload: Any) -> str | None:
    """Pull the first http(s) image URL out of a Kie recordInfo payload.

    Official docs: data.resultJson is a JSON *string* containing resultUrls.
    """
    if isinstance(payload, str):
        return _first_http_url(payload)
    if not isinstance(payload, dict):
        return None
    # Unwrap poll_kie_task envelope if the caller passed the whole poll dict.
    nested = payload.get("payload")
    if nested is not None and nested is not payload:
        found = extract_kie_image_url(nested)
        if found:
            return found
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None
    blobs: list[Any] = [payload, data]
    for src in (payload, data):
        if not isinstance(src, dict):
            continue
        for key in ("resultJson", "result_json"):
            raw = src.get(key)
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
                if parsed is not None:
                    blobs.append(parsed)
            elif isinstance(raw, (dict, list)):
                blobs.append(raw)
    url_keys = (
        "resultUrls",
        "result_urls",
        "urls",
        "output",
        "images",
        "resultUrl",
        "firstFrameUrl",
    )
    for blob in blobs:
        if isinstance(blob, dict):
            for key in url_keys:
                found = _first_http_url(blob.get(key))
                if found:
                    return found
        found = _first_http_url(blob)
        if found:
            return found
    return None


def kie_record_data(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("payload"), dict):
        payload = payload["payload"]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    return data if isinstance(data, dict) else {}


def kie_fail_message(payload: Any, task_id: str, state: str | None = None) -> str:
    """Honest Kie failCode+failMsg. Never a traceback."""
    data = kie_record_data(payload)
    fail_code = data.get("failCode")
    if fail_code in (None, ""):
        fail_code = data.get("fail_code")
    fail_msg = data.get("failMsg") or data.get("fail_msg")
    st = str(state or data.get("state") or "fail").strip() or "fail"
    parts = [f"Kie task {task_id} failed (state={st})"]
    if fail_code not in (None, ""):
        parts.append("code=" + str(fail_code))
    if fail_msg:
        parts.append("msg=" + str(fail_msg))
    return " ".join(parts)


def kie_poll_timeout_message(task_id: str, last_state: str | None) -> str:
    """Timeout after poll loop. Still-generating is not 'no image URL'."""
    state = (last_state or "").strip() or "unknown"
    if state.lower() in KIE_GENERATING_STATES or state.lower() in {"", "unknown"}:
        return f"Kie task {task_id} still generating (state={state})"
    return f"Kie task {task_id} produced no image URL (state={state})"



SEEDREAM_QUALITY_DEFAULT = "basic"
SEEDREAM_QUALITY_ALLOWED: frozenset[str] = frozenset({"basic", "high"})


def _is_seedream_model(model_id: str | None) -> bool:
    return (model_id or "").startswith("seedream/")


def _kie_ref_url_field(model_id: str | None) -> str:
    """Official Kie input array name. Seedream uses image_urls; GPT uses input_urls; Nano Banana uses image_input."""
    mid = (model_id or "").strip()
    if mid.startswith("seedream/"):
        return "image_urls"
    if mid.startswith("nano-banana"):
        return "image_input"
    return "input_urls"


def build_kie_create_task_body(
    *,
    model: str,
    prompt: str,
    input_urls: list[str] | None = None,
    aspect_ratio: str = "1:1",
    quality: str | None = None,
) -> dict[str, Any]:
    """Build the official createTask JSON. Seedream requires prompt+aspect_ratio+quality (docs.kie.ai)."""
    model_id = (model or "").strip()
    inp: dict[str, Any] = {"prompt": prompt or ""}
    aspect = normalize_kie_aspect(aspect_ratio)
    if aspect:
        inp["aspect_ratio"] = aspect
    if _is_seedream_model(model_id):
        q = (quality or SEEDREAM_QUALITY_DEFAULT).strip().lower()
        if q not in SEEDREAM_QUALITY_ALLOWED:
            q = SEEDREAM_QUALITY_DEFAULT
        inp["quality"] = q
    urls = [u.strip() for u in (input_urls or []) if isinstance(u, str) and u.strip()]
    if urls:
        inp[_kie_ref_url_field(model_id)] = urls
    return {"model": model_id, "input": inp}


async def submit_kie_image_task(
    api_key: str,
    *,
    model: str,
    prompt: str,
    input_urls: list[str] | None = None,
    aspect_ratio: str = "1:1",
    quality: str | None = None,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        return {"ok": False, "error": "NO_KEY", "message": "No API key supplied.", "mock": False}
    model_id = (model or "").strip()
    if not model_id:
        return {"ok": False, "error": "NO_MODEL", "message": "No Kie model string supplied.", "mock": False}
    payload = build_kie_create_task_body(
        model=model_id,
        prompt=prompt or "",
        input_urls=input_urls,
        aspect_ratio=aspect_ratio,
        quality=quality,
    )
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
    kie_code = None
    kie_msg = None
    if isinstance(body, dict):
        kie_code = body.get("code")
        kie_msg = body.get("msg") or body.get("message")
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data, dict):
            task_id = data.get("taskId") or data.get("task_id") or data.get("id")
            if kie_msg is None:
                kie_msg = data.get("msg") or data.get("message")
            if kie_code is None:
                kie_code = data.get("code")
    ok = response.status_code < 400 and bool(task_id)
    message = None
    if not ok:
        parts = ["httpStatus=" + str(response.status_code)]
        if kie_code is not None:
            parts.append("code=" + str(kie_code))
        if kie_msg:
            parts.append("msg=" + str(kie_msg))
        elif response.text:
            parts.append("body=" + response.text[:400])
        message = "Kie createTask failed: " + " ".join(parts)
    return {
        "ok": ok,
        "httpStatus": response.status_code,
        "taskId": task_id,
        "payload": body,
        "request": payload,
        "model": model_id,
        "code": kie_code,
        "message": message,
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
    fail_code = None
    fail_msg = None
    kie_code = None
    kie_msg = None
    if isinstance(body, dict):
        kie_code = body.get("code")
        kie_msg = body.get("msg") or body.get("message")
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data, dict):
            state = data.get("state") or data.get("status")
            fail_code = data.get("failCode")
            if fail_code in (None, ""):
                fail_code = data.get("fail_code")
            fail_msg = data.get("failMsg") or data.get("fail_msg")
    image_url = extract_kie_image_url(body)
    st = str(state or "").lower()
    failed = st in KIE_FAIL_STATES
    message = kie_fail_message(body, tid, st) if failed else None
    return {
        "ok": response.status_code < 400 and not failed,
        "httpStatus": response.status_code,
        "taskId": tid,
        "state": state,
        "payload": body,
        "imageUrl": image_url,
        "failCode": fail_code,
        "failMsg": fail_msg,
        "code": kie_code,
        "msg": kie_msg,
        "message": message,
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
