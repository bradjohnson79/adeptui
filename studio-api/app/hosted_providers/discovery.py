"""Dynamic API model discovery → normalize → classify → persist.

Discovery does not activate models. Dock reads only the normalized store.
Primary-provider policy: only the active preferred provider populates API sections.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ..secrets_store import get_secret, secret_status
from .adapters import probe_fal, probe_kie, probe_wavespeed
from .model_store import load_catalog, save_catalog
from .preferences import load_preferences
from .registry import PROVIDERS

Modality = Literal["llm", "video", "image", "audio"]
Readiness = Literal[
    "Ready",
    "Requires Adapter",
    "Requires Setup",
    "Permission Denied",
    "Insufficient Balance",
    "Temporarily Unavailable",
    "Unsupported",
    "Discovered",
]

# Adept-compatible hosted models known to the product (not a fake dock dump).
# Live account access is probed; adapterAvailable marks certified product wiring.
_PROVIDER_CATALOG: dict[str, list[dict[str, Any]]] = {
    "kie": [
        {
            "providerModelId": "seedance",
            "displayName": "Seedance 2.0",
            "modality": "video",
            "capabilities": ["text_to_video", "image_to_video"],
            "adapterAvailable": True,
            "dockModelId": "seedance-kie",
        },
        {
            "providerModelId": "kling",
            "displayName": "Kling",
            "modality": "video",
            "capabilities": ["text_to_video", "image_to_video"],
            "adapterAvailable": True,
            "dockModelId": "kling-kie",
        },
        {
            "providerModelId": "flux",
            "displayName": "FLUX",
            "modality": "image",
            "capabilities": ["text_to_image", "edit"],
            "adapterAvailable": True,
            "dockModelId": "flux-kie",
        },
        {
            "providerModelId": "nano-banana",
            "displayName": "Nano Banana",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": True,
            "dockModelId": "nano-banana-kie",
        },
        {
            "providerModelId": "audio",
            "displayName": "Hosted Audio",
            "modality": "audio",
            "capabilities": ["music", "sfx"],
            "adapterAvailable": False,
            "dockModelId": "audio-kie",
        },
    ],
    "wavespeed": [
        {
            "providerModelId": "seedance",
            "displayName": "Seedance",
            "modality": "video",
            "capabilities": ["text_to_video"],
            "adapterAvailable": False,
            "dockModelId": "seedance-wavespeed",
        },
        {
            "providerModelId": "veo",
            "displayName": "Veo",
            "modality": "video",
            "capabilities": ["text_to_video"],
            "adapterAvailable": False,
            "dockModelId": "veo-wavespeed",
        },
        {
            "providerModelId": "wavespeed-ai/flux-dev",
            "displayName": "FLUX Dev",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": False,
            "dockModelId": "flux-wavespeed",
        },
        {
            "providerModelId": "seedream",
            "displayName": "Seedream",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": False,
            "dockModelId": "seedream-wavespeed",
        },
    ],
    "fal": [
        {
            "providerModelId": "fal-ai/bytedance/seedance",
            "displayName": "Seedance",
            "modality": "video",
            "capabilities": ["text_to_video", "image_to_video"],
            "adapterAvailable": True,
            "dockModelId": "seedance-fal",
        },
        {
            "providerModelId": "fal-ai/kling-video",
            "displayName": "Kling 3.0",
            "modality": "video",
            "capabilities": ["text_to_video", "image_to_video"],
            "adapterAvailable": True,
            "dockModelId": "kling-fal",
        },
        {
            "providerModelId": "fal-ai/veo",
            "displayName": "Veo",
            "modality": "video",
            "capabilities": ["text_to_video"],
            "adapterAvailable": True,
            "dockModelId": "veo-fal",
        },
        {
            "providerModelId": "fal-ai/flux/dev",
            "displayName": "FLUX Kontext",
            "modality": "image",
            "capabilities": ["text_to_image", "edit"],
            "adapterAvailable": True,
            "dockModelId": "flux-fal",
        },
        {
            "providerModelId": "fal-ai/flux/kontext",
            "displayName": "FLUX Kontext Pro",
            "modality": "image",
            "capabilities": ["text_to_image", "edit"],
            "adapterAvailable": False,
            "dockModelId": "flux-kontext-fal",
        },
        {
            "providerModelId": "fal-ai/krea-2/turbo",
            "displayName": "Krea 2 Turbo",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": True,
            "dockModelId": "krea2-turbo-fal",
        },
        {
            "providerModelId": "krea/v2/medium/text-to-image",
            "displayName": "Krea 2 Medium",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": True,
            "dockModelId": "krea2-medium-fal",
        },
        {
            "providerModelId": "krea/v2/large/text-to-image",
            "displayName": "Krea 2 Large",
            "modality": "image",
            "capabilities": ["text_to_image"],
            "adapterAvailable": True,
            "dockModelId": "krea2-large-fal",
        },
        {
            "providerModelId": "fal-ai/mmaudio",
            "displayName": "Hosted Audio",
            "modality": "audio",
            "capabilities": ["music", "sfx"],
            "adapterAvailable": False,
            "dockModelId": "audio-fal",
        },
    ],
}

_PROBES = {
    "kie": probe_kie,
    "wavespeed": probe_wavespeed,
    "fal": probe_fal,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_provider_id() -> str | None:
    prefs = load_preferences()
    preferred = str(prefs.get("preferredProvider") or "automatic")
    if preferred in PROVIDERS:
        defn = PROVIDERS[preferred]
        if get_secret(defn.secret_name):
            return preferred
        return preferred  # still primary even if key missing (empty reason elsewhere)
    # automatic → first connected provider in priority order
    from .registry import PRIORITY_ORDER

    for pid in PRIORITY_ORDER:
        defn = PROVIDERS[pid]
        if get_secret(defn.secret_name):
            return pid
    return None


def _classify(
    *,
    account_accessible: bool,
    adapter_available: bool,
    probe: dict[str, Any] | None,
) -> tuple[Readiness, str, bool]:
    """Return readiness, emptyReason hint, selectable."""
    if not account_accessible:
        msg = (probe or {}).get("message") or ""
        low = msg.lower()
        if "balance" in low or "credit" in low or "quota" in low:
            return "Insufficient Balance", "insufficient_balance", False
        if "permission" in low or "forbidden" in low or "denied" in low:
            return "Permission Denied", "permission_denied", False
        if "invalid" in low or "unauthorized" in low or "401" in low:
            return "Requires Setup", "invalid_key", False
        return "Requires Setup", "invalid_or_inactive_key", False
    if not adapter_available:
        return "Requires Adapter", "requires_adapter", False
    return "Ready", "ok", True


async def discover_provider(provider_id: str, *, persist_as_active: bool = True) -> dict[str, Any]:
    """Validate access, discover Adept-compatible models, normalize, store."""
    pid = (provider_id or "").strip().lower()
    defn = PROVIDERS.get(pid)
    if not defn:
        return {"ok": False, "error": "UNKNOWN_PROVIDER", "message": f"Unknown provider: {provider_id}", "mock": False}

    key = get_secret(defn.secret_name)
    if not key:
        catalog = {
            "activeProviderId": pid if persist_as_active else load_catalog().get("activeProviderId"),
            "emptyReason": "no_key",
            "emptyMessage": "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard.",
            "models": [],
            "summary": {
                "providerId": pid,
                "videoFound": 0,
                "imageFound": 0,
                "audioFound": 0,
                "llmFound": 0,
                "compatible": 0,
                "requiresAdapter": 0,
                "unavailable": 0,
            },
            "probe": None,
        }
        if persist_as_active:
            save_catalog(catalog)
        return {"ok": False, "error": "NOT_CONFIGURED", "message": f"No {defn.display_name} API key configured.", **catalog, "mock": False}

    probe_fn = _PROBES[pid]
    probe = await probe_fn(key)
    account_ok = probe.get("valid") is True

    raw_rows = list(_PROVIDER_CATALOG.get(pid) or [])
    discovered_at = _now()
    models: list[dict[str, Any]] = []
    for row in raw_rows:
        readiness, _reason, selectable = _classify(
            account_accessible=account_ok,
            adapter_available=bool(row.get("adapterAvailable")),
            probe=probe,
        )
        models.append(
            {
                "id": row["dockModelId"],
                "providerId": pid,
                "providerModelId": row["providerModelId"],
                "displayName": row["displayName"],
                "modality": row["modality"],
                "capabilities": list(row.get("capabilities") or []),
                "accountAccessible": account_ok,
                "adapterAvailable": bool(row.get("adapterAvailable")),
                "liveProbeStatus": "ok" if account_ok else "failed",
                "pricingMetadata": None,
                "lastDiscoveredAt": discovered_at,
                "lastVerifiedAt": discovered_at if account_ok else None,
                "readiness": readiness,
                "selectable": selectable and account_ok and bool(row.get("adapterAvailable")),
                "capabilityLabel": (
                    "Certified"
                    if readiness == "Ready"
                    else "Requires Setup"
                    if readiness in ("Requires Setup", "Permission Denied", "Insufficient Balance")
                    else "Unsupported"
                    if readiness == "Requires Adapter"
                    else "Unavailable"
                ),
                "locality": "hosted",
                "label": f"{row['displayName']} — {defn.display_name}",
                "executable": bool(selectable and account_ok and row.get("adapterAvailable")),
            }
        )

    summary = {
        "providerId": pid,
        "providerDisplayName": defn.display_name,
        "videoFound": sum(1 for m in models if m["modality"] == "video"),
        "imageFound": sum(1 for m in models if m["modality"] == "image"),
        "audioFound": sum(1 for m in models if m["modality"] == "audio"),
        "llmFound": sum(1 for m in models if m["modality"] == "llm"),
        "compatible": sum(1 for m in models if m["readiness"] == "Ready"),
        "requiresAdapter": sum(1 for m in models if m["readiness"] == "Requires Adapter"),
        "unavailable": sum(1 for m in models if m["readiness"] not in ("Ready", "Requires Adapter")),
        "accountAccessible": account_ok,
    }

    if not account_ok:
        empty_reason = "invalid_key"
        empty_message = "No API models available.\n\nThe API key is invalid or inactive."
    elif not models:
        empty_reason = "none_discovered"
        empty_message = "No compatible models were found\nfor the connected provider."
    elif summary["compatible"] == 0:
        empty_reason = "none_supported"
        empty_message = (
            "Models were discovered, but none are\ncurrently supported by Adept UI."
        )
    else:
        empty_reason = None
        empty_message = None

    catalog = {
        "activeProviderId": pid,
        "emptyReason": empty_reason,
        "emptyMessage": empty_message,
        "models": models,
        "summary": summary,
        "probe": {
            "valid": probe.get("valid"),
            "message": probe.get("message"),
            "httpStatus": probe.get("httpStatus"),
        },
    }
    if persist_as_active:
        save_catalog(catalog)

    return {
        "ok": account_ok,
        "providerId": pid,
        "discovery": catalog,
        "summary": summary,
        "mock": False,
    }


async def discover_active_provider() -> dict[str, Any]:
    pid = _active_provider_id()
    if not pid:
        catalog = {
            "activeProviderId": None,
            "emptyReason": "no_provider",
            "emptyMessage": "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard.",
            "models": [],
            "summary": {},
        }
        save_catalog(catalog)
        return {"ok": False, "error": "NO_PROVIDER", "message": "No hosted provider selected or connected.", **catalog, "mock": False}
    return await discover_provider(pid, persist_as_active=True)


def discovery_status() -> dict[str, Any]:
    cat = load_catalog()
    return {
        "ok": True,
        "activeProviderId": cat.get("activeProviderId"),
        "emptyReason": cat.get("emptyReason"),
        "emptyMessage": cat.get("emptyMessage"),
        "summary": cat.get("summary") or {},
        "modelCount": len(cat.get("models") or []),
        "updatedAt": cat.get("updatedAt"),
        "mock": False,
    }


def dock_api_models(modality: str) -> dict[str, Any]:
    """API section payload for Production Dock menus (primary provider only)."""
    cat = load_catalog()
    active = cat.get("activeProviderId") or _active_provider_id()
    all_models = list(cat.get("models") or [])
    rows = []
    for m in all_models:
        if m.get("modality") != modality:
            continue
        if active and m.get("providerId") != active:
            continue
        rows.append(m)

    empty_reason = cat.get("emptyReason")
    empty_message = cat.get("emptyMessage")
    if rows:
        empty_reason = None
        empty_message = None
    elif not active:
        empty_reason = "no_provider"
        empty_message = (
            "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard."
        )
    elif not all_models:
        # Provider selected/connected but discovery has not populated the catalog yet.
        empty_reason = "needs_discovery"
        empty_message = (
            "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard."
        )
    elif empty_message and empty_reason in ("invalid_key", "invalid_or_inactive_key", "none_supported"):
        pass  # keep diagnostic catalog message
    else:
        empty_reason = "none_for_modality"
        empty_message = (
            f"No compatible {modality} models were found\nfor the connected provider."
        )

    return {
        "activeProviderId": active,
        "models": rows,
        "emptyReason": empty_reason if not rows else None,
        "emptyMessage": empty_message if not rows else None,
        "summary": cat.get("summary") or {},
        "updatedAt": cat.get("updatedAt"),
    }
