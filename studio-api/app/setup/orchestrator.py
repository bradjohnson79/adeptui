from __future__ import annotations

import logging
import shutil
import threading
import traceback
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..config import settings
from .catalog import COMPONENTS, get_component
from .diagnostics import diagnose, invalidate_verify_cache, verify_component
from .operations import registry
from .paths import browse_path, path_selector_mode, suggested_install_path
from .state import load_state, update_state
from .status import build_status

logger = logging.getLogger(__name__)

_CONTEXTS: dict[str, dict[str, Any]] = {}
_CONTEXT_LOCK = threading.RLock()


def get_setup_status() -> dict[str, Any]:
    return build_status()


def diagnose_component(component_id: str) -> dict[str, Any]:
    result = diagnose(component_id)
    component = get_component(component_id)
    if component.installer == "asset_pack":
        from .pack_install import directory_byte_size, staging_root
        from .pack_manifests import get_pack_manifest, public_source_host

        manifest = get_pack_manifest(component_id)
        state = load_state()
        location = (state.get("model_locations") or {}).get(component_id)
        url = manifest.source_url()
        result["technical_details"] = list(result.get("technical_details") or [])
        result["technical_details"].extend(
            [
                f"Pack ID: {manifest.id}",
                f"Manifest version: {manifest.version}",
                f"Source type: {manifest.source.type}",
                f"Source valid: {manifest.has_valid_source()}",
                f"Source host: {public_source_host(url) or 'none'}",
                f"Destination path: {location or suggested_install_path(component_id)}",
                f"Staging root: {staging_root(component_id, '<operation-id>', destination=location or suggested_install_path(component_id))}",
                f"Actual installed bytes: {directory_byte_size(Path(location)) if location else 0}",
                f"Required files: {', '.join(manifest.install.required_files) or 'none'}",
            ]
        )
        github_diag = (state.get("pack_source_meta") or {}).get(component_id) or {}
        for key in (
            "github_owner",
            "repository",
            "release_api_url",
            "repo_found",
            "releases_found",
            "draft_count",
            "prerelease_count",
            "selected_release_tag",
            "available_asset_names",
            "expected_asset_pattern",
            "selection_reason",
        ):
            if key in github_diag and github_diag[key] is not None:
                result["technical_details"].append(f"{key}: {github_diag[key]}")
        attempts = (state.get("pack_install_attempts") or {}).get(component_id) or []
        if attempts:
            last = attempts[-1]
            result["technical_details"].extend(
                [
                    f"Last operation phase: {last.get('status')}",
                    f"Last error code: {last.get('errorCode') or last.get('error_code') or 'none'}",
                    f"Last error message: {last.get('errorMessage') or last.get('error_message') or 'none'}",
                ]
            )

    def persist_diagnostic(state: dict[str, Any]) -> None:
        status = state.setdefault("status", {}).setdefault(component_id, {})
        status["diagnostic"] = deepcopy(result)

    update_state(persist_diagnostic)
    return result


