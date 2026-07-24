"""Migrate legacy source_overrides into normalized Source Manager records."""

from __future__ import annotations

import logging
from typing import Any

from ..setup.state import SCHEMA_VERSION, load_state, update_state
from .models import normalize_assignment, source_from_override, utc_now

logger = logging.getLogger(__name__)

TARGET_SCHEMA_VERSION = max(SCHEMA_VERSION, 3)


def migrate_source_overrides_v2_to_v3(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Ensure sources + component_sources exist.
    Migrates legacy source_overrides without deleting them (dual-read compatibility).
    Idempotent.
    """
    working = state if isinstance(state, dict) else load_state()
    migrated = 0
    skipped = 0

    sources = working.setdefault("sources", {})
    if not isinstance(sources, dict):
        sources = {}
        working["sources"] = sources
    assignments = working.setdefault("component_sources", {})
    if not isinstance(assignments, dict):
        assignments = {}
        working["component_sources"] = assignments
    working.setdefault("install_receipts", {})
    working.setdefault("download_queue", {})

    overrides = working.get("source_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}

    # Index existing sources by fingerprint/url to avoid duplicates on re-run
    by_fingerprint: dict[str, str] = {}
    by_url_component: dict[str, str] = {}
    for source_id, record in sources.items():
        if not isinstance(record, dict):
            continue
        fp = record.get("verificationFingerprint")
        if fp:
            by_fingerprint[str(fp)] = str(source_id)
        url = str(record.get("sourceUrl") or "")
        meta = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        component_hint = str(meta.get("componentId") or "")
        if url and component_hint:
            by_url_component[f"{component_hint}|{url}"] = str(source_id)

    for component_id, override in overrides.items():
        if not isinstance(override, dict):
            skipped += 1
            continue
        if component_id in assignments and isinstance(assignments.get(component_id), dict):
            skipped += 1
            continue
        url = str(override.get("sourceUrl") or override.get("source_url") or "").strip()
        if not url:
            skipped += 1
            continue

        fp = override.get("verificationFingerprint") or override.get("verification_fingerprint")
        existing_id = None
        if fp and str(fp) in by_fingerprint:
            existing_id = by_fingerprint[str(fp)]
        elif f"{component_id}|{url}" in by_url_component:
            existing_id = by_url_component[f"{component_id}|{url}"]

        if existing_id:
            source_id = existing_id
        else:
            record = source_from_override(str(component_id), override)
            if not record:
                skipped += 1
                continue
            source_id = record["id"]
            sources[source_id] = record
            if fp:
                by_fingerprint[str(fp)] = source_id
            by_url_component[f"{component_id}|{url}"] = source_id
            migrated += 1

        selected = override.get("selectedFiles") or override.get("selected_files") or []
        assignment = normalize_assignment(
            {
                "componentId": str(component_id),
                "sourceId": source_id,
                "selectedArtifacts": list(selected) if isinstance(selected, list) else [],
                "isOverride": True,
                "createdAt": override.get("verifiedAt") or utc_now(),
            }
        )
        if assignment:
            assignments[str(component_id)] = assignment

    working["schema_version"] = TARGET_SCHEMA_VERSION
    working.setdefault("source_manager", {})
    if isinstance(working["source_manager"], dict):
        working["source_manager"]["migration"] = {
            "lastRunAt": utc_now(),
            "migratedOverrides": migrated,
            "skipped": skipped,
            "from": "source_overrides",
            "to": "sources+component_sources",
        }

    if state is None:
        update_state(lambda s: _apply_migration_into(s, working))
        return load_state()
    return working


def _apply_migration_into(target: dict[str, Any], migrated: dict[str, Any]) -> None:
    for key in (
        "sources",
        "component_sources",
        "install_receipts",
        "download_queue",
        "source_manager",
        "schema_version",
    ):
        if key in migrated:
            target[key] = migrated[key]


def ensure_migrated() -> dict[str, Any]:
    """Load state, migrate if needed, persist when changes applied."""
    state = load_state()
    before_sources = len(state.get("sources") or {})
    before_assignments = len(state.get("component_sources") or {})
    overrides = state.get("source_overrides") or {}
    needs = False
    if not isinstance(state.get("sources"), dict) or not isinstance(state.get("component_sources"), dict):
        needs = True
    elif isinstance(overrides, dict):
        for component_id in overrides:
            if component_id not in (state.get("component_sources") or {}):
                needs = True
                break
    if int(state.get("schema_version") or 0) < TARGET_SCHEMA_VERSION:
        needs = True
    if not needs and before_sources == 0 and before_assignments == 0 and not overrides:
        # Still ensure empty keys exist for Source Manager UI
        def ensure_keys(s: dict[str, Any]) -> None:
            s.setdefault("sources", {})
            s.setdefault("component_sources", {})
            s.setdefault("install_receipts", {})
            s.setdefault("download_queue", {})
            if int(s.get("schema_version") or 0) < TARGET_SCHEMA_VERSION:
                s["schema_version"] = TARGET_SCHEMA_VERSION

        return update_state(ensure_keys)

    result = migrate_source_overrides_v2_to_v3()
    logger.info(
        "Source Manager migration complete sources=%s assignments=%s",
        len(result.get("sources") or {}),
        len(result.get("component_sources") or {}),
    )
    return result
