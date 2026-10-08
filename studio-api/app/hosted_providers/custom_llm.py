"""Custom OpenAI-compatible LLM endpoint registration (base URL + secret)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from ..secrets_store import clear_secret, get_secret, set_secret, set_secret_verification, secret_status

_LOCK = threading.RLock()

# Reserved Playwright fixture from tests/e2e/setup/hosted-api-provider-setup.spec.ts.
# These records must never be stored in the owner provider registry.
_RESERVED_TEST_DISPLAY_NAME = "Mock OpenAI Compat"
_RESERVED_TEST_MODELS = frozenset({"mock-chat-mini", "mock-chat-pro"})
_DISPOSABLE_TTL_SEC = 15 * 60


def config_path() -> Path:
    return settings.data_dir / "custom_llm_providers.json"


def disposable_config_path() -> Path:
    """Scratch registry for automated tests. Not the owner Setup catalog."""
    return settings.data_dir / "e2e" / "openai_compat_disposable.json"


def _empty_store() -> dict[str, Any]:
    return {"schemaVersion": 1, "endpoints": []}


def _load_at(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_store()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _empty_store()
        if not isinstance(raw.get("endpoints"), list):
            raw["endpoints"] = []
        return raw
    except (OSError, ValueError, TypeError):
        return _empty_store()


def _load() -> dict[str, Any]:
    return _load_at(config_path())


def _save_at(path: Path, data: dict[str, Any]) -> dict[str, Any]:
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


def _save(data: dict[str, Any]) -> dict[str, Any]:
    return _save_at(config_path(), data)


def _is_loopback(base_url: str | None) -> bool:
    raw = (base_url or "").strip().lower()
    if not raw:
        return False
    host = raw
    if "://" in raw:
        host = raw.split("://", 1)[1]
    host = host.split("/", 1)[0]
    host = host.split("@")[-1]
    hostname = host.split(":")[0].strip("[]")
    return hostname in {"127.0.0.1", "localhost", "::1"}


def is_reserved_test_endpoint(entry: dict[str, Any] | None) -> bool:
    """True only for the known Playwright mock fixture, never a named owner provider."""
    if not isinstance(entry, dict):
        return False
    name = str(entry.get("displayName") or "").strip()
    if name == _RESERVED_TEST_DISPLAY_NAME:
        return True
    models = {str(model) for model in (entry.get("discoveredModels") or []) if str(model)}
    if models and models <= _RESERVED_TEST_MODELS and _is_loopback(str(entry.get("baseUrl") or "")):
        return True
    return False


def _parse_expiry(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("expiresAt")
    if not raw:
        return None
    try:
        exp = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp


def _is_expired(entry: dict[str, Any], *, now: datetime | None = None) -> bool:
    exp = _parse_expiry(entry)
    if exp is None:
        return False
    return exp <= (now or datetime.now(timezone.utc))


def _clear_endpoint_secret(endpoint_id: str | None) -> None:
    if not endpoint_id:
        return
    clear_secret(secret_name_for(str(endpoint_id)))


def purge_reserved_from_owner() -> list[str]:
    """Drop leaked test fixtures from the owner registry and delete their secrets."""
    removed: list[dict[str, Any]] = []
    with _LOCK:
        data = _load()
        kept: list[dict[str, Any]] = []
        for entry in data.get("endpoints") or []:
            if is_reserved_test_endpoint(entry):
                removed.append(entry)
            else:
                kept.append(entry)
        if removed:
            data["endpoints"] = kept
            _save(data)
    ids = [str(entry.get("id")) for entry in removed if entry.get("id")]
    for endpoint_id in ids:
        _clear_endpoint_secret(endpoint_id)
    return ids


def sweep_expired_disposable() -> list[str]:
    removed: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    with _LOCK:
        path = disposable_config_path()
        data = _load_at(path)
        kept: list[dict[str, Any]] = []
        for entry in data.get("endpoints") or []:
            if _is_expired(entry, now=now):
                removed.append(entry)
            else:
                kept.append(entry)
        if removed:
            data["endpoints"] = kept
            _save_at(path, data)
    ids = [str(entry.get("id")) for entry in removed if entry.get("id")]
    for endpoint_id in ids:
        _clear_endpoint_secret(endpoint_id)
    return ids


def purge_leaked_test_providers() -> dict[str, Any]:
    """Remove owner-registry leaks and the entire disposable test scratch store.

    Called on Studio API startup and by the Playwright cleanup path so an
    interrupted test cannot leave mock endpoints in the owner configuration.
    """
    owner_ids = purge_reserved_from_owner()
    disposable: list[dict[str, Any]] = []
    with _LOCK:
        path = disposable_config_path()
        data = _load_at(path)
        disposable = [entry for entry in (data.get("endpoints") or []) if isinstance(entry, dict)]
        if disposable or path.exists():
            _save_at(path, _empty_store())
    disposable_ids = [str(entry.get("id")) for entry in disposable if entry.get("id")]
    for endpoint_id in disposable_ids:
        _clear_endpoint_secret(endpoint_id)
    return {
        "ownerRemoved": owner_ids,
        "disposableRemoved": disposable_ids,
        "mock": False,
    }


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
    disposable: bool = False,
) -> dict[str, Any]:
    from .adapters.openai_compatible_adapter import probe_openai_compatible

    eid = endpoint_id or str(uuid.uuid4())
    probe = await probe_openai_compatible(api_key, base_url=base_url, models_path=models_path)
    if not probe.get("valid"):
        return {"ok": False, "error": "INVALID_KEY", "message": probe.get("message"), "probe": probe, "mock": False}
    now = datetime.now(timezone.utc)
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
        "updatedAt": now.isoformat(),
    }
    # The Playwright mock fixture is refused from the owner registry even when a
    # caller forgets the disposable flag. Explicit disposable=True is the opt-in
    # for any other automated endpoint.
    use_disposable = bool(disposable) or is_reserved_test_endpoint(entry)
    if use_disposable:
        entry["disposable"] = True
        entry["testArtifact"] = True
        entry["expiresAt"] = (now + timedelta(seconds=_DISPOSABLE_TTL_SEC)).isoformat()
    store_path = disposable_config_path() if use_disposable else config_path()
    # Owner registry never keeps the Playwright fixture, including leftovers from
    # a previous run that wrote before this guard existed. Purge before storing
    # the new secret so a leaked copy of this same id cannot clear it.
    purge_reserved_from_owner()
    set_secret(secret_name_for(eid), api_key)
    set_secret_verification(
        secret_name_for(eid),
        verified=True,
        message=probe.get("message") or "",
        detail={"httpStatus": probe.get("httpStatus"), "baseUrl": base_url},
    )
    with _LOCK:
        data = _load_at(store_path)
        endpoints = [e for e in data["endpoints"] if e.get("id") != eid]
        endpoints.append(entry)
        data["endpoints"] = endpoints
        _save_at(store_path, data)
    public = {k: v for k, v in entry.items() if k != "api_key"}
    return {
        "ok": True,
        "endpoint": {**public, "apiKeyStatus": secret_status(secret_name_for(eid))},
        "probe": probe,
        "disposable": use_disposable,
        "mock": False,
    }


def _public_endpoints(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for e in entries:
        eid = str(e.get("id"))
        out.append({**e, "apiKeyStatus": secret_status(secret_name_for(eid)), "secretIncluded": False})
    return out


def list_endpoints() -> list[dict[str, Any]]:
    """Owner registry only. Test fixtures are purged, never returned."""
    purge_reserved_from_owner()
    sweep_expired_disposable()
    with _LOCK:
        endpoints = [e for e in (_load().get("endpoints") or []) if not is_reserved_test_endpoint(e)]
    return _public_endpoints(endpoints)


def list_disposable_endpoints() -> list[dict[str, Any]]:
    sweep_expired_disposable()
    with _LOCK:
        endpoints = list(_load_at(disposable_config_path()).get("endpoints") or [])
    return _public_endpoints(endpoints)


def delete_endpoint(endpoint_id: str) -> bool:
    removed = False
    with _LOCK:
        for path in (config_path(), disposable_config_path()):
            data = _load_at(path)
            before = list(data.get("endpoints") or [])
            kept = [e for e in before if e.get("id") != endpoint_id]
            if len(kept) != len(before):
                data["endpoints"] = kept
                _save_at(path, data)
                removed = True
    if removed:
        clear_secret(secret_name_for(endpoint_id))
    return removed


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