def _link_existing_checkpoint(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    return {
        "type": "path",
        "component_id": component_id,
        "summary": (
            f"Choose a folder that already contains {component.name}. "
            "A valid pack.json manifest is required."
        ),
        "required_fields": ["path"],
        "requires_user_interaction": True,
        "suggested_path": suggested_install_path(component_id),
        "path_selector": "directory",
        "field_label": "Existing pack folder",
        "title": "Link Existing Folder",
        "action": "link_existing",
        "action_label": "Link Folder",
        "workflow": "link_existing",
    }


def _install_destination_checkpoint(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    return {
        "type": "path",
        "component_id": component_id,
        "summary": (
            f"Choose an empty folder or create a new folder for {component.name}. "
            "Adept UI will download and install the required files."
        ),
        "required_fields": ["path"],
        "requires_user_interaction": True,
        "suggested_path": suggested_install_path(component_id),
        "path_selector": "directory",
        "field_label": "Install location",
        "title": "Choose Install Location",
        "action": "choose_install_location",
        "action_label": "Download and Install",
        "workflow": "download_install",
    }


def _checkpoint_for(component_id: str, recommendation: str) -> dict[str, Any]:
    component = get_component(component_id)
    if component.installer == "asset_pack":
        if recommendation in ("link_existing", "correct_path"):
            return _link_existing_checkpoint(component_id)
        if recommendation in (
            "install",
            "update",
            "repair",
            "reinstall",
            "choose_install_location",
            "configure",
            "none",
        ):
            return _install_destination_checkpoint(component_id)
        return _install_destination_checkpoint(component_id)

    extra: dict[str, Any] = {}
    if recommendation in ("correct_path", "configure") or component.installer == "path_link":
        kind = (
            "model_path"
            if component.id in ("ltx_checkpoint", "wan_models", "zimage_models")
            else "path"
        )
        selector = path_selector_mode(component_id)
        noun = "file" if selector == "file" else "folder"
        if component.verifier == "linked_files":
            summary = (
                f"Select a {noun} that already contains {component.name} files."
            )
        else:
            summary = f"Choose the existing {component.name} {noun}."
        fields = ["path"]
        extra = {
            "suggested_path": suggested_install_path(component_id),
            "path_selector": selector,
            "field_label": "Installation path",
            "title": "Setup Needs Your Input",
            **(
                {"requires_license_acceptance": True, "license": "Model-specific"}
                if kind == "model_path"
                else {}
            ),
        }
        if kind == "model_path":
            fields.append("license_accepted")
    elif component.installer == "credentials":
        kind = "credentials"
        summary = f"Configure {component.name} in the secure credentials screen."
        fields = []
    elif component.installer == "m210b_qwen_voice":
        kind = "qwen_voice_install"
        summary = (
            f"Install {component.name} from the official Hugging Face repository "
            "(isolated venv + multi-GB weights). Progress appears in Source Manager Active Downloads."
        )
        fields = []
        extra = {
            "estimated_download_bytes": component.download_bytes,
            "official_source_only": True,
            "may_require_elevation": False,
        }
    elif component.installer == "index_tts2":
        kind = "index_tts2_install"
        summary = (
            f"Install {component.name} from the official pinned IndexTTS repository into an isolated runtime. "
            "Repo clone + dedicated venv are prepared first; model download can remain deferred until explicitly requested."
        )
        fields = []
        extra = {
            "estimated_download_bytes": component.download_bytes,
            "official_source_only": True,
            "may_require_elevation": False,
            "pinned_revision": "13495845e3028f0bb6ca1462ad22aa0e76349e40",
        }
    elif component.installer == "realesrgan_ncnn":
        kind = "realesrgan_ncnn_install"
        summary = (
            "Install MAGI GPU Upscaling (Real-ESRGAN) from the pinned official Windows portable package. "
            "Reuses an existing valid install on the second click."
        )
        fields = []
        extra = {
            "estimated_download_bytes": component.download_bytes,
            "official_source_only": True,
            "may_require_elevation": False,
            "pinned_version": "v0.2.5.0-20220424",
        }
    elif component.installer == "stills_perception_hf":
        kind = "stills_perception_hf_install"
        summary = (
            f"Install {component.name} from the pinned Hugging Face snapshot "
            "(isolated stills-perception directory). Optional Testing component — "
            "Prepare My Studio will not force this download."
        )
        fields = []
        extra = {
            "estimated_download_bytes": component.download_bytes,
            "official_source_only": True,
            "may_require_elevation": False,
            "independent_install": True,
        }
    elif component.installer == "huggingface_snapshot":
        if component.id in ("videochat3_4b", "internvideo3_8b"):
            kind = "video_understanding_hf_install"
            summary = (
                f"Install {component.name} from the pinned Hugging Face snapshot "
                "(isolated video-understanding directory, reused if already present). "
                "Progress appears in Source Manager Active Downloads."
            )
        else:
            kind = "hunyuan_hf_install"
            summary = (
                f"Install {component.name} from the official Tencent Hugging Face repository "
                "(isolated model directory, resume-safe). Each Hunyuan model installs independently — "
                "this never overwrites the other. Progress appears in Source Manager Active Downloads."
            )
        fields = []
        extra = {
            "estimated_download_bytes": component.download_bytes,
            "official_source_only": True,
            "may_require_elevation": False,
            "independent_install": True,
        }
    else:
        kind = "manual_installer"
        summary = (
            f"{component.name} does not have a supported unattended installer. "
            "Install it manually, then continue to verify."
        )
        fields = []
        extra = {"may_require_elevation": True}
    return {
        "type": kind,
        "component_id": component_id,
        "summary": summary,
        "required_fields": fields,
        "requires_user_interaction": True,
        **extra,
    }


def get_prepare_plan() -> dict[str, Any]:
    status = build_status()
    by_id = {item["component_id"]: item for item in status["components"]}
    actions: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    required_disk = 0
    for component in COMPONENTS:
        if not component.required:
            continue
        current = by_id[component.id]
        if current["status"] in ("ready", "update_available"):
            continue
        diagnostic = diagnose(component.id)
        recommendation = diagnostic["recommendation"]
        action = {
            "component_id": component.id,
            "action": recommendation if recommendation != "none" else "verify",
            "phase": "configuring" if component.installer == "path_link" else "installing",
            "description": diagnostic["summary"],
            "download_bytes": component.download_bytes,
            "dependencies": list(component.dependencies),
        }
        actions.append(action)
        required_disk += component.download_bytes
        if diagnostic["requires_user_interaction"] or component.installer != "detect_only":
            checkpoints.append(_checkpoint_for(component.id, recommendation))

    try:
        available_disk = shutil.disk_usage(settings.data_dir).free
    except OSError:
        available_disk = None
    if available_disk is not None and required_disk > available_disk:
        checkpoints.insert(
            0,
            {
                "type": "disk_space",
                "component_id": None,
                "summary": "Free additional disk space before continuing.",
                "required_bytes": required_disk,
                "available_bytes": available_disk,
                "requires_user_interaction": True,
            },
        )
    return {
        "required_actions": actions,
        "skipped_optional_component_ids": [item.id for item in COMPONENTS if not item.required],
        "required_disk_bytes": required_disk,
        "available_disk_bytes": available_disk,
        "user_checkpoints": checkpoints,
        "can_run_unattended": not checkpoints,
    }


def _persist_install_destination(component_id: str, value: str) -> str:
    from .pack_install import PackInstallError, validate_install_destination

    try:
        validated = validate_install_destination(component_id, value)
    except PackInstallError as exc:
        raise ValueError(exc.message) from exc
    destination = validated["destination"]
    update_state(
        lambda state: state.setdefault("model_locations", {}).__setitem__(
            component_id, destination
        )
    )
    invalidate_verify_cache(component_id)
    return destination


def _persist_link_existing(component_id: str, value: str) -> str:
    from .pack_install import PackInstallError, link_existing_pack

    try:
        linked = link_existing_pack(component_id, value)
    except PackInstallError as exc:
        raise ValueError(exc.message) from exc
    update_state(
        lambda state: state.setdefault("model_locations", {}).__setitem__(
            component_id, linked["destination"]
        )
    )
    invalidate_verify_cache(component_id)
    return linked["destination"]


def _persist_path(component_id: str, value: str, *, workflow: str | None = None) -> None:
    from .paths import ensure_path_exists, path_selector_mode

    component = get_component(component_id)
    path = Path(value).expanduser()
    mode = path_selector_mode(component_id)

    if component.installer == "asset_pack":
        if workflow == "link_existing":
            _persist_link_existing(component_id, str(path))
        else:
            _persist_install_destination(component_id, str(path))
        return

    if mode == "directory":
        path = ensure_path_exists(path, mode=mode)
    elif not path.exists():
        ensure_path_exists(path, mode=mode)
        raise ValueError(f"Path not found: {value}")
    update_state(
        lambda state: state.setdefault("model_locations", {}).__setitem__(
            component_id, str(path)
        )
    )
    invalidate_verify_cache(component_id)
    if (
        component.verifier == "linked_files"
        and path.is_dir()
        and not any(path.iterdir())
    ):
        raise ValueError(
            f"The {component.name} folder is empty. "
            "Copy pack assets into this folder, or browse to a folder that already contains them."
        )


def _record_pack_attempt(component_id: str, attempt: dict[str, Any]) -> None:
    def mutate(state: dict[str, Any]) -> None:
        history = state.setdefault("pack_install_attempts", {}).setdefault(component_id, [])
        history.append(attempt)
        del history[:-20]
        state.setdefault("pack_installs", {})[component_id] = attempt

    update_state(mutate)


def _run_asset_pack_install(operation_id: str, component_id: str, action: dict[str, Any]) -> None:
    from .diagnostics import utc_now
    from .pack_install import PackInstallError, install_asset_pack
    from .pack_manifests import get_pack_manifest

    manifest = get_pack_manifest(component_id)
    started = utc_now()
    downloaded = 0
    installed = 0
    destination = action.get("destination") or (load_state().get("model_locations") or {}).get(
        component_id
    )

    def on_progress(phase: str, percent: float, done: int, total: int | None) -> None:
        nonlocal downloaded
        downloaded = done
        registry.update(
            operation_id,
            status="running",
            phase=phase,
            progress=percent,
            stage={
                "validating": "Validating download source",
                "downloading": f"Downloading {done:,} bytes",
                "verifying_download": "Verifying downloaded files",
                "extracting": "Extracting pack archive",
                "verifying_install": "Verifying required pack files",
                "completed": "Install complete",
            }.get(phase, phase),
            downloaded_bytes=done,
            total_bytes=total,
        )

    try:
        if not manifest.has_valid_source():
            raise PackInstallError(
                "download_source_missing",
                "This pack does not currently have a valid download source.",
            )
        result = install_asset_pack(
            component_id,
            operation_id,
            destination=destination,
            on_progress=on_progress,
        )
        downloaded = int(result["downloaded_bytes"])
        installed = int(result["installed_bytes"])
        update_state(
            lambda state: state.setdefault("model_locations", {}).__setitem__(
                component_id, result["destination"]
            )
        )
        invalidate_verify_cache(component_id)
        verified = verify_component(component_id)
        if not verified.healthy:
            raise PackInstallError(
                "required_files_missing",
                "Pack files were written but failed final verification.",
            )
        _record_pack_attempt(
            component_id,
            {
                "operationId": operation_id,
                "packId": component_id,
                "startedAt": started,
                "completedAt": utc_now(),
                "status": "completed",
                "sourceVersion": manifest.version,
                "downloadedBytes": downloaded,
                "installedBytes": installed,
            },
        )
    except PackInstallError as exc:
        _record_pack_attempt(
            component_id,
            {
                "operationId": operation_id,
                "packId": component_id,
                "startedAt": started,
                "completedAt": utc_now(),
                "status": "failed",
                "sourceVersion": manifest.version,
                "downloadedBytes": downloaded,
                "installedBytes": installed,
                "errorCode": exc.code,
                "errorMessage": exc.message,
            },
        )
        raise
    except Exception as exc:
        logger.exception(
            "Unexpected pack install failure operation=%s component=%s",
            operation_id,
            component_id,
        )
        _record_pack_attempt(
            component_id,
            {
                "operationId": operation_id,
                "packId": component_id,
                "startedAt": started,
                "completedAt": utc_now(),
                "status": "failed",
                "sourceVersion": manifest.version,
                "downloadedBytes": downloaded,
                "installedBytes": installed,
                "errorCode": "unexpected_error",
                "errorMessage": str(exc)[:500],
            },
        )
        raise PackInstallError("unexpected_error", f"Pack installation failed: {exc}") from exc


def _fail_component(
    failures: list[dict[str, Any]],
    component_id: str,
    *,
    issue_code: str,
    error: str,
    recommendation: str = "install",
) -> None:
    failures.append(
        {
            "component_id": component_id,
            "issue_code": issue_code,
            "error": error,
            "recommendation": recommendation,
        }
    )


def _run_context(operation_id: str) -> None:
    with _CONTEXT_LOCK:
        context = _CONTEXTS.get(operation_id)
        if context is None:
            logger.error("No setup context for operation %s", operation_id)
            try:
                registry.finish(operation_id, error="Setup context was lost. Retry the operation.")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to finish orphaned operation %s", operation_id)
            return
    actions = context["actions"]
    failures = context["failures"]
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        (settings.data_dir / "models").mkdir(parents=True, exist_ok=True)
        registry.update(operation_id, status="running", stage="Checking required components")

        while context["index"] < len(actions):
            action = actions[context["index"]]
            component_id = action["component_id"]
            component = get_component(component_id)
            failed_ids = {item["component_id"] for item in failures}
            blocked_by = [dependency for dependency in component.dependencies if dependency in failed_ids]
            if blocked_by:
                failures.append(
                    {
                        "component_id": component_id,
                        "issue_code": "dependency_failed",
                        "dependencies": blocked_by,
                        "recommendation": "manual_help",
                    }
                )
                context["index"] += 1
                continue
            progress = context["index"] / max(1, len(actions))
            registry.update(
                operation_id,
                phase=action.get("phase", "installing"),
                progress=progress,
                stage=f"Preparing {component.name}",
            )
            registry.log(operation_id, f"Checking {component.name}.")

            response = context.pop("response", None)
            if response is not None:
                if response.get("cancelled") or response.get("accepted") is False:
                    failures.append({"component_id": component_id, "error": "Checkpoint declined."})
                    context["index"] += 1
                    continue
                path = str(response.get("path") or "").strip()
                action_kind = str(action.get("action") or "")
                workflow = (
                    "link_existing"
                    if action_kind == "link_existing"
                    else "download_install"
                )

                if component.installer == "asset_pack" and path:
                    try:
                        if workflow == "link_existing":
                            _persist_link_existing(component_id, path)
                        else:
                            destination = _persist_install_destination(component_id, path)
                            action["destination"] = destination
                    except ValueError as exc:
                        checkpoint = (
                            _link_existing_checkpoint(component_id)
                            if workflow == "link_existing"
                            else _install_destination_checkpoint(component_id)
                        )
                        # Surface validation errors in `message` — FE prefers message over summary.
                        registry.pause(
                            operation_id,
                            {**checkpoint, "message": str(exc), "summary": str(exc)},
                        )
                        return

                    if workflow == "link_existing":
                        registry.update(
                            operation_id, phase="verifying", stage=f"Verifying {component.name}"
                        )
                        verified = verify_component(component_id)
                        if not verified.healthy:
                            diagnostic = diagnose_component(component_id)
                            _fail_component(
                                failures,
                                component_id,
                                issue_code=diagnostic["issue_code"] or "verify_failed",
                                error=diagnostic["summary"],
                                recommendation=diagnostic.get("recommendation") or "link_existing",
                            )
                        context["index"] += 1
                        continue

                    if action_kind == "choose_install_location":
                        # Destination only — do not download in this workflow.
                        context["index"] += 1
                        continue

                    # Download/install after destination chosen.
                    try:
                        from .pack_manifests import get_pack_manifest

                        manifest = get_pack_manifest(component_id)
                        if not manifest.has_valid_source():
                            _fail_component(
                                failures,
                                component_id,
                                issue_code="download_source_missing",
                                error="This pack does not currently have a valid download source.",
                                recommendation="refresh_source",
                            )
                        else:
                            _run_asset_pack_install(operation_id, component_id, action)
                    except Exception as exc:  # noqa: BLE001 — never kill API for pack failures
                        from .pack_install import PackInstallError

                        if isinstance(exc, PackInstallError):
                            _fail_component(
                                failures,
                                component_id,
                                issue_code=exc.code,
                                error=exc.message,
                                recommendation="install" if exc.recoverable else "manual_help",
                            )
                        else:
                            logger.exception(
                                "Pack install crashed operation=%s component=%s\n%s",
                                operation_id,
                                component_id,
                                traceback.format_exc(),
                            )
                            _fail_component(
                                failures,
                                component_id,
                                issue_code="unexpected_error",
                                error=str(exc)[:500],
                                recommendation="install",
                            )
                        # Persist failure state immediately.
                        registry.update(
                            operation_id,
                            status="running",
                            phase="failed",
                            stage=str(exc)[:200],
                            error=str(exc)[:500],
                        )
                    context["index"] += 1
                    continue

                # Non-pack path bind
                if path:
                    try:
                        _persist_path(component_id, path, workflow=workflow)
                    except ValueError as exc:
                        registry.pause(
                            operation_id,
                            {
                                **_checkpoint_for(component_id, action_kind),
                                "summary": str(exc),
                            },
                        )
                        return

                registry.update(
                    operation_id, phase="verifying", stage=f"Verifying {component.name}"
                )
                verified = verify_component(component_id)
                if not verified.healthy:
                    diagnostic = diagnose_component(component_id)
                    failures.append(
                        {
                            "component_id": component_id,
                            "issue_code": diagnostic["issue_code"],
                            "recommendation": diagnostic["recommendation"],
                            "error": diagnostic["summary"],
                        }
                    )
                context["index"] += 1
                continue

            verified = verify_component(component_id)
            if verified.healthy and action.get("action") not in (
                "choose_install_location",
                "update",
                "reinstall",
            ):
                context["index"] += 1
                continue

            # Asset pack: Download and Install — choose destination first (empty OK).
            if component.installer == "asset_pack" and action.get("action") in (
                "install",
                "update",
                "repair",
                "reinstall",
                "choose_install_location",
            ):
                from .pack_install import PackInstallError
                from .pack_manifests import get_pack_manifest

                if not action.get("destination"):
                    registry.pause(operation_id, _install_destination_checkpoint(component_id))
                    return

                if action.get("action") == "choose_install_location":
                    # Path-only action: destination already set via response path above.
                    context["index"] += 1
                    continue

                manifest = get_pack_manifest(component_id)
                if not manifest.has_valid_source():
                    _fail_component(
                        failures,
                        component_id,
                        issue_code="download_source_missing",
                        error="This pack does not currently have a valid download source.",
                        recommendation="refresh_source",
                    )
                    context["index"] += 1
                    continue
                try:
                    _run_asset_pack_install(operation_id, component_id, action)
                except PackInstallError as exc:
                    _fail_component(
                        failures,
                        component_id,
                        issue_code=exc.code,
                        error=exc.message,
                        recommendation="install" if exc.recoverable else "manual_help",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Pack install crashed operation=%s component=%s\n%s",
                        operation_id,
                        component_id,
                        traceback.format_exc(),
                    )
                    _fail_component(
                        failures,
                        component_id,
                        issue_code="unexpected_error",
                        error=str(exc)[:500],
                        recommendation="install",
                    )
                context["index"] += 1
                continue

            if component.installer == "asset_pack" and action.get("action") == "link_existing":
                registry.pause(operation_id, _link_existing_checkpoint(component_id))
                return

            registry.pause(operation_id, _checkpoint_for(component_id, action["action"]))
            return

        registry.update(
            operation_id,
            status="finalizing",
            phase="verifying",
            stage="Verifying studio",
            progress=0.95,
        )
        final_status = build_status()
        result = {
            "ready": final_status["overall_status"] == "ready" and not failures,
            "overall_status": final_status["overall_status"],
            "failures": failures,
        }
        finish_error = None
        if failures:
            first = failures[0]
            finish_error = str(
                first.get("error")
                or first.get("issue_code")
                or "One or more components failed verification."
            )
        registry.finish(operation_id, result=result, error=finish_error)
        with _CONTEXT_LOCK:
            _CONTEXTS.pop(operation_id, None)
    except Exception as exc:
        logger.exception(
            "Setup operation %s failed unexpectedly\n%s",
            operation_id,
            traceback.format_exc(),
        )
        try:
            registry.finish(operation_id, error=str(exc)[:500])
        except Exception:  # noqa: BLE001
            logger.exception("Failed to persist setup operation failure %s", operation_id)
        with _CONTEXT_LOCK:
            _CONTEXTS.pop(operation_id, None)


def _start_context(
    kind: str,
    actions: list[dict[str, Any]],
    *,
    global_operation: bool,
    initial_checkpoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    operation = registry.create(
        kind, [item["component_id"] for item in actions], global_operation=global_operation
    )
    with _CONTEXT_LOCK:
        _CONTEXTS[operation["operation_id"]] = {
            "actions": deepcopy(actions),
            "index": 0,
            "failures": [],
            "preflight": bool(initial_checkpoint),
        }
    if initial_checkpoint:
        return registry.pause(operation["operation_id"], initial_checkpoint)
    threading.Thread(
        target=_run_context,
        args=(operation["operation_id"],),
        name=f"setup-{operation['operation_id'][:8]}",
        daemon=True,
    ).start()
    return registry.snapshot(operation["operation_id"])


def start_prepare() -> dict[str, Any]:
    plan = get_prepare_plan()
    disk_checkpoint = next(
        (item for item in plan["user_checkpoints"] if item.get("type") == "disk_space"),
        None,
    )
    return _start_context(
        "prepare",
        plan["required_actions"],
        global_operation=True,
        initial_checkpoint=disk_checkpoint,
    )


def get_operation(operation_id: str) -> dict[str, Any]:
    return registry.snapshot(operation_id)


def respond_to_checkpoint(operation_id: str, response: dict[str, Any]) -> dict[str, Any]:
    pending = registry.snapshot(operation_id).get("checkpoint") or {}
    cancelled = bool(response.get("cancelled") or response.get("accepted") is False)
    if cancelled:
        registry.respond(operation_id, {**response, "cancelled": True})
        with _CONTEXT_LOCK:
            _CONTEXTS.pop(operation_id, None)
        return registry.cancel(operation_id, reason="Cancelled by user")

    missing_fields = [
        field
        for field in pending.get("required_fields", [])
        if (
            response.get(field) is not True
            if field.endswith("_accepted")
            else not str(response.get(field) or "").strip()
        )
    ]
    if missing_fields:
        raise ValueError(f"Checkpoint response requires: {', '.join(missing_fields)}")
    registry.respond(operation_id, response)
    with _CONTEXT_LOCK:
        if operation_id not in _CONTEXTS:
            raise KeyError(f"Operation {operation_id} cannot be resumed.")
        context = _CONTEXTS[operation_id]
        if context.pop("preflight", False):
            pass
        else:
            context["response"] = dict(response)
    threading.Thread(
        target=_run_context,
        args=(operation_id,),
        name=f"setup-resume-{operation_id[:8]}",
        daemon=True,
    ).start()
    return registry.snapshot(operation_id)


def browse_setup_path(
    *,
    mode: str = "directory",
    start_dir: str | None = None,
    title: str | None = None,
    component_id: str | None = None,
    forced_path: str | None = None,
) -> dict[str, Any]:
    import os

    selector: str = mode
    start = start_dir
    dialog_title = title
    if component_id:
        component = get_component(component_id)
        selector = path_selector_mode(component_id)
        start = start or suggested_install_path(component_id)
        dialog_title = dialog_title or f"Select {component.name}"
    if selector not in ("directory", "file"):
        raise ValueError("Browse mode must be 'directory' or 'file'.")
    # E2E automation: skip native OS dialogs when STUDIO_E2E=1 and a path is supplied.
    if os.environ.get("STUDIO_E2E", "").strip() in ("1", "true", "TRUE", "yes", "YES"):
        candidate = (forced_path or "").strip()
        if candidate:
            return {"path": candidate, "cancelled": False, "e2e_forced": True}
    return browse_path(mode=selector, start_dir=start, title=dialog_title)


def _enqueue_qwen_voice_install(component_id: str) -> dict[str, Any]:
    """Product path: queue HF+venv install via Source Manager download executor."""
    from ..codirector.m210b.qwen_voice_install import COMPONENT_SPECS, scaffold
    from ..source_manager.downloads.models import create_install_plan
    from ..source_manager.downloads.queue import get_queue_manager

    if component_id not in COMPONENT_SPECS:
        raise ValueError(f"Not a Qwen voice component: {component_id}")
    spec = COMPONENT_SPECS[component_id]
    sandbox = scaffold(component_id)
    plan = create_install_plan(
        component_id=component_id,
        source_id=spec["sourceKey"],
        provider_id="huggingface_snapshot",
        artifacts=[
            {
                "remotePath": spec["sourceKey"],
                "destinationRelativePath": "models",
                "downloadUrl": f"https://huggingface.co/{spec['sourceKey']}",
            }
        ],
        destination_root=str(sandbox),
        estimated_download_bytes=3_500_000_000,
        estimated_extracted_bytes=3_500_000_000,
        metadata={
            "componentId": component_id,
            "registryId": spec["registryId"],
            "sourceKey": spec["sourceKey"],
            "officialOnly": True,
        },
    )
    op = get_queue_manager().enqueue(plan, priority=50)
    operation = registry.create("component_action", [component_id])
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": True,
            "downloadOperationId": op.get("id"),
            "message": (
                f"{component_id} install queued (venv + official HF weights). "
                "Track progress in Source Manager Active Downloads."
            ),
            "operation": op,
        },
    )


def _enqueue_video_understanding_install(component_id: str) -> dict[str, Any]:
    from ..codirector.video_intelligence.paths import (
        INTERNVIDEO3_HF_ID,
        INTERNVIDEO3_MARKERS,
        VIDEOCHAT3_HF_ID,
        VIDEOCHAT3_MARKERS,
        internvideo3_dir,
        model_present,
        videochat3_dir,
    )
    from ..source_manager.downloads.models import create_install_plan
    from ..source_manager.downloads.queue import get_queue_manager

    dest = videochat3_dir() if component_id == "videochat3_4b" else internvideo3_dir()
    markers = VIDEOCHAT3_MARKERS if component_id == "videochat3_4b" else INTERNVIDEO3_MARKERS
    if model_present(dest, markers):
        operation = registry.create("component_action", [component_id])
        return registry.finish(
            operation["operation_id"],
            result={
                "component_id": component_id,
                "queued": False,
                "reused": True,
                "message": "Existing video-understanding weights reused.",
                "localDir": str(dest),
            },
        )

    repo = VIDEOCHAT3_HF_ID if component_id == "videochat3_4b" else INTERNVIDEO3_HF_ID
    plan = create_install_plan(
        component_id=component_id,
        source_id=repo,
        provider_id="huggingface_snapshot",
        artifacts=[
            {
                "remotePath": repo,
                "destinationRelativePath": ".",
                "downloadUrl": f"https://huggingface.co/{repo}",
            }
        ],
        destination_root=str(dest),
        estimated_download_bytes=get_component(component_id).download_bytes,
        estimated_extracted_bytes=get_component(component_id).installed_bytes,
        metadata={"componentId": component_id, "officialOnly": True, "videoUnderstanding": True},
    )
    op = get_queue_manager().enqueue(plan, priority=45)
    operation = registry.create("component_action", [component_id])
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": True,
            "downloadOperationId": op.get("id"),
            "message": (
                f"{component_id} install queued from the pinned Hugging Face snapshot. "
                "Track progress in Source Manager Active Downloads."
            ),
            "operation": op,
        },
    )


