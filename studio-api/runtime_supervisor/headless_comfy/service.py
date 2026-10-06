"""Adept Headless Comfy Service — only process allowed to spawn/stop :8188.

Supervisor start_comfy / stop comfyui are thin requests into this module.
Vite, HMR, frontend tests, and Studio API recycle must not call this service.
force=True never means kill whatever is on :8188.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..constants import COMFY_PORT
from ..health import comfy_healthy, comfy_queue_running
from ..paths import RuntimePaths
from ..ports import port_owner_pid
from ..process import (
    is_comfy_command,
    kill_process_tree,
    process_alive,
    process_command_line,
    process_image_name,
    process_parent_pid,
)
from ..state import SupervisorState
from . import config_yaml, ownership

HEADLESS_READY_TIMEOUT_SEC = 180
EXTERNAL_MESSAGE = "EXTERNAL COMFY PROCESS OWNS :8188"


def _result(ok: bool, message: str, pid: int | None = None, ownership_kind: str = "external"):
    from ..services import ServiceResult

    return ServiceResult("comfyui", ok, message, pid, ownership_kind)


def _logs_dir(paths: RuntimePaths) -> Path:
    return paths.repo_root / "logs" / "runtime" / "headless-comfy"


def _tail(path: Path, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[-limit:].decode("utf-8", "replace")


def _resolve_engine(paths: RuntimePaths) -> tuple[Path | None, Path | None]:
    env_root = (os.environ.get("ADEPT_COMFY_ROOT") or "").strip()
    env_py = (os.environ.get("ADEPT_COMFY_PYTHON") or "").strip()
    if env_root:
        root = Path(env_root)
        py = Path(env_py) if env_py else None
        if py is None:
            for candidate in (
                root / "ComfyUI" / ".venv" / "Scripts" / "python.exe",
                root / ".venv" / "Scripts" / "python.exe",
                root / "python.exe",
            ):
                if candidate.is_file():
                    py = candidate
                    break
        if root.is_dir() and py is not None and py.is_file():
            return root, py
    if paths.comfy_python and paths.comfy_install_root:
        return paths.comfy_install_root, paths.comfy_python
    return None, None


def _identity_matches(pid: int, yaml: Path, *, python: Path | None = None) -> bool:
    if not process_alive(pid):
        return False
    if ownership.command_is_adept_headless(process_command_line(pid), yaml):
        return True
    if python is None:
        return False
    try:
        image = Path(process_image_name(pid)).resolve()
        return image == Path(python).resolve()
    except OSError:
        return False


def _port_identity(yaml: Path) -> tuple[int | None, str]:
    owner = port_owner_pid(COMFY_PORT)
    cmd = process_command_line(owner) if owner else ""
    return owner, cmd


def _record_matches_live(record: dict[str, Any] | None, yaml: Path) -> bool:
    if not record or not record.get("owned"):
        return False
    try:
        pid = int(record.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    python = Path(str(record.get("python") or "")) if record.get("python") else None
    owner, _cmd = _port_identity(yaml)
    if not _identity_matches(pid, yaml, python=python):
        if owner and _identity_matches(owner, yaml, python=python):
            parent = process_parent_pid(owner)
            if parent == pid or owner == pid:
                stored_yaml = str(record.get("yaml") or "")
                return not stored_yaml or Path(stored_yaml).resolve() == yaml.resolve()
        return False
    if owner not in {None, pid}:
        if not _identity_matches(owner, yaml, python=python):
            return False
    stored_yaml = str(record.get("yaml") or "")
    if stored_yaml and Path(stored_yaml).resolve() != yaml.resolve():
        return False
    return True


def _capture_death(paths: RuntimePaths, record: dict[str, Any] | None, reason: str) -> None:
    logs = _logs_dir(paths)
    payload = {
        "reason": reason,
        "record": record or {},
        "portOwner": port_owner_pid(COMFY_PORT),
        "queueRunning": comfy_queue_running() if comfy_healthy() else 0,
        "stdoutTail": _tail(logs / "stdout.log"),
        "stderrTail": _tail(logs / "stderr.log"),
        "lastAction": "capture_before_recovery",
    }
    ownership.write_death(config_yaml.adept_config_dir(), payload, extra_log=logs / "last_death.json")


def _spawn_headless(python: Path, cwd: Path, args: list[str], logs: Path) -> subprocess.Popen[bytes]:
    logs.mkdir(parents=True, exist_ok=True)
    out_f = open(logs / "stdout.log", "ab")
    err_f = open(logs / "stderr.log", "ab")
    creationflags = 0
    if sys.platform == "win32":
        # CREATE_NO_WINDOW only. DETACHED_PROCESS triggers Intel Fortran
        # "window-CLOSE event" abort (forrtl 200) and kills headless Comfy.
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    return subprocess.Popen(
        [str(python), *args],
        cwd=str(cwd),
        stdout=out_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def _write_owned(
    state: SupervisorState,
    *,
    pid: int,
    cmd: str,
    cwd: Path,
    yaml: Path,
    python: Path,
) -> dict[str, Any]:
    parent = process_parent_pid(pid)
    record = ownership.write_record(
        config_yaml.adept_config_dir(),
        {
            "pid": pid,
            "parentPid": parent,
            "cmd": cmd,
            "cwd": str(cwd),
            "yaml": str(yaml),
            "python": str(python),
            "port": COMFY_PORT,
        },
    )
    state.write_pid("comfyui", pid, cmd, owned=True)
    return record


def status(paths: RuntimePaths | None = None, state: SupervisorState | None = None) -> dict[str, Any]:
    yaml = config_yaml.yaml_path()
    record = ownership.read_record(config_yaml.adept_config_dir())
    owner, cmd = _port_identity(yaml)
    healthy = comfy_healthy()
    matches = _record_matches_live(record, yaml) if record else False
    # A healthy Comfy on :8188 that Adept did not spawn (e.g. Comfy Desktop) is a
    # usable runtime, not a failure. Report it as "reused" so the unified fabric
    # shows green and features run against it. Ownership semantics are preserved:
    # "owned" stays False, so Adept will never stop/restart/kill it.
    if healthy and matches:
        kind = "owned"
    elif healthy:
        kind = "reused"
    else:
        kind = "down"
    return {
        "healthy": healthy,
        "ownership": kind,
        "pid": (record or {}).get("pid") if matches else owner,
        "portOwnerPid": owner,
        "command": cmd,
        "yaml": str(yaml),
        "owned": bool(matches),
        "record": record,
        "queueRunning": comfy_queue_running() if healthy else 0,
    }


def request_start(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True):
    yaml = config_yaml.yaml_path()
    record = ownership.read_record(config_yaml.adept_config_dir())
    healthy = comfy_healthy()
    owner, cmd = _port_identity(yaml)

    if healthy and _record_matches_live(record, yaml):
        live_pid = owner or int(record.get("pid") or 0)
        if owner and record and owner != int(record.get("pid") or 0) and _identity_matches(owner, yaml):
            _write_owned(
                state,
                pid=owner,
                cmd=process_command_line(owner),
                cwd=Path(str(record.get("cwd") or paths.comfy_install_root or ".")),
                yaml=yaml,
                python=Path(str(record.get("python") or paths.comfy_python or "")),
            )
            live_pid = owner
        elif record:
            state.write_pid("comfyui", int(record["pid"]), str(record.get("cmd") or cmd), owned=True)
        return _result(True, f"Adept-owned healthy — reused PID {live_pid}", live_pid, "owned")

    if healthy or owner:
        # A healthy external Comfy (e.g. Comfy Desktop) is reused, not fought.
        # Adept does not adopt or kill it; it simply runs against it.
        return _result(True, f"Reusing healthy Comfy on :8188 (PID {owner}) — not Adept-owned", owner, "reused")

    if record and not process_alive(int(record.get("pid") or 0)):
        _capture_death(paths, record, "owned process not alive; port free")
        ownership.clear_record(config_yaml.adept_config_dir())
        rec = state.read_pid("comfyui")
        if rec and rec.pid == int(record.get("pid") or 0):
            state.remove_pid("comfyui")

    yaml_path, errors = config_yaml.write_and_validate()
    if errors:
        return _result(False, "CONFIGURATION ERROR: " + "; ".join(errors), None, "external")

    from ..gpu_admission import request_comfy_admission_with_route_a_handoff

    # Canonical admission with Route A handoff (mirrors start_route_a_on_demand):
    # if Route A :8192 is healthy but idle-warm, its resident H3 models are released
    # via POST /free (models only — Route A process stays up) so :8188 may start.
    # If Route A is actively generating, admission is refused — never interrupt a render.
    admission = request_comfy_admission_with_route_a_handoff()
    if not admission.get("allowed"):
        return _result(False, str(admission.get("reason") or "GPU admission refused"), None, "external")

    cwd, python = _resolve_engine(paths)
    if not cwd or not python:
        return _result(
            False,
            "CONFIGURATION ERROR: Comfy engine missing — set ADEPT_COMFY_ROOT / ADEPT_COMFY_PYTHON",
            None,
            "external",
        )
    main = cwd / "ComfyUI" / "main.py"
    if not main.is_file():
        return _result(False, f"CONFIGURATION ERROR: Comfy main.py missing at {main}", None, "external")

    if not spawn:
        return _result(False, "port free — spawn disabled (test)", None, "external")

    args = [
        "-s",
        "ComfyUI\\main.py",
        "--listen",
        "127.0.0.1",
        "--port",
        str(COMFY_PORT),
        "--disable-auto-launch",
        "--enable-manager",
        "--extra-model-paths-config",
        str(yaml_path),
    ]
    if paths.comfy_input_dir:
        args += ["--input-directory", str(paths.comfy_input_dir)]
    if paths.comfy_output_dir:
        args += ["--output-directory", str(paths.comfy_output_dir)]

    logs = _logs_dir(paths)
    proc = _spawn_headless(python, cwd, args, logs)
    cmd_line = f"{python} " + " ".join(args)
    _write_owned(state, pid=proc.pid, cmd=cmd_line, cwd=cwd, yaml=yaml_path, python=python)

    deadline = time.time() + HEADLESS_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(3)
        if comfy_healthy():
            live_owner, live_cmd = _port_identity(yaml_path)
            ours = live_owner in {None, proc.pid} or process_parent_pid(live_owner) == proc.pid
            if ours or (live_owner and _identity_matches(live_owner, yaml_path, python=python)):
                claim = live_owner or proc.pid
                cmd = live_cmd if ownership.command_is_adept_headless(live_cmd, yaml_path) else cmd_line
                _write_owned(state, pid=claim, cmd=cmd, cwd=cwd, yaml=yaml_path, python=python)
                return _result(True, f"healthy PID {claim}", claim, "owned")
            _capture_death(paths, ownership.read_record(config_yaml.adept_config_dir()), "healthy but identity mismatch")
            return _result(False, f"{EXTERNAL_MESSAGE} after spawn PID {live_owner}", live_owner, "external")
        if owner_now := port_owner_pid(COMFY_PORT):
            if owner_now != proc.pid and process_parent_pid(owner_now) != proc.pid:
                live_cmd = process_command_line(owner_now)
                if is_comfy_command(live_cmd) and not ownership.command_is_adept_headless(live_cmd, yaml_path):
                    return _result(False, f"{EXTERNAL_MESSAGE} PID {owner_now}", owner_now, "external")
    return _result(False, f"did not become healthy within {HEADLESS_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def request_stop(state: SupervisorState, *, force: bool = False):
    yaml = config_yaml.yaml_path()
    record = ownership.read_record(config_yaml.adept_config_dir())
    rec = state.read_pid("comfyui")
    target = int((record or {}).get("pid") or (rec.pid if rec else 0) or 0)

    if not target:
        owner = port_owner_pid(COMFY_PORT)
        if owner:
            return _result(False, f"{EXTERNAL_MESSAGE} — stop refused PID {owner}", owner, "external")
        return _result(True, "nothing to stop", None, "external")

    if not process_alive(target):
        ownership.clear_record(config_yaml.adept_config_dir())
        state.remove_pid("comfyui")
        return _result(True, "already gone", target, "owned")

    python = Path(str((record or {}).get("python") or "")) if (record or {}).get("python") else None
    if not _identity_matches(target, yaml, python=python) and not _record_matches_live(record, yaml):
        return _result(
            False,
            f"identity mismatch — stop refused (force={bool(force)} never kills :8188 occupant)",
            target,
            "external",
        )

    if comfy_queue_running() > 0:
        return _result(False, "queue_running — not stopping a busy generation", target, "owned")

    kill_process_tree(target)
    time.sleep(2)
    if process_alive(target):
        return _result(False, f"failed to stop PID {target}", target, "owned")
    ownership.clear_record(config_yaml.adept_config_dir())
    state.remove_pid("comfyui")
    return _result(True, f"stopped PID {target}", target, "owned")
