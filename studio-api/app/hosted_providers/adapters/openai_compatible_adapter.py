"""Probe OpenAI-compatible /v1/models and optional /v1/chat/completions readiness."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx


async def probe_openai_compatible(
    api_key: str,
    *,
    base_url: str,
    models_path: str = "/v1/models",
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return {
            "providerId": "openai_compatible",
            "valid": False,
            "httpStatus": None,
            "message": "API base URL is required.",
            "models": [],
            "mock": False,
        }
    path = models_path if models_path.startswith("/") else f"/{models_path}"
    url = f"{base}{path}"
    headers = {"Authorization": f"Bearer {api_key.strip()}"} if api_key.strip() else {}
    out: dict[str, Any] = {
        "providerId": "openai_compatible",
        "valid": False,
        "httpStatus": None,
        "message": "",
        "probeEndpoint": url,
        "models": [],
        "capabilities": {"llm": False},
        "mock": False,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            r = await client.get(url, headers=headers)
            out["httpStatus"] = r.status_code
            if r.status_code in (401, 403):
                out["message"] = "Provider rejected this API key."
                return out
            if r.status_code >= 400:
                out["message"] = f"Models probe failed with HTTP {r.status_code}."
                return out
            data = r.json()
            models_raw = data.get("data") if isinstance(data, dict) else None
            names: list[str] = []
            if isinstance(models_raw, list):
                for item in models_raw:
                    if isinstance(item, dict) and item.get("id"):
                        names.append(str(item["id"]))
            out["valid"] = True
            out["models"] = names[:100]
            out["capabilities"] = {"llm": True, "image": False, "video": False, "audio": False}
            out["message"] = f"Connected — {len(names)} model(s) discovered." if names else "Connected — no models listed."
            return out
    except Exception as exc:  # noqa: BLE001
        out["message"] = f"Connection failed: {exc}"
        return out


async def list_chat_models(api_key: str, *, base_url: str, models_path: str = "/v1/models") -> list[dict[str, Any]]:
    probe = await probe_openai_compatible(api_key, base_url=base_url, models_path=models_path)
    return [{"id": m, "modality": "llm", "providerId": "openai_compatible"} for m in probe.get("models") or []]