def _enqueue_stills_perception_install(component_id: str) -> dict[str, Any]:
    from ..codirector.perception.paths import COMPONENT_SPECS, model_present
    from ..source_manager.downloads.models import create_install_plan
    from ..source_manager.downloads.queue import get_queue_manager

    spec = COMPONENT_SPECS[component_id]
    dest_fn = spec["dest"]
    dest = dest_fn() if callable(dest_fn) else dest_fn
    markers = tuple(spec["markers"])
    if model_present(dest, markers):
        operation = registry.create("component_action", [component_id])
        return registry.finish(
            operation["operation_id"],
            result={
                "component_id": component_id,
                "queued": False,
                "reused": True,
                "message": "Existing stills-perception weights reused.",
                "localDir": str(dest),
            },
        )
    repo = str(spec["repo"])
    plan = create_install_plan(
        component_id=component_id,
        source_id=repo,
        provider_id="stills_perception_hf",
        artifacts=[
            {
                "remotePath": repo,
                "destinationRelativePath": ".",
                "downloadUrl": f"https://huggingface.co/{repo}",
            }
        ],
        destination_root=str(dest),
        estimated_download_bytes=get_component(component_id).download_bytes,
        estimated_extracted_bytes=get_component(component_id).installed_bytes,
        metadata={"componentId": component_id, "officialOnly": True, "stillsPerception": True},
    )
    op = get_queue_manager().enqueue(plan, priority=55)
    operation = registry.create("component_action", [component_id])
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": True,
            "downloadOperationId": op.get("id"),
            "message": f"{component_id} install queued into the isolated stills-perception directory.",
            "operation": op,
        },
    )


