"""Kie.ai live credential probe via GET /api/v1/chat/credit (no generation job)."""

from __future__ import annotations

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
