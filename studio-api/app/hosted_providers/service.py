"""Hosted provider status, connect/test, preferences — no mock credentials or balances."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..secrets_store import (
    clear_secret,
    get_secret,
    secret_status,
    set_secret,
    set_secret_verification,
)
from .adapters import probe_fal, probe_kie, probe_wavespeed
from .capabilities import capability_matrix, executable_capabilities
from .models import list_canonical_models
from .preferences import load_preferences, save_preferences
from .registry import PRIORITY_ORDER, PROVIDERS, list_providers
from .resolver import resolve_hosted_provider

_PROBES = {
    "kie": probe_kie,
    "wavespeed": probe_wavespeed,
    "fal": probe_fal,
}

# In-memory last successful execution stamps (process-local; not fabricated).
_LAST_SUCCESS: dict[str, str] = {}


def record_successful_execution(provider_id: str) -> None:
    _LAST_SUCCESS[provider_id] = datetime.now(timezone.utc).isoformat()


async def connect_and_verify(provider_id: str, api_key: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    defn = PROVIDERS.get(pid)
    if not defn:
        return {"ok": False, "error": "UNKNOWN_PROVIDER", "message": f"Unknown provider: {provider_id}", "mock": False}
    key = (api_key or "").strip()
    if not key:
        return {"ok": False, "error": "KEY_REQUIRED", "message": "api_key is required", "mock": False}

    probe = await _PROBES[pid](key)
    if probe.get("valid") is False:
        return {
            "ok": False,
            "error": "INVALID_KEY",
            "message": probe.get("message") or "Provider rejected this API key.",
            "probe": probe,
            "mock": False,
        }

    set_secret(defn.secret_name, key)
    set_secret_verification(
        defn.secret_name,
        verified=probe.get("valid"),
        message=probe.get("message", ""),
        detail={"httpStatus": probe.get("httpStatus"), "probeEndpoint": probe.get("probeEndpoint")},
    )
    # Prefer this provider after successful connect (primary-provider policy).
    try:
        save_preferences(preferred_provider=pid)  # type: ignore[arg-type]
    except Exception:
        pass
    try:
        from ..production_control.store import patch_user_preferences

        patch_user_preferences({"defaultHostedProviderId": pid})
    except Exception:
        pass
    discovery: dict[str, Any] = {}
    try:
        from .discovery import discover_provider

        discovery = await discover_provider(pid, persist_as_active=True)
    except Exception as exc:
        discovery = {"ok": False, "error": "DISCOVERY_FAILED", "message": str(exc), "mock": False}
    card = provider_card(pid)
    return {
        "ok": True,
        "provider": card,
        "probe": probe,
        "discovery": discovery.get("discovery") or discovery,
        "summary": discovery.get("summary"),
        "mock": False,
    }


async def test_provider(provider_id: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    defn = PROVIDERS.get(pid)
    if not defn:
        return {"ok": False, "error": "UNKNOWN_PROVIDER", "message": f"Unknown provider: {provider_id}", "mock": False}
    key = get_secret(defn.secret_name)
    if not key:
        return {"ok": False, "error": "NOT_CONFIGURED", "message": f"No {defn.display_name} API key is configured.", "mock": False}
    probe = await _PROBES[pid](key)
    set_secret_verification(
        defn.secret_name,
        verified=probe.get("valid"),
        message=probe.get("message", ""),
        detail={"httpStatus": probe.get("httpStatus"), "probeEndpoint": probe.get("probeEndpoint")},
    )
    discovery: dict[str, Any] = {}
    try:
        from .discovery import discover_provider

        discovery = await discover_provider(pid, persist_as_active=True)
    except Exception as exc:
        discovery = {"ok": False, "error": "DISCOVERY_FAILED", "message": str(exc), "mock": False}
    return {
        "ok": probe.get("valid") is True,
        "provider": provider_card(pid),
        "probe": probe,
        "discovery": discovery.get("discovery") or discovery,
        "summary": discovery.get("summary"),
        "mock": False,
    }


def clear_provider(provider_id: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    defn = PROVIDERS.get(pid)
    if not defn:
        return {"ok": False, "error": "UNKNOWN_PROVIDER", "mock": False}
    clear_secret(defn.secret_name)
    try:
        from .model_store import clear_provider_models

        clear_provider_models(pid)
    except Exception:
        pass
    return {"ok": True, "provider": provider_card(pid), "mock": False}


def set_preferred(provider_id: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    if pid not in ("kie", "wavespeed", "fal", "automatic"):
        return {"ok": False, "error": "INVALID_PREFERENCE", "message": "preferredProvider must be kie|wavespeed|fal|automatic", "mock": False}
    prefs = save_preferences(preferred_provider=pid)  # type: ignore[arg-type]
    # Keep Production Dock primary-provider preference in sync.
    try:
        from ..production_control.store import patch_user_preferences

        patch_user_preferences({"defaultHostedProviderId": pid})
    except Exception:
        pass
    return {"ok": True, "preferences": prefs, "mock": False}


def provider_card(provider_id: str) -> dict[str, Any]:
    pid = (provider_id or "").strip().lower()
    defn = PROVIDERS[pid]
    status = secret_status(defn.secret_name)
    health = "healthy" if status.get("state") == "verified" else (
        "degraded" if status.get("state") == "unverified" else (
            "error" if status.get("state") == "invalid" else "disconnected"
        )
    )
    return {
        "providerId": pid,
        "displayName": defn.display_name,
        "role": defn.role,
        "recommended": defn.recommended,
        "priority": PRIORITY_ORDER.index(pid) + 1,  # type: ignore[arg-type]
        "connectionStatus": status.get("state"),
        "apiKeyStatus": {
            "configured": status.get("configured"),
            "hint": status.get("hint"),
            "state": status.get("state"),
            "verifiedAt": status.get("verifiedAt"),
            "message": status.get("message"),
        },
        "availableBalance": None,  # populated only from live probe responses when supported
        "supportedModalities": list(defn.supported_modalities),
        "certifiedModels": list(defn.certified_models),
        "estimatedPricing": defn.estimated_pricing_notes,
        "healthStatus": health,
        "lastSuccessfulExecution": _LAST_SUCCESS.get(pid),
        "currentVersion": defn.current_version,
        "adapterVersion": defn.adapter_version,
        "integrationStatus": defn.integration_status,
        "executableCapabilities": executable_capabilities(pid),
        "keysUrl": defn.keys_url,
        "dashboardUrl": defn.dashboard_url,
        "billingUrl": defn.billing_url,
        "docsUrl": defn.docs_url,
        "mock": False,
    }


def catalog() -> dict[str, Any]:
    prefs = load_preferences()
    cards = [provider_card(pid) for pid in PRIORITY_ORDER]
    # Attach balances from last verification detail if present — do not invent
    states = {c["providerId"]: c["connectionStatus"] for c in cards}
    return {
        "title": "Hosted AI Providers",
        "recommendationOrder": list(PRIORITY_ORDER),
        "providers": cards,
        "preferences": prefs,
        "canonicalModels": list_canonical_models(include_mappings=False),
        "capabilities": capability_matrix(),
        "credentialStates": states,
        "pipeline": [
            "Product surface",
            "Canonical Intent",
            "Capability Resolver",
            "Certified Provider Resolver",
            "Kie.ai OR WaveSpeed.ai OR fal.ai",
            "Canonical Queue",
            "Asset Library",
            "Timeline",
            "VersionGraph",
            "Provenance",
        ],
        "silentSwitchForbidden": True,
        "mock": False,
    }


def resolve(
    *,
    capability: str | None = None,
    canonical_model: str | None = None,
) -> dict[str, Any]:
    states = {pid: secret_status(PROVIDERS[pid].secret_name).get("state") or "missing" for pid in PRIORITY_ORDER}
    return resolve_hosted_provider(
        capability=capability,
        canonical_model=canonical_model,
        credential_states=states,
    )


def registry_snapshot() -> dict[str, Any]:
    return {
        "providers": list_providers(),
        "models": list_canonical_models(include_mappings=True),
        "capabilities": capability_matrix(),
        "mock": False,
    }
