from __future__ import annotations

from pathlib import Path
from typing import Any

from .catalog import COMPONENTS, ComponentDefinition
from .diagnostics import Verification, utc_now, verify_component
from .state import load_state, update_state

CANONICAL_STATUSES = {
    "unknown", "checking", "ready", "not_installed",
    "update_available", "installing", "error",
    "download_unavailable",
    "source_pending",
}

_RECOMMENDATION_LABELS = {
    "none": "No Action Required",
    "install": "Download and Install",
    "repair": "Repair Installation",
    "reinstall": "Reinstall",
    "update": "Update Now",
    "correct_path": "Locate Existing Files",
    "grant_permission": "Grant Permission",
    "configure": "Configure API Key",
    "manual_help": "View Manual Help",
    "link_existing": "Link Existing Folder",
    "choose_install_location": "Choose Install Location",
    "refresh_source": "Check Again",
    "add_source_url": "Add Source URL",
}


def _diagnostic_from_verification(component_id: str, verification: Verification) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "healthy": verification.healthy,
        "issue_code": verification.issue_code,
        "summary": verification.summary,
        "technical_details": list(verification.details),
        "recommendation": verification.recommendation,
        "recommended_action_label": _RECOMMENDATION_LABELS.get(
            verification.recommendation, "Run Diagnostics"
        ),
        "requires_user_interaction": verification.requires_user_interaction,
        "checked_at": utc_now(),
    }


