"""Normalized generator availability for the Film Timeline model list.

The shell renders this payload. It does not decide connectivity itself, and
this module never returns credential values.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.request import urlopen

from ..director_timeline_w46.generation.registry import get_registry
from ..secrets_store import get_secret


def _secret_present(*names: str) -> bool:
    for name in names:
        if (os.environ.get(name) or "").strip():
            return True
        try:
            if (get_secret(name) or "").strip():
                return True
        except Exception:
            continue
    return False


def _comfy_reachable() -> bool:
    try:
        with urlopen("http://127.0.0.1:8188/system_stats", timeout=1.5) as response:
            return int(getattr(response, "status", 0) or 0) == 200
    except Exception:
        return False


def _provider_for(generator_id: str, execution_type: str) -> str:
    if execution_type == "local":
        return "comfy"
    lowered = generator_id.lower()
    if "veo" in lowered:
        return "kie"
    return "fal"


def list_generator_status() -> list[dict[str, Any]]:
    comfy = _comfy_reachable()
    fal = _secret_present("FAL_KEY", "FAL_API_KEY", "fal_api_key")
    kie = _secret_present("KIE_API_KEY", "KIE_KEY", "kie_api_key")
    rows: list[dict[str, Any]] = []
    for caps in get_registry().list_capabilities():
        payload = caps.model_dump()
        generator_id = str(payload.get("id") or "")
        if "stub" in generator_id or payload.get("executable") is False:
            continue
        execution = str(payload.get("executionType") or "api")
        provider = _provider_for(generator_id, execution)
        if execution == "local":
            available = comfy
            reason = "" if available else "Local video runtime is not reachable"
        elif provider == "kie":
            available = kie
            reason = "" if available else "API not connected"
        else:
            available = fal
            reason = "" if available else "API not connected"
        payload.update(
            {
                "provider": provider,
                "local": execution == "local",
                "adapterRegistered": True,
                "configured": available,
                "authenticated": available if execution != "local" else True,
                "runtimeAvailable": comfy if execution == "local" else available,
                "available": available,
                "unavailableReason": reason,
            }
        )
        rows.append(payload)
    # Local MiniMax is one Director row. Text-to-video and image-to-video stay hidden.
    h3_local = "minimax-h3-i2v-local"
    collapsed: list[dict[str, Any]] = []
    for row in rows:
        generator_id = str(row.get("id") or "")
        if "minimax-h3" in generator_id and row.get("local") and generator_id != h3_local:
            continue
        if generator_id == h3_local:
            row["label"] = "MiniMax H3 Director — Local"
        collapsed.append(row)
    collapsed.sort(key=lambda item: (0 if item.get("local") else 1, str(item.get("label") or "")))
    return collapsed
