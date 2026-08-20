from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...avatar_runtimes import (
    benchmark_runtime as benchmark_avatar_runtime,
    install_runtime as install_avatar_runtime,
    is_avatar_runtime_component,
    preflight as avatar_runtime_preflight,
    verify_runtime as verify_avatar_runtime,
)
from ...config import settings
from ...setup.catalog import get_component
from ...setup.diagnostics import verify_component
from ...setup.operations import registry as setup_registry
from ...setup.paths import suggested_install_path
from ...setup.state import load_state
from ...source_manager.downloads.models import create_install_plan
from ...source_manager.downloads.queue import get_queue_manager
from ...source_manager.downloads.receipts import history_entries
from ...source_manager.persistence import get_assignment, get_source
from ...source_manager.registry import get_provider, select_provider
from ...source_manager.voice_models import COMPONENT_SPECS
from ...video_runtime.hunyuan_providers import OFFICIAL_SOURCES, PROVIDER_BY_COMPONENT, provider_dir
from ...voice_performance.runtime import get_index_tts2_runtime
from ..contracts import ArtifactQueryContext, SourceInput, VerificationContext
from .adapter import download_operation_to_install_job, setup_operation_to_install_job
from .errors import InstallJobError, InstallJobErrorCode, normalize_failure
from .heartbeat import (
    build_heartbeat,
    evaluate_stall,
    stall_label,
    stall_recovery_actions,
)
from .phases import build_phase_steps, overall_percent
from .schema import InstallJob, RecoveryAction
from .sources import save_source
from .states import InstallState
from . import events as install_events

_CUSTOM_LOCK = threading.RLock()
_CUSTOM_THREADS: dict[str, threading.Thread] = {}
_CUSTOM_THREAD_META: dict[str, dict[str, Any]] = {}
_INDEX_TTS2_STEP_TOTAL = 4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs_dir() -> Path:
    return Path(settings.data_dir) / "source_manager" / "install_jobs"


def _job_path(job_id: str) -> Path:
    return _jobs_dir() / f"{job_id}.json"


def _job_id(component_id: str) -> str:
    return f"ij_{component_id}_{uuid.uuid4().hex[:10]}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _job_from_payload(payload: dict[str, Any]) -> InstallJob:
    error = payload.get("error")
    if isinstance(error, dict):
        payload = {**payload, "error": InstallJobError.model_validate(error)}
    return InstallJob.model_validate(payload)


def _persist_job(job: InstallJob) -> InstallJob:
    enriched = _enrich_job(job)
    _write_json(_job_path(enriched.id), enriched.model_dump(mode="json", by_alias=True))
    install_events.publish_job(enriched)
    return enriched


def _worker_alive_for(job: InstallJob) -> bool:
    if job.kind == "custom_install":
        thread = _CUSTOM_THREADS.get(job.id)
        return bool(thread and thread.is_alive())
    if job.kind == "download_queue":
        return bool(job.active and not job.terminal)
    if job.kind == "comfy_extension":
        thread = _CUSTOM_THREADS.get(job.id)
        return bool(thread and thread.is_alive()) if thread is not None else bool(job.active)
    return bool(job.active and not job.terminal)


def _enrich_job(job: InstallJob, *, previous_phase: str | None = None) -> InstallJob:
    ready = job.state == InstallState.READY
    failed = job.state in {InstallState.FAILED, InstallState.REPAIR_REQUIRED, InstallState.CANCELLED}
    phase_steps = build_phase_steps(job.state, phase=job.phase, ready=ready, failed=failed)
    percent = overall_percent(
        state=job.state,
        phase=job.phase,
        download_percent=job.percent if job.state == InstallState.DOWNLOADING else None,
        ready=ready,
    )
    # Preserve download percent for downloading phase display, but never claim 100 until ready.
    if job.state == InstallState.DOWNLOADING and job.percent is not None:
        display_percent = min(99.0, float(job.percent))
    elif ready:
        display_percent = 100.0
    else:
        display_percent = percent

    prev_hb = job.heartbeat
    hb = build_heartbeat(
        job_id=job.id,
        previous=prev_hb,
        bytes_downloaded=job.progress_bytes,
        phase=job.phase,
        previous_phase=previous_phase,
        worker_alive=_worker_alive_for(job),
        network_active=(job.raw or {}).get("networkActive"),
    )
    stall = evaluate_stall(state=job.state, component_id=job.component_id, heartbeat=hb)
    actions = list(job.recovery_actions or [])
    if stall != "none":
        existing = {a.action for a in actions}
        for item in stall_recovery_actions(stall):
            if item["action"] not in existing:
                actions.append(RecoveryAction.model_validate(item))
    return job.model_copy(
        update={
            "percent": display_percent,
            "phase_steps": phase_steps,
            "heartbeat": hb,
            "stall_status": stall,
            "stall_label": stall_label(stall),
            "recovery_actions": actions,
            "indeterminate": bool(job.indeterminate or (display_percent is None and not ready)),
        }
    )


def _load_custom_jobs() -> list[InstallJob]:
    jobs: list[InstallJob] = []
    for path in _jobs_dir().glob("*.json"):
        payload = _read_json(path)
        if not payload:
            continue
        try:
            jobs.append(_job_from_payload(payload))
        except Exception:
            continue
    return jobs


def _recover_stale_custom_jobs() -> None:
    for job in _load_custom_jobs():
        if not job.active or job.terminal:
            continue
        thread = _CUSTOM_THREADS.get(job.id)
        if thread and thread.is_alive():
            continue
        repaired = job.model_copy(
            update={
                "state": InstallState.REPAIR_REQUIRED,
                "active": False,
                "terminal": False,
                "message": "Install was interrupted by an API restart.",
                "error": InstallJobError(
                    code=InstallJobErrorCode.INTERRUPTED,
                    message="Install was interrupted by an API restart.",
                    recoverable=True,
                    recommended_action="retry",
                ),
                "recovery_actions": [
                    RecoveryAction(
                        action="retry",
                        label="Retry install",
                        description="Retry this install from the last saved intent.",
                    )
                ],
                "updated_at": _now(),
            }
        )
        _persist_job(repaired)


