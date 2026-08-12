"""Image Provider Registry — local Comfy + cloud providers (M42 W2)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT = _REPO_ROOT / "config" / "image-runtime" / "provider-registry.json"


@lru_cache(maxsize=2)
def load_provider_registry(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT
    if not p.is_file():
        return {"version": "1.0.0", "providers": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"version": "1.0.0", "providers": []}


def reload_provider_registry() -> None:
    load_provider_registry.cache_clear()


def list_providers() -> list[dict[str, Any]]:
    return list(load_provider_registry().get("providers") or [])


def get_provider(provider_id: str) -> dict[str, Any] | None:
    for p in list_providers():
        if p.get("providerId") == provider_id or p.get("id") == provider_id:
            return p
    return None


def probe_provider_availability(provider: dict[str, Any]) -> dict[str, Any]:
    """Runtime probe — credentials / reachability, not hard-coded assumptions."""
    pid = str(provider.get("providerId") or "")
    kind = str(provider.get("kind") or "local")
    result = {
        "providerId": pid,
        "kind": kind,
        "available": False,
        "reason": "",
        "credentialConfigured": False,
    }
    if kind == "local" or pid in {"comfyui", "local"}:
        try:
            import urllib.request

            url = os.environ.get("COMFY_URL") or "http://127.0.0.1:8188"
            with urllib.request.urlopen(f"{url.rstrip('/')}/system_stats", timeout=2) as resp:
                result["available"] = resp.status == 200
                result["reason"] = "ComfyUI reachable" if result["available"] else f"status={resp.status}"
        except Exception as exc:
            result["available"] = False
            result["reason"] = f"ComfyUI unreachable: {exc}"
        return result

    # Cloud credential env keys from registry
    env_keys = provider.get("credentialEnvKeys") or provider.get("credential_env_keys") or []
    configured = any(bool(os.environ.get(str(k))) for k in env_keys) if env_keys else False
    result["credentialConfigured"] = configured
    if not configured:
        result["available"] = False
        result["reason"] = "Provider unavailable or credentials not configured."
    else:
        result["available"] = True
        result["reason"] = "Credentials configured (live API probe deferred to execution)."
    return result


def provider_inventory() -> dict[str, Any]:
    providers = []
    for p in list_providers():
        probe = probe_provider_availability(p)
        providers.append({**p, "probe": probe})
    return {
        "phase": "M42-W2",
        "providers": providers,
        "localAvailable": any(
            x.get("probe", {}).get("available") and x.get("kind") == "local" for x in providers
        ),
        "cloudAvailable": [
            x["providerId"]
            for x in providers
            if x.get("kind") == "cloud" and x.get("probe", {}).get("available")
        ],
    }
