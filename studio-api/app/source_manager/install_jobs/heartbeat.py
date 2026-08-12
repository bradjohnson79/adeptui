from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .states import InstallState

StallStatus = Literal["none", "possible_stall", "interrupted", "waiting_for_source"]

_DEFAULT_STALL_SECONDS = 120
_COMPONENT_STALL_SECONDS: dict[str, int] = {
    "index_tts2": 600,
    "pack_essential_photoreal": 300,
    "qwen3_tts": 300,
    "qwen_voice": 300,
}
_LARGE_COMPONENT_PREFIXES = ("hunyuan", "qwen", "pack_", "index_tts")

_ACTIVE_PROGRESS_STATES = {
    InstallState.QUEUED,
    InstallState.PREPARING,
    InstallState.DOWNLOADING,
    InstallState.VERIFYING_DOWNLOAD,
    InstallState.INSTALLING,
    InstallState.CONFIGURING,
    InstallState.VERIFYING_INSTALL,
}


class InstallHeartbeat(BaseModel):
    job_id: str = Field(alias="jobId")
    last_progress_at: str = Field(alias="lastProgressAt")
    last_bytes_downloaded: int | None = Field(default=None, alias="lastBytesDownloaded")
    last_phase_change_at: str = Field(alias="lastPhaseChangeAt")
    worker_alive: bool = Field(alias="workerAlive")
    network_active: bool | None = Field(default=None, alias="networkActive")

    model_config = {"populate_by_name": True}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def stall_threshold_seconds(component_id: str | None) -> int:
    cid = str(component_id or "").strip().lower()
    if cid in _COMPONENT_STALL_SECONDS:
        return _COMPONENT_STALL_SECONDS[cid]
    if any(cid.startswith(prefix) for prefix in _LARGE_COMPONENT_PREFIXES):
        return 300
    if "comfy" in cid or "extension" in cid or "custom_node" in cid:
        return 90
    return _DEFAULT_STALL_SECONDS


def build_heartbeat(
    *,
    job_id: str,
    previous: InstallHeartbeat | dict[str, Any] | None,
    bytes_downloaded: int | None,
    phase: str | None,
    previous_phase: str | None,
    worker_alive: bool,
    network_active: bool | None = None,
    now: str | None = None,
) -> InstallHeartbeat:
    stamp = now or _now()
    prev = InstallHeartbeat.model_validate(previous) if isinstance(previous, dict) else previous

    last_progress = prev.last_progress_at if prev else stamp
    last_bytes = prev.last_bytes_downloaded if prev else None
    last_phase_at = prev.last_phase_change_at if prev else stamp

    phase_changed = previous_phase is not None and phase is not None and phase != previous_phase
    if prev is None:
        phase_changed = True

    bytes_advanced = False
    if bytes_downloaded is not None:
        if last_bytes is None:
            bytes_advanced = int(bytes_downloaded) > 0
        else:
            bytes_advanced = int(bytes_downloaded) > int(last_bytes)

    if phase_changed:
        last_phase_at = stamp
    if bytes_advanced or phase_changed:
        last_progress = stamp
    if bytes_downloaded is not None:
        last_bytes = int(bytes_downloaded)

    return InstallHeartbeat(
        jobId=job_id,
        lastProgressAt=last_progress,
        lastBytesDownloaded=last_bytes,
        lastPhaseChangeAt=last_phase_at,
        workerAlive=bool(worker_alive),
        networkActive=network_active,
    )


def evaluate_stall(
    *,
    state: InstallState | str,
    component_id: str | None,
    heartbeat: InstallHeartbeat | dict[str, Any] | None,
    now: datetime | None = None,
) -> StallStatus:
    try:
        install_state = state if isinstance(state, InstallState) else InstallState(str(state))
    except ValueError:
        return "none"
    if install_state not in _ACTIVE_PROGRESS_STATES:
        return "none"
    if heartbeat is None:
        return "none"
    hb = InstallHeartbeat.model_validate(heartbeat) if isinstance(heartbeat, dict) else heartbeat
    if not hb.worker_alive:
        return "interrupted"

    current = now or datetime.now(timezone.utc)
    last_progress = _parse_ts(hb.last_progress_at) or current
    quiet_for = (current - last_progress).total_seconds()
    threshold = stall_threshold_seconds(component_id)
    if quiet_for < threshold:
        return "none"
    if hb.network_active is True and hb.worker_alive:
        return "waiting_for_source"
    return "possible_stall"


def stall_recovery_actions(stall_status: StallStatus) -> list[dict[str, Any]]:
    if stall_status == "none":
        return []
    return [
        {
            "action": "retry_connection",
            "label": "Retry Connection",
            "description": "Retry the network connection for this install.",
            "enabled": True,
            "destructive": False,
        },
        {
            "action": "resume",
            "label": "Resume",
            "description": "Resume the install if it was paused or interrupted.",
            "enabled": True,
            "destructive": False,
        },
        {
            "action": "restart_worker",
            "label": "Restart Worker",
            "description": "Restart the install worker for this component.",
            "enabled": True,
            "destructive": False,
        },
        {
            "action": "open_diagnostics",
            "label": "Open Diagnostics",
            "description": "Open technical diagnostics for this install job.",
            "enabled": True,
            "destructive": False,
        },
        {
            "action": "cancel_safely",
            "label": "Cancel Safely",
            "description": "Cancel this install without leaving a corrupt ready state.",
            "enabled": True,
            "destructive": True,
        },
    ]


def stall_label(stall_status: StallStatus) -> str | None:
    return {
        "possible_stall": "Possible Stall",
        "interrupted": "Interrupted",
        "waiting_for_source": "Waiting for Source",
        "none": None,
    }.get(stall_status)


def touch_heartbeat_from_job(
    *,
    job_id: str,
    component_id: str | None,
    state: InstallState | str,
    phase: str | None,
    previous_phase: str | None,
    bytes_downloaded: int | None,
    previous_heartbeat: InstallHeartbeat | dict[str, Any] | None,
    worker_alive: bool,
    network_active: bool | None = None,
) -> tuple[InstallHeartbeat, StallStatus]:
    hb = build_heartbeat(
        job_id=job_id,
        previous=previous_heartbeat,
        bytes_downloaded=bytes_downloaded,
        phase=phase,
        previous_phase=previous_phase,
        worker_alive=worker_alive,
        network_active=network_active,
    )
    status = evaluate_stall(state=state, component_id=component_id, heartbeat=hb)
    return hb, status
