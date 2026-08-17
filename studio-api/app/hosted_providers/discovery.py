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
            "providerModelId": 'bytedance/seedance-2',
            "displayName": 'Seedance 2.0',
            "modality": 'video',
            "capabilities": ['text_to_video', 'image_to_video'],
            "adapterAvailable": True,
            "dockModelId": 'seedance-kie',
        },
        {
            "providerModelId": 'kling-3.0/video',
            "displayName": 'Kling 3.0',
            "modality": 'video',
            "capabilities": ['text_to_video', 'image_to_video'],
            "adapterAvailable": True,
            "dockModelId": 'kling-kie',
        },
        {
            "providerModelId": 'veo3',
            "displayName": 'Veo 3.1',
            "modality": 'video',
            "capabilities": ['text_to_video', 'image_to_video'],
            "adapterAvailable": False,
            "dockModelId": 'veo-kie',
        },
        {
            "providerModelId": 'flux',
            "displayName": 'FLUX',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": True,
            "dockModelId": 'flux-kie',
        },
        {
            "providerModelId": 'nano-banana',
            "displayName": 'Nano Banana',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'nano-banana-kie',
        },
        {
            "providerModelId": 'gpt-image-2-text-to-image',
            "displayName": 'GPT Image 2',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": True,
            "dockModelId": 'gpt-image-2-kie',
        },
        {
            "providerModelId": 'seedream/5-pro-text-to-image',
            "displayName": 'Seedream',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": True,
            "dockModelId": 'seedream-kie',
        },
        {
            "providerModelId": 'elevenlabs/text-to-speech-multilingual-v2',
            "displayName": 'ElevenLabs Multilingual v2',
            "modality": 'audio',
            "capabilities": ['tts'],
            "adapterAvailable": False,
            "dockModelId": 'audio-kie',
        },
        {
            "providerModelId": 'elevenlabs/text-to-dialogue-v3',
            "displayName": 'ElevenLabs Dialogue v3',
            "modality": 'audio',
            "capabilities": ['tts', 'dialogue'],
            "adapterAvailable": False,
            "dockModelId": 'elevenlabs-dialogue-kie',
        },
        {
            "providerModelId": 'gemini-3-pro',
            "displayName": 'Gemini 3 Pro',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": True,
            "dockModelId": 'gemini-3-pro-kie',
        },
        {
            "providerModelId": 'claude-sonnet-4-6',
            "displayName": 'Claude Sonnet 4.6',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": False,
            "dockModelId": 'claude-sonnet-4-6-kie',
        },
        {
            "providerModelId": 'gpt-5-5',
            "displayName": 'GPT 5.5',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": False,
            "dockModelId": 'gpt-5-5-kie',
        },
    ],
    "wavespeed": [
        {
            "providerModelId": 'bytedance/seedance-2.0/text-to-video',
            "displayName": 'Seedance 2.0',
            "modality": 'video',
            "capabilities": ['text_to_video'],
            "adapterAvailable": False,
            "dockModelId": 'seedance-wavespeed',
        },
        {
            "providerModelId": 'google/veo3-fast',
            "displayName": 'Veo 3 Fast',
            "modality": 'video',
            "capabilities": ['text_to_video'],
            "adapterAvailable": False,
            "dockModelId": 'veo-wavespeed',
        },
        {
            "providerModelId": 'wavespeed-ai/flux-dev',
            "displayName": 'FLUX Dev',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": False,
            "dockModelId": 'flux-wavespeed',
        },
        {
            "providerModelId": 'bytedance/seedream-v5.0-pro',
            "displayName": 'Seedream',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": False,
            "dockModelId": 'seedream-wavespeed',
        },
        {
            "providerModelId": 'wavespeed-ai/z-image/turbo',
            "displayName": 'Z-Image Turbo',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": False,
            "dockModelId": 'z-image-turbo-wavespeed',
        },
        {
            "providerModelId": 'minimax/speech-2.6-hd',
            "displayName": 'MiniMax Speech 2.6 HD',
            "modality": 'audio',
            "capabilities": ['tts'],
            "adapterAvailable": False,
            "dockModelId": 'minimax-speech-wavespeed',
        },
        {
            "providerModelId": 'deepseek/deepseek-v4-flash',
            "displayName": 'DeepSeek V4 Flash',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": True,
            "dockModelId": 'deepseek-v4-flash-wavespeed',
        },
        {
            "providerModelId": 'anthropic/claude-opus-4.7',
            "displayName": 'Claude Opus 4.7',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": True,
            "dockModelId": 'claude-opus-4.7-wavespeed',
        },
        {
            "providerModelId": 'openai/gpt-5.5',
            "displayName": 'GPT 5.5',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": True,
            "dockModelId": 'gpt-5.5-wavespeed',
        },
    ],
    "fal": [
        {
            "providerModelId": 'fal-ai/bytedance/seedance/v1/pro/text-to-video',
            "displayName": 'Seedance 1 Pro',
            "modality": 'video',
            "capabilities": ['text_to_video', 'image_to_video'],
            "adapterAvailable": True,
            "dockModelId": 'seedance-fal',
        },
        {
            "providerModelId": 'fal-ai/kling-video/v3/pro/text-to-video',
            "displayName": 'Kling 3 Pro',
            "modality": 'video',
            "capabilities": ['text_to_video', 'image_to_video'],
            "adapterAvailable": True,
            "dockModelId": 'kling-fal',
        },
        {
            "providerModelId": 'fal-ai/veo3.1',
            "displayName": 'Veo 3.1',
            "modality": 'video',
            "capabilities": ['text_to_video'],
            "adapterAvailable": True,
            "dockModelId": 'veo-fal',
        },
        {
            "providerModelId": 'fal-ai/flux/dev',
            "displayName": 'FLUX Kontext',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": True,
            "dockModelId": 'flux-fal',
        },
        {
            "providerModelId": 'fal-ai/flux-pro/kontext',
            "displayName": 'FLUX Kontext Pro',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": False,
            "dockModelId": 'flux-kontext-fal',
        },
        {
            "providerModelId": 'fal-ai/krea-2/turbo',
            "displayName": 'Krea 2 Turbo',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'krea2-turbo-fal',
        },
        {
            "providerModelId": 'krea/v2/medium/text-to-image',
            "displayName": 'Krea 2 Medium',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'krea2-medium-fal',
        },
        {
            "providerModelId": 'krea/v2/large/text-to-image',
            "displayName": 'Krea 2 Large',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'krea2-large-fal',
        },
        {
            "providerModelId": 'fal-ai/mmaudio',
            "displayName": 'Hosted Audio',
            "modality": 'audio',
            "capabilities": ['music', 'sfx'],
            "adapterAvailable": False,
            "dockModelId": 'audio-fal',
        },
        {
            "providerModelId": 'fal-ai/flux-2-pro',
            "displayName": 'FLUX.2 Pro',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'flux-2-pro-fal',
        },
        {
            "providerModelId": 'fal-ai/flux/schnell',
            "displayName": 'FLUX.1 Schnell',
            "modality": 'image',
            "capabilities": ['text_to_image'],
            "adapterAvailable": True,
            "dockModelId": 'flux-schnell-fal',
        },
        {
            "providerModelId": 'fal-ai/nano-banana-2',
            "displayName": 'Nano Banana 2',
            "modality": 'image',
            "capabilities": ['text_to_image', 'edit'],
            "adapterAvailable": True,
            "dockModelId": 'nano-banana-2-fal',
        },
        {
            "providerModelId": 'fal-ai/minimax/speech-02-hd',
            "displayName": 'MiniMax Speech 02 HD',
            "modality": 'audio',
            "capabilities": ['tts'],
            "adapterAvailable": False,
            "dockModelId": 'minimax-speech-fal',
        },
        {
            "providerModelId": 'fal-ai/any-llm',
            "displayName": 'Any LLM',
            "modality": 'llm',
            "capabilities": ['chat'],
            "adapterAvailable": True,
            "dockModelId": 'any-llm-fal',
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



def _normalize_provider_models(
    pid: str,
    *,
    account_ok: bool,
    probe: dict[str, Any] | None,
    discovered_at: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize one provider catalog into dock rows. Does not persist."""
    defn = PROVIDERS[pid]
    stamp = discovered_at or _now()
    models: list[dict[str, Any]] = []
    for row in list(_PROVIDER_CATALOG.get(pid) or []):
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
                "lastDiscoveredAt": stamp,
                "lastVerifiedAt": stamp if account_ok else None,
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
    return models


def _verified_provider_ids() -> list[str]:
    """Providers whose stored key probe is verified. Missing/invalid/unverified are omitted."""
    from .registry import PRIORITY_ORDER

    out: list[str] = []
    for pid in PRIORITY_ORDER:
        defn = PROVIDERS[pid]
        st = secret_status(defn.secret_name)
        if st.get("state") == "verified":
            out.append(pid)
    return out


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

    discovered_at = _now()
    models = _normalize_provider_models(
        pid, account_ok=account_ok, probe=probe, discovered_at=discovered_at
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


def _dock_api_models_primary(modality: str) -> dict[str, Any]:
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
        empty_reason = "needs_discovery"
        empty_message = (
            "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard."
        )
    elif empty_message and empty_reason in ("invalid_key", "invalid_or_inactive_key", "none_supported"):
        pass
    else:
        empty_reason = "none_for_modality"
        empty_message = (
            f"No compatible {modality} models were found\nfor the connected provider."
        )

    return {
        "activeProviderId": active,
        "scope": "primary",
        "models": rows,
        "emptyReason": empty_reason if not rows else None,
        "emptyMessage": empty_message if not rows else None,
        "summary": cat.get("summary") or {},
        "updatedAt": cat.get("updatedAt"),
    }


def _dock_api_models_all_keyed(modality: str) -> dict[str, Any]:
    """Union image/other rows for every provider whose key probe is verified."""
    verified = _verified_provider_ids()
    stamp = _now()
    rows: list[dict[str, Any]] = []
    by_provider: dict[str, int] = {}
    for pid in verified:
        defn = PROVIDERS[pid]
        st = secret_status(defn.secret_name)
        probe = {
            "valid": True,
            "message": st.get("message") or "",
            "httpStatus": 200,
        }
        models = _normalize_provider_models(
            pid, account_ok=True, probe=probe, discovered_at=stamp
        )
        # Only executable rows are offered as selectable cloud generators.
        # adapterAvailable=False / executable=False rows (e.g. flux-kontext-fal)
        # must never appear as selectable api_models (CDX-080).
        kept = [
            m
            for m in models
            if m.get("modality") == modality
            and m.get("adapterAvailable") is True
            and m.get("executable") is True
        ]
        rows.extend(kept)
        by_provider[pid] = len(kept)

    empty_reason = None
    empty_message = None
    if not verified:
        empty_reason = "no_provider"
        empty_message = (
            "No API models available.\n\nCheck your API key or add a provider\nthrough the Setup Wizard."
        )
    elif not rows:
        empty_reason = "none_for_modality"
        empty_message = (
            f"No compatible {modality} models were found\nfor the connected providers."
        )

    return {
        "activeProviderId": _active_provider_id(),
        "scope": "all_keyed",
        "models": rows,
        "emptyReason": empty_reason,
        "emptyMessage": empty_message,
        "summary": {
            "scope": "all_keyed",
            "providers": verified,
            "found": len(rows),
            "byProvider": by_provider,
        },
        "updatedAt": stamp,
    }


def dock_api_models(modality: str, scope: str | None = None) -> dict[str, Any]:
    """API section payload.

    Image defaults to every provider whose key probe is verified (Character Creator
    Cloud Generators). Video/audio/llm stay primary-provider-only unless scope is
    passed explicitly. scope='primary' restores the old single-provider filter.
    """
    requested = (scope or "").strip().lower()
    if requested not in {"primary", "all_keyed"}:
        requested = "all_keyed" if modality == "image" else "primary"
    if requested == "all_keyed":
        return _dock_api_models_all_keyed(modality)
    return _dock_api_models_primary(modality)
