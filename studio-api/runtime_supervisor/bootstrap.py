"""Setup Wizard / Settings enable chain. Config first, task second."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .canonical_config import (
    ConfigurationError,
    RuntimeConfig,
    build_discovered_config,
    try_load_runtime_config,
    validate_runtime_config,
    write_runtime_config,
)
from .control_client import call_control, control_plane_reachable
from .paths import repo_root_from
from .windows_task import (
    PrivilegeRequired,
    list_legacy_owners,
    query_task,
    register_task,
    retire_legacy_tasks,
    start_task,
    task_exists,
    unregister_task,
)


@dataclass
class EnableReport:
    ok: bool
    message: str
    configPath: str = ""
    taskRegistered: bool = False
    needsElevation: bool = False
    legacyDetected: list[str] = field(default_factory=list)
    legacyRetired: list[str] = field(default_factory=list)
    serviceReady: bool = False
    comfyReady: bool = False
    apiReady: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "configPath": self.configPath,
            "taskRegistered": self.taskRegistered,
            "needsElevation": self.needsElevation,
            "legacyDetected": self.legacyDetected,
            "legacyRetired": self.legacyRetired,
            "serviceReady": self.serviceReady,
            "comfyReady": self.comfyReady,
            "apiReady": self.apiReady,
            "details": self.details,
        }


def _wait_ready(timeout_sec: float = 180.0) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        if control_plane_reachable():
            last = call_control("GET", "/status")
            comfy_state = str(last.get("comfyState") or "")
            api = last.get("studioApi") if isinstance(last.get("studioApi"), dict) else {}
            api_ready = str(api.get("health") or last.get("studioApiHealth") or "") in {"healthy", "ready"}
            if last.get("ok") and comfy_state in {"ready", "busy"} and api_ready:
                return last
            if last.get("ok") and comfy_state in {"ready", "busy"}:
                # Report independently; do not hide API truth while Comfy is ready.
                last.setdefault("studioApiReady", api_ready)
                if api_ready or time.time() + 2 >= deadline:
                    return last
        time.sleep(2)
    return last


def enable_recommended(
    *,
    start_with_windows: bool = True,
    repo_root: Path | None = None,
    wait: bool = True,
    retire_legacy: bool = True,
) -> EnableReport:
    root = repo_root or repo_root_from()
    legacy = list_legacy_owners()
    existing = try_load_runtime_config()
    discovered = build_discovered_config(repo_root=root)
    if existing:
        if not discovered.comfyRoot:
            discovered.comfyRoot = existing.comfyRoot
        if not discovered.comfyPython:
            discovered.comfyPython = existing.comfyPython
        if not discovered.modelRoot:
            discovered.modelRoot = existing.modelRoot
        if not discovered.modelFolders:
            discovered.modelFolders = existing.modelFolders
        if not discovered.servicePython:
            discovered.servicePython = existing.servicePython
        discovered.repoRoot = discovered.repoRoot or existing.repoRoot or str(root)
        if existing.studioApi.python:
            discovered.studioApi.python = existing.studioApi.python
        if existing.studioApi.appRoot:
            discovered.studioApi.appRoot = existing.studioApi.appRoot
        discovered.studioApi.enabled = existing.studioApi.enabled
        discovered.autostart = existing.autostart
    else:
        discovered.repoRoot = discovered.repoRoot or str(root)

    errors = validate_runtime_config(discovered)
    if errors:
        return EnableReport(
            ok=False,
            message="CONFIGURATION ERROR: " + "; ".join(errors),
            legacyDetected=legacy,
            details={"errors": errors},
        )

    try:
        path = write_runtime_config(discovered)
    except ConfigurationError as exc:
        return EnableReport(ok=False, message=str(exc), legacyDetected=legacy)

    if start_with_windows:
        try:
            register_task(discovered)
        except PrivilegeRequired as exc:
            return EnableReport(
                ok=False,
                message=str(exc),
                configPath=str(path),
                needsElevation=True,
                legacyDetected=legacy,
                details={"code": "PRIVILEGE_REQUIRED"},
            )
        except Exception as exc:
            return EnableReport(
                ok=False,
                message=str(exc),
                configPath=str(path),
                legacyDetected=legacy,
            )
    else:
        if task_exists():
            unregister_task()

    if start_with_windows:
        try:
            if not control_plane_reachable():
                start_task()
        except Exception as exc:
            return EnableReport(
                ok=False,
                message=str(exc),
                configPath=str(path),
                taskRegistered=task_exists(),
                legacyDetected=legacy,
            )

    status: dict[str, Any] = {}
    if wait and start_with_windows:
        status = _wait_ready()
    elif control_plane_reachable():
        status = call_control("GET", "/status")

    comfy_ready = str(status.get("comfyState") or "") in {"ready", "busy"}
    api_blob = status.get("studioApi") if isinstance(status.get("studioApi"), dict) else {}
    api_ready = str(api_blob.get("health") or status.get("studioApiHealth") or "") in {"healthy", "ready"}
    service_ready = bool(status.get("ok") or status.get("serviceState") == "running")
    retired: list[str] = []
    if retire_legacy and task_exists() and service_ready and (comfy_ready or api_ready):
        retired = retire_legacy_tasks()

    if start_with_windows and not comfy_ready:
        return EnableReport(
            ok=False,
            message=str(status.get("creatorMessage") or status.get("error") or "Runtime Service did not become Ready."),
            configPath=str(path),
            taskRegistered=task_exists(),
            legacyDetected=legacy,
            serviceReady=service_ready,
            comfyReady=False,
            apiReady=api_ready,
            details=status,
        )

    return EnableReport(
        ok=True,
        message="Background services are ready." if comfy_ready else "Runtime configuration saved.",
        configPath=str(path),
        taskRegistered=task_exists(),
        legacyDetected=legacy,
        legacyRetired=retired,
        serviceReady=service_ready or comfy_ready,
        comfyReady=comfy_ready,
        apiReady=api_ready,
        details=status,
    )


def repair_services(*, repo_root: Path | None = None) -> EnableReport:
    """Recreate config, scheduler, and PID records. Does not reinstall models."""
    root = repo_root or repo_root_from()
    existing = try_load_runtime_config()
    discovered = build_discovered_config(repo_root=root)
    if existing:
        if not discovered.comfyRoot:
            discovered.comfyRoot = existing.comfyRoot
        if not discovered.comfyPython:
            discovered.comfyPython = existing.comfyPython
        if not discovered.modelRoot:
            discovered.modelRoot = existing.modelRoot
        if not discovered.modelFolders:
            discovered.modelFolders = existing.modelFolders
        if not discovered.servicePython:
            discovered.servicePython = existing.servicePython
        discovered.repoRoot = discovered.repoRoot or existing.repoRoot or str(root)
        if existing.studioApi.python:
            discovered.studioApi.python = existing.studioApi.python
        if existing.studioApi.appRoot:
            discovered.studioApi.appRoot = existing.studioApi.appRoot
    else:
        discovered.repoRoot = discovered.repoRoot or str(root)
    errors = validate_runtime_config(discovered)
    if errors:
        return EnableReport(ok=False, message="CONFIGURATION ERROR: " + "; ".join(errors), details={"errors": errors})
    try:
        path = write_runtime_config(discovered)
    except ConfigurationError as exc:
        return EnableReport(ok=False, message=str(exc))
    try:
        register_task(discovered)
    except PrivilegeRequired as exc:
        return EnableReport(
            ok=False,
            message=str(exc),
            configPath=str(path),
            needsElevation=True,
            details={"code": "PRIVILEGE_REQUIRED"},
        )
    except Exception as exc:
        return EnableReport(ok=False, message=str(exc), configPath=str(path))
    if not control_plane_reachable():
        try:
            start_task()
        except Exception as exc:
            return EnableReport(ok=False, message=str(exc), configPath=str(path), taskRegistered=task_exists())
    if control_plane_reachable():
        call_control("POST", "/start")
        status = _wait_ready()
    else:
        status = {}
    comfy_ready = str(status.get("comfyState") or "") in {"ready", "busy"}
    api_blob = status.get("studioApi") if isinstance(status.get("studioApi"), dict) else {}
    api_ready = str(api_blob.get("health") or status.get("studioApiHealth") or "") in {"healthy", "ready"}
    return EnableReport(
        ok=bool(status.get("ok") or comfy_ready or api_ready),
        message="Background services repaired." if (comfy_ready or api_ready) else "Repair requested.",
        configPath=str(path),
        taskRegistered=task_exists(),
        serviceReady=bool(status.get("ok")),
        comfyReady=comfy_ready,
        apiReady=api_ready,
        details=status,
    )


def apply_start_with_windows(enabled: bool) -> dict[str, Any]:
    cfg = try_load_runtime_config()
    if enabled:
        if cfg is None:
            return {
                "ok": False,
                "startWithWindows": False,
                "taskRegistered": False,
                "message": "CONFIGURATION ERROR: set up Background Services before enabling Start with Windows.",
            }
        errors = validate_runtime_config(cfg)
        if errors:
            return {
                "ok": False,
                "startWithWindows": False,
                "taskRegistered": False,
                "message": "CONFIGURATION ERROR: " + "; ".join(errors),
            }
        try:
            register_task(cfg)
        except PrivilegeRequired as exc:
            return {
                "ok": False,
                "startWithWindows": False,
                "taskRegistered": False,
                "needsElevation": True,
                "message": str(exc),
            }
        return {"ok": True, "startWithWindows": True, "taskRegistered": True, "message": "AdeptRuntimeService registered."}
    unregister_task()
    return {
        "ok": True,
        "startWithWindows": False,
        "taskRegistered": False,
        "message": "AdeptRuntimeService unregistered.",
    }


def actual_start_with_windows() -> bool:
    return query_task().exists
