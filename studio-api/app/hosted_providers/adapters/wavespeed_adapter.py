"""WaveSpeed.ai live credential probe — GET prediction status path (no billed POST)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

# Non-existent prediction id: auth is evaluated without creating a generation job.
_PROBE_URL = "https://api.wavespeed.ai/api/v3/predictions/{task_id}/result"


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

    # 404 (missing prediction) or 200 with auth = key accepted; no job was created via POST.
    out.update(
        valid=True,
        status="verified",
        message="WaveSpeed.ai accepted this API key (auth probe; no generation job submitted).",
    )
    return out