def _serialize(job: InstallJob) -> dict[str, Any]:
    job = _enrich_job(job)
    payload = job.model_dump(mode="json", by_alias=True)
    step_index = None
    for index, step in enumerate(job.phase_steps or []):
        if step.get("status") == "active":
            step_index = index
            break
    raw = job.raw if isinstance(job.raw, dict) else {}
    raw_progress = raw.get("progress")
    raw_progress_dict = raw_progress if isinstance(raw_progress, dict) else {}
    payload["progress"] = {
        "phase": job.phase,
        "phaseLabel": job.stall_label
        or (job.phase or "").replace("_", " ")
        or None,
        "percent": job.percent,
        "indeterminate": bool(job.indeterminate or job.percent is None),
        "bytesDownloaded": job.progress_bytes,
        "bytesTotal": job.total_bytes,
        "speedBytesPerSecond": raw.get("speedBytesPerSecond")
        or raw_progress_dict.get("speedBytesPerSecond"),
        "etaSeconds": raw.get("etaSeconds")
        or raw_progress_dict.get("etaSeconds"),
        "currentFile": raw.get("currentFile")
        or raw_progress_dict.get("currentArtifact"),
        "currentStep": job.message or job.phase,
        "stepIndex": step_index if step_index is not None else job.files_completed,
        "stepCount": len(job.phase_steps) if job.phase_steps else job.files_total,
        "phaseSteps": job.phase_steps,
        "stallStatus": job.stall_status,
        "stallLabel": job.stall_label,
    }
    payload["destinationRoot"] = job.destination
    payload["heartbeat"] = job.heartbeat.model_dump(mode="json", by_alias=True) if job.heartbeat else None
    payload["stallStatus"] = job.stall_status
    payload["stallLabel"] = job.stall_label
    payload["phaseSteps"] = job.phase_steps
    if isinstance(job.error, InstallJobError):
        err = payload.get("error") or {}
        if isinstance(err, dict):
            err["code"] = job.error.code.value
            err.setdefault("title", job.error.title)
            err.setdefault("userMessage", job.error.user_message or job.error.message)
            err.setdefault("message", job.error.user_message or job.error.message)
            err.setdefault("technicalMessage", job.error.technical_message)
            err.setdefault("affectedFiles", job.error.affected_files)
            err.setdefault("affectedDependencies", job.error.affected_dependencies)
            err.setdefault("retryable", bool(job.error.retryable or job.recoverable))
            err.setdefault("repairable", bool(job.error.repairable or job.recovery_actions))
            err.setdefault("suggestedAction", job.error.suggested_action or job.error.recommended_action)
            err.setdefault("recommendedAction", job.error.recommended_action or job.error.suggested_action)
            err.setdefault("logReference", job.error.log_reference)
            payload["error"] = err
    caps = dict(payload.get("capabilities") or {})
    caps.setdefault("canPause", bool(caps.get("canPause")))
    caps.setdefault("canResume", bool(caps.get("canResume")))
    caps.setdefault("canCancel", caps.get("canCancel", True))
    caps.setdefault("canRetry", job.state in {InstallState.FAILED, InstallState.CANCELLED, InstallState.REPAIR_REQUIRED})
    caps.setdefault("canRepair", job.state in {InstallState.FAILED, InstallState.REPAIR_REQUIRED})
    payload["capabilities"] = caps
    return payload


def _source_summary(component_id: str) -> dict[str, Any]:
    assignment = get_assignment(component_id)
    if not assignment:
        return {"available": False}
    source = get_source(str(assignment.get("sourceId") or ""))
    return {
        "available": bool(source),
        "sourceId": assignment.get("sourceId"),
        "provider": source.get("provider") if source else None,
        "sourceUrl": source.get("sourceUrl") if source else None,
        "selectedArtifacts": list(assignment.get("selectedArtifacts") or []),
    }


def preflight_summary(
    component_id: str,
    *,
    destination: str | None = None,
    source_available: bool | None = None,
    required_free_bytes: int | None = None,
) -> dict[str, Any]:
    component = get_component(component_id)
    if component.installer == "avatar_runtime":
        runtime_preflight = avatar_runtime_preflight(component_id, destination=destination)
        verification = verify_component(component_id)
        return {
            **runtime_preflight,
            "componentId": component_id,
            "destination": runtime_preflight.get("destination") or str(destination or ""),
            "destinationExists": Path(str(runtime_preflight.get("destination") or "")).exists(),
            "destinationWritable": os_access_writable(Path(str(runtime_preflight.get("destination") or settings.data_dir))),
            "sourceAvailable": True if source_available is None else bool(source_available),
            "currentVerification": {
                "healthy": verification.healthy,
                "issueCode": verification.issue_code,
                "summary": verification.summary,
            },
        }
    selected_path = str(destination or suggested_install_path(component_id))
    target = Path(selected_path)
    disk_target = target if target.exists() else target.parent
    free_bytes = None
    disk_error = None
    try:
        free_bytes = shutil.disk_usage(disk_target or settings.data_dir).free
    except OSError as exc:
        disk_error = str(exc)
    verification = verify_component(component_id)
    needed = required_free_bytes or max(component.download_bytes, component.installed_bytes)
    return {
        "componentId": component_id,
        "destination": selected_path,
        "destinationExists": target.exists(),
        "destinationWritable": os_access_writable(target),
        "availableDiskBytes": free_bytes,
        "requiredFreeBytes": needed,
        "hasEnoughDisk": None if free_bytes is None else free_bytes >= needed,
        "diskError": disk_error,
        "sourceAvailable": bool(source_available) if source_available is not None else _source_summary(component_id).get("available"),
        "currentVerification": {
            "healthy": verification.healthy,
            "issueCode": verification.issue_code,
            "summary": verification.summary,
        },
    }


def os_access_writable(path: Path) -> bool | None:
    try:
        probe = path if path.exists() else path.parent
        if not probe.exists():
            return None
        return os.access(probe, os.W_OK)
    except OSError:
        return None


def _placeholder_job(
    component_id: str,
    *,
    state: InstallState,
    message: str,
    error: InstallJobError | None = None,
    source: dict[str, Any] | None = None,
    destination: str | None = None,
) -> InstallJob:
    component = get_component(component_id)
    recovery_actions = []
    if state in {InstallState.SOURCE_REQUIRED, InstallState.REPAIR_REQUIRED, InstallState.FAILED}:
        recovery_actions.append(
            RecoveryAction(
                action="retry",
                label="Retry install",
                description="Retry after fixing the blocking issue.",
            )
        )
    return _persist_job(
        InstallJob(
            id=_job_id(component_id),
            componentId=component.id,
            componentName=component.name,
            state=state,
            kind="custom_install",
            phase=state.value,
            message=message,
            indeterminate=True,
            active=False,
            terminal=state in {InstallState.CANCELLED, InstallState.FAILED, InstallState.READY},
            recoverable=bool(error.recoverable if error else True),
            source=source or {},
            destination=destination,
            createdAt=_now(),
            updatedAt=_now(),
            preflight=preflight_summary(component_id, destination=destination),
            error=error,
            recoveryActions=recovery_actions,
            raw={},
        )
    )


