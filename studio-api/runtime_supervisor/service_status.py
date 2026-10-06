"""Creator-facing local runtime states. Hosted providers are a separate probe."""

from __future__ import annotations

from typing import Any

from .canonical_config import try_load_runtime_config
from .constants import API_PORT, COMFY_PORT
from .health import comfy_healthy, comfy_queue_running, studio_api_healthy
from .headless_comfy.service import status as headless_status
from .ports import port_owner_pid
from .windows_task import list_legacy_owners, query_task

SERVICE_NOT_CONFIGURED = "not_configured"
SERVICE_CONFIGURATION_ERROR = "configuration_error"
SERVICE_STARTING = "starting"
SERVICE_RUNNING = "running"
SERVICE_OFFLINE = "offline"

COMFY_STARTING = "starting"
COMFY_READY = "ready"
COMFY_BUSY = "busy"
COMFY_PORT_CONFLICT = "port_conflict"
COMFY_OFFLINE = "offline"
COMFY_CRASHED = "crashed"


def manager_is_running() -> bool:
    """True when the Background Services manager (this supervisor) is alive."""
    try:
        from .paths import repo_root_from
        from .process import process_alive
        from .state import SupervisorState

        rec = SupervisorState.from_env(repo_root_from()).read_pid("runtime_service")
        return bool(rec and rec.owned and rec.pid and process_alive(rec.pid))
    except Exception:
        return False


def probe_fal_connected() -> bool | None:
    """Best-effort hosted connectivity. Must never gate local Comfy readiness."""
    try:
        import os
        import urllib.request

        key = (os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY") or "").strip()
        if not key:
            return None
        req = urllib.request.Request(
            "https://api.fal.ai/v1/models",
            headers={"Authorization": f"Key {key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return 200 <= int(resp.status) < 500
    except Exception:
        return False


def collect_runtime_view(*, assume_local_api: bool = False) -> dict[str, Any]:
    cfg = try_load_runtime_config()
    task = query_task()
    legacy_owners = list_legacy_owners()
    try:
        headless = headless_status()
    except Exception as exc:
        headless = {"healthy": False, "ownership": "down", "error": str(exc)}
    healthy = bool(headless.get("healthy"))
    ownership = str(headless.get("ownership") or "down")
    queue = int(headless.get("queueRunning") or 0) if healthy else 0
    owned = bool(headless.get("owned"))
    comfy_pid = headless.get("pid") or port_owner_pid(COMFY_PORT)

    # Manager running (this view is served by it) means the unified fabric is up.
    # Start-with-Windows is a separate preference and must not mark a running,
    # configured service as "not_configured".
    if cfg is None:
        service_state = SERVICE_NOT_CONFIGURED
        creator = "Background services are not set up yet."
    elif healthy or manager_is_running():
        service_state = SERVICE_RUNNING
    elif not task.exists:
        service_state = SERVICE_NOT_CONFIGURED
        creator = "Start with Windows is not configured."
    else:
        service_state = SERVICE_RUNNING if healthy or task.running else SERVICE_STARTING

    if ownership == "reused" and healthy:
        # Healthy external Comfy (e.g. Comfy Desktop) reused — green, not a conflict.
        comfy_state = COMFY_BUSY if queue > 0 else COMFY_READY
        creator = (
            "The local image runtime is busy."
            if queue > 0
            else "Local image runtime is ready."
        )
        service_state = SERVICE_RUNNING
    elif ownership == "external" and (healthy or port_owner_pid(COMFY_PORT)):
        comfy_state = COMFY_PORT_CONFLICT
        creator = "Another image program is using the local picture engine. Adept will not take it over."
    elif healthy and queue > 0:
        comfy_state = COMFY_BUSY
        creator = "The local image runtime is busy."
        service_state = SERVICE_RUNNING
    elif healthy and owned:
        comfy_state = COMFY_READY
        creator = "Local image runtime is ready."
        service_state = SERVICE_RUNNING
    elif service_state == SERVICE_STARTING or (task.exists and not healthy):
        comfy_state = COMFY_STARTING
        if cfg is None:
            comfy_state = COMFY_OFFLINE
        else:
            creator = "Preparing Qwen Image Edit…"
    elif cfg is None:
        comfy_state = COMFY_OFFLINE
        creator = "Background services are not set up yet."
    else:
        comfy_state = COMFY_OFFLINE
        creator = (
            "The local image runtime is offline. Pictures already made stay as they are. "
            "Start Background Services to make new Side, 3/4, or Back views."
        )

    fal = None if assume_local_api else probe_fal_connected()
    api_child: dict[str, Any] = {}
    try:
        from .studio_api_child import child_view

        api_child = child_view(assume_healthy=assume_local_api)
    except Exception as exc:
        api_child = {"health": "unknown", "error": str(exc), "port": API_PORT}
    api_healthy = True if assume_local_api else bool(studio_api_healthy())
    manager_pid = None
    try:
        from .paths import repo_root_from
        from .state import SupervisorState

        rec = SupervisorState.from_env(repo_root_from()).read_pid("runtime_service")
        if rec and rec.owned:
            manager_pid = rec.pid
    except Exception:
        manager_pid = None

    return {
        "configured": cfg is not None,
        "taskRegistered": task.exists,
        "startWithWindows": task.exists,
        "windowsStartupPresent": bool(task.exists or legacy_owners),
        "legacyOwners": legacy_owners,
        "serviceState": service_state,
        "comfyState": comfy_state,
        "worker": "busy" if comfy_state == COMFY_BUSY else ("qwen_ready" if comfy_state == COMFY_READY else "idle"),
        "falConnected": fal,
        "creatorMessage": creator,
        "comfyPid": comfy_pid,
        "owned": owned,
        "ownership": ownership,
        "queueRunning": queue,
        "controlPort": int(cfg.controlPort) if cfg else None,
        "headless": headless,
        "healthy": healthy,
        "comfyHealthy": comfy_healthy(),
        "managerPid": manager_pid,
        "studioApi": api_child,
        "studioApiPid": api_child.get("pid"),
        "studioApiOwned": bool(api_child.get("owned")),
        "studioApiHealth": api_child.get("health") or ("healthy" if api_healthy else "offline"),
        "studioApiStartedAt": api_child.get("startedAt"),
        "comfyStartedAt": (headless.get("record") or {}).get("startedAt") if isinstance(headless.get("record"), dict) else None,
    }
