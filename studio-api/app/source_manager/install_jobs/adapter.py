from __future__ import annotations

from typing import Any

from ...setup.catalog import get_component
from ...source_manager.downloads.phases import is_terminal
from .errors import InstallJobError, InstallJobErrorCode, normalize_failure
from .schema import InstallJob, RecoveryAction
from .states import InstallState


_DOWNLOAD_PHASE_TO_STATE: dict[str, InstallState] = {
    "queued": InstallState.QUEUED,
    "preflighting": InstallState.PREPARING,
    "resolving": InstallState.PREPARING,
    "verifying_source": InstallState.PREPARING,
    "waiting_for_auth": InstallState.SOURCE_REQUIRED,
    "waiting_for_disk_space": InstallState.REPAIR_REQUIRED,
    "downloading": InstallState.DOWNLOADING,
    "pausing": InstallState.PAUSED,
    "paused": InstallState.PAUSED,
    "resuming": InstallState.DOWNLOADING,
    "extracting": InstallState.INSTALLING,
    "validating": InstallState.VERIFYING_INSTALL,
    "finalizing": InstallState.CONFIGURING,
    "cancelling": InstallState.CANCELLED,
    "installed": InstallState.READY,
    "failed": InstallState.FAILED,
    "cancelled": InstallState.CANCELLED,
    "interrupted": InstallState.REPAIR_REQUIRED,
    "rolled_back": InstallState.REPAIR_REQUIRED,
}

_SETUP_STATUS_TO_STATE: dict[str, InstallState] = {
    "queued": InstallState.QUEUED,
    "running": InstallState.PREPARING,
    "awaiting_checkpoint": InstallState.AWAITING_CONFIRMATION,
    "downloading": InstallState.DOWNLOADING,
    "extracting": InstallState.INSTALLING,
    "verifying": InstallState.VERIFYING_INSTALL,
    "configuring": InstallState.CONFIGURING,
    "completed": InstallState.READY,
    "failed": InstallState.FAILED,
    "cancelled": InstallState.CANCELLED,
    "interrupted": InstallState.REPAIR_REQUIRED,
}


def _download_recovery_actions(op: dict[str, Any]) -> list[RecoveryAction]:
    phase = str(op.get("phase") or "")
    caps = dict(op.get("capabilities") or {})
    actions: list[RecoveryAction] = []
    if phase == "downloading" and caps.get("canPause"):
        actions.append(
            RecoveryAction(
                action="pause",
                label="Pause download",
                description="Pause this download at the provider layer.",
            )
        )
    if phase in {"paused", "interrupted"}:
        actions.append(
            RecoveryAction(
                action="resume",
                label="Resume download",
                description="Resume this install from the existing queue state.",
                enabled=bool(phase == "interrupted" or caps.get("canResume")),
            )
        )
    if phase not in {"installed", "cancelled"}:
        actions.append(
            RecoveryAction(
                action="cancel",
                label="Cancel install",
                description="Cancel this queued or active install.",
            )
        )
    if phase in {"failed", "cancelled", "interrupted"}:
        actions.append(
            RecoveryAction(
                action="retry",
                label="Retry install",
                description="Create another queue attempt from the same plan.",
            )
        )
    return actions


def _setup_recovery_actions(op: dict[str, Any]) -> list[RecoveryAction]:
    status = str(op.get("status") or "")
    if status in {"failed", "interrupted"}:
        return [
            RecoveryAction(
                action="retry",
                label="Retry setup",
                description="Retry the install workflow from the beginning.",
            )
        ]
    if status == "awaiting_checkpoint":
        return [
            RecoveryAction(
                action="cancel",
                label="Cancel setup",
                description="Cancel this guided setup workflow.",
            )
        ]
    return []


def _normalize_progress(raw_progress: Any) -> dict[str, Any]:
    if isinstance(raw_progress, dict):
        return dict(raw_progress)
    if isinstance(raw_progress, (int, float)) and not isinstance(raw_progress, bool):
        percent = float(raw_progress)
        if percent <= 1.0:
            percent *= 100.0
        return {
            "bytesDownloaded": None,
            "bytesTotal": None,
            "percent": percent,
            "speedBytesPerSecond": None,
            "etaSeconds": None,
            "currentArtifact": None,
            "artifactsCompleted": 0,
            "artifactsTotal": 0,
        }
    return {}