def _build_provider_plan(
    component_id: str,
    *,
    install_path: str | None = None,
    source_url: str | None = None,
    confirm: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    component = get_component(component_id)
    if source_url:
        saved = save_source(component_id, url=source_url, confirm=confirm)
        source_record = dict(saved.get("source") or {})
        assignment = dict(saved.get("assignment") or {})
    else:
        assignment = get_assignment(component_id) or {}
        source_record = get_source(str(assignment.get("sourceId") or "")) or {}
    if not source_record and component.installer == "asset_pack":
        from ...setup.pack_manifests import PackInstallError, resolve_pack_download

        try:
            resolved = resolve_pack_download(component_id, force_refresh=False)
        except PackInstallError:
            resolved = None
        if resolved:
            destination = str(install_path or suggested_install_path(component_id))
            provider_id = (
                "fixture"
                if os.environ.get("ADEPT_PACK_PROVIDER", "").strip().lower() == "fixture_http"
                else "direct_http"
            )
            source_record = {
                "id": f"official:{component_id}",
                "provider": provider_id,
                "sourceUrl": resolved.download_url,
                "revision": resolved.tag_name or resolved.version,
                "officialDefault": True,
            }
            plan = create_install_plan(
                component_id=component.id,
                source_id=None,
                provider_id=provider_id,
                artifacts=[
                    {
                        "remotePath": resolved.archive_asset_name or "pack.zip",
                        "destinationRelativePath": resolved.archive_asset_name or "pack.zip",
                        "expectedSize": resolved.expected_bytes or None,
                        "downloadUrl": resolved.download_url,
                        "role": "pack",
                    }
                ],
                destination_root=destination,
                source_revision=source_record.get("revision"),
                estimated_download_bytes=resolved.expected_bytes or component.download_bytes or None,
                estimated_extracted_bytes=component.installed_bytes or None,
                metadata={
                    "componentId": component.id,
                    "sourceUrl": resolved.download_url,
                    "version": resolved.version,
                    "officialOnly": True,
                },
            )
            return plan, source_record, assignment
    if not source_record:
        raise ValueError("A verified source is required before this component can be installed.")
    provider = get_provider(str(source_record.get("provider") or "")) or select_provider(
        SourceInput(
            url=source_record.get("sourceUrl"),
            revision=source_record.get("revision"),
            component_id=component_id,
        )
    )
    parsed = provider.parse_source(
        SourceInput(
            url=source_record.get("sourceUrl"),
            revision=source_record.get("revision"),
            component_id=component_id,
        )
    )
    verified = provider.verify_source(parsed, VerificationContext(component_id=component_id))
    if not verified.ok:
        normalized = normalize_failure(
            {
                "code": "source_invalid",
                "message": verified.message or "Source verification failed.",
                "details": {"blocking": verified.blocking_errors},
                "recommendedAction": "save_source",
            }
        )
        raise ValueError(normalized.message)
    artifacts = provider.list_artifacts(verified, ArtifactQueryContext(component_id=component_id))
    selected = set(assignment.get("selectedArtifacts") or [])
    if selected:
        artifacts = [item for item in artifacts if item.path in selected or item.name in selected]
    if not artifacts:
        raise ValueError("The selected source does not expose any installable artifacts.")
    destination = str(install_path or suggested_install_path(component_id))
    metadata = {
        "componentId": component.id,
        "sourceUrl": source_record.get("sourceUrl"),
        "officialOnly": False,
    }
    if provider.id in {"local_folder", "existing_install"}:
        metadata["localPath"] = source_record.get("sourceUrl")
        metadata["mode"] = "link_existing" if provider.id == "existing_install" else "copy"
    plan = create_install_plan(
        component_id=component.id,
        source_id=source_record.get("id"),
        provider_id=provider.id,
        artifacts=[
            {
                "remotePath": item.path,
                "destinationRelativePath": item.destination or item.path,
                "expectedSize": item.size,
                "downloadUrl": item.download_url,
                "role": item.kind,
            }
            for item in artifacts
        ],
        destination_root=destination,
        source_revision=source_record.get("revision"),
        estimated_download_bytes=component.download_bytes or None,
        estimated_extracted_bytes=component.installed_bytes or None,
        metadata=metadata,
    )
    return plan, source_record, assignment


def _enqueue_qwen(component_id: str) -> dict[str, Any]:
    from ...codirector.m210b.qwen_voice_install import scaffold

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
    return get_queue_manager().enqueue(plan, priority=50)


def _enqueue_video_understanding(component_id: str) -> dict[str, Any]:
    from ...codirector.video_intelligence.paths import (
        INTERNVIDEO3_HF_ID,
        VIDEOCHAT3_HF_ID,
        internvideo3_dir,
        videochat3_dir,
    )

    component = get_component(component_id)
    repo = VIDEOCHAT3_HF_ID if component_id == "videochat3_4b" else INTERNVIDEO3_HF_ID
    dest = videochat3_dir() if component_id == "videochat3_4b" else internvideo3_dir()
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
        estimated_download_bytes=component.download_bytes,
        estimated_extracted_bytes=component.installed_bytes,
        metadata={"componentId": component_id, "officialOnly": True, "videoUnderstanding": True},
    )
    return get_queue_manager().enqueue(plan, priority=45)


def _enqueue_hunyuan(component_id: str) -> dict[str, Any]:
    provider_id = PROVIDER_BY_COMPONENT[component_id]
    meta = OFFICIAL_SOURCES[provider_id]
    component = get_component(component_id)
    plan = create_install_plan(
        component_id=component_id,
        source_id=str(meta["hfRepo"]),
        provider_id="huggingface_snapshot",
        artifacts=[
            {
                "remotePath": str(meta["hfRepo"]),
                "destinationRelativePath": ".",
                "downloadUrl": f"https://huggingface.co/{meta['hfRepo']}",
            }
        ],
        destination_root=str(provider_dir(provider_id)),
        estimated_download_bytes=component.download_bytes,
        estimated_extracted_bytes=component.installed_bytes,
        metadata={
            "componentId": component_id,
            "providerId": provider_id,
            "engine": meta["engine"],
            "officialOnly": True,
            "hunyuan": True,
        },
    )
    return get_queue_manager().enqueue(plan, priority=40)


