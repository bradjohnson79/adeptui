"""Source Manager orchestration used by API + Setup Wizard facades."""

from __future__ import annotations

from typing import Any

from ..setup.download_sources.overrides import remove_override, save_override
from ..setup.download_sources.service import verify_source_url
from ..setup.pack_manifests import set_source_override
from .contracts import ArtifactQueryContext, SourceInput, VerificationContext
from .migration import ensure_migrated
from .models import new_id, normalize_source_record, utc_now
from .persistence import (
    get_assignment,
    list_assignments,
    list_sources,
    remove_assignment,
    remove_source,
    upsert_assignment,
    upsert_source,
)
from .registry import overview_payload, select_provider


def get_overview() -> dict[str, Any]:
    return overview_payload()


def save_verified_source_for_component(
    component_id: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Dual-write: legacy override + normalized SourceRecord + assignment."""
    if not verification.get("ok"):
        raise ValueError("Cannot save an unverified source.")
    source = verification.get("source") or {}
    url = source.get("source_url") or source.get("resolved_download_url")
    if not url:
        raise ValueError("Verified source is missing a URL.")

    # Legacy pack path
    set_source_override(component_id, url)
    override = save_override(
        component_id,
        {
            "provider": source.get("provider"),
            "sourceUrl": url,
            "repository": verification.get("repository"),
            "revision": verification.get("revision"),
            "selectedFiles": [verification["selected_file"]] if verification.get("selected_file") else [],
            "assetName": source.get("asset_name"),
            "installMethod": verification.get("installation_method"),
            "verifiedAt": utc_now(),
            "verificationFingerprint": verification.get("verification_fingerprint"),
        },
    )

    ensure_migrated()
    record = normalize_source_record(
        {
            "id": new_id("src"),
            "provider": source.get("provider") or "direct",
            "sourceType": source.get("kind") or "url",
            "sourceUrl": url,
            "displayName": verification.get("repository") or url,
            "owner": source.get("owner"),
            "repository": verification.get("repository") or source.get("repository"),
            "revision": verification.get("revision"),
            "assetPath": source.get("asset_name") or source.get("file_path"),
            "authenticationRequired": bool(verification.get("authentication_required")),
            "verificationStatus": "verified",
            "verifiedAt": utc_now(),
            "verificationFingerprint": verification.get("verification_fingerprint"),
            "metadata": {
                "installMethod": verification.get("installation_method"),
                "selectedFiles": override.get("selectedFiles") or [],
                "componentId": component_id,
            },
            "userDefined": True,
        }
    )
    if not record:
        raise ValueError("Failed to normalize source record.")

    # Reuse existing source with same fingerprint when present
    fingerprint = record.get("verificationFingerprint")
    for existing_id, existing in list_sources().items():
        if fingerprint and existing.get("verificationFingerprint") == fingerprint:
            record["id"] = existing_id
            record["createdAt"] = existing.get("createdAt") or record["createdAt"]
            break

    saved = upsert_source(record)
    assignment = upsert_assignment(
        {
            "componentId": component_id,
            "sourceId": saved["id"],
            "selectedArtifacts": override.get("selectedFiles") or [],
            "isOverride": True,
        }
    )
    return {
        "override": override,
        "source": saved,
        "assignment": assignment,
    }


def remove_component_source(component_id: str) -> dict[str, Any]:
    assignment = get_assignment(component_id)
    source_id = assignment.get("sourceId") if assignment else None
    remove_assignment(component_id)
    removed_override = remove_override(component_id)
    set_source_override(component_id, None)
    # Remove orphaned user-defined source if unused
    removed_source = False
    if source_id:
        still_used = any(
            item.get("sourceId") == source_id for item in list_assignments().values()
        )
        if not still_used:
            removed_source = remove_source(source_id)
    return {
        "componentId": component_id,
        "removedOverride": removed_override,
        "removedSource": removed_source,
        "sourceId": source_id,
    }


def verify_and_select(url: str, *, component_id: str | None = None, revision: str | None = None) -> dict[str, Any]:
    source_input = SourceInput(url=url, revision=revision, component_id=component_id)
    provider = select_provider(source_input)
    parsed = provider.parse_source(source_input)
    verified = provider.verify_source(parsed, VerificationContext(component_id=component_id))
    artifacts = provider.list_artifacts(verified, ArtifactQueryContext(component_id=component_id))
    # Prefer existing verify_source_url payload shape for Setup Wizard compatibility
    legacy = verify_source_url(url=url, component_id=component_id, revision=revision)
    return {
        "providerId": provider.id,
        "provider": provider.detect().to_dict(),
        "parsed": parsed.to_dict(),
        "verified": {
            "ok": verified.ok,
            "status": verified.verification_status,
            "fingerprint": verified.verification_fingerprint,
            "message": verified.message,
        },
        "artifacts": [item.to_dict() for item in artifacts],
        "legacy": legacy,
    }