def download_operation_to_install_job(op: dict[str, Any]) -> InstallJob:
    component = get_component(str(op.get("componentId") or ""))
    progress = _normalize_progress(op.get("progress"))
    phase = str(op.get("phase") or "queued")
    failure = normalize_failure(op.get("failure"))
    error = failure if phase == "failed" else None
    return InstallJob(
        id=str(op.get("id") or ""),
        componentId=component.id,
        componentName=component.name,
        state=_DOWNLOAD_PHASE_TO_STATE.get(phase, InstallState.PREPARING),
        kind="download_queue",
        phase=phase,
        message=str((op.get("failure") or {}).get("message") or phase.replace("_", " ").title()),
        progressBytes=progress.get("bytesDownloaded"),
        totalBytes=progress.get("bytesTotal"),
        percent=progress.get("percent"),
        indeterminate=progress.get("bytesTotal") in (None, 0),
        filesCompleted=progress.get("artifactsCompleted"),
        filesTotal=progress.get("artifactsTotal"),
        queuePosition=op.get("queuePosition"),
        active=not is_terminal(phase),
        terminal=is_terminal(phase),
        recoverable=bool(error.recoverable if error else phase in {"interrupted", "failed"}),
        capabilities=dict(op.get("capabilities") or {}),
        source={
            "sourceId": op.get("sourceId"),
            "providerId": op.get("providerId"),
            "installPlanId": op.get("installPlanId"),
        },
        destination=((op.get("paths") or {}).get("finalDestination")),
        createdAt=op.get("createdAt"),
        updatedAt=op.get("updatedAt"),
        completedAt=op.get("completedAt"),
        error=error,
        recoveryActions=_download_recovery_actions(op),
        raw=dict(op),
    )


def setup_operation_to_install_job(op: dict[str, Any]) -> InstallJob | None:
    component_ids = list(op.get("component_ids") or op.get("componentIds") or [])
    if len(component_ids) != 1:
        return None
    component = get_component(str(component_ids[0]))
    status = str(op.get("status") or "queued")
    phase = str(op.get("phase") or status)
    checkpoint = op.get("checkpoint") if isinstance(op.get("checkpoint"), dict) else None
    state = _SETUP_STATUS_TO_STATE.get(status, InstallState.PREPARING)
    if checkpoint and checkpoint.get("type") == "disk_space":
        state = InstallState.REPAIR_REQUIRED
    error: InstallJobError | None = None
    if status in {"failed", "interrupted"}:
        code = (
            InstallJobErrorCode.INTERRUPTED
            if status == "interrupted"
            else InstallJobErrorCode.INSTALL_FAILED
        )
        error = InstallJobError(
            code=code,
            message=str(op.get("error") or "Setup install failed."),
            recoverable=bool(op.get("recoverable", True)),
            phase=phase,
            recommendedAction="retry",
        )
    return InstallJob(
        id=str(op.get("operation_id") or op.get("id") or ""),
        componentId=component.id,
        componentName=component.name,
        state=state,
        kind="setup_operation",
        phase=phase,
        message=str(
            (checkpoint or {}).get("message")
            or (checkpoint or {}).get("summary")
            or op.get("stage")
            or phase.replace("_", " ").title()
        ),
        percent=float(op.get("progress") or 0.0) * 100.0 if op.get("progress") is not None else None,
        indeterminate=False,
        active=status not in {"completed", "failed", "cancelled", "interrupted"},
        terminal=status in {"completed", "failed", "cancelled", "interrupted"},
        recoverable=bool(op.get("recoverable", False)),
        source={"kind": op.get("kind"), "checkpoint": checkpoint},
        createdAt=op.get("created_at") or op.get("createdAt"),
        updatedAt=op.get("updated_at") or op.get("updatedAt"),
        error=error,
        recoveryActions=_setup_recovery_actions(op),
        raw=dict(op),
    )