def _start_avatar_runtime_job(
    component_id: str,
    *,
    confirm_download_models: bool,
    force: bool,
    source_url: str | None,
    install_path: str | None,
) -> InstallJob:
    component = get_component(component_id)
    details = avatar_runtime_preflight(component_id, destination=install_path)
    job = InstallJob(
        id=_job_id(component_id),
        componentId=component.id,
        componentName=component.name,
        state=InstallState.QUEUED,
        kind="custom_install",
        phase="queued",
        message="Queued avatar runtime install.",
        indeterminate=True,
        filesCompleted=0,
        filesTotal=5,
        active=True,
        terminal=False,
        recoverable=True,
        source={
            "providerId": component_id,
            "sourceUrl": source_url,
            "confirmDownloadModels": confirm_download_models,
        },
        destination=str(install_path or details.get("destination") or ""),
        createdAt=_now(),
        updatedAt=_now(),
        preflight=preflight_summary(
            component_id,
            destination=str(install_path or details.get("destination") or ""),
            source_available=True,
            required_free_bytes=component.download_bytes,
        ),
        recoveryActions=[],
        raw={
            "force": force,
            "officialSource": details.get("officialSource"),
            "gpu": details.get("gpu"),
            "blockers": details.get("blockers"),
            "notes": details.get("notes"),
            "logPaths": [str(Path(settings.data_dir) / "runtimes" / "avatar")],
        },
    )
    _persist_job(job)

    phase_state = {
        "preflight": InstallState.PREPARING,
        "preparing": InstallState.PREPARING,
        "installing": InstallState.INSTALLING,
        "downloading": InstallState.DOWNLOADING,
        "verifying_install": InstallState.VERIFYING_INSTALL,
        "completed": InstallState.READY,
    }

    def emit(phase: str, frac: float, message: str, details: dict[str, Any] | None = None) -> None:
        current = _job_from_payload(_read_json(_job_path(job.id)) or _serialize(job))
        payload = details or {}
        updated = current.model_copy(
            update={
                "state": phase_state.get(phase, InstallState.PREPARING),
                "phase": phase,
                "message": message,
                "progress_bytes": int(max(0.0, min(1.0, frac)) * int(component.download_bytes or 0))
                if component.download_bytes
                else current.progress_bytes,
                "total_bytes": component.download_bytes or current.total_bytes,
                "files_completed": int(payload.get("stepIndex") or current.files_completed or 0),
                "files_total": int(payload.get("stepCount") or current.files_total or 5),
                "updated_at": _now(),
                "indeterminate": False,
                "raw": {
                    **(current.raw or {}),
                    "progress": {
                        **(((current.raw or {}).get("progress")) or {}),
                        "currentArtifact": payload.get("currentFile"),
                    },
                    "currentFile": payload.get("currentFile"),
                },
            }
        )
        _persist_job(updated)

    def run() -> None:
        try:
            result = install_avatar_runtime(
                component_id,
                destination=install_path,
                confirm_download_models=confirm_download_models,
                source_url=source_url,
                progress_callback=emit,
                cancel_check=lambda: False,
                force=force,
            )
            current = _job_from_payload(_read_json(_job_path(job.id)) or _serialize(job))
            if result.get("ok"):
                verify = verify_avatar_runtime(component_id)
                final = current.model_copy(
                    update={
                        "state": InstallState.READY,
                        "phase": "completed",
                        "message": str(result.get("message") or "Avatar runtime install completed."),
                        "files_completed": 5,
                        "files_total": 5,
                        "progress_bytes": component.download_bytes or current.progress_bytes,
                        "total_bytes": component.download_bytes or current.total_bytes,
                        "active": False,
                        "terminal": True,
                        "completed_at": _now(),
                        "updated_at": _now(),
                        "raw": {
                            **(current.raw or {}),
                            "result": result,
                            "inspection": verify.get("inspection"),
                            "healthState": (verify.get("inspection") or {}).get("healthState"),
                            "logPaths": result.get("logPaths") or ((verify.get("inspection") or {}).get("logPaths") or []),
                        },
                        "recovery_actions": [
                            RecoveryAction(
                                action="benchmark",
                                label="Benchmark",
                                description="Record the benchmark hook for this experimental runtime.",
                            ),
                            RecoveryAction(
                                action="reverify",
                                label="Verify runtime",
                                description="Re-check the runtime files, launch path, and GPU probe.",
                            ),
                            RecoveryAction(
                                action="open_diagnostics",
                                label="Open Logs",
                                description="Open runtime log paths and diagnostics.",
                            ),
                        ],
                    }
                )
                _persist_job(final)
            else:
                error = normalize_failure(result.get("error"))
                final = current.model_copy(
                    update={
                        "state": InstallState.REPAIR_REQUIRED,
                        "phase": "repair_required",
                        "message": error.message,
                        "active": False,
                        "terminal": False,
                        "completed_at": _now(),
                        "updated_at": _now(),
                        "error": error,
                        "raw": {
                            **(current.raw or {}),
                            "result": result,
                            "logPaths": result.get("logPaths") or [],
                        },
                        "recovery_actions": [
                            RecoveryAction(
                                action="repair_dependencies",
                                label="Repair runtime",
                                description="Retry the pinned runtime install in this isolated folder.",
                            ),
                            RecoveryAction(
                                action="reverify",
                                label="Verify runtime",
                                description="Re-check runtime files without downloading again.",
                            ),
                            RecoveryAction(
                                action="open_diagnostics",
                                label="Open Logs",
                                description="Open runtime log paths and diagnostics.",
                            ),
                        ],
                    }
                )
                _persist_job(final)
        finally:
            with _CUSTOM_LOCK:
                _CUSTOM_THREADS.pop(job.id, None)
                _CUSTOM_THREAD_META.pop(job.id, None)

    thread = threading.Thread(target=run, name=f"avatar-install-{job.id[:12]}", daemon=True)
    with _CUSTOM_LOCK:
        _CUSTOM_THREADS[job.id] = thread
        _CUSTOM_THREAD_META[job.id] = {
            "componentId": component_id,
            "confirmDownloadModels": confirm_download_models,
            "sourceUrl": source_url,
            "installPath": install_path,
            "force": force,
            "kind": "avatar_runtime",
        }
    thread.start()
    return job


def _start_index_tts2_job(
    component_id: str,
    *,
    confirm_download_models: bool,
    force: bool,
) -> InstallJob:
    component = get_component(component_id)
    job = InstallJob(
        id=_job_id(component_id),
        componentId=component.id,
        componentName=component.name,
        state=InstallState.QUEUED,
        kind="custom_install",
        phase="queued",
        message="Queued for IndexTTS2 runtime install.",
        indeterminate=True,
        filesCompleted=0,
        filesTotal=_INDEX_TTS2_STEP_TOTAL,
        active=True,
        terminal=False,
        recoverable=True,
        source={"providerId": "index-tts2-local", "confirmDownloadModels": confirm_download_models},
        destination=str(get_index_tts2_runtime().runtime_root),
        createdAt=_now(),
        updatedAt=_now(),
        preflight=preflight_summary(
            component_id,
            destination=str(get_index_tts2_runtime().runtime_root),
            source_available=True,
            required_free_bytes=component.download_bytes,
        ),
        recoveryActions=[],
        raw={"force": force},
    )
    _persist_job(job)

    def emit(phase: str, payload: dict[str, Any]) -> None:
        current = _job_from_payload(_read_json(_job_path(job.id)) or _serialize(job))
        state = {
            "clone_repo": InstallState.PREPARING,
            "create_environment": InstallState.PREPARING,
            "install_dependencies": InstallState.INSTALLING,
            "import_probe": InstallState.VERIFYING_INSTALL,
            "download_models": InstallState.DOWNLOADING,
            "verify_runtime": InstallState.VERIFYING_INSTALL,
        }.get(phase, InstallState.PREPARING)
        updated = current.model_copy(
            update={
                "state": state,
                "phase": phase,
                "message": str(payload.get("message") or phase.replace("_", " ").title()),
                "files_completed": int(payload.get("step") or current.files_completed or 0),
                "files_total": int(payload.get("totalSteps") or current.files_total or _INDEX_TTS2_STEP_TOTAL),
                "updated_at": _now(),
                "indeterminate": True,
            }
        )
        _persist_job(updated)

    def run() -> None:
        runtime = get_index_tts2_runtime()
        try:
            emit("clone_repo", {"message": "Preparing the pinned IndexTTS2 runtime.", "step": 1, "totalSteps": _INDEX_TTS2_STEP_TOTAL})
            result = runtime.install(
                confirm=True,
                confirm_download_models=confirm_download_models,
                force=force,
                progress_callback=emit,
            )
            current = _job_from_payload(_read_json(_job_path(job.id)) or _serialize(job))
            if result.get("ok"):
                final = current.model_copy(
                    update={
                        "state": InstallState.READY
                        if result.get("state") == "ready"
                        else InstallState.VERIFYING_INSTALL,
                        "phase": "completed",
                        "message": str(result.get("message") or "IndexTTS2 install completed."),
                        "files_completed": _INDEX_TTS2_STEP_TOTAL,
                        "files_total": _INDEX_TTS2_STEP_TOTAL,
                        "active": False,
                        "terminal": result.get("state") == "ready",
                        "completed_at": _now(),
                        "updated_at": _now(),
                        "raw": {"result": result},
                        "recovery_actions": (
                            []
                            if result.get("state") == "ready"
                            else [
                                RecoveryAction(
                                    action="repair",
                                    label="Download models",
                                    description="Finish the deferred IndexTTS2 model download.",
                                )
                            ]
                        ),
                    }
                )
                _persist_job(final)
            else:
                error = normalize_failure(result.get("error"))
                final = current.model_copy(
                    update={
                        "state": InstallState.FAILED,
                        "phase": "failed",
                        "message": error.message,
                        "active": False,
                        "terminal": True,
                        "completed_at": _now(),
                        "updated_at": _now(),
                        "error": error,
                        "raw": {"result": result},
                        "recovery_actions": [
                            RecoveryAction(
                                action="retry",
                                label="Retry install",
                                description="Retry the IndexTTS2 runtime install.",
                            )
                        ],
                    }
                )
                _persist_job(final)
        finally:
            with _CUSTOM_LOCK:
                _CUSTOM_THREADS.pop(job.id, None)
                _CUSTOM_THREAD_META.pop(job.id, None)

    thread = threading.Thread(target=run, name=f"install-job-{job.id[:12]}", daemon=True)
    with _CUSTOM_LOCK:
        _CUSTOM_THREADS[job.id] = thread
        _CUSTOM_THREAD_META[job.id] = {
            "componentId": component_id,
            "confirmDownloadModels": confirm_download_models,
            "force": force,
        }
    thread.start()
    return job


