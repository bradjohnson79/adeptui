"""Start/stop/status for Studio API, Comfy, tunnel, Ollama."""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    API_PORT,
    API_READY_TIMEOUT_SEC,
    COMFY_PORT,
    COMFY_READY_TIMEOUT_SEC,
    OLLAMA_PORT,
    OLLAMA_READY_TIMEOUT_SEC,
    PORT_RELEASE_TIMEOUT_SEC,
    RETIRED_WEB_PORT,
    TUNNEL_READY_TIMEOUT_SEC,
)
from .health import comfy_healthy, ollama_healthy, studio_api_healthy, tunnel_process_healthy
from .identity import PortState, classify_api_port
from .paths import RuntimePaths, discover_paths
from .ports import port_owner_pid, wait_port_released
from .process import (
    is_cloudflared_command,
    is_comfy_command,
    is_ollama_command,
    is_studio_api_command,
    kill_process_tree,
    process_alive,
    process_command_line,
)
from .state import SupervisorState


class LifecycleError(RuntimeError):
    def __init__(self, message: str, *, fail_closed: bool = True):
        super().__init__(message)
        self.fail_closed = fail_closed


@dataclass
class ServiceResult:
    service: str
    ok: bool
    message: str
    pid: int | None = None
    ownership: str = "external"


@dataclass
class StartReport:
    results: dict[str, ServiceResult] = field(default_factory=dict)
    started_web_8760: bool = False

    @property
    def ok(self) -> bool:
        api = self.results.get("studio_api")
        comfy = self.results.get("comfyui")
        return bool(api and api.ok and comfy and comfy.ok)

    def lines(self) -> list[str]:
        out = ["ADEPT UI RUNTIME SUPERVISOR"]
        for name in ("studio_api", "comfyui", "cloudflared", "ollama"):
            rec = self.results.get(name)
            if rec:
                out.append(f"  {name}: {'OK' if rec.ok else 'FAIL'} ({rec.ownership}) {rec.message}")
        out.append(f"  retired_web_8760: not started (Law 15)")
        return out


