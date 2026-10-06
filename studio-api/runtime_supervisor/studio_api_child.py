"""Owned Studio API child of Adept Background Services.

Stale-PID contract:
- Record the :8758 listener PID after bind, not the venv shim.
- Stop inspects :8758 if the recorded PID is gone.
- Never adopt a foreign listener. Healthy unknown :8758 is PORT_CONFLICT.
- Owner-authorized migration may stop a proven Adept uvicorn leftover.
- Spawn uses CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP. No DETACHED_PROCESS.
- Command: python -m uvicorn app.main:app --host 127.0.0.1 --port 8758 (no --workers 1).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .canonical_config import default_log_dir, try_load_runtime_config
from .constants import API_PORT, API_READY_TIMEOUT_SEC, PORT_RELEASE_TIMEOUT_SEC
from .health import studio_api_healthy
from .identity import PortState, classify_api_port
from .paths import RuntimePaths
from .env import load_beta_env
from .ports import port_owner_pid, wait_port_released
from .process import (
    is_studio_api_command,
    kill_process_tree,
    process_alive,
    process_command_line,
    process_image_name,
    process_parent_pid,
)
from .state import SupervisorState

SERVICE = "studio_api"
PORT_CONFLICT = "PORT_CONFLICT"


class PortConflict(RuntimeError):
    def __init__(self, message: str, pid: int | None = None):
        super().__init__(message)
        self.pid = pid
        self.code = PORT_CONFLICT


def _result(ok: bool, message: str, pid: int | None = None, ownership: str = "external"):
    from .services import ServiceResult

    return ServiceResult(SERVICE, ok, message, pid, ownership)


def studio_api_log_paths(log_dir: Path | None = None) -> tuple[Path, Path]:
    root = Path(log_dir) if log_dir else default_log_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / "studio-api.log", root / "studio-api.error.log"


def _rotate_if_huge(path: Path, limit_bytes: int = 8_000_000) -> None:
    if path.is_file() and path.stat().st_size >= limit_bytes:
        rotated = path.with_suffix(path.suffix + ".1")
        try:
            if rotated.exists():
                rotated.unlink()
            path.replace(rotated)
        except OSError:
            pass


def resolve_studio_api_launch(paths: RuntimePaths) -> tuple[Path | None, Path, int]:
    cfg = try_load_runtime_config()
    repo = Path(cfg.repoRoot) if cfg and cfg.repoRoot else paths.repo_root
    python = paths.studio_api_python
    app_root = paths.studio_api_dir
    port = API_PORT
    if cfg and cfg.studioApi.python:
        configured = Path(cfg.studioApi.python)
        if configured.is_file():
            python = configured
    if python is None or not Path(python).is_file():
        win = repo / "studio-api" / ".venv" / "Scripts" / "python.exe"
        nix = repo / "studio-api" / ".venv" / "bin" / "python"
        if win.is_file():
            python = win
        elif nix.is_file():
            python = nix
    if cfg and cfg.studioApi.appRoot:
        configured_app = Path(cfg.studioApi.appRoot)
        if configured_app.is_dir():
            app_root = configured_app
    if not app_root or not Path(app_root).is_dir():
        candidate = repo / "studio-api"
        if candidate.is_dir():
            app_root = candidate
    if cfg and cfg.studioApi.port:
        port = int(cfg.studioApi.port)
    return (Path(python) if python else None), Path(app_root), port


def is_known_adept_uvicorn(cmd: str, *, port: int = API_PORT) -> bool:
    if not is_studio_api_command(cmd):
        return False
    lower = (cmd or "").lower()
    return str(port) in lower or f"--port {port}" in lower or f"--port={port}" in lower or not (
        "--port" in lower
    )


def verify_studio_api_identity(pid: int, *, port: int = API_PORT) -> bool:
    if not process_alive(pid):
        return False
    cmd = process_command_line(pid)
    if is_known_adept_uvicorn(cmd, port=port):
        return True
    owner = port_owner_pid(port)
    return bool(owner == pid and is_studio_api_command(cmd))


def _comfy_pid() -> int | None:
    try:
        from .headless_comfy.service import status as headless_status

        pid = headless_status().get("pid")
        return int(pid) if pid else None
    except Exception:
        return port_owner_pid(8188)


def _write_child(
    state: SupervisorState,
    pid: int,
    cmd: str,
    *,
    owned: bool,
    reason: str = "",
    executable: str = "",
    cwd: str = "",
    log_path: str = "",
    health: str = "",
    child_state: str = "",
    last_exit: str = "",
    bump_restart: bool = False,
) -> None:
    prev = state.read_pid(SERVICE)
    restart_count = int(prev.restart_count) if prev else 0
    if bump_restart:
        restart_count += 1
    started = prev.started_at if prev and prev.pid == pid and prev.started_at else ""
    state.write_pid(
        SERVICE,
        pid,
        cmd,
        owned,
        started_at=started,
        last_exit=last_exit or (prev.last_exit if prev else ""),
        restart_count=restart_count,
        last_restart_reason=reason or (prev.last_restart_reason if prev else ""),
        executable=executable or process_image_name(pid),
        cwd=cwd,
        log_path=log_path or (prev.log_path if prev else ""),
        health=health,
        state=child_state,
    )


def classify_owned_listener(
    state: SupervisorState,
    *,
    classify_fn: Callable[[], PortState] | None = None,
    port: int = API_PORT,
) -> tuple[PortState, str]:
    """Return (port state, role) where role is owned|stale-owned|known-adept|foreign|free."""
    st = (classify_fn or classify_api_port)()
    rec = state.read_pid(SERVICE)
    if st.state == "free" or not st.pid:
        return st, "free"
    if rec and rec.owned and rec.pid == st.pid and verify_studio_api_identity(st.pid, port=port):
        return st, "owned"
    if rec and rec.owned and not process_alive(rec.pid) and is_known_adept_uvicorn(st.cmd, port=port):
        return st, "stale-owned"
    if rec and rec.owned and process_alive(rec.pid) and rec.pid != st.pid:
        if process_parent_pid(st.pid) == rec.pid and is_known_adept_uvicorn(st.cmd, port=port):
            return st, "stale-owned"
    if is_known_adept_uvicorn(st.cmd, port=port):
        return st, "known-adept"
    return st, "foreign"


def _spawn_studio_api(python: Path, app_root: Path, port: int, stdout: Path, stderr: Path, *, env: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
    stdout.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_huge(stdout)
    _rotate_if_huge(stderr)
    out_f = open(stdout, "ab")
    err_f = open(stderr, "ab")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    return subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(app_root),
        stdout=out_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=creationflags,
        close_fds=True,
    )


def start_studio_api_child(
    paths: RuntimePaths,
    state: SupervisorState,
    *,
    classify_fn=None,
    healthy_fn=None,
    spawn: bool = True,
    allow_migrate: bool = False,
) -> Any:
    classify_fn = classify_fn or classify_api_port
    healthy_fn = healthy_fn or studio_api_healthy
    python, app_root, port = resolve_studio_api_launch(paths)
    if port != API_PORT:
        return _result(False, f"CONFIGURATION ERROR: studioApi.port must be {API_PORT}", None, "external")
    if not python or not python.is_file():
        return _result(False, "CONFIGURATION ERROR: Studio API python not found", None, "external")
    if not app_root.is_dir():
        return _result(False, f"CONFIGURATION ERROR: Studio API appRoot missing: {app_root}", None, "external")

    st, role = classify_owned_listener(state, classify_fn=classify_fn, port=port)
    if role == "owned":
        _write_child(state, st.pid or 0, st.cmd or "uvicorn app.main:app", owned=True, health="healthy", child_state="running")
        return _result(True, f"already owned — PID {st.pid}", st.pid, "owned")
    if role == "stale-owned" and st.pid:
        _write_child(
            state,
            st.pid,
            st.cmd or "uvicorn app.main:app",
            owned=True,
            reason="reconcile-listener",
            health="healthy" if healthy_fn() else "starting",
            child_state="running",
        )
        return _result(True, f"reconciled listener PID {st.pid}", st.pid, "owned")
    if st.state == "healthy" and role in {"known-adept", "foreign"}:
        if allow_migrate and role == "known-adept" and st.pid:
            stopped = stop_studio_api_child(state, force=False, allow_migrate=True, classify_fn=classify_fn)
            if not stopped.ok:
                return _result(False, f"{PORT_CONFLICT}: migrate failed — {stopped.message}", st.pid, "external")
        else:
            return _result(
                False,
                f"{PORT_CONFLICT}: :{port} owned by PID {st.pid} ({role})",
                st.pid,
                "external",
            )
    if st.state == "starting" and st.pid:
        deadline = time.time() + API_READY_TIMEOUT_SEC
        while time.time() < deadline:
            time.sleep(2)
            if healthy_fn():
                now, now_role = classify_owned_listener(state, classify_fn=classify_fn, port=port)
                if now_role in {"owned", "stale-owned"} and now.pid:
                    _write_child(state, now.pid, now.cmd, owned=True, health="healthy", child_state="running")
                    return _result(True, f"healthy PID {now.pid}", now.pid, "owned")
                return _result(False, f"{PORT_CONFLICT}: starter became unknown PID {now.pid}", now.pid, "external")
            now = classify_fn()
            if now.state == "free":
                return start_studio_api_child(
                    paths,
                    state,
                    classify_fn=classify_fn,
                    healthy_fn=healthy_fn,
                    spawn=spawn,
                    allow_migrate=allow_migrate,
                )
            if now.state in ("phantom", "unrelated"):
                from .services import LifecycleError

                raise LifecycleError(f"FAIL CLOSED: starter replaced by {now.state} PID {now.pid}")
        return _result(False, f"uvicorn PID {st.pid} did not become healthy in {API_READY_TIMEOUT_SEC}s", st.pid, "external")
    if st.state == "phantom":
        from .services import LifecycleError

        raise LifecycleError(
            f"FAIL CLOSED: :{port} owned by PHANTOM PID {st.pid}. "
            f"Run: taskkill /F /PID {st.pid} (elevated) or reboot."
        )
    if st.state == "unrelated":
        from .services import LifecycleError

        raise LifecycleError(
            f"{PORT_CONFLICT}: :{port} owned by unrelated process PID {st.pid}. Do not kill arbitrary processes."
        )
    if not spawn:
        return _result(False, "port free — spawn disabled (test)", None, "external")

    cfg = try_load_runtime_config()
    log_dir = Path(cfg.logDir) if cfg and cfg.logDir else default_log_dir()
    stdout, stderr = studio_api_log_paths(log_dir)
    load_beta_env(paths.repo_root)
    child_env = dict(os.environ)
    # Pin Character Identity so IG/Character Creator survive restarts even if a launcher skipped .env
    child_env.setdefault("STUDIO_FEATURE_CHARACTER_IDENTITY_V1", "1")
    proc = _spawn_studio_api(python, app_root, port, stdout, stderr, env=child_env)
    cmd = f"{python} -m uvicorn app.main:app --host 127.0.0.1 --port {port}"
    _write_child(
        state,
        proc.pid,
        cmd,
        owned=True,
        reason="spawn",
        executable=str(python),
        cwd=str(app_root),
        log_path=str(stdout),
        health="starting",
        child_state="starting",
        bump_restart=True,
    )
    deadline = time.time() + API_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(2)
        if healthy_fn():
            listener = port_owner_pid(port)
            if listener and verify_studio_api_identity(listener, port=port):
                _write_child(
                    state,
                    listener,
                    process_command_line(listener) or cmd,
                    owned=True,
                    reason="bind",
                    executable=str(python),
                    cwd=str(app_root),
                    log_path=str(stdout),
                    health="healthy",
                    child_state="running",
                )
                return _result(True, f"healthy PID {listener}", listener, "owned")
            if verify_studio_api_identity(proc.pid, port=port):
                _write_child(
                    state,
                    proc.pid,
                    cmd,
                    owned=True,
                    executable=str(python),
                    cwd=str(app_root),
                    log_path=str(stdout),
                    health="healthy",
                    child_state="running",
                )
                return _result(True, f"healthy PID {proc.pid}", proc.pid, "owned")
            return _result(False, f"{PORT_CONFLICT}: healthy :{port} is not the spawned child", listener, "external")
        now = classify_fn()
        if now.state in ("phantom", "unrelated"):
            from .services import LifecycleError

            raise LifecycleError(f"Launch failed: :{port} taken by {now.state} PID {now.pid}")
    return _result(False, f"did not become healthy within {API_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def stop_studio_api_child(
    state: SupervisorState,
    *,
    force: bool = False,
    allow_migrate: bool = False,
    classify_fn=None,
) -> Any:
    classify_fn = classify_fn or classify_api_port
    rec = state.read_pid(SERVICE)
    st, role = classify_owned_listener(state, classify_fn=classify_fn)

    target: int | None = rec.pid if rec else None
    if target and not process_alive(target):
        if st.state == "free" or not st.pid:
            state.remove_pid(SERVICE)
            return _result(True, "already gone — :8758 free", target, "owned")
        if role in {"stale-owned", "owned"} or (allow_migrate and role == "known-adept"):
            target = st.pid
        elif role == "foreign" or (role == "known-adept" and not allow_migrate):
            return _result(False, f"{PORT_CONFLICT}: :8758 held by PID {st.pid} ({role})", st.pid, "external")
        else:
            state.remove_pid(SERVICE)
            return _result(True, "already gone — :8758 free", target, "owned")

    if not target:
        if st.state == "free" or not st.pid:
            return _result(True, "nothing to stop", None, "external")
        if allow_migrate and role in {"known-adept", "stale-owned", "owned"} and st.pid:
            target = st.pid
        elif st.state == "phantom":
            from .services import LifecycleError

            raise LifecycleError(
                f"FAIL CLOSED: :{API_PORT} owned by PHANTOM PID {st.pid}. "
                f"Run: taskkill /F /PID {st.pid} (elevated) or reboot."
            )
        else:
            return _result(False, f"{PORT_CONFLICT}: :8758 held by PID {st.pid}", st.pid, "external")

    if not process_alive(target):
        if st.pid and st.pid != target and (role in {"stale-owned", "owned"} or (allow_migrate and role == "known-adept")):
            target = st.pid
        else:
            state.remove_pid(SERVICE)
            return _result(True, "already gone", target, "owned")

    if not verify_studio_api_identity(target):
        if role == "foreign" or not allow_migrate:
            return _result(False, f"identity mismatch — stop refused PID {target}", target, "external")
        if st.pid and verify_studio_api_identity(st.pid):
            target = st.pid
        else:
            state.remove_pid(SERVICE)
            return _result(True, "identity mismatch — stale PID file removed", target, "external")

    kill_process_tree(target)
    time.sleep(2)
    if process_alive(target):
        return _result(False, f"failed to stop PID {target}", target, "owned")
    _write_child(state, target, rec.cmd if rec else "uvicorn", owned=True, last_exit="stopped", child_state="stopped", health="offline")
    state.remove_pid(SERVICE)
    if not wait_port_released(API_PORT, PORT_RELEASE_TIMEOUT_SEC):
        owner = port_owner_pid(API_PORT)
        from .services import LifecycleError

        raise LifecycleError(
            f"Process stopped but :{API_PORT} still held by PID {owner} (phantom/orphaned). "
            f"Run: taskkill /F /PID {owner} (elevated) or reboot."
        )
    return _result(True, f"stopped PID {target}", target, "owned")


def restart_studio_api_child(
    paths: RuntimePaths,
    state: SupervisorState,
    *,
    classify_fn=None,
    healthy_fn=None,
    spawn: bool = True,
    allow_migrate: bool = True,
) -> dict[str, Any]:
    old_pid = None
    rec = state.read_pid(SERVICE)
    if rec:
        old_pid = rec.pid
    listener = port_owner_pid(API_PORT)
    if listener:
        old_pid = listener
    comfy_before = _comfy_pid()
    stopped = stop_studio_api_child(state, force=False, allow_migrate=allow_migrate, classify_fn=classify_fn)
    if not stopped.ok and PORT_CONFLICT in (stopped.message or ""):
        return {
            "ok": False,
            "message": stopped.message,
            "oldPid": old_pid,
            "newPid": None,
            "comfyPid": comfy_before,
            "comfyPidUnchanged": True,
        }
    started = start_studio_api_child(
        paths,
        state,
        classify_fn=classify_fn,
        healthy_fn=healthy_fn,
        spawn=spawn,
        allow_migrate=False,
    )
    comfy_after = _comfy_pid()
    return {
        "ok": started.ok,
        "message": started.message,
        "oldPid": old_pid,
        "newPid": started.pid,
        "comfyPid": comfy_after,
        "comfyPidUnchanged": comfy_before == comfy_after,
        "ownership": started.ownership,
    }


def child_view(state: SupervisorState | None = None, *, assume_healthy: bool = False) -> dict[str, Any]:
    from .paths import repo_root_from

    st = state or SupervisorState.from_env(repo_root_from())
    rec = st.read_pid(SERVICE)
    healthy = True if assume_healthy else studio_api_healthy()
    owner = port_owner_pid(API_PORT)
    pid = rec.pid if rec else owner
    owned = bool(rec and rec.owned and pid and (rec.pid == pid or (owner == rec.pid)))
    if rec and rec.owned and owner and owner != rec.pid and verify_studio_api_identity(owner):
        pid = owner
        owned = True
    health = "healthy" if healthy and owned else ("conflict" if healthy and not owned else ("offline" if not healthy else "starting"))
    return {
        "pid": pid,
        "owned": owned,
        "startedAt": rec.started_at if rec else "",
        "health": health,
        "port": API_PORT,
        "lastExit": rec.last_exit if rec else "",
        "restartCount": rec.restart_count if rec else 0,
        "lastRestartReason": rec.last_restart_reason if rec else "",
        "executable": rec.executable if rec else "",
        "cwd": rec.cwd if rec else "",
        "logPath": rec.log_path if rec else str(studio_api_log_paths()[0]),
        "state": rec.state if rec else ("running" if healthy else "offline"),
    }