def list_jobs(active_only: bool = False) -> list[dict[str, Any]]:
    _recover_stale_custom_jobs()
    jobs: list[InstallJob] = []
    queue_filters = {"active": True} if active_only else None
    for op in get_queue_manager().list(queue_filters):
        jobs.append(download_operation_to_install_job(op))
    operations = (load_state().get("operations") or {}) if not active_only else (load_state().get("operations") or {})
    for op_id, payload in operations.items():
        if not isinstance(payload, dict):
            continue
        item = setup_operation_to_install_job({**payload, "operation_id": op_id})
        if item is None:
            continue
        if active_only and not item.active:
            continue
        jobs.append(item)
    for job in _load_custom_jobs():
        if active_only and not job.active:
            continue
        jobs.append(job)
    jobs.sort(
        key=lambda item: (
            0 if item.active else 1,
            str(item.updated_at or ""),
        ),
        reverse=False,
    )
    return [_serialize(job) for job in jobs]


def get_job(job_id: str) -> dict[str, Any]:
    op = get_queue_manager().get(job_id)
    if op:
        return _serialize(download_operation_to_install_job(op))
    payload = (load_state().get("operations") or {}).get(job_id)
    if isinstance(payload, dict):
        job = setup_operation_to_install_job({**payload, "operation_id": job_id})
        if job:
            return _serialize(job)
    custom = _read_json(_job_path(job_id))
    if custom:
        return _serialize(_job_from_payload(custom))
    raise KeyError(job_id)


def jobs_for_component(component_id: str) -> list[dict[str, Any]]:
    return [job for job in list_jobs(active_only=False) if job.get("componentId") == component_id]


def create_or_resume_install(
    component_id: str,
    *,
    confirm: bool = True,
    confirm_download_models: bool = False,
    source_url: str | None = None,
    install_path: str | None = None,
) -> dict[str, Any]:
    component = get_component(component_id)
    for job in jobs_for_component(component_id):
        if job.get("active"):
            return job
    if not confirm:
        return _serialize(
            _placeholder_job(
                component_id,
                state=InstallState.AWAITING_CONFIRMATION,
                message=f"{component.name} install requires explicit confirmation.",
                destination=install_path,
                error=InstallJobError(
                    code=InstallJobErrorCode.CONFIRM_REQUIRED,
                    message=f"{component.name} install requires explicit confirmation.",
                    recoverable=True,
                    recommendedAction="confirm_install",
                ),
            )
        )
    if component_id == "index_tts2":
        return _serialize(
            _start_index_tts2_job(
                component_id,
                confirm_download_models=bool(confirm_download_models),
                force=False,
            )
        )
    if component.installer == "avatar_runtime" or is_avatar_runtime_component(component_id):
        if not confirm_download_models:
            return _serialize(
                _placeholder_job(
                    component_id,
                    state=InstallState.AWAITING_CONFIRMATION,
                    message=f"{component.name} requires explicit model-download confirmation.",
                    destination=install_path,
                    error=InstallJobError(
                        code=InstallJobErrorCode.CONFIRM_REQUIRED,
                        message=f"{component.name} requires explicit model-download confirmation.",
                        recoverable=True,
                        recommendedAction="confirm_install",
                    ),
                )
            )
        return _serialize(
            _start_avatar_runtime_job(
                component_id,
                confirm_download_models=True,
                force=False,
                source_url=source_url,
                install_path=install_path,
            )
        )
    if component.installer == "comfy_extension" or (
        component_id.startswith("comfyui_") and "nodes" in component_id
    ):
        return _serialize(
            _start_comfy_extension_job(
                component_id,
                source_url=source_url,
                install_path=install_path,
                confirm_executable=bool(confirm),
            )
        )
    if component.installer == "m210b_qwen_voice":
        return _serialize(download_operation_to_install_job(_enqueue_qwen(component_id)))
    if component.installer == "huggingface_snapshot":
        if component_id in ("videochat3_4b", "internvideo3_8b"):
            return _serialize(download_operation_to_install_job(_enqueue_video_understanding(component_id)))
        return _serialize(download_operation_to_install_job(_enqueue_hunyuan(component_id)))
    if component.installer == "asset_pack":
        try:
            plan, source_record, _assignment = _build_provider_plan(
                component_id,
                install_path=install_path,
                source_url=source_url,
                confirm=confirm,
            )
        except ValueError as exc:
            return _serialize(
                _placeholder_job(
                    component_id,
                    state=InstallState.SOURCE_REQUIRED,
                    message=str(exc),
                    destination=install_path,
                    source=_source_summary(component_id),
                    error=InstallJobError(
                        code=InstallJobErrorCode.SOURCE_REQUIRED,
                        message=str(exc),
                        recoverable=True,
                        recommendedAction="save_source",
                    ),
                )
            )
        queued = get_queue_manager().enqueue(plan, priority=45)
        job = download_operation_to_install_job(queued)
        job.preflight = preflight_summary(
            component_id,
            destination=str(plan.get("destinationRoot") or install_path or ""),
            source_available=True,
            required_free_bytes=plan.get("requiredFreeBytes"),
        )
        job.source = {
            "sourceId": source_record.get("id"),
            "provider": source_record.get("provider"),
            "sourceUrl": source_record.get("sourceUrl"),
        }
        return _serialize(job)
    return _serialize(
        _placeholder_job(
            component_id,
            state=InstallState.AWAITING_CONFIRMATION,
            message=f"{component.name} still uses its existing guided setup flow.",
            destination=install_path,
            error=InstallJobError(
                code=InstallJobErrorCode.UNSUPPORTED_ACTION,
                message=f"{component.name} cannot be enqueued through install jobs yet.",
                recoverable=True,
                recommendedAction="open_setup",
            ),
        )
    )


def pause(job_id: str) -> dict[str, Any]:
    return _serialize(download_operation_to_install_job(get_queue_manager().pause(job_id)))