def _reconcile_diagnostic(
    component_id: str,
    verification: Verification,
    diagnostic: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Drop or refresh cached diagnostics that no longer match live verification."""
    if verification.healthy:
        return None
    if diagnostic is None or diagnostic.get("issue_code") != verification.issue_code:
        return _diagnostic_from_verification(component_id, verification)
    return diagnostic


def _download_stage_label(download_op: dict[str, Any]) -> str:
    phase = str(download_op.get("phase") or "")
    prog = download_op.get("progress") or {}
    percent = prog.get("percent")
    speed = prog.get("speedBytesPerSecond")
    eta = prog.get("etaSeconds")
    position = download_op.get("queuePosition")
    if phase == "queued":
        return f"Waiting to download — position {position or '?'}"
    if phase == "downloading":
        parts = ["Downloading"]
        if percent is not None:
            parts.append(f"{percent:.0f}%")
        if speed:
            mb = float(speed) / (1024 * 1024)
            parts.append(f"{mb:.1f} MB/s")
        if eta is not None:
            mins = max(1, int(eta) // 60) if eta >= 60 else 0
            parts.append("less than a minute remaining" if mins == 0 else f"about {mins} minutes remaining")
        return " — ".join(parts)
    labels = {
        "paused": "Download paused",
        "extracting": "Download complete — extracting files",
        "validating": "Verifying installation",
        "finalizing": "Finalizing installation",
        "failed": "Download failed — Retry available",
        "interrupted": "Installation was interrupted — Resume or Retry",
        "waiting_for_disk_space": "Waiting for disk space",
        "cancelling": "Cancelling…",
    }
    return labels.get(phase, phase.replace("_", " ").title())


def _filesystem_bytes(path: str | None) -> int:
    if not path or "://" in path:
        return 0
    from .pack_install import directory_byte_size

    return directory_byte_size(Path(path).expanduser())


def _reported_installed_bytes(
    definition: ComponentDefinition,
    verification: Verification,
) -> int:
    """Installed size is filesystem truth for packs; never catalog estimates."""
    if definition.installer == "asset_pack" or definition.verifier in ("linked_files", "asset_pack"):
        if not verification.healthy:
            return 0
        return _filesystem_bytes(verification.path)
    if not verification.healthy:
        return 0 if definition.verifier in (
            "ltx_file", "wan_files", "zimage_files", "ic_lora_file"
        ) else definition.installed_bytes
    return definition.installed_bytes


def _primary_action(
    status: str,
    diagnostic: dict[str, Any] | None,
    *,
    source_valid: bool | None = None,
    kind: str | None = None,
    source_state: str | None = None,
) -> dict[str, Any] | None:
    from .component_kinds import KIND_CREDENTIAL, primary_action_for_kind

    if kind == KIND_CREDENTIAL:
        return primary_action_for_kind(
            kind, status=status, source_state=source_state, diagnostic=diagnostic
        )
    if status == "ready" or status in ("checking", "installing"):
        return None
    if status == "source_pending":
        return {"action": "add_source_url", "label": "Add Source URL", "disabled": False}
    if status == "download_unavailable":
        return {
            "action": "add_source_url",
            "label": "Add Source URL",
            "disabled": False,
        }
    if status == "not_installed":
        if source_valid is False:
            return {
                "action": "add_source_url",
                "label": "Add Source URL",
                "disabled": False,
            }
        return {"action": "install", "label": "Download and Install"}
    if status == "update_available":
        return {"action": "update", "label": "Update Now"}
    if diagnostic and diagnostic.get("recommendation") not in (None, "none"):
        recommendation = str(diagnostic["recommendation"])
        if recommendation in ("manual_help", "add_source_url") and source_valid is False:
            return {
                "action": "add_source_url",
                "label": "Add Source URL",
                "disabled": False,
            }
        labels = {
            "install": "Download and Install",
            "repair": "Repair Installation",
            "reinstall": "Reinstall",
            "update": "Update Now",
            "correct_path": "Locate Existing Files",
            "grant_permission": "Grant Permission",
            "configure": "Configure API Key",
            "manual_help": "View Details",
            "link_existing": "Link Existing Folder",
            "choose_install_location": "Choose Install Location",
            "refresh_source": "Check Again",
            "add_source_url": "Add Source URL",
        }
        return {"action": recommendation, "label": labels.get(recommendation, "Run Diagnostics")}
    return {"action": "diagnostics", "label": "Run Diagnostics"}


def _pack_source_fields(definition: ComponentDefinition) -> dict[str, Any]:
    if definition.installer != "asset_pack":
        return {}
    from .component_kinds import (
        SOURCE_INSTALLABLE_FROM_MANUAL,
        SOURCE_NOT_CONFIGURED,
        SOURCE_NOT_PUBLISHED,
        SOURCE_READY_TO_DOWNLOAD,
    )
    from .pack_manifests import get_pack_manifest, public_source_host
    from .pack_release_cache import get_cached_release
    from .pack_settings import pack_settings

    manifest = get_pack_manifest(definition.id)
    url = manifest.source_url()
    cached = get_cached_release(definition.id)
    custom = _custom_source_active(definition.id)
    source_available = bool(url) or bool(cached) or custom
    # Never advertise a shared ADEPT_PACK_GITHUB_* repo as this pack's repository.
    repository = (cached or {}).get("repository")
    if not repository and manifest.source.owner and manifest.source.repository:
        repository = f"{manifest.source.owner}/{manifest.source.repository}"
    if source_available:
        source_state = SOURCE_INSTALLABLE_FROM_MANUAL if custom and not cached else SOURCE_READY_TO_DOWNLOAD
    elif not manifest.is_published():
        source_state = SOURCE_NOT_PUBLISHED
    else:
        source_state = SOURCE_NOT_CONFIGURED
    install_disabled = not source_available
    return {
        "pack_version": (cached or {}).get("version") or manifest.version,
        "source_type": manifest.source.type,
        "provider_id": manifest.source.provider_id,
        "source_valid": manifest.has_valid_source(),
        "source_available": source_available,
        "source_state": source_state,
        "distribution_status": manifest.distribution_status,
        "distribution_label": manifest.distribution_label(),
        "component_kind": manifest.kind or "downloadable_pack",
        "source_host": public_source_host(url),
        "available_version": (cached or {}).get("version"),
        "repository": repository,
        "tag_name": (cached or {}).get("tag_name"),
        "archive_asset_name": (cached or {}).get("archive_asset_name"),
        "expected_download_bytes": (
            (cached or {}).get("expected_bytes")
            or manifest.archive.expected_download_bytes
            or definition.download_bytes
        ),
        "expected_installed_bytes": (
            manifest.install.expected_installed_bytes or definition.installed_bytes
        ),
        "required_files": list(
            (cached or {}).get("required_files") or manifest.install.required_files
        ),
        "secondary_action": {
            "action": "link_existing",
            "label": "Link Existing Folder",
        },
        "tertiary_action": {
            "action": "choose_install_location",
            "label": "Choose Install Location",
        },
        "pack_actions": [
            {
                "action": "install",
                "label": "Download and Install",
                "disabled": install_disabled,
                "disabled_reason": (
                    None
                    if source_available
                    else "No official distribution has been published yet. Add a Source URL or Link Existing Folder."
                ),
            },
            {"action": "choose_install_location", "label": "Choose Install Location"},
            {"action": "link_existing", "label": "Link Existing Folder"},
            {"action": "add_source_url", "label": "Add Source URL"},
            {
                "action": "view_pack_spec",
                "label": "View Pack Specification",
                "disabled": False,
            },
            {
                "action": "refresh_source",
                "label": "Check Again",
                "disabled": not manifest.is_published() and not source_available,
            },
        ],
        "custom_source_active": custom,
        "provider": (pack_settings().provider or "").strip() or None,
    }


def _custom_source_active(component_id: str) -> bool:
    try:
        from .download_sources.overrides import get_override

        return bool(get_override(component_id))
    except Exception:  # noqa: BLE001
        return False


def _record_pack_attempt_cleanup(state: dict[str, Any], component_id: str) -> None:
    """Clear stale installed flags when verification proves the pack is absent."""
    status = state.setdefault("status", {}).setdefault(component_id, {})
    status.pop("installed", None)
    packs = state.setdefault("pack_installs", {})
    current = packs.get(component_id)
    if isinstance(current, dict) and current.get("status") == "completed":
        # Keep history but mark reconciled when files disappear.
        current["reconciled"] = "missing_files"


def build_status(*, persist: bool = True) -> dict[str, Any]:
    state = load_state()
    previous_status = state.get("status", {})
    components: list[dict[str, Any]] = []

    # Import lazily to keep the operation engine independent from detection.
    from .operations import registry
    from .paths import ensure_configured_paths, path_selector_mode

    auto_bound = ensure_configured_paths(state)
    if auto_bound and persist:
        update_state(
            lambda latest: latest.setdefault("model_locations", {}).update(auto_bound)
        )
        state = load_state()

    for definition in COMPONENTS:
        active = registry.active_for_component(definition.id)
        old = previous_status.get(definition.id, {})
        verification = verify_component(definition.id, state)
        raw_diagnostic = old.get("diagnostic") if isinstance(old, dict) else None
        diagnostic = _reconcile_diagnostic(
            definition.id,
            verification,
            raw_diagnostic if isinstance(raw_diagnostic, dict) else None,
        )
        pack_fields = _pack_source_fields(definition)
        source_valid = pack_fields.get("source_valid") if pack_fields else None

        # Phase 1B: prefer Source Manager download-queue ops when present
        download_op = None
        try:
            from ..source_manager.downloads.queue import get_queue_manager

            download_op = get_queue_manager().active_for_component(definition.id)
        except Exception:
            download_op = None

        if download_op:
            dl_phase = str(download_op.get("phase") or "")
            if dl_phase in {"validating", "verifying_source", "preflighting"}:
                canonical = "checking"
            else:
                canonical = "installing"
            prog = download_op.get("progress") or {}
            percent = prog.get("percent")
            progress = (float(percent) / 100.0) if percent is not None else None
            eta = prog.get("etaSeconds")
            operation_id = download_op.get("id")
            stage = _download_stage_label(download_op)
            phase = dl_phase
        elif active:
            phase = active.get("phase")
            if phase in ("verifying", "verifying_download", "verifying_install"):
                canonical = "checking"
            elif phase == "downloading":
                canonical = "installing"
            else:
                canonical = "installing" if active.get("phase") != "verifying" else "checking"
            progress = active.get("progress")
            eta = active.get("estimated_remaining_seconds")
            operation_id = active.get("operation_id")
            stage = active.get("stage")
        else:
            available = old.get("available_version") if isinstance(old, dict) else None
            if verification.healthy and available and available != verification.version:
                canonical = "update_available"
            elif verification.healthy:
                canonical = "ready"
            elif verification.issue_code in (
                "source_not_published",
            ):
                if pack_fields.get("source_available"):
                    canonical = "not_installed"
                else:
                    canonical = "source_pending"
            elif verification.issue_code in (
                "source_not_configured",
                "download_source_missing",
                "pack_provider_not_configured",
                "pack_release_not_found",
            ):
                # A cached / available source means Install can proceed even if files are absent.
                if pack_fields.get("source_available"):
                    canonical = "not_installed"
                elif verification.issue_code == "pack_release_not_found":
                    canonical = "download_unavailable"
                else:
                    canonical = "source_pending"
            elif verification.issue_code in (
                "pack_registry_unreachable",
                "github_rate_limited",
                "pack_release_manifest_invalid",
            ):
                canonical = "error"
            elif verification.absent:
                canonical = "not_installed"
            else:
                canonical = "error"
            phase = None
            progress = None
            eta = None
            operation_id = None
            stage = None

        if (
            definition.installer == "asset_pack"
            and not verification.healthy
            and isinstance(old, dict)
            and old.get("status") == "ready"
        ):
            _record_pack_attempt_cleanup(state, definition.id)

        from .component_kinds import KIND_CREDENTIAL, component_kind

        kind = component_kind(definition)
        last_verified = utc_now() if verification.healthy else old.get("last_verified_at")
        path_selector = (
            path_selector_mode(definition.id)
            if definition.installer in ("path_link", "asset_pack")
            else None
        )
        installed_bytes = _reported_installed_bytes(definition, verification)
        download_bytes = int(
            pack_fields.get("expected_download_bytes") or definition.download_bytes
        )
        # Credentials are not downloadable software — never advertise download/install sizes.
        if kind == KIND_CREDENTIAL:
            download_bytes = 0
            installed_bytes = 0
            if verification.issue_code == "credential_missing":
                canonical = "not_installed"
            elif verification.issue_code == "credential_unverified":
                canonical = "error"
        source_state = pack_fields.get("source_state")
        item = {
            "component_id": definition.id,
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "category": getattr(definition, "category", "Core"),
            "required": definition.required,
            "status": canonical,
            "operation_phase": phase,
            "operation_id": operation_id,
            "stage": stage,
            "installed_version": verification.version,
            "available_version": old.get("available_version"),
            "installation_path": verification.path,
            "path": verification.path,
            "last_verified_at": last_verified,
            "progress": progress,
            "estimated_remaining_seconds": eta,
            "diagnostic": diagnostic,
            "issue_code": diagnostic.get("issue_code") if diagnostic else None,
            "issue_summary": diagnostic.get("summary") if diagnostic else None,
            "primary_action": _primary_action(
                canonical,
                diagnostic,
                source_valid=source_valid if isinstance(source_valid, bool) else None,
                kind=kind,
                source_state=str(source_state) if source_state else None,
            ),
            "download_bytes": download_bytes,
            "installed_bytes": installed_bytes,
            "estimated_installed_bytes": 0 if kind == KIND_CREDENTIAL else definition.installed_bytes,
            "disk_bytes": {
                "download": download_bytes,
                "installed": installed_bytes,
                "estimated_installed": 0 if kind == KIND_CREDENTIAL else definition.installed_bytes,
            },
            "dependencies": list(definition.dependencies),
            "installer": definition.installer,
            "install_kind": definition.installer,
            "component_kind": kind,
            "path_selector": path_selector,
            "verifier": definition.verifier,
            "show_download_sizes": kind != KIND_CREDENTIAL,
            **pack_fields,
        }
        # Install must stay disabled when no download source exists.
        if canonical in ("download_unavailable", "source_pending") and not pack_fields.get("source_available"):
            item["install_disabled"] = True
        elif pack_fields.get("source_available") and canonical in (
            "not_installed",
            "error",
            "update_available",
        ):
            item["install_disabled"] = False
        components.append(item)
        previous_status[definition.id] = {
            "status": canonical,
            "installed_version": verification.version,
            "available_version": old.get("available_version"),
            "installation_path": verification.path,
            "last_verified_at": last_verified,
            "diagnostic": diagnostic,
        }

    required = [item for item in components if item["required"]]
    if any(item["status"] == "error" for item in required):
        overall = "needs_attention"
        overall_label = "Needs Attention"
    elif any(item["status"] in ("installing", "checking") for item in required):
        overall = "preparing"
        overall_label = "Preparing Studio"
    elif any(
        item["status"] in ("unknown", "not_installed", "download_unavailable", "source_pending")
        for item in required
    ):
        overall = "additional_setup_required"
        overall_label = "Additional Setup Required"
    else:
        overall = "ready"
        overall_label = "Ready to Generate"

    state["status"] = previous_status
    if persist:
        update_state(lambda latest: latest.__setitem__("status", previous_status))
    counts = {
        "ready": sum(item["status"] == "ready" for item in components),
        "not_installed": sum(
            item["status"] in ("not_installed", "download_unavailable") for item in components
        ),
        "needs_attention": sum(item["status"] == "error" for item in components),
        "update_available": sum(item["status"] == "update_available" for item in components),
        "download_unavailable": sum(
            item["status"] == "download_unavailable" for item in components
        ),
    }
    return {
        "schema_version": 2,
        "overall_status": overall,
        "overall_label": overall_label,
        "counts": counts,
        "components": components,
        "active_operation": registry.active_global(),
        "primary_action": (
            {"action": "prepare", "label": "Prepare My Studio"}
            if overall != "ready" else None
        ),
        "checked_at": utc_now(),
    }