def _spawn(exe: Path, args: list[str], cwd: Path, stdout: Path, stderr: Path) -> subprocess.Popen[bytes]:
    stdout.parent.mkdir(parents=True, exist_ok=True)
    out_f = open(stdout, "ab")
    err_f = open(stderr, "ab")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen(
        [str(exe), *args],
        cwd=str(cwd),
        stdout=out_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def _matches_service(service: str, cmd: str) -> bool:
    if service == "studio_api":
        return is_studio_api_command(cmd)
    if service == "comfyui":
        return is_comfy_command(cmd)
    if service == "cloudflared":
        return is_cloudflared_command(cmd)
    if service == "ollama":
        return is_ollama_command(cmd)
    return False


def verify_identity(service: str, pid: int, port: int | None = None) -> bool:
    if not process_alive(pid):
        return False
    cmd = process_command_line(pid)
    if _matches_service(service, cmd):
        return True
    if port is not None:
        return port_owner_pid(port) == pid
    return False


def stop_owned_service(
    state: SupervisorState,
    service: str,
    *,
    force: bool = False,
    allow_external: bool = False,
) -> ServiceResult:
    rec = state.read_pid(service)
    port = {"studio_api": API_PORT, "comfyui": COMFY_PORT, "ollama": OLLAMA_PORT}.get(service)

    if service == "ollama" and rec and not rec.owned and not allow_external:
        return ServiceResult(service, True, "EXTERNAL Ollama left running", rec.pid, "external")

    if rec and not rec.owned and not force and service != "studio_api":
        return ServiceResult(service, True, "adopted — not stopped without force", rec.pid, "reused")

    target_pid = rec.pid if rec else None
    if not target_pid and service == "studio_api":
        st = classify_api_port()
        if st.state in ("healthy", "starting") and st.pid and verify_identity("studio_api", st.pid, API_PORT):
            target_pid = st.pid
        elif st.state == "phantom":
            raise LifecycleError(
                f"FAIL CLOSED: :{API_PORT} owned by PHANTOM PID {st.pid}. "
                f"Run: taskkill /F /PID {st.pid} (elevated) or reboot."
            )
        else:
            return ServiceResult(service, True, "nothing to stop", None, "external")

    if not target_pid:
        return ServiceResult(service, True, "no PID record", None, "external")

    if not process_alive(target_pid):
        state.remove_pid(service)
        return ServiceResult(service, True, "already gone", target_pid, "owned")

    if not verify_identity(service, target_pid, port):
        state.remove_pid(service)
        return ServiceResult(service, True, "identity mismatch — stale PID file removed", target_pid, "external")

    kill_process_tree(target_pid)
    time.sleep(2)
    if process_alive(target_pid):
        return ServiceResult(service, False, f"failed to stop PID {target_pid}", target_pid, "owned")
    state.remove_pid(service)
    if service == "studio_api" and not wait_port_released(API_PORT, PORT_RELEASE_TIMEOUT_SEC):
        owner = port_owner_pid(API_PORT)
        raise LifecycleError(
            f"Process stopped but :{API_PORT} still held by PID {owner} (phantom/orphaned). "
            f"Run: taskkill /F /PID {owner} (elevated) or reboot."
        )
    return ServiceResult(service, True, f"stopped PID {target_pid}", target_pid, "owned")


def start_studio_api(
    paths: RuntimePaths,
    state: SupervisorState,
    *,
    classify_fn=None,
    healthy_fn=None,
    spawn: bool = True,
) -> ServiceResult:
    classify_fn = classify_fn or classify_api_port
    healthy_fn = healthy_fn or studio_api_healthy
    if not paths.studio_api_python:
        return ServiceResult("studio_api", False, "venv Python not found", None, "external")
    st: PortState = classify_fn()
    if st.state == "healthy" and st.pid:
        state.write_pid("studio_api", st.pid, st.cmd or "adopted", owned=False)
        return ServiceResult("studio_api", True, f"already healthy — reused PID {st.pid}", st.pid, "reused")
    if st.state == "starting" and st.pid:
        deadline = time.time() + API_READY_TIMEOUT_SEC
        while time.time() < deadline:
            time.sleep(2)
            if healthy_fn():
                state.write_pid("studio_api", st.pid, st.cmd or "adopted", owned=False)
                return ServiceResult("studio_api", True, f"healthy PID {st.pid}", st.pid, "reused")
            now = classify_fn()
            if now.state == "free":
                return start_studio_api(paths, state, classify_fn=classify_fn, healthy_fn=healthy_fn, spawn=spawn)
            if now.state in ("phantom", "unrelated"):
                raise LifecycleError(f"FAIL CLOSED: starter replaced by {now.state} PID {now.pid}")
        return ServiceResult("studio_api", False, f"uvicorn PID {st.pid} did not become healthy in {API_READY_TIMEOUT_SEC}s", st.pid, "reused")
    if st.state == "phantom":
        raise LifecycleError(
            f"FAIL CLOSED: :{API_PORT} owned by PHANTOM PID {st.pid}. "
            f"Run: taskkill /F /PID {st.pid} (elevated) or reboot."
        )
    if st.state == "unrelated":
        raise LifecycleError(
            f"FAIL CLOSED: :{API_PORT} owned by unrelated process PID {st.pid}. "
            "Do not kill arbitrary processes."
        )
    if not spawn:
        return ServiceResult("studio_api", False, "port free — spawn disabled (test)", None, "external")

    logs = paths.logs_dir
    logs.mkdir(parents=True, exist_ok=True)
    proc = _spawn(
        paths.studio_api_python,
        ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        paths.studio_api_dir,
        logs / "studio_api_stdout.log",
        logs / "studio_api_err.log",
    )
    state.write_pid("studio_api", proc.pid, f"{paths.studio_api_python} -m uvicorn app.main:app --port {API_PORT}", owned=True)
    deadline = time.time() + API_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(2)
        if healthy_fn():
            return ServiceResult("studio_api", True, f"healthy PID {proc.pid}", proc.pid, "owned")
        now = classify_fn()
        if now.state in ("phantom", "unrelated"):
            raise LifecycleError(f"Launch failed: :{API_PORT} taken by {now.state} PID {now.pid}")
    return ServiceResult("studio_api", False, f"did not become healthy within {API_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def start_comfy(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True) -> ServiceResult:
    if comfy_healthy():
        owner = port_owner_pid(COMFY_PORT)
        if owner:
            state.write_pid("comfyui", owner, "adopted", owned=False)
        return ServiceResult("comfyui", True, "already healthy — reused", owner, "reused")
    if not paths.comfy_python or not paths.comfy_install_root:
        return ServiceResult("comfyui", False, "ComfyUI Python not found", None, "external")
    if not spawn:
        return ServiceResult("comfyui", False, "not healthy — spawn disabled (test)", None, "external")
    args = ["-s", "ComfyUI\\main.py", "--enable-manager"]
    if paths.comfy_shared_paths:
        args += ["--extra-model-paths-config", str(paths.comfy_shared_paths)]
    if paths.comfy_input_dir:
        args += ["--input-directory", str(paths.comfy_input_dir)]
    if paths.comfy_output_dir:
        args += ["--output-directory", str(paths.comfy_output_dir)]
    logs = paths.logs_dir
    proc = _spawn(paths.comfy_python, args, paths.comfy_install_root, logs / "comfyui_stdout.log", logs / "comfyui_err.log")
    state.write_pid("comfyui", proc.pid, " ".join(args), owned=True)
    deadline = time.time() + COMFY_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(3)
        if comfy_healthy():
            return ServiceResult("comfyui", True, f"healthy PID {proc.pid}", proc.pid, "owned")
    return ServiceResult("comfyui", False, f"did not become healthy within {COMFY_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def start_tunnel(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True) -> ServiceResult:
    if tunnel_process_healthy(state):
        rec = state.read_pid("cloudflared")
        return ServiceResult("cloudflared", True, "already healthy — reused", rec.pid if rec else None, "reused")
    if not paths.cloudflared:
        return ServiceResult("cloudflared", False, "cloudflared not found", None, "external")
    if not paths.tunnel_config:
        return ServiceResult("cloudflared", False, "tunnel config missing — refuse start without --config", None, "external")
    if not spawn:
        return ServiceResult("cloudflared", False, "spawn disabled (test)", None, "external")
    args = ["tunnel", "--config", str(paths.tunnel_config), "run", paths.tunnel_name]
    logs = paths.logs_dir
    proc = _spawn(paths.cloudflared, args, paths.repo_root, logs / "cloudflared_stdout.log", logs / "cloudflared_err.log")
    state.write_pid("cloudflared", proc.pid, " ".join(args), owned=True)
    deadline = time.time() + TUNNEL_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(2)
        if tunnel_process_healthy(state):
            return ServiceResult("cloudflared", True, f"process up PID {proc.pid}", proc.pid, "owned")
    return ServiceResult("cloudflared", False, f"process not healthy within {TUNNEL_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def start_ollama(
    paths: RuntimePaths,
    state: SupervisorState,
    *,
    start_if_down: bool = False,
    spawn: bool = True,
) -> ServiceResult:
    if ollama_healthy():
        owner = port_owner_pid(OLLAMA_PORT)
        if owner:
            state.write_pid("ollama", owner, "adopted", owned=False)
        return ServiceResult("ollama", True, "already healthy — EXTERNAL/reused", owner, "external")
    if not start_if_down:
        return ServiceResult("ollama", True, "not running — left EXTERNAL (not started)", None, "external")
    if not paths.ollama:
        return ServiceResult("ollama", False, "ollama not found", None, "external")
    if not spawn:
        return ServiceResult("ollama", False, "spawn disabled (test)", None, "external")
    logs = paths.logs_dir
    proc = _spawn(paths.ollama, ["serve"], paths.repo_root, logs / "ollama_stdout.log", logs / "ollama_err.log")
    state.write_pid("ollama", proc.pid, "ollama serve", owned=True)
    deadline = time.time() + OLLAMA_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(2)
        if ollama_healthy():
            return ServiceResult("ollama", True, f"started PID {proc.pid}", proc.pid, "owned")
    return ServiceResult("ollama", False, "did not become healthy", proc.pid, "owned")


def start_all(
    *,
    start_ollama_if_down: bool = False,
    no_cloudflare: bool = False,
    spawn: bool = True,
    repo_root: Path | None = None,
    state: SupervisorState | None = None,
) -> StartReport:
    paths = discover_paths(repo_root)
    st = state or SupervisorState.from_env(paths.repo_root)
    if not st.try_lock("all"):
        raise LifecycleError("Another lifecycle operation is in progress — start refused (exclusive lock).")
    report = StartReport()
    try:
        report.results["studio_api"] = start_studio_api(paths, st, spawn=spawn)
        report.results["comfyui"] = start_comfy(paths, st, spawn=spawn)
        if no_cloudflare:
            report.results["cloudflared"] = ServiceResult("cloudflared", True, "skipped", None, "external")
        else:
            report.results["cloudflared"] = start_tunnel(paths, st, spawn=spawn)
        report.results["ollama"] = start_ollama(paths, st, start_if_down=start_ollama_if_down, spawn=spawn)
        report.started_web_8760 = False
        st.write_snapshot(
            {
                "action": "start",
                "retired_web_port": RETIRED_WEB_PORT,
                "started_web_8760": False,
                "results": {k: {"ok": v.ok, "ownership": v.ownership, "pid": v.pid} for k, v in report.results.items()},
            }
        )
        return report
    finally:
        st.clear_lock()


def stop_all(*, force: bool = False, repo_root: Path | None = None, state: SupervisorState | None = None) -> list[ServiceResult]:
    paths = discover_paths(repo_root)
    st = state or SupervisorState.from_env(paths.repo_root)
    out: list[ServiceResult] = []
    for service in ("studio_api", "comfyui", "cloudflared", "ollama"):
        out.append(stop_owned_service(st, service, force=force, allow_external=False))
    return out


def restart_all(**kwargs: Any) -> StartReport:
    stop_all(force=kwargs.pop("force", False), repo_root=kwargs.get("repo_root"), state=kwargs.get("state"))
    time.sleep(2)
    return start_all(**kwargs)


def collect_status(repo_root: Path | None = None, state: SupervisorState | None = None) -> dict[str, Any]:
    paths = discover_paths(repo_root)
    st = state or SupervisorState.from_env(paths.repo_root)

    def ownership(service: str, running: bool) -> str:
        rec = st.read_pid(service)
        if not running:
            return "external"
        if rec and rec.owned:
            return "owned"
        if service == "ollama":
            return "external"
        if rec:
            return "reused"
        return "reused" if running else "external"

    api_ok = studio_api_healthy()
    comfy_ok = comfy_healthy()
    ol_ok = ollama_healthy()
    tun_ok = tunnel_process_healthy(st)
    api_rec = st.read_pid("studio_api")
    return {
        "studio_api": {
            "running": api_ok,
            "ownership": ownership("studio_api", api_ok),
            "pid": api_rec.pid if api_rec else port_owner_pid(API_PORT),
            "port": API_PORT,
        },
        "comfyui": {
            "running": comfy_ok,
            "ownership": ownership("comfyui", comfy_ok),
            "pid": (st.read_pid("comfyui").pid if st.read_pid("comfyui") else port_owner_pid(COMFY_PORT)),
            "port": COMFY_PORT,
        },
        "cloudflared": {
            "running": tun_ok,
            "ownership": ownership("cloudflared", tun_ok),
            "pid": st.read_pid("cloudflared").pid if st.read_pid("cloudflared") else None,
            "health": "process",
        },
        "ollama": {
            "running": ol_ok,
            "ownership": ownership("ollama", ol_ok),
            "pid": st.read_pid("ollama").pid if st.read_pid("ollama") else port_owner_pid(OLLAMA_PORT),
            "port": OLLAMA_PORT,
        },
        "retired_web_8760": {"started": False, "port": RETIRED_WEB_PORT},
        "state_dir": str(st.state_dir),
    }