def _enqueue_hunyuan_install(component_id: str) -> dict[str, Any]:
    from ..video_runtime.hunyuan_install import enqueue_install

    op_wrap = enqueue_install(component_id)
    op = op_wrap.get("operation") or {}
    operation = registry.create("component_action", [component_id])
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": True,
            "downloadOperationId": op.get("id"),
            "providerId": op_wrap.get("providerId"),
            "message": (
                f"{component_id} install queued from official Tencent HF source. "
                "Track progress in Source Manager Active Downloads. "
                "The other Hunyuan model is not queued."
            ),
            "operation": op,
        },
    )


def _install_realesrgan_ncnn(component_id: str, *, force: bool = False) -> dict[str, Any]:
    from ..magi.realesrgan_runtime import install as install_realesrgan
    from ..magi.realesrgan_runtime import verify as verify_realesrgan

    result = verify_realesrgan(repair=force) if force else install_realesrgan(force=force)
    operation = registry.create("component_action", [component_id])
    if not result.get("ok") and not result.get("realesrganReady"):
        return registry.finish(
            operation["operation_id"],
            error=(result.get("error") or {}).get("code") or "realesrgan_install_failed",
            result={
                "component_id": component_id,
                "queued": False,
                "message": result.get("message") or "MAGI GPU Upscaling install failed.",
                "runtime": result,
            },
        )
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": False,
            "reused": bool(result.get("reused")),
            "message": result.get("message") or "MAGI GPU Upscaling ready.",
            "runtime": result,
        },
    )