def resume(job_id: str) -> dict[str, Any]:
    return _serialize(download_operation_to_install_job(get_queue_manager().resume(job_id)))


def cancel(job_id: str) -> dict[str, Any]:
    op = get_queue_manager().get(job_id)
    if op:
        return _serialize(download_operation_to_install_job(get_queue_manager().cancel(job_id)))
    current = _read_json(_job_path(job_id))
    if current:
        job = _job_from_payload(current)
        thread = _CUSTOM_THREADS.get(job_id)
        if thread and thread.is_alive():
            raise ValueError("Cancel is not supported while this install is actively running.")
        cancelled = job.model_copy(
            update={
                "state": InstallState.CANCELLED,
                "phase": "cancelled",
                "message": "Install cancelled.",
                "active": False,
                "terminal": True,
                "completed_at": _now(),
                "updated_at": _now(),
                "error": InstallJobError(
                    code=InstallJobErrorCode.CANCELLED,
                    message="Install cancelled.",
                    recoverable=True,
                ),
            }
        )
        return _serialize(_persist_job(cancelled))
    raise KeyError(job_id)


def retry(job_id: str) -> dict[str, Any]:
    op = get_queue_manager().get(job_id)
    if op:
        return _serialize(download_operation_to_install_job(get_queue_manager().retry(job_id)))
    job = get_job(job_id)
    component_id = str(job.get("componentId") or "")
    if component_id == "index_tts2":
        confirm_download_models = bool((job.get("source") or {}).get("confirmDownloadModels"))
        return _serialize(_start_index_tts2_job(component_id, confirm_download_models=confirm_download_models, force=True))
    if is_avatar_runtime_component(component_id):
        confirm_download_models = bool((job.get("source") or {}).get("confirmDownloadModels"))
        return _serialize(
            _start_avatar_runtime_job(
                component_id,
                confirm_download_models=confirm_download_models,
                force=True,
                source_url=(job.get("source") or {}).get("sourceUrl"),
                install_path=job.get("destinationRoot") or job.get("destination"),
            )
        )
    if component_id.startswith("comfyui_") or (job.get("kind") == "comfy_extension"):
        return _serialize(
            _start_comfy_extension_job(
                component_id,
                source_url=(job.get("source") or {}).get("sourceUrl"),
                install_path=job.get("destinationRoot") or job.get("destination"),
                confirm_executable=True,
            )
        )
    raise ValueError("Retry is only supported for queue-backed installs, IndexTTS2, and ComfyUI extensions.")


def repair(job_id: str, action: str) -> dict[str, Any]:
    op = get_queue_manager().get(job_id)
    if op:
        if action in {"resume_download", "resume", "retry_connection"}:
            return _serialize(download_operation_to_install_job(get_queue_manager().resume(job_id)))
        if action in {"retry_download", "restart_worker"}:
            return _serialize(download_operation_to_install_job(get_queue_manager().retry(job_id)))
        if action == "cancel_safely":
            return cancel(job_id)
        raise ValueError(f"Unsupported queue repair action: {action}")
    job = get_job(job_id)
    component_id = str(job.get("componentId") or "")
    if action == "cancel_safely":
        return cancel(job_id)
    if action in {"retry_connection", "resume", "restart_worker"} and component_id == "index_tts2":
        confirm_download_models = bool((job.get("source") or {}).get("confirmDownloadModels"))
        return _serialize(
            _start_index_tts2_job(component_id, confirm_download_models=confirm_download_models, force=True)
        )
    if is_avatar_runtime_component(component_id):
        if action == "reverify":
            verify = verify_avatar_runtime(component_id)
            current = _job_from_payload(_read_json(_job_path(job_id)) or job)
            updated = current.model_copy(
                update={
                    "state": InstallState.READY if verify.get("runtimeReady") else InstallState.REPAIR_REQUIRED,
                    "phase": "verify_runtime",
                    "message": str(verify.get("message") or "Verification completed."),
                    "active": False,
                    "updated_at": _now(),
                    "error": None if verify.get("runtimeReady") else InstallJobError(
                        code=InstallJobErrorCode.INSTALL_FAILED,
                        message=str(verify.get("message") or "Verification failed."),
                        recoverable=True,
                        recommendedAction="repair_dependencies",
                    ),
                    "raw": {**(current.raw or {}), "inspection": verify.get("inspection")},
                }
            )
            return _serialize(_persist_job(updated))
        if action == "benchmark":
            result = benchmark_avatar_runtime(component_id)
            current = _job_from_payload(_read_json(_job_path(job_id)) or job)
            updated = current.model_copy(
                update={
                    "message": str(result.get("message") or current.message or "Benchmark hook recorded."),
                    "updated_at": _now(),
                    "raw": {**(current.raw or {}), "benchmark": result},
                }
            )
            return _serialize(_persist_job(updated))
        if action in {"repair_dependencies", "retry_download", "resume_download", "restart_worker", "retry_connection", "retry"}:
            confirm_download_models = bool((job.get("source") or {}).get("confirmDownloadModels"))
            return _serialize(
                _start_avatar_runtime_job(
                    component_id,
                    confirm_download_models=confirm_download_models,
                    force=True,
                    source_url=(job.get("source") or {}).get("sourceUrl"),
                    install_path=job.get("destinationRoot") or job.get("destination"),
                )
            )
        if action == "open_diagnostics":
            current = _job_from_payload(_read_json(_job_path(job_id)) or job)
            updated = current.model_copy(
                update={
                    "updated_at": _now(),
                    "raw": {**(current.raw or {}), "diagnosticsOpen": True},
                }
            )
            return _serialize(_persist_job(updated))
    if component_id.startswith("comfyui_") or job.get("kind") == "comfy_extension":
        return _repair_comfy_extension(job_id, action)
    if component_id != "index_tts2":
        raise ValueError(f"Unsupported repair action for {component_id}: {action}")
    runtime = get_index_tts2_runtime()
    if action == "reverify":
        result = runtime.verify()
        current = _job_from_payload(_read_json(_job_path(job_id)) or job)
        updated = current.model_copy(
            update={
                "state": InstallState.READY if result.get("runtimeReady") else InstallState.REPAIR_REQUIRED,
                "phase": "verify_runtime",
                "message": str((result.get("health") or {}).get("message") or result.get("message") or "Verification completed."),
                "active": False,
                "updated_at": _now(),
                "raw": {"verify": result},
            }
        )
        return _serialize(_persist_job(updated))
    if action in {"download_missing_files", "repair_dependencies", "retry_download", "resume_download"}:
        return _serialize(_start_index_tts2_job(component_id, confirm_download_models=True, force=True))
    raise ValueError(f"Unsupported IndexTTS2 repair action: {action}")


