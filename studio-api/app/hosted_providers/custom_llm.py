"""Custom OpenAI-compatible LLM endpoint registration (base URL + secret)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..secrets_store import clear_secret, get_secret, set_secret, set_secret_verification, secret_status

_LOCK = threading.RLock()


def config_path() -> Path:
    return settings.data_dir / "custom_llm_providers.json"


def _load() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {"schemaVersion": 1, "endpoints": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"schemaVersion": 1, "endpoints": []}
        if not isinstance(raw.get("endpoints"), list):
            raw["endpoints"] = []
        return raw
    except (OSError, ValueError, TypeError):
        return {"schemaVersion": 1, "endpoints": []}


def _save(data: dict[str, Any]) -> dict[str, Any]:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return data


def secret_name_for(endpoint_id: str) -> str:
    return f"openai_compat_{endpoint_id}_api_key"


async def connect_endpoint(
    *,
    display_name: str,
    base_url: str,
    api_key: str,
    models_path: str = "/v1/models",
    chat_path: str = "/v1/chat/completions",
    billing_currency: str = "USD",
    endpoint_id: str | None = None,
) -> dict[str, Any]:
    from .adapters.openai_compatible_adapter import probe_openai_compatible

    eid = endpoint_id or str(uuid.uuid4())
    probe = await probe_openai_compatible(api_key, base_url=base_url, models_path=models_path)
    if not probe.get("valid"):
        return {"ok": False, "error": "INVALID_KEY", "message": probe.get("message"), "probe": probe, "mock": False}
    set_secret(secret_name_for(eid), api_key)
    set_secret_verification(
        secret_name_for(eid),
        verified=True,
        message=probe.get("message") or "",
        detail={"httpStatus": probe.get("httpStatus"), "baseUrl": base_url},
    )
    entry = {
        "id": eid,
        "providerId": "openai_compatible",
        "displayName": display_name or "OpenAI-compatible",
        "baseUrl": base_url.rstrip("/"),
        "modelsPath": models_path,
        "chatPath": chat_path,
        "billingCurrency": billing_currency,
        "discoveredModels": probe.get("models") or [],
        "capabilities": probe.get("capabilities") or {"llm": True},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        data = _load()
        endpoints = [e for e in data["endpoints"] if e.get("id") != eid]
        endpoints.append(entry)
        data["endpoints"] = endpoints
        _save(data)
    return {
        "ok": True,
        "endpoint": {**entry, "apiKeyStatus": secret_status(secret_name_for(eid))},
        "probe": probe,
        "mock": False,
    }


def list_endpoints() -> list[dict[str, Any]]:
    with _LOCK:
        endpoints = list(_load().get("endpoints") or [])
    out = []
    for e in endpoints:
        eid = str(e.get("id"))
        out.append({**e, "apiKeyStatus": secret_status(secret_name_for(eid)), "secretIncluded": False})
    return out


def delete_endpoint(endpoint_id: str) -> bool:
    with _LOCK:
        data = _load()
        before = len(data["endpoints"])
        data["endpoints"] = [e for e in data["endpoints"] if e.get("id") != endpoint_id]
        _save(data)
    clear_secret(secret_name_for(endpoint_id))
    return len(data["endpoints"]) < before


def dock_llm_models() -> list[dict[str, Any]]:
    """Rows for Production Dock API LLM section."""
    rows = []
    for e in list_endpoints():
        configured = bool((e.get("apiKeyStatus") or {}).get("configured"))
        for mid in e.get("discoveredModels") or []:
            rows.append(
                {
                    "id": f"openai-compat:{e['id']}:{mid}",
                    "modality": "llm",
                    "label": f"{mid} ({e.get('displayName') or 'API'})",
                    "locality": "hosted",
                    "executionClass": "hosted_api",
                    "providerId": "openai_compatible",
                    "endpointId": e.get("id"),
                    "capabilityLabel": "Available" if configured else "Requires Setup",
                    "supports": ["chat"],
                    "executable": configured,
                    "group": "HOSTED API",
                }
            )
        if not e.get("discoveredModels"):
            rows.append(
                {
                    "id": f"openai-compat:{e['id']}:default",
                    "modality": "llm",
                    "label": e.get("displayName") or "OpenAI-compatible",
                    "locality": "hosted",
                    "executionClass": "hosted_api",
                    "providerId": "openai_compatible",
                    "endpointId": e.get("id"),
                    "capabilityLabel": "Available" if configured else "Requires Setup",
                    "supports": ["chat"],
                    "executable": configured,
                    "group": "HOSTED API",
                }
            )
    return rows