def _install_index_tts2(component_id: str, *, force: bool = False) -> dict[str, Any]:
    from ..voice_performance.runtime import get_index_tts2_runtime

    runtime = get_index_tts2_runtime()
    result = runtime.install(confirm=True, confirm_download_models=False, force=force)
    operation = registry.create("component_action", [component_id])
    if not result.get("ok"):
        return registry.finish(
            operation["operation_id"],
            error=(result.get("error") or {}).get("code") or "index_tts2_install_failed",
            result={
                "component_id": component_id,
                "queued": False,
                "message": (result.get("error") or {}).get("message") or "IndexTTS2 install failed.",
                "runtime": result,
            },
        )
    return registry.finish(
        operation["operation_id"],
        result={
            "component_id": component_id,
            "queued": False,
            "message": result.get("message") or "IndexTTS2 runtime prepared.",
            "runtime": result,
        },
    )


def execute_recommended_action(component_id: str) -> dict[str, Any]:
    component = get_component(component_id)
    diagnostic = diagnose_component(component_id)
    action = diagnostic["recommendation"]

    if component.installer == "m210b_qwen_voice" and action in (
        "install",
        "repair",
        "reinstall",
        "update",
    ):
        return _enqueue_qwen_voice_install(component_id)

    if component.installer == "stills_perception_hf" and action in (
        "install",
        "repair",
        "reinstall",
        "update",
    ):
        return _enqueue_stills_perception_install(component_id)

    if component.installer == "huggingface_snapshot" and action in (
        "install",
        "repair",
        "reinstall",
        "update",
    ):
        if component_id in ("videochat3_4b", "internvideo3_8b"):
            return _enqueue_video_understanding_install(component_id)
        return _enqueue_hunyuan_install(component_id)

    if component.installer == "index_tts2" and action in (
        "install",
        "repair",
        "reinstall",
        "update",
    ):
        return _install_index_tts2(component_id, force=action in ("repair", "reinstall", "update"))

    if component.installer == "realesrgan_ncnn" and action in (
        "install",
        "repair",
        "reinstall",
        "update",
    ):
        return _install_realesrgan_ncnn(component_id, force=action in ("repair", "reinstall", "update"))

    if component.installer == "asset_pack":
        from .pack_manifests import get_pack_manifest
        from .pack_release_cache import get_cached_release

        manifest = get_pack_manifest(component_id)
        # Fail closed for install-like and missing-source recommendations — never queue
        # a download/install that cannot succeed and must not create destination folders.
        source_missing_for_action = not manifest.has_valid_source()
        if (
            action == "refresh_source"
            and manifest.uses_provider()
            and not get_cached_release(component_id)
            and not manifest.source_url()
            and not manifest.has_explicit_remote_source()
        ):
            # A status refresh must not be misrouted into an install worker when
            # provider discovery has not produced a usable release yet.
            source_missing_for_action = True
        if action in (
            "install",
            "none",
            "manual_help",
            "add_source_url",
            "refresh_source",
        ) and source_missing_for_action:
            code = (
                "source_not_published"
                if not manifest.is_published()
                else (
                    "pack_release_not_found"
                    if action == "refresh_source" and manifest.uses_provider()
                    else "pack_provider_not_configured"
                    if action in ("add_source_url", "refresh_source")
                    else "source_not_configured"
                )
            )
            if action == "refresh_source" and not manifest.is_published():
                code = "source_not_published"
            message = (
                "No official distribution has been published for this pack yet."
                if code == "source_not_published"
                else "No official source has been assigned to this component."
            )
            operation = registry.create("component_action", [component_id])
            return registry.finish(
                operation["operation_id"],
                error=code,
                result={
                    "component_id": component_id,
                    "issue_code": code,
                    "message": message,
                },
            )
        if action == "install" and manifest.uses_provider() and not get_cached_release(component_id) and not manifest.source_url():
            # Require Check Again discovery before Install unless a direct URL override exists.
            operation = registry.create("component_action", [component_id])
            return registry.finish(
                operation["operation_id"],
                error="pack_release_not_found",
                result={
                    "component_id": component_id,
                    "issue_code": "pack_release_not_found",
                    "message": "No published GitHub release was found for this pack. Use Check Again first.",
                },
            )
        if action == "install" and manifest.has_valid_source():
            # Clears stale errors by starting a fresh operation that pauses for install location.
            return _start_context(
                "component_action",
                [{
                    "component_id": component_id,
                    "action": "install",
                    "phase": "configuring",
                }],
                global_operation=False,
            )

    if action == "none":
        operation = registry.create("component_action", [component_id])
        return registry.finish(
            operation["operation_id"],
            result={"component_id": component_id, "verified": True},
        )
    return _start_context(
        "component_action",
        [{
            "component_id": component_id,
            "action": action,
            "phase": {
                "update": "updating",
                "repair": "repairing",
                "reinstall": "repairing",
                "correct_path": "configuring",
                "configure": "configuring",
                "link_existing": "configuring",
                "choose_install_location": "configuring",
            }.get(action, "installing"),
        }],
        global_operation=False,
    )