def _start_comfy_extension_job(
    component_id: str,
    *,
    source_url: str | None,
    install_path: str | None,
    confirm_executable: bool,
) -> InstallJob:
    from .comfy_extension_installer import (
        clone_or_update_extension,
        extension_error,
        install_extension_dependencies,
        preflight_extension,
    )

    component = get_component(component_id)
    try:
        preflight = preflight_extension(
            component_id,
            source_url=source_url,
            install_path=install_path,
        )
    except ValueError as exc:
        return _placeholder_job(
            component_id,
            state=InstallState.SOURCE_REQUIRED,
            message=str(exc),
            destination=install_path,
            error=extension_error(
                InstallJobErrorCode.INSTALL_SOURCE_MISSING,
                str(exc),
                recommendedAction="save_source",
                suggestedAction="save_source",
            ),
        )
    if not preflight.get("ok"):
        return _placeholder_job(
            component_id,
            state=InstallState.REPAIR_REQUIRED,
            message=str(preflight.get("error") or "ComfyUI custom_nodes is not writable."),
            destination=preflight.get("customNodesDir"),
            error=extension_error(
                InstallJobErrorCode.INSTALL_PERMISSION_DENIED,
                str(preflight.get("error") or "ComfyUI custom_nodes is not writable."),
                recommendedAction="change_destination",
            ),
        )
    source = dict(preflight.get("source") or {})
    if source.get("executesCode") and not confirm_executable and not source.get("officialDefault"):
        return _placeholder_job(
            component_id,
            state=InstallState.AWAITING_CONFIRMATION,
            message="This user-supplied extension executes code. Confirm before installing.",
            destination=preflight.get("targetDir"),
            source=source,
            error=extension_error(
                InstallJobErrorCode.INSTALL_CONFIRM_REQUIRED,
                "Confirm installation of this executable ComfyUI extension.",
                recommendedAction="confirm_install",
            ),
        )

    job = InstallJob(
        id=_job_id(component_id),
        componentId=component.id,
        componentName=component.name,
        state=InstallState.QUEUED,
        kind="comfy_extension",
        phase="queued",
        message="Queued ComfyUI extension install.",
        indeterminate=True,
        filesCompleted=0,
        filesTotal=5,
        active=True,
        terminal=False,
        recoverable=True,
        source={**source, "sourceUrl": source.get("url")},
        destination=str(preflight.get("targetDir")),
        createdAt=_now(),
        updatedAt=_now(),
        preflight=preflight,
        recoveryActions=[],
        raw={"requiredNodes": list(preflight.get("requiredNodes") or [])},
    )
    _persist_job(job)

    def emit(phase: str, state: InstallState, message: str, *, step: int) -> None:
        current = _job_from_payload(_read_json(_job_path(job.id)) or _serialize(job))
        _persist_job(
            current.model_copy(
                update={
                    "state": state,
                    "phase": phase,
                    "message": message,
                    "files_completed": step,
                    "files_total": 5,
                    "updated_at": _now(),
                    "indeterminate": True,
                }
            )
        )

    def run() -> None:
        try:
            emit("preparing", InstallState.PREPARING, "Preparing ComfyUI custom_nodes target.", step=1)
            target = Path(str(preflight["targetDir"]))
            clone = clone_or_update_extension(
                target_dir=target,
                source_url=str(source["url"]),
                revision=source.get("revision"),
            )
            if not clone.get("ok"):
                current = _job_from_payload(_read_json(_job_path(job.id)) or {})
                _persist_job(
                    current.model_copy(
                        update={
                            "state": InstallState.FAILED,
                            "phase": "failed",
                            "message": clone.get("message") or "Extension clone failed.",
                            "active": False,
                            "terminal": True,
                            "completed_at": _now(),
                            "updated_at": _now(),
                            "error": extension_error(
                                InstallJobErrorCode.INSTALL_DOWNLOAD_FAILED,
                                str(clone.get("message") or "Extension clone failed."),
                                technicalMessage=str(clone),
                                recommendedAction="retry",
                            ),
                            "recovery_actions": [
                                RecoveryAction(
                                    action="retry",
                                    label="Retry install",
                                    description="Retry cloning the ComfyUI extension.",
                                )
                            ],
                            "raw": {**(current.raw or {}), "clone": clone},
                        }
                    )
                )
                return

            emit("installing", InstallState.INSTALLING, "Installing extension dependencies.", step=2)
            deps = install_extension_dependencies(target)
            if not deps.get("ok"):
                current = _job_from_payload(_read_json(_job_path(job.id)) or {})
                _persist_job(
                    current.model_copy(
                        update={
                            "state": InstallState.REPAIR_REQUIRED,
                            "phase": "repair_required",
                            "message": deps.get("message") or "Extension dependency install failed.",
                            "active": False,
                            "terminal": False,
                            "updated_at": _now(),
                            "error": extension_error(
                                InstallJobErrorCode.INSTALL_DEPENDENCY_FAILED,
                                str(deps.get("message") or "Extension dependency install failed."),
                                recommendedAction="repair_dependencies",
                            ),
                            "recovery_actions": [
                                RecoveryAction(
                                    action="repair_dependencies",
                                    label="Repair Dependencies",
                                    description="Retry installing the extension Python dependencies.",
                                ),
                                RecoveryAction(
                                    action="open_diagnostics",
                                    label="Open Diagnostics",
                                    description="Open technical diagnostics for this install.",
                                ),
                            ],
                            "raw": {**(current.raw or {}), "clone": clone, "deps": deps},
                        }
                    )
                )
                return

            # Clone success must NOT mark ready — require restart + live node probe.
            emit(
                "restart_required",
                InstallState.CONFIGURING,
                "Installation complete. ComfyUI must restart before the new nodes become available.",
                step=3,
            )
            current = _job_from_payload(_read_json(_job_path(job.id)) or {})
            _persist_job(
                current.model_copy(
                    update={
                        "state": InstallState.CONFIGURING,
                        "phase": "restart_required",
                        "message": "Installation complete. ComfyUI must restart before the new nodes become available.",
                        "active": False,
                        "terminal": False,
                        "updated_at": _now(),
                        "files_completed": 3,
                        "recovery_actions": [
                            RecoveryAction(
                                action="restart_comfyui",
                                label="Restart ComfyUI",
                                description="Restart ComfyUI, then re-detect required nodes.",
                            ),
                            RecoveryAction(
                                action="restart_later",
                                label="Restart Later",
                                description="Keep the extension installed and verify nodes after a manual restart.",
                            ),
                        ],
                        "raw": {
                            **(current.raw or {}),
                            "clone": clone,
                            "deps": deps,
                            "awaitingRestart": True,
                            "nodesReady": False,
                        },
                    }
                )
            )
        finally:
            with _CUSTOM_LOCK:
                _CUSTOM_THREADS.pop(job.id, None)
                _CUSTOM_THREAD_META.pop(job.id, None)

    thread = threading.Thread(target=run, name=f"comfy-ext-{job.id[:12]}", daemon=True)
    with _CUSTOM_LOCK:
        _CUSTOM_THREADS[job.id] = thread
        _CUSTOM_THREAD_META[job.id] = {"componentId": component_id, "kind": "comfy_extension"}
    thread.start()
    return job


