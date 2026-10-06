"""Single entry: ensure Studio API :8758 is healthy and owned when possible.

Law:
- detect port/process/health -> reuse healthy / start if offline / recover owned
- no duplicate spawns; owned may restart; external healthy = PORT_CONFLICT (no kill)
- Harden Unified Runtime Fabric; do not invent a parallel launcher
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_config import default_log_dir
from .env import load_beta_env
from .constants import API_PORT, API_READY_TIMEOUT_SEC, CONTROL_PORT, TASK_NAME
from .control_client import call_control, control_plane_reachable
from .health import studio_api_healthy
from .identity import classify_api_port
from .paths import discover_paths
from .ports import port_owner_pid
from .state import SupervisorState
from .process import process_alive
from .studio_api_child import child_view, classify_owned_listener, start_studio_api_child
from .windows_task import start_task, task_exists

ENSURE_LOG_NAME = "studio-api-ensure.log"
PORT_CONFLICT = "PORT_CONFLICT"


def _ensure_log_path() -> Path:
    root = default_log_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / ENSURE_LOG_NAME


def _log_attempt(action: str, ok: bool, message: str, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "ok": bool(ok),
        "message": message,
        "pids": {
            "api": port_owner_pid(API_PORT),
            "control": port_owner_pid(CONTROL_PORT),
            "self": os.getpid(),
        },
    }
    payload.update(extra)
    try:
        with _ensure_log_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except OSError:
        pass


def _we_own_control_plane() -> bool:
    owner = port_owner_pid(CONTROL_PORT)
    return bool(owner and owner == os.getpid())


def _wait_healthy(timeout_sec: float) -> bool:
    deadline = time.time() + max(1.0, float(timeout_sec))
    while time.time() < deadline:
        if studio_api_healthy():
            return True
        time.sleep(2.0)
    return studio_api_healthy()


def _wait_control_plane(timeout_sec: float = 90.0) -> bool:
    deadline = time.time() + max(1.0, float(timeout_sec))
    while time.time() < deadline:
        if control_plane_reachable():
            return True
        time.sleep(1.0)
    return control_plane_reachable()


def _has_port_conflict(msg: str) -> bool:
    return PORT_CONFLICT in (msg or "")


def _result(
    ok: bool,
    *,
    action: str,
    code: str = "",
    message: str = "",
    **extra: Any,
) -> dict[str, Any]:
    view = child_view()
    body: dict[str, Any] = {
        "ok": bool(ok),
        "action": action,
        "code": code or ("READY" if ok else "FAILED"),
        "message": message,
        "port": API_PORT,
        "pid": view.get("pid") or port_owner_pid(API_PORT),
        "apiStartedAt": view.get("startedAt") or "",
        "health": "healthy" if studio_api_healthy() else "offline",
        "controlPlane": control_plane_reachable(),
        "taskExists": task_exists(TASK_NAME),
        "logPath": str(_ensure_log_path()),
    }
    body.update(extra)
    _log_attempt(action, ok, message, code=body["code"], resultPid=body.get("pid"))
    return body


def _start_via_inprocess(allow_migrate: bool, ready_timeout_sec: float) -> dict[str, Any]:
    paths = discover_paths()
    state = SupervisorState.from_env(paths.repo_root)
    started = start_studio_api_child(paths, state, spawn=True, allow_migrate=allow_migrate)
    if started.ok and (studio_api_healthy() or _wait_healthy(ready_timeout_sec)):
        return _result(
            True,
            action="start_inprocess",
            code="READY",
            message=started.message,
            ownership=started.ownership,
            pid=started.pid,
        )
    msg = started.message or "in-process start failed"
    code = PORT_CONFLICT if _has_port_conflict(msg) else "START_FAILED"
    return _result(
        False,
        action="start_inprocess",
        code=code,
        message=msg,
        ownership=getattr(started, "ownership", "owned"),
        pid=started.pid,
    )


def _start_via_control(ready_timeout_sec: float) -> dict[str, Any]:
    remote = call_control("POST", "/start-api", timeout=max(30.0, min(float(ready_timeout_sec), 180.0)))
    if (remote.get("ok") and studio_api_healthy()) or _wait_healthy(ready_timeout_sec):
        return _result(
            True,
            action="start_control",
            code="READY",
            message=str(remote.get("message") or "control /start-api ok"),
            remoteOk=bool(remote.get("ok")),
        )
    msg = str(remote.get("message") or remote.get("error") or "control /start-api failed")
    code = PORT_CONFLICT if _has_port_conflict(msg) else "START_FAILED"
    return _result(False, action="start_control", code=code, message=msg, remote=remote)



def _control_listener_pid() -> int | None:
    """TCP listener on control port — independent of HTTP reachability."""
    return port_owner_pid(CONTROL_PORT)


def _spawn_user_serve() -> subprocess.Popen[bytes]:
    """Start runtime_supervisor serve as the current user (no schtasks / no elevation)."""
    from .canonical_config import load_runtime_config, try_load_runtime_config
    from .windows_task import _serve_launch

    cfg = try_load_runtime_config() or load_runtime_config()
    py, cwd_hint = _serve_launch(cfg)
    # Prefer console python for child logs when pythonw was selected for tasks
    if py.name.lower() == "pythonw.exe":
        alt = py.with_name("python.exe")
        if alt.is_file():
            py = alt
    log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    out_f = open(log_dir / "serve-user-spawn-stdout.log", "ab")
    err_f = open(log_dir / "serve-user-spawn-stderr.log", "ab")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    from .paths import discover_paths as _dp_serve
    load_beta_env(_dp_serve().repo_root)
    os.environ.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    return subprocess.Popen(
        [str(py), "-m", "runtime_supervisor", "serve"],
        cwd=str(cwd_hint),
        stdout=out_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def ensure_studio_api_running(
    *,
    ready_timeout_sec: float | None = None,
    allow_start_task: bool = False,  # optional/deferred Windows task; never required for READY
    allow_migrate: bool = True,
) -> dict[str, Any]:
    """Ensure :8758 is healthy. Returns a JSON-serializable status dict."""
    try:
        from .paths import discover_paths as _discover_paths_for_env
        load_beta_env(_discover_paths_for_env().repo_root)
    except Exception:
        pass
    timeout = float(API_READY_TIMEOUT_SEC if ready_timeout_sec is None else ready_timeout_sec)
    _log_attempt(
        "ensure_begin",
        True,
        "begin",
        ready_timeout_sec=timeout,
        allow_start_task=allow_start_task,
        allow_migrate=allow_migrate,
    )

    # 1) Healthy -> reuse (no spawn)
    if studio_api_healthy():
        paths = discover_paths()
        state = SupervisorState.from_env(paths.repo_root)
        st, role = classify_owned_listener(state)
        return _result(
            True,
            action="reuse",
            code="READY",
            message=f"already healthy — role={role} pid={st.pid}",
            role=role,
            pid=st.pid,
        )

    # 2) Port classification — foreign healthy = PORT_CONFLICT, never blind-kill
    st = classify_api_port()
    paths = discover_paths()
    state = SupervisorState.from_env(paths.repo_root)
    _, role = classify_owned_listener(state)
    if st.state == "healthy" and role == "foreign":
        return _result(
            False,
            action="conflict",
            code=PORT_CONFLICT,
            message=f"{PORT_CONFLICT}: :{API_PORT} healthy foreign PID {st.pid} — will not kill",
            pid=st.pid,
            role=role,
        )
    if st.state == "healthy" and role == "known-adept" and not allow_migrate:
        return _result(
            False,
            action="conflict",
            code=PORT_CONFLICT,
            message=f"{PORT_CONFLICT}: :{API_PORT} known-adept PID {st.pid} — migrate disabled",
            pid=st.pid,
            role=role,
        )
    if st.state in ("phantom", "unrelated"):
        return _result(
            False,
            action="conflict",
            code="FAIL_CLOSED" if st.state == "phantom" else PORT_CONFLICT,
            message=f"{st.state}: :{API_PORT} PID {st.pid} — ensure will not blind-kill",
            pid=st.pid,
            role=role,
        )

    # 2b) Owned/known start already in flight (serve watchdog may block control HTTP) — wait
    rec = state.read_pid("studio_api")
    owned_starting = bool(
        rec
        and rec.owned
        and rec.pid
        and (
            st.state == "starting"
            or role in {"owned", "stale-owned", "known-adept"}
            or (st.state == "free" and process_alive(rec.pid))
        )
    )
    if owned_starting or st.state == "starting":
        wait_pid = st.pid or (rec.pid if rec else None)
        _log_attempt("wait_starting", True, f"waiting for starting role={role} pid={wait_pid}")
        if _wait_healthy(timeout):
            return _result(
                True,
                action="wait_starting",
                code="READY",
                message=f"became healthy while starting — role={role} pid={port_owner_pid(API_PORT)}",
                role=role,
            )

    # 3) Control plane: listener and/or HTTP
    # Law: if :8759 already has a TCP listener, NEVER schtasks /Run / start_task.
    # If WE own the control listener (serve boot ensure), start API in-process
    # WITHOUT requiring HTTP /status first — otherwise boot deadlocks: main thread
    # waits on reachable while /status is slow/blocked during the same ensure.
    ctrl_pid = _control_listener_pid()
    if _we_own_control_plane():
        return _start_via_inprocess(allow_migrate=allow_migrate, ready_timeout_sec=timeout)

    if ctrl_pid or control_plane_reachable() or _wait_control_plane(min(20.0, timeout)):
        ctrl_pid = _control_listener_pid() or ctrl_pid
        if control_plane_reachable():
            return _start_via_control(ready_timeout_sec=timeout)
        # Foreign/other listener up but HTTP down (serve blocked in ready-wait).
        # Wait the FULL ready timeout for API — NEVER start_task / second serve.
        _log_attempt(
            "control_listener_wait",
            True,
            f"control listener pid={ctrl_pid} HTTP down — waiting up to {timeout}s (no start_task)",
        )
        st_busy = classify_api_port()
        if st_busy.state in {"starting", "healthy"} or port_owner_pid(API_PORT):
            if _wait_healthy(timeout):
                return _result(
                    True,
                    action="wait_starting",
                    code="READY",
                    message=f"API healthy under existing control listener={ctrl_pid} pid={port_owner_pid(API_PORT)}",
                )
        if _wait_healthy(timeout):
            return _result(
                True,
                action="wait_starting",
                code="READY",
                message=f"API healthy while control HTTP down — listener={ctrl_pid}",
            )
        if control_plane_reachable() or _wait_control_plane(min(30.0, timeout)):
            return _start_via_control(ready_timeout_sec=timeout)
        return _result(
            False,
            action="control_busy",
            code="CONTROL_BUSY",
            message=(
                f"control :{CONTROL_PORT} has listener pid={ctrl_pid} but HTTP stayed unreachable "
                f"and API did not become healthy within {timeout}s; "
                "refusing Windows task start to avoid a second serve. Retry ensure-api."
            ),
        )

    # 4) Optional deferred Windows task — ONLY when no control listener and explicitly allowed.
    # AdeptRuntimeService is parked/optional; product READY must not depend on it.
    if allow_start_task and task_exists(TASK_NAME) and not _control_listener_pid():
        try:
            start_task(TASK_NAME)
        except Exception as exc:  # noqa: BLE001
            return _result(
                False,
                action="start_task",
                code="TASK_START_FAILED",
                message=f"AdeptRuntimeService start failed: {exc}",
            )
        _log_attempt("start_task", True, f"started {TASK_NAME} (explicit allow_start_task)")
        if not _wait_control_plane(90.0):
            return _result(
                False,
                action="start_task",
                code="CONTROL_TIMEOUT",
                message="AdeptRuntimeService started but control plane :8759 did not become reachable",
            )
        if studio_api_healthy():
            return _result(True, action="start_task", code="READY", message="API healthy after task start")
        return _start_via_control(ready_timeout_sec=timeout)

    # 5) In-process only when we own the control plane process
    if _we_own_control_plane():
        try:
            return _start_via_inprocess(allow_migrate=allow_migrate, ready_timeout_sec=timeout)
        except Exception as exc:  # noqa: BLE001
            return _result(False, action="start_inprocess", code="START_FAILED", message=str(exc))

    # 6) Both planes down: spawn serve as current user (Python only — no PowerShell, no schtasks)
    if not _control_listener_pid() and not port_owner_pid(API_PORT):
        try:
            proc = _spawn_user_serve()
            _log_attempt("spawn_user_serve", True, f"spawned serve pid={proc.pid}")
        except Exception as exc:  # noqa: BLE001
            return _result(
                False,
                action="spawn_user_serve",
                code="SERVE_SPAWN_FAILED",
                message=f"failed to spawn runtime_supervisor serve as current user: {exc}",
            )
        if not _wait_control_plane(max(120.0, float(API_READY_TIMEOUT_SEC))):
            return _result(
                False,
                action="spawn_user_serve",
                code="CONTROL_TIMEOUT",
                message=f"user-level serve spawned (pid={proc.pid}) but :{CONTROL_PORT} not reachable",
            )
        if studio_api_healthy() or _wait_healthy(timeout):
            return _result(
                True,
                action="spawn_user_serve",
                code="READY",
                message=f"API healthy after user-level serve pid={proc.pid}",
            )
        return _start_via_control(ready_timeout_sec=timeout)

    # 7) Last chance: owned/starting API — wait out ready timeout
    st2 = classify_api_port()
    paths = discover_paths()
    state = SupervisorState.from_env(paths.repo_root)
    rec2 = None
    try:
        rec2 = state.read_pid("studio_api")
    except Exception:
        rec2 = None
    if (
        studio_api_healthy()
        or st2.state in {"starting", "healthy"}
        or (rec2 and getattr(rec2, "owned", False) and getattr(rec2, "pid", None) and process_alive(rec2.pid))
    ):
        if _wait_healthy(timeout):
            return _result(
                True,
                action="wait_starting",
                code="READY",
                message=f"recovered pid={port_owner_pid(API_PORT)}",
            )

    # 8) Clear user-level guidance (Windows task optional/deferred — not required for READY)
    ctrl_pid = _control_listener_pid()
    if ctrl_pid:
        return _result(
            False,
            action="control_busy",
            code="CONTROL_BUSY",
            message=(
                f"control :{CONTROL_PORT} listener pid={ctrl_pid} present but API not ready; "
                "retry: python scripts\\run_runtime_supervisor.py ensure-api"
            ),
        )
    return _result(
        False,
        action="serve_required",
        code="SERVE_REQUIRED",
        message=(
            "Studio API offline and no control plane. Start user-level fabric: "
            "python scripts\\run_runtime_supervisor.py ensure-api "
            "or python scripts\\run_runtime_supervisor.py serve. "
            "AdeptRuntimeService Windows task is optional/deferred (not required for READY)."
        ),
    )



# Docs / FE-friendly camelCase alias
ensureStudioApiRunning = ensure_studio_api_running

__all__ = ["ensure_studio_api_running", "ensureStudioApiRunning"]