def start_link_existing_pack(component_id: str) -> dict[str, Any]:
    get_component(component_id)
    # Start the worker so it owns the pause/resume cycle. Using initial_checkpoint
    # would mark the pause as preflight and drop the path response on resume.
    return _start_context(
        "component_action",
        [{
            "component_id": component_id,
            "action": "link_existing",
            "phase": "configuring",
        }],
        global_operation=False,
    )


def start_choose_install_location(component_id: str) -> dict[str, Any]:
    """Prompt for a new install destination (empty folders accepted). Does not download alone."""
    get_component(component_id)
    return _start_context(
        "component_action",
        [{
            "component_id": component_id,
            "action": "choose_install_location",
            "phase": "configuring",
        }],
        global_operation=False,
    )


def refresh_component_source(component_id: str) -> dict[str, Any]:
    from .pack_manifests import is_asset_pack, refresh_pack_source

    if not is_asset_pack(component_id):
        raise KeyError(f"Component {component_id} does not support source refresh")
    result = refresh_pack_source(component_id, force_refresh=True)
    # Persist retrieval metadata only — never mark installed / create dirs / URLs / tokens.
    update_state(
        lambda state: state.setdefault("pack_source_meta", {}).__setitem__(
            component_id,
            {
                "version": result.get("available_version") or result.get("version"),
                "retrieved_at": result.get("retrieved_at"),
                "source_valid": result.get("source_valid"),
                "source_available": result.get("source_available"),
                "source_host": result.get("source_host"),
                "provider_id": result.get("provider_id"),
                "repository": result.get("repository"),
                "tag_name": result.get("tag_name"),
                "archive_asset_name": result.get("archive_asset_name"),
                "error": result.get("error"),
                "github_owner": result.get("github_owner"),
                "release_api_url": result.get("release_api_url"),
                "repo_found": result.get("repo_found"),
                "releases_found": result.get("releases_found"),
                "draft_count": result.get("draft_count"),
                "prerelease_count": result.get("prerelease_count"),
                "selected_release_tag": result.get("selected_release_tag"),
                "available_asset_names": result.get("available_asset_names"),
                "expected_asset_pattern": result.get("expected_asset_pattern"),
                "selection_reason": result.get("selection_reason"),
            },
        )
    )
    return result


def dismiss_update(component_id: str) -> dict[str, Any]:
    get_component(component_id)
    from .diagnostics import utc_now

    update_state(
        lambda state: state.setdefault("update_dismissals", {}).__setitem__(
            component_id, {"dismissed_at": utc_now()}
        )
    )
    return {"component_id": component_id, "dismissed": True}
