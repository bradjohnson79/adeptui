from __future__ import annotations

from typing import Any


async def probe_fal(api_key: str) -> dict[str, Any]:
    """Delegate to existing fal live probe — no mock path."""
    from ...fal_client import validate_fal_key

    probe = await validate_fal_key(api_key)
    return {
        "providerId": "fal",
        "valid": probe.get("valid"),
        "status": probe.get("status"),
        "httpStatus": probe.get("httpStatus"),
        "message": probe.get("message") or "",
        "probeEndpoint": probe.get("probeEndpoint"),
        "balance": None,
        "mock": False,
    }
