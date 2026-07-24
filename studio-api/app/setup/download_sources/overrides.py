"""Persist per-component source overrides (no secrets)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..state import load_state, update_state


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_overrides() -> dict[str, dict[str, Any]]:
    state = load_state()
    raw = state.get("source_overrides") or {}
    return {k: dict(v) for k, v in raw.items() if isinstance(v, dict)}


def get_override(component_id: str) -> dict[str, Any] | None:
    item = list_overrides().get(component_id)
    return dict(item) if item else None


def save_override(component_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "componentId": component_id,
        "provider": str(payload.get("provider") or ""),
        "sourceUrl": str(payload.get("sourceUrl") or payload.get("source_url") or ""),
        "repository": payload.get("repository"),
        "revision": payload.get("revision") or payload.get("release_tag"),
        "selectedFiles": list(payload.get("selectedFiles") or payload.get("selected_files") or []),
        "assetName": payload.get("assetName") or payload.get("asset_name"),
        "installMethod": str(payload.get("installMethod") or payload.get("install_method") or "manual_url"),
        "verifiedAt": payload.get("verifiedAt") or payload.get("verified_at") or _now(),
        "verificationFingerprint": payload.get("verificationFingerprint")
        or payload.get("verification_fingerprint"),
        "userDefined": True,
    }
    # Never persist secrets
    for key in ("token", "authorization", "password", "cookie", "auth_headers"):
        clean.pop(key, None)

    def mutate(state: dict[str, Any]) -> None:
        overrides = state.setdefault("source_overrides", {})
        overrides[component_id] = clean

    update_state(mutate)
    return clean


def remove_override(component_id: str) -> bool:
    existed = {"ok": False}

    def mutate(state: dict[str, Any]) -> None:
        overrides = state.setdefault("source_overrides", {})
        if component_id in overrides:
            overrides.pop(component_id, None)
            existed["ok"] = True

    update_state(mutate)
    return existed["ok"]