def _repair_comfy_extension(job_id: str, action: str) -> dict[str, Any]:
    from .comfy_extension_installer import (
        extension_error,
        install_extension_dependencies,
        probe_required_nodes,
        refresh_capabilities_after_probe,
        restart_comfyui_best_effort,
        summarize_capability_shift,
    )

    payload = _read_json(_job_path(job_id))
    if not payload:
        raise KeyError(job_id)
    current = _job_from_payload(payload)
    component_id = current.component_id
    required = list((current.raw or {}).get("requiredNodes") or [])

    if action in {"restart_later"}:
        updated = current.model_copy(
            update={
                "message": "Restart ComfyUI when ready, then verify required nodes.",
                "phase": "restart_required",
                "state": InstallState.CONFIGURING,
                "updated_at": _now(),
            }
        )
        return _serialize(_persist_job(updated))

    if action in {"restart_comfyui", "restart_service"}:
        restart = restart_comfyui_best_effort()
        emit_msg = "Checking required nodes..."
        probing = current.model_copy(
            update={
                "state": InstallState.VERIFYING_INSTALL,
                "phase": "probing_nodes",
                "message": emit_msg,
                "active": True,
                "updated_at": _now(),
                "raw": {**(current.raw or {}), "restart": restart},
            }
        )
        _persist_job(probing)
        probe = probe_required_nodes(required or None)
        refresh_capabilities_after_probe()
        caps = summarize_capability_shift(component_id)
        if probe.get("ok"):
            ready = probing.model_copy(
                update={
                    "state": InstallState.READY,
                    "phase": "completed",
                    "message": f"{probe.get('message')}. Capability ready.",
                    "active": False,
                    "terminal": True,
                    "completed_at": _now(),
                    "updated_at": _now(),
                    "files_completed": 5,
                    "files_total": 5,
                    "percent": 100.0,
                    "recovery_actions": [],
                    "error": None,
                    "raw": {
                        **(probing.raw or {}),
                        "probe": probe,
                        "capabilities": caps,
                        "nodesReady": True,
                        "awaitingRestart": False,
                    },
                }
            )
            return _serialize(_persist_job(ready))
        missing = probe.get("missing") or []
        failed = probing.model_copy(
            update={
                "state": InstallState.REPAIR_REQUIRED,
                "phase": "nodes_missing",
                "message": (
                    f"Extension installed, but {len(missing)} required nodes were not registered."
                ),
                "active": False,
                "terminal": False,
                "updated_at": _now(),
                "error": extension_error(
                    InstallJobErrorCode.INSTALL_EXTENSION_MISSING,
                    f"Extension installed, but {len(missing)} required nodes were not registered.",
                    affectedFiles=list(missing),
                    recommendedAction="repair_dependencies",
                    suggestedAction="repair_dependencies",
                ),
                "recovery_actions": [
                    RecoveryAction(
                        action="repair_dependencies",
                        label="Repair Dependencies",
                        description="Reinstall extension dependencies and probe nodes again.",
                    ),
                    RecoveryAction(
                        action="open_diagnostics",
                        label="Open Logs",
                        description="Open technical diagnostics for this extension install.",
                    ),
                    RecoveryAction(
                        action="verify_comfy_instance",
                        label="Verify Correct ComfyUI Instance",
                        description="Confirm Adept is probing the ComfyUI instance that received the extension.",
                    ),
                    RecoveryAction(
                        action="restart_comfyui",
                        label="Restart ComfyUI",
                        description="Restart ComfyUI and re-detect required nodes.",
                    ),
                ],
                "raw": {
                    **(probing.raw or {}),
                    "probe": probe,
                    "capabilities": caps,
                    "nodesReady": False,
                },
            }
        )
        return _serialize(_persist_job(failed))

    if action in {"reverify", "verify_nodes", "verify_comfy_instance"}:
        probe = probe_required_nodes(required or None)
        refresh_capabilities_after_probe()
        caps = summarize_capability_shift(component_id)
        if probe.get("ok"):
            ready = current.model_copy(
                update={
                    "state": InstallState.READY,
                    "phase": "completed",
                    "message": f"{probe.get('message')}. Capability ready.",
                    "active": False,
                    "terminal": True,
                    "completed_at": _now(),
                    "updated_at": _now(),
                    "percent": 100.0,
                    "error": None,
                    "recovery_actions": [],
                    "raw": {**(current.raw or {}), "probe": probe, "capabilities": caps, "nodesReady": True},
                }
            )
            return _serialize(_persist_job(ready))
        updated = current.model_copy(
            update={
                "state": InstallState.REPAIR_REQUIRED,
                "phase": "nodes_missing",
                "message": probe.get("message") or "Required nodes still missing.",
                "updated_at": _now(),
                "error": extension_error(
                    InstallJobErrorCode.INSTALL_EXTENSION_MISSING,
                    str(probe.get("message") or "Required nodes still missing."),
                    affectedFiles=list(probe.get("missing") or []),
                    recommendedAction="restart_comfyui",
                ),
                "raw": {**(current.raw or {}), "probe": probe, "capabilities": caps, "nodesReady": False},
            }
        )
        return _serialize(_persist_job(updated))

    if action in {"repair_dependencies", "retry", "retry_download"}:
        target = Path(current.destination or "")
        if target.is_dir():
            deps = install_extension_dependencies(target)
            if not deps.get("ok"):
                updated = current.model_copy(
                    update={
                        "state": InstallState.REPAIR_REQUIRED,
                        "message": deps.get("message") or "Dependency repair failed.",
                        "updated_at": _now(),
                        "error": extension_error(
                            InstallJobErrorCode.INSTALL_DEPENDENCY_FAILED,
                            str(deps.get("message") or "Dependency repair failed."),
                            recommendedAction="repair_dependencies",
                        ),
                        "raw": {**(current.raw or {}), "deps": deps},
                    }
                )
                return _serialize(_persist_job(updated))
        return _serialize(
            _start_comfy_extension_job(
                component_id,
                source_url=(current.source or {}).get("sourceUrl") or (current.source or {}).get("url"),
                install_path=str(Path(current.destination).parent) if current.destination else None,
                confirm_executable=True,
            )
        )

    if action == "open_diagnostics":
        return _serialize(
            current.model_copy(
                update={
                    "message": current.message or "Diagnostics available in install details.",
                    "updated_at": _now(),
                    "raw": {**(current.raw or {}), "diagnosticsOpen": True},
                }
            )
        )

    raise ValueError(f"Unsupported ComfyUI extension repair action: {action}")


def download_queue(*, active_only: bool | None = None, component_id: str | None = None) -> dict[str, Any]:
    jobs = list_jobs(active_only=bool(active_only))
    if component_id:
        jobs = [job for job in jobs if job.get("componentId") == component_id]
    return {"operations": jobs}


def install_history() -> dict[str, Any]:
    queue_history = list(history_entries())
    custom_entries = []
    for job in _load_custom_jobs():
        if job.active:
            continue
        custom_entries.append(
            {
                "id": job.id,
                "componentId": job.component_id,
                "version": None,
                "providerId": (job.source or {}).get("providerId"),
                "sourceId": (job.source or {}).get("sourceId"),
                "result": "passed" if job.state == InstallState.READY else "failed",
                "installedAt": job.completed_at or job.updated_at,
                "destinationSummary": str(Path(job.destination).name) if job.destination else "",
                "managed": True,
                "kind": job.kind,
                "fileCount": job.files_completed or 0,
                "totalSize": job.progress_bytes or 0,
                "verificationState": "passed" if job.state == InstallState.READY else None,
                "rollbackAvailable": False,
                "installJobId": job.id,
            }
        )
    entries = queue_history + custom_entries
    entries.sort(key=lambda item: str(item.get("installedAt") or ""), reverse=True)
    return {"entries": entries, "count": len(entries)}
