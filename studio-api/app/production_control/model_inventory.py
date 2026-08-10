"""Model inventory — stale-while-revalidate cache for /models endpoint.

One background discovery populates a shared snapshot for all 4 modalities.
No per-request blocking I/O.  No thundering herd from concurrent requests.
"""

from __future__ import annotations

import logging
import threading
import time
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

#: Cache entry: (timestamp, dict of complete model payload)
_MODEL_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_MODEL_CACHE_KEY = "_global"
_MODEL_CACHE_STALE_AFTER = 30.0
_MODEL_CACHE_LOCK = RLock()
_MODEL_REFRESH_IN_FLIGHT = False


def _discover_all_models() -> dict[str, Any]:
    """Run the full model discovery chain once and return merged result.

    This is the only place that performs blocking I/O (Ollama HTTP probe,
    Docker discovery, filesystem scans, setup status, hosted API catalog).
    """
    from .model_registry import filter_for_action
    from ..hosted_providers.discovery import dock_api_models

    modalities = ["llm", "video", "image", "audio"]
    sections: dict[str, list[dict[str, Any]]] = {}
    api_metas: dict[str, dict[str, Any]] = {}
    flat_models: list[dict[str, Any]] = []

    for mod in modalities:
        all_annotated = filter_for_action(mod, "generate")
        local_models = [m for m in all_annotated if m.get("locality") == "local"]

        api_section = dock_api_models(mod)
        api_models = []
        for row in api_section.get("models") or []:
            api_models.append({
                "id": row.get("id"),
                "modality": mod,
                "label": row.get("label") or row.get("displayName"),
                "locality": "hosted",
                "providerId": row.get("providerId"),
                "capabilityLabel": row.get("capabilityLabel") or "Requires Setup",
                "supports": row.get("capabilities") or [],
                "doesNotSupport": [],
                "gpuCompatible": False,
                "executable": bool(row.get("executable")),
                "selectable": bool(row.get("selectable")),
                "readiness": row.get("readiness"),
                "providerModelId": row.get("providerModelId"),
                "accountAccessible": row.get("accountAccessible"),
                "adapterAvailable": row.get("adapterAvailable"),
                "group": "HOSTED API",
                "actionMatch": True,
                "action": "generate",
            })

        if mod == "llm":
            try:
                from ..hosted_providers.custom_llm import dock_llm_models

                for row in dock_llm_models():
                    api_models.append({**row, "selectable": bool(row.get("executable")), "actionMatch": True, "action": "generate"})
            except Exception:
                pass

        for m in local_models:
            pid = str(m.get("providerId") or "")
            mid = str(m.get("id") or "")
            if mid.startswith("docker-runtime:") or pid == "docker-runtime":
                m["group"] = "DOCKER LOCAL"
            elif mid.startswith("custom-local:"):
                m["group"] = "CUSTOM LOCAL"
            elif pid == "ollama" or mid.startswith("ollama-"):
                m["group"] = "OLLAMA LOCAL"
            else:
                m["group"] = "NATIVE LOCAL"

        sections[mod] = {
            "local": local_models,
            "api": api_models,
            "groups": ["NATIVE LOCAL", "OLLAMA LOCAL", "CUSTOM LOCAL", "DOCKER LOCAL", "HOSTED API"],
        }
        api_metas[mod] = {
            "activeProviderId": api_section.get("activeProviderId"),
            "emptyReason": api_section.get("emptyReason"),
            "emptyMessage": api_section.get("emptyMessage"),
            "summary": api_section.get("summary") or {},
            "updatedAt": api_section.get("updatedAt"),
        }
        flat_models.extend(list(local_models) + [m for m in api_models if m.get("selectable")])

    return {
        "models": flat_models,
        "sections": sections,
        "api": api_metas,
        "discoveredAt": time.monotonic(),
    }


def warm_model_inventory() -> None:
    """Pre-warm the model inventory cache on startup."""
    import os
    if not os.environ.get("STUDIO_API_PORT"):
        logger.debug("Skipping model inventory warm — no API configured (test environment).")
        return
    logger.info("Warming Production Control model inventory...")
    try:
        payload = _discover_all_models()
        with _MODEL_CACHE_LOCK:
            _MODEL_CACHE[_MODEL_CACHE_KEY] = (time.monotonic(), payload)
        logger.info("Model inventory warm complete (%d models).", len(payload.get("models") or []))
    except Exception as exc:
        logger.warning("Model inventory warm failed: %s", exc)


def _background_refresh() -> None:
    """Refresh the full model inventory in a background thread."""
    global _MODEL_REFRESH_IN_FLIGHT
    try:
        payload = _discover_all_models()
        with _MODEL_CACHE_LOCK:
            _MODEL_CACHE[_MODEL_CACHE_KEY] = (time.monotonic(), payload)
        logger.debug("Background model inventory refresh complete (%d models).", len(payload.get("models") or []))
    except Exception as exc:
        logger.warning("Background model inventory refresh failed: %s", exc)
    finally:
        _MODEL_REFRESH_IN_FLIGHT = False


def get_model_inventory() -> dict[str, Any] | None:
    """Return cached model inventory. May return STALE data — never blocks.

    If the cache is stale, one background refresh is triggered.
    The caller receives the stale value immediately.
    """
    global _MODEL_REFRESH_IN_FLIGHT
    with _MODEL_CACHE_LOCK:
        entry = _MODEL_CACHE.get(_MODEL_CACHE_KEY)
        if entry is None:
            return None
        cached_at, payload = entry
        if time.monotonic() - cached_at >= _MODEL_CACHE_STALE_AFTER:
            if not _MODEL_REFRESH_IN_FLIGHT:
                _MODEL_REFRESH_IN_FLIGHT = True
                threading.Thread(target=_background_refresh, daemon=True).start()
        return payload


def invalidate_model_cache() -> None:
    """Clear the model inventory cache."""
    with _MODEL_CACHE_LOCK:
        _MODEL_CACHE.pop(_MODEL_CACHE_KEY, None)


def get_models_cached(modality: str, action: str = "generate") -> dict[str, Any]:
    """Return models for a single modality from the shared inventory cache.

    If no cache exists, performs a single bounded discovery.
    """
    inventory = get_model_inventory()
    if inventory is None:
        inventory = _discover_all_models()
        with _MODEL_CACHE_LOCK:
            _MODEL_CACHE[_MODEL_CACHE_KEY] = (time.monotonic(), inventory)

    inventory_sections = inventory.get("sections") or {}
    section = inventory_sections.get(modality, {"local": [], "api": [], "groups": []})
    local_models = section.get("local") or []
    api_models = section.get("api") or []
    groups = section.get("groups") or []
    api_meta = (inventory.get("api") or {}).get(modality) or {}

    flat = list(local_models) + [m for m in api_models if m.get("selectable")]
    return {
        "ok": True,
        "modality": modality,
        "action": action,
        "models": flat,
        "sections": {"local": local_models, "api": api_models, "groups": groups},
        "api": api_meta,
        "mock": False,
    }
