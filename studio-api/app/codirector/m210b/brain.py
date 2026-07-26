"""Gemma primary/fallback brain helpers for Co-Director (M2.10b addendum)."""

from __future__ import annotations

from typing import Any

import httpx

from ...config import settings
from .. import config_store

PRIMARY_MODEL = "gemma4:31b-it-qat"
FALLBACK_MODEL = "gemma4:12b"


def default_brain_config() -> dict[str, Any]:
    return {
        "primaryModel": PRIMARY_MODEL,
        "fallbackModel": FALLBACK_MODEL,
        "selectedModel": PRIMARY_MODEL,
        "allowAutomaticModelDownload": False,
    }


def discover_ollama_tags(
    *,
    endpoint: str | None = None,
    timeout_sec: float = 5.0,
) -> list[dict[str, Any]]:
    """Query Ollama /api/tags and return model metadata dicts."""
    base = (endpoint or settings.ollama_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.get(f"{base}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc), "models": []}]
    models = data.get("models") or []
    out: list[dict[str, Any]] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        out.append(
            {
                "name": m.get("name"),
                "model": m.get("model") or m.get("name"),
                "digest": m.get("digest"),
                "size": m.get("size"),
                "modifiedAt": m.get("modified_at") or m.get("modifiedAt"),
                "details": m.get("details") or {},
            }
        )
    return out


def installed_model_names(tags: list[dict[str, Any]] | None = None) -> set[str]:
    items = tags if tags is not None else discover_ollama_tags()
    names: set[str] = set()
    for m in items:
        if m.get("error"):
            continue
        for key in ("name", "model"):
            val = m.get(key)
            if val:
                names.add(str(val))
    return names


def resolve_brain_models(tags: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Pick primary/fallback from installed tags; never auto-download."""
    names = installed_model_names(tags)
    primary = PRIMARY_MODEL if PRIMARY_MODEL in names else None
    # Allow close variants containing gemma4 + 31b
    if primary is None:
        for n in sorted(names):
            low = n.lower()
            if "gemma4" in low and "31b" in low:
                primary = n
                break
    fallback = FALLBACK_MODEL if FALLBACK_MODEL in names else None
    if fallback is None:
        for n in sorted(names):
            low = n.lower()
            if "gemma4" in low and "12b" in low:
                fallback = n
                break
    return {
        "primaryModel": primary or PRIMARY_MODEL,
        "fallbackModel": fallback or FALLBACK_MODEL,
        "primaryInstalled": primary is not None,
        "fallbackInstalled": fallback is not None,
        "allowAutomaticModelDownload": False,
        "installed": sorted(names),
    }


def persist_brain_config(
    *,
    primary: str | None = None,
    fallback: str | None = None,
    allow_download: bool = False,
) -> dict[str, Any]:
    """Persist primary/fallback via config_store (selectedModel kept in sync)."""
    resolved = resolve_brain_models()
    primary_model = primary or resolved["primaryModel"]
    fallback_model = fallback or resolved["fallbackModel"]
    patch = {
        "selectedModel": primary_model,
        "primaryModel": primary_model,
        "fallbackModel": fallback_model,
        "allowAutomaticModelDownload": bool(allow_download),
    }
    return config_store.save_config(patch)


def load_brain_config() -> dict[str, Any]:
    cfg = config_store.load_config()
    primary = cfg.get("primaryModel") or cfg.get("selectedModel") or PRIMARY_MODEL
    return {
        "endpoint": cfg.get("endpoint"),
        "selectedModel": cfg.get("selectedModel") or primary,
        "primaryModel": primary,
        "fallbackModel": cfg.get("fallbackModel") or FALLBACK_MODEL,
        "allowAutomaticModelDownload": bool(
            cfg.get("allowAutomaticModelDownload", False)
        ),
        "timeoutSec": cfg.get("timeoutSec"),
    }
