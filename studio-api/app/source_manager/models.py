"""Normalized Source Manager records (no secrets)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


SECRET_KEYS = frozenset(
    {
        "token",
        "authorization",
        "password",
        "cookie",
        "auth_headers",
        "api_key",
        "access_token",
        "hf_token",
        "github_token",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "src") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def strip_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        lower = str(key).lower()
        if lower in SECRET_KEYS or "token" in lower or "secret" in lower or "password" in lower:
            continue
        if isinstance(value, dict):
            clean[key] = strip_secrets(value)
        else:
            clean[key] = value
    return clean


def normalize_source_record(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    source_id = str(raw.get("id") or "").strip() or new_id("src")
    provider = str(raw.get("provider") or "").strip().lower()
    source_url = str(raw.get("sourceUrl") or raw.get("source_url") or "").strip()
    if not provider or not source_url:
        return None
    now = utc_now()
    record = {
        "id": source_id,
        "provider": provider,
        "sourceType": str(raw.get("sourceType") or raw.get("source_type") or "unknown"),
        "sourceUrl": source_url,
        "displayName": str(
            raw.get("displayName")
            or raw.get("display_name")
            or raw.get("repository")
            or source_url
        ),
        "owner": raw.get("owner"),
        "repository": raw.get("repository"),
        "revision": raw.get("revision"),
        "branch": raw.get("branch"),
        "commit": raw.get("commit"),
        "assetPath": raw.get("assetPath") or raw.get("asset_path") or raw.get("assetName"),
        "repositoryType": raw.get("repositoryType") or raw.get("repository_type"),
        "authenticationRequired": bool(
            raw.get("authenticationRequired") or raw.get("authentication_required")
        ),
        "verificationStatus": str(
            raw.get("verificationStatus") or raw.get("verification_status") or "unverified"
        ),
        "verifiedAt": raw.get("verifiedAt") or raw.get("verified_at"),
        "verificationFingerprint": raw.get("verificationFingerprint")
        or raw.get("verification_fingerprint"),
        "metadata": dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), dict) else {},
        "userDefined": bool(raw.get("userDefined", raw.get("user_defined", True))),
        "createdAt": raw.get("createdAt") or raw.get("created_at") or now,
        "updatedAt": raw.get("updatedAt") or raw.get("updated_at") or now,
    }
    return strip_secrets(record)


def normalize_assignment(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    component_id = str(raw.get("componentId") or raw.get("component_id") or "").strip()
    source_id = str(raw.get("sourceId") or raw.get("source_id") or "").strip()
    if not component_id or not source_id:
        return None
    now = utc_now()
    selected = raw.get("selectedArtifacts") or raw.get("selected_artifacts") or raw.get("selectedFiles") or []
    if not isinstance(selected, list):
        selected = []
    return strip_secrets(
        {
            "componentId": component_id,
            "sourceId": source_id,
            "selectedArtifacts": [str(x) for x in selected if x],
            "installPlanId": raw.get("installPlanId") or raw.get("install_plan_id"),
            "isOverride": bool(raw.get("isOverride", raw.get("is_override", True))),
            "createdAt": raw.get("createdAt") or raw.get("created_at") or now,
            "updatedAt": raw.get("updatedAt") or raw.get("updated_at") or now,
        }
    )


def source_from_override(component_id: str, override: dict[str, Any]) -> dict[str, Any]:
    """Build a SourceRecord from a legacy per-component source_overrides entry."""
    url = str(override.get("sourceUrl") or override.get("source_url") or "").strip()
    provider = str(override.get("provider") or "direct").strip().lower() or "direct"
    repo = override.get("repository")
    revision = override.get("revision")
    display = str(repo or url)
    selected = override.get("selectedFiles") or override.get("selected_files") or []
    fingerprint = override.get("verificationFingerprint") or override.get("verification_fingerprint")
    return normalize_source_record(
        {
            "id": new_id("src"),
            "provider": provider,
            "sourceType": "release_asset" if override.get("assetName") else "url",
            "sourceUrl": url,
            "displayName": display,
            "owner": None,
            "repository": repo,
            "revision": revision,
            "assetPath": override.get("assetName") or override.get("asset_name"),
            "authenticationRequired": False,
            "verificationStatus": "verified" if fingerprint else "migrated",
            "verifiedAt": override.get("verifiedAt") or override.get("verified_at"),
            "verificationFingerprint": fingerprint,
            "metadata": {
                "migratedFrom": "source_overrides",
                "componentId": component_id,
                "installMethod": override.get("installMethod") or override.get("install_method"),
                "selectedFiles": list(selected) if isinstance(selected, list) else [],
            },
            "userDefined": True,
        }
    ) or {}
