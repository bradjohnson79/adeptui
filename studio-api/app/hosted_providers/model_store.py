"""Persisted normalized discovered API model catalog (primary-provider scoped)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings

_STORE_PATH = settings.data_dir / "hosted_providers" / "discovered_models.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_path() -> Path:
    return _STORE_PATH


def load_catalog() -> dict[str, Any]:
    path = _STORE_PATH
    if not path.is_file():
        return {
            "version": 1,
            "activeProviderId": None,
            "emptyReason": "no_provider",
            "models": [],
            "summary": {},
            "updatedAt": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"version": 1, "models": []}
    except Exception:
        return {"version": 1, "models": [], "emptyReason": "store_error"}


def save_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    path = _STORE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["version"] = 1
    body["updatedAt"] = _now()
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return body


def clear_provider_models(provider_id: str) -> dict[str, Any]:
    cat = load_catalog()
    models = [m for m in (cat.get("models") or []) if m.get("providerId") != provider_id]
    cat["models"] = models
    if cat.get("activeProviderId") == provider_id:
        cat["activeProviderId"] = None
        cat["emptyReason"] = "no_provider"
        cat["summary"] = {}
    return save_catalog(cat)


def models_for_modality(modality: str, *, provider_id: str | None = None) -> list[dict[str, Any]]:
    cat = load_catalog()
    active = provider_id or cat.get("activeProviderId")
    out = []
    for row in cat.get("models") or []:
        if row.get("modality") != modality:
            continue
        if active and row.get("providerId") != active:
            continue
        out.append(row)
    return out
