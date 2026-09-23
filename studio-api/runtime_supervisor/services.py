"""Start/stop/status for Studio API, Comfy, tunnel, Ollama."""

from __future__ import annotations

import subprocess
import sys
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import (
    API_PORT,
    API_READY_TIMEOUT_SEC,
    COMFY_PORT,
    COMFY_READY_TIMEOUT_SEC,
    H3_COMFY_PORT,
    API_HOST,
    LOGICAL_COMFY,
    LOGICAL_LOCAL_LLM,
    LOGICAL_VIDEO,
    OLLAMA_PORT,
    OLLAMA_TAGS_PATH,
    OLLAMA_READY_TIMEOUT_SEC,
    PORT_RELEASE_TIMEOUT_SEC,
    RETIRED_WEB_PORT,
    ROUTE_A_READY_TIMEOUT_SEC,
    ROUTE_A_SERVICE,
    TUNNEL_READY_TIMEOUT_SEC,
)
from .health import (
    comfy_healthy,
    fetch_json,
    ollama_healthy,
    ollama_model_names,
    ollama_model_ready,
    required_local_llm_model,
    studio_api_healthy,
    tunnel_process_healthy,
)
from .identity import PortState, classify_api_port
from .paths import RuntimePaths, discover_paths
from .ports import port_owner_pid, wait_port_released
from .process import (
    is_cloudflared_command,
    is_comfy_command,
    is_ollama_command,
    is_route_a_command,
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


MANAGER_UNAVAILABLE = (
    "Background Services unavailable. Start or Repair Adept Background Services."
)


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
        for name in ("studio_api", "comfyui", "minimax_h3_route_a", "cloudflared", "ollama"):
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
        # CREATE_NO_WINDOW only. DETACHED_PROCESS triggers Intel Fortran
        # "window-CLOSE event" abort (forrtl 200) and kills headless Comfy,
        # including isolated Route A :8192. Same rule as headless_comfy.
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) | int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
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
    if service == ROUTE_A_SERVICE:
        return is_route_a_command(cmd)
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
    port = {
        "studio_api": API_PORT,
        "comfyui": COMFY_PORT,
        ROUTE_A_SERVICE: H3_COMFY_PORT,
        "ollama": OLLAMA_PORT,
    }.get(service)

    if service == "ollama" and rec and not rec.owned and not allow_external:
        return ServiceResult(service, True, "EXTERNAL Ollama left running", rec.pid, "external")

    if service == "comfyui":
        from .headless_comfy.service import request_stop

        return request_stop(state, force=force)

    if service == "studio_api":
        from .studio_api_child import stop_studio_api_child

        return stop_studio_api_child(state, force=force, allow_migrate=bool(force))

    if rec and not rec.owned and not force:
        return ServiceResult(service, True, "adopted — not stopped without force", rec.pid, "reused")

    target_pid = rec.pid if rec else None
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
    allow_migrate: bool = False,
) -> ServiceResult:
    from .studio_api_child import start_studio_api_child

    return start_studio_api_child(
        paths,
        state,
        classify_fn=classify_fn,
        healthy_fn=healthy_fn,
        spawn=spawn,
        allow_migrate=allow_migrate,
    )


def start_comfy(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True) -> ServiceResult:
    """Thin request to Adept Headless Comfy Service. Never adopts Desktop or unknown :8188."""
    from .headless_comfy.service import request_start

    return request_start(paths, state, spawn=spawn)


def _discover_route_a_launch(repo_root: Path) -> tuple[Path | None, Path | None]:
    import os

    env_root = (os.environ.get("ADEPT_H3_COMFY_ROOT") or "").strip()
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(repo_root.parent / "AIVideoStudio-h3" / "runtime" / "minimax-h3" / "comfyui")
    candidates.append(repo_root / "runtime" / "minimax-h3" / "comfyui")
    for root in candidates:
        main = root / "main.py"
        # The H3 venv lives at the minimax-h3 level (root.parent), NOT under comfyui/.
        # The previous code probed only root/.venv (comfyui/.venv), which does not exist
        # on the live install (confirmed: C:\AdeptFilmWorks\AIVideoStudio-h3\runtime\
        # minimax-h3\.venv exists; comfyui/.venv does not). Probe the parent venv first
        # (the real layout used by start_isolated_comfy_route_a.ps1), then fall back to
        # root/.venv for legacy layouts.
        py = root.parent / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = root.parent / ".venv" / "bin" / "python"
        if not py.exists():
            py = root / ".venv" / "Scripts" / "python.exe"
        if not py.exists():
            py = root / ".venv" / "bin" / "python"
        if main.exists() and py.exists():
            return py, main
    return None, None


def _route_a_preview_args() -> list[str]:
    """Live draft preview (Golden Phase 8-13): Comfy only emits WebSocket PREVIEW_IMAGE
    latent-preview events when launched with --preview-method. Without it the Preview
    Monitor never receives draft frames (proven: isolated :8299 with this flag streamed
    20 progressive frames over a 140s H3 1F render via Adept's existing tap). "auto" picks
    the cheapest available method (latent2rgb/taesd) — a non-destructive observer that does
    NOT touch the final render path. Override with ADEPT_H3_COMFY_PREVIEW_METHOD ("none" disables)."""
    import os

    method = (os.environ.get("ADEPT_H3_COMFY_PREVIEW_METHOD") or "auto").strip().lower()
    return [] if method in ("", "none", "off") else ["--preview-method", method]


def adopt_route_a(state: SupervisorState) -> ServiceResult:
    """Observe Route A :8192. Never claim Adept-owned Ready for an external stack."""
    if comfy_healthy(port=H3_COMFY_PORT):
        owner = port_owner_pid(H3_COMFY_PORT)
        cmd = process_command_line(owner) if owner else ""
        ownership = "reused" if owner and is_route_a_command(cmd) else "external"
        if owner:
            state.write_pid(ROUTE_A_SERVICE, owner, cmd or "adopted", owned=False)
        return ServiceResult(
            ROUTE_A_SERVICE,
            True,
            f"already healthy — {ownership} (not Adept-owned Ready)",
            owner,
            ownership,
        )
    return ServiceResult(
        ROUTE_A_SERVICE,
        True,
        "not running — not started by normal start (GPU admission; start Route A explicitly)",
        None,
        "external",
    )


def start_route_a(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True) -> ServiceResult:
    adopted = adopt_route_a(state)
    if adopted.pid:
        return adopted
    from .gpu_admission import assess_gpu_admission

    admission = assess_gpu_admission(ROUTE_A_SERVICE)
    if not admission.get("allowed"):
        return ServiceResult(ROUTE_A_SERVICE, False, str(admission.get("reason") or "GPU admission refused"), None, "external")
    py, main = _discover_route_a_launch(paths.repo_root)
    if not py or not main:
        return ServiceResult(
            ROUTE_A_SERVICE,
            False,
            "Route A Comfy not found — set ADEPT_H3_COMFY_ROOT or leave as EXTERNAL",
            None,
            "external",
        )
    if not spawn:
        return ServiceResult(ROUTE_A_SERVICE, False, "not healthy — spawn disabled (test)", None, "external")
    logs = paths.logs_dir
    # MiniMax H3 models (15GB CLIP + 20GB UNet) FIT in 32GB VRAM individually, but Comfy's
    # "dynamic VRAM" mode streams them layer-by-layer from CPU, leaving the GPU idle for
    # ~110s during sampling (measured: 9% avg GPU util). Disabling dynamic VRAM falls back to
    # traditional management: the active model is resident on GPU (fast sampling), unused
    # models offload to CPU. Override with ADEPT_H3_COMFY_VRAM_ARGS (space-separated).
    vram_args = (os.environ.get("ADEPT_H3_COMFY_VRAM_ARGS") or "").split()
    args = ["-s", str(main), "--listen", "127.0.0.1", "--port", str(H3_COMFY_PORT), *_route_a_preview_args(), *vram_args]
    proc = _spawn(py, args, main.parent, logs / "route_a_stdout.log", logs / "route_a_err.log")
    state.write_pid(ROUTE_A_SERVICE, proc.pid, " ".join(args), owned=True)
    deadline = time.time() + ROUTE_A_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(3)
        if comfy_healthy(port=H3_COMFY_PORT):
            return ServiceResult(ROUTE_A_SERVICE, True, f"healthy PID {proc.pid}", proc.pid, "owned")
    return ServiceResult(ROUTE_A_SERVICE, False, f"did not become healthy within {ROUTE_A_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def start_route_a_on_demand(paths: RuntimePaths, state: SupervisorState, *, spawn: bool = True) -> ServiceResult:
    """On-demand start of Route A with GPU handoff from canonical Comfy :8188.

    Unified Runtime Fabric contract: Route A (MiniMax H3 :8192) is ON DEMAND — it is
    started when an H3 generation is requested, not at boot. If canonical Comfy :8188
    holds the GPU while idle, release its resident models via POST /free first
    (handoff). /free releases models; it is NOT kill/restart/reset (ComfyUI
    Protection Law item 14). Comfy :8188 stays healthy and is never killed. If :8188
    is busy (queue running), the start is refused — finish that job first.
    """
    adopted = adopt_route_a(state)
    if adopted.pid:
        return adopted
    from .gpu_admission import request_route_a_admission_with_handoff

    admission = request_route_a_admission_with_handoff()
    if not admission.get("allowed"):
        return ServiceResult(
            ROUTE_A_SERVICE,
            False,
            str(admission.get("reason") or "GPU admission refused"),
            None,
            "external",
        )
    py, main = _discover_route_a_launch(paths.repo_root)
    if not py or not main:
        return ServiceResult(
            ROUTE_A_SERVICE,
            False,
            "Route A Comfy not found — set ADEPT_H3_COMFY_ROOT or leave as EXTERNAL",
            None,
            "external",
        )
    if not spawn:
        return ServiceResult(ROUTE_A_SERVICE, False, "not healthy — spawn disabled (test)", None, "external")
    logs = paths.logs_dir
    # MiniMax H3 models (15GB CLIP + 20GB UNet) FIT in 32GB VRAM individually, but Comfy's
    # "dynamic VRAM" mode streams them layer-by-layer from CPU, leaving the GPU idle for
    # ~110s during sampling (measured: 9% avg GPU util). Disabling dynamic VRAM falls back to
    # traditional management: the active model is resident on GPU (fast sampling), unused
    # models offload to CPU. Override with ADEPT_H3_COMFY_VRAM_ARGS (space-separated).
    vram_args = (os.environ.get("ADEPT_H3_COMFY_VRAM_ARGS") or "").split()
    args = ["-s", str(main), "--listen", "127.0.0.1", "--port", str(H3_COMFY_PORT), *_route_a_preview_args(), *vram_args]
    proc = _spawn(py, args, main.parent, logs / "route_a_stdout.log", logs / "route_a_err.log")
    state.write_pid(ROUTE_A_SERVICE, proc.pid, " ".join(args), owned=True)
    deadline = time.time() + ROUTE_A_READY_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(3)
        if comfy_healthy(port=H3_COMFY_PORT):
            return ServiceResult(ROUTE_A_SERVICE, True, f"healthy PID {proc.pid} (on-demand handoff)", proc.pid, "owned")
    return ServiceResult(ROUTE_A_SERVICE, False, f"did not become healthy within {ROUTE_A_READY_TIMEOUT_SEC}s", proc.pid, "owned")


def stop_route_a(state: SupervisorState, *, force: bool = False) -> ServiceResult:
    """Stop Adept-owned Route A :8192. Never kills an external/adopted Route A unless force."""
    rec = state.read_pid(ROUTE_A_SERVICE)
    if rec and not rec.owned and not force:
        return ServiceResult(ROUTE_A_SERVICE, True, "adopted — not stopped without force", rec.pid, "reused")
    target_pid = rec.pid if rec else None
    if not target_pid:
        # No PID record — probe the port for an owner but do NOT kill an external owner.
        owner = port_owner_pid(H3_COMFY_PORT)
        if owner:
            return ServiceResult(ROUTE_A_SERVICE, True, "external Route A on :8192 — left running", owner, "external")
        return ServiceResult(ROUTE_A_SERVICE, True, "Route A not running", None, "external")
    if not process_alive(target_pid):
        state.remove_pid(ROUTE_A_SERVICE)
        return ServiceResult(ROUTE_A_SERVICE, True, "stale PID — cleared", None, "external")
    # Re-verify identity before killing (stale-PID safety, Law item 8).
    if not verify_identity(ROUTE_A_SERVICE, target_pid, port=H3_COMFY_PORT):
        return ServiceResult(ROUTE_A_SERVICE, False, "identity mismatch — stop refused (PID reused)", target_pid, "external")
    kill_process_tree(target_pid)
    wait_port_released(H3_COMFY_PORT, PORT_RELEASE_TIMEOUT_SEC)
    state.remove_pid(ROUTE_A_SERVICE)
    return ServiceResult(ROUTE_A_SERVICE, True, f"stopped PID {target_pid}", target_pid, "owned")


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
        rec = state.read_pid("ollama")
        owner = port_owner_pid(OLLAMA_PORT)
        # Preserve Adept ownership when we started this daemon. Ollama may fork a
        # child that binds the port; do not overwrite owned=True as EXTERNAL.
        if rec and rec.owned and process_alive(rec.pid):
            return ServiceResult(
                "ollama",
                True,
                "already healthy — Adept-owned reused",
                rec.pid,
                "owned",
            )
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
    start_ollama_if_down: bool = True,
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
        from .control_client import call_control, control_plane_reachable

        if control_plane_reachable():
            remote = call_control("POST", "/start")
            api_remote = remote.get("studioApi") if isinstance(remote.get("studioApi"), dict) else {}
            comfy_remote = remote.get("comfy") if isinstance(remote.get("comfy"), dict) else {}
            report.results["studio_api"] = ServiceResult(
                "studio_api",
                bool(api_remote.get("ok", remote.get("ok"))),
                str(api_remote.get("message") or remote.get("message") or "manager start"),
                api_remote.get("pid") or remote.get("studioApiPid"),
                str(api_remote.get("ownership") or "owned"),
            )
            report.results["comfyui"] = ServiceResult(
                "comfyui",
                bool(comfy_remote.get("ok", remote.get("ok"))),
                str(comfy_remote.get("message") or remote.get("creatorMessage") or "Runtime Service start"),
                comfy_remote.get("pid") or remote.get("comfyPid"),
                str(comfy_remote.get("ownership") or "owned"),
            )
        else:
            from .windows_task import start_task, task_exists

            unavailable = MANAGER_UNAVAILABLE
            if task_exists():
                try:
                    start_task()
                    unavailable = (
                        "Background Services manager start requested. "
                        "It will start Studio and pictures."
                    )
                    if control_plane_reachable():
                        remote = call_control("POST", "/start")
                        api_remote = remote.get("studioApi") if isinstance(remote.get("studioApi"), dict) else {}
                        comfy_remote = remote.get("comfy") if isinstance(remote.get("comfy"), dict) else {}
                        report.results["studio_api"] = ServiceResult(
                            "studio_api",
                            bool(api_remote.get("ok", remote.get("ok"))),
                            str(api_remote.get("message") or remote.get("message") or "manager start"),
                            api_remote.get("pid") or remote.get("studioApiPid"),
                            str(api_remote.get("ownership") or "owned"),
                        )
                        report.results["comfyui"] = ServiceResult(
                            "comfyui",
                            bool(comfy_remote.get("ok", remote.get("ok"))),
                            str(comfy_remote.get("message") or remote.get("creatorMessage") or "Runtime Service start"),
                            comfy_remote.get("pid") or remote.get("comfyPid"),
                            str(comfy_remote.get("ownership") or "owned"),
                        )
                    else:
                        report.results["studio_api"] = ServiceResult(
                            "studio_api", False, unavailable, None, "external"
                        )
                        report.results["comfyui"] = ServiceResult(
                            "comfyui", False, unavailable, None, "external"
                        )
                except Exception as exc:
                    report.results["studio_api"] = ServiceResult(
                        "studio_api", False, f"{MANAGER_UNAVAILABLE} ({exc})", None, "external"
                    )
                    report.results["comfyui"] = ServiceResult(
                        "comfyui", False, f"{MANAGER_UNAVAILABLE} ({exc})", None, "external"
                    )
            else:
                report.results["studio_api"] = ServiceResult(
                    "studio_api", False, unavailable, None, "external"
                )
                report.results["comfyui"] = ServiceResult(
                    "comfyui", False, unavailable, None, "external"
                )
        report.results[ROUTE_A_SERVICE] = adopt_route_a(st)
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
    from .control_client import call_control, control_plane_reachable

    if control_plane_reachable():
        remote = call_control("POST", "/stop")
        api_remote = remote.get("studioApi") if isinstance(remote.get("studioApi"), dict) else {}
        comfy_remote = remote.get("comfy") if isinstance(remote.get("comfy"), dict) else {}
        return [
            ServiceResult(
                "studio_api",
                bool(api_remote.get("ok", remote.get("ok"))),
                str(api_remote.get("message") or remote.get("message") or "manager stop"),
                api_remote.get("pid"),
                "owned",
            ),
            ServiceResult(
                "comfyui",
                bool(comfy_remote.get("ok", remote.get("ok"))),
                str(comfy_remote.get("message") or remote.get("creatorMessage") or "manager stop"),
                comfy_remote.get("pid") or remote.get("comfyPid"),
                "owned",
            ),
        ]
    return [
        ServiceResult("studio_api", False, MANAGER_UNAVAILABLE, None, "external"),
        ServiceResult(
            "comfyui",
            False,
            "Comfy lifecycle owned by Adept Runtime Service — stop_all will not stop :8188",
            None,
            "external",
        ),
    ]


def restart_all(**kwargs: Any) -> StartReport:
    from .control_client import call_control, control_plane_reachable

    kwargs.pop("force", None)
    if control_plane_reachable():
        remote = call_control("POST", "/restart-api")
        report = StartReport()
        report.results["studio_api"] = ServiceResult(
            "studio_api",
            bool(remote.get("ok")),
            str(remote.get("message") or "restart-api"),
            remote.get("newPid") or remote.get("studioApiPid"),
            "owned",
        )
        report.results["comfyui"] = ServiceResult(
            "comfyui",
            True,
            f"Comfy not restarted (pid={remote.get('comfyPid')})",
            remote.get("comfyPid"),
            "owned",
        )
        return report
    report = StartReport()
    report.results["studio_api"] = ServiceResult(
        "studio_api", False, MANAGER_UNAVAILABLE, None, "external"
    )
    report.results["comfyui"] = ServiceResult(
        "comfyui", False, MANAGER_UNAVAILABLE, None, "external"
    )
    return report


def _ollama_status_row(
    paths: RuntimePaths,
    state: SupervisorState,
    running: bool,
    ownership: str,
) -> dict[str, Any]:
    rec = state.read_pid("ollama")
    pid = rec.pid if rec else port_owner_pid(OLLAMA_PORT)
    starting = bool(rec and rec.owned and process_alive(rec.pid) and not running)
    tags = fetch_json(f"http://{API_HOST}:{OLLAMA_PORT}{OLLAMA_TAGS_PATH}", timeout=5.0) if running else None
    models = ollama_model_names(tags)
    required = required_local_llm_model()
    return {
        "logicalId": LOGICAL_LOCAL_LLM,
        "running": running,
        "starting": starting,
        "configured": bool(paths.ollama),
        "ownership": ownership,
        "pid": pid,
        "daemonOnline": running,
        "requiredModel": required,
        "models": models,
        "modelReady": bool(running and ollama_model_ready(required, tags=tags)),
        "availability": (
            "ONLINE"
            if running
            else "STARTING"
            if starting
            else "ON_DEMAND"
            if not bool(paths.ollama)
            else "STARTING"
        ),
        "gpuResidency": "RESIDENT" if running else "FREE",
    }


def _gpu_residency(*, running: bool, busy: bool = False, handoff: bool = False) -> str:
    if handoff:
        return "HANDOFF_REQUIRED"
    if not running:
        return "FREE"
    if busy:
        return "BUSY"
    return "RESIDENT"


def _comfy_logical_row(
    *,
    running: bool,
    ownership: str,
    pid: int | None,
    admission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    starting = bool(pid and ownership == "owned" and not running)
    failed = False
    headless = _headless_comfy_status()
    if str(headless.get("state") or "") in {"crashed", "port_conflict"}:
        failed = True
    availability = (
        "FAILED"
        if failed
        else "ONLINE"
        if running
        else "STARTING"
        if starting
        else "FAILED"
    )
    comfy_adm = (admission or {}).get("comfyui") or {}
    residents = (admission or {}).get("residents") or {}
    return {
        "logicalId": LOGICAL_COMFY,
        "running": running,
        "starting": starting,
        "configured": True,
        "ownership": ownership,
        "pid": pid,
        "availability": availability,
        "gpuResidency": _gpu_residency(
            running=running,
            busy=str((admission or {}).get("comfyState") or "") == "busy"
            or bool(residents.get("busy")),
            handoff=bool(residents.get("dualResident")) or not bool(comfy_adm.get("allowed", True)),
        ),
    }


def _video_logical_row(
    *,
    running: bool,
    ownership: str,
    pid: int | None,
    adept_owned_ready: bool,
    admission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    starting = bool(pid and ownership == "owned" and not running)
    availability = "ONLINE" if running else "STARTING" if starting else "ON_DEMAND"
    route_adm = (admission or {}).get(ROUTE_A_SERVICE) or {}
    residents = (admission or {}).get("residents") or {}
    return {
        "logicalId": LOGICAL_VIDEO,
        "running": running,
        "starting": starting,
        "configured": True,
        "ownership": ownership,
        "pid": pid,
        "adeptOwnedReady": adept_owned_ready,
        "availability": availability,
        "gpuResidency": _gpu_residency(
            running=running,
            handoff=bool(residents.get("dualResident")) or not bool(route_adm.get("allowed", True)),
        ),
    }


def collect_status(
    repo_root: Path | None = None,
    state: SupervisorState | None = None,
    *,
    assume_local_api: bool = False,
    include_gpu: bool = True,
) -> dict[str, Any]:
    paths = discover_paths(repo_root)
    st = state or SupervisorState.from_env(paths.repo_root)

    def ownership(service: str, running: bool) -> str:
        rec = st.read_pid(service)
        if rec and rec.owned:
            return "owned"
        if not running:
            return "external"
        if rec:
            return "reused"
        return "reused"

    api_ok = True if assume_local_api else studio_api_healthy()
    comfy_ok = comfy_healthy()
    ol_ok = ollama_healthy()
    tun_ok = tunnel_process_healthy(st)
    api_rec = st.read_pid("studio_api")
    ol_row = _ollama_status_row(paths, st, ol_ok, ownership("ollama", ol_ok))
    comfy_pid = st.read_pid("comfyui").pid if st.read_pid("comfyui") else port_owner_pid(COMFY_PORT)
    route_running = comfy_healthy(port=H3_COMFY_PORT)
    route_rec = st.read_pid(ROUTE_A_SERVICE)
    route_pid = route_rec.pid if route_rec else port_owner_pid(H3_COMFY_PORT)
    route_owned_ready = bool(route_rec and route_rec.owned and route_running)
    gpu = _gpu_admission_status() if include_gpu else {}
    comfy_row = _comfy_logical_row(
        running=comfy_ok,
        ownership=ownership("comfyui", comfy_ok),
        pid=comfy_pid,
        admission=gpu,
    )
    video_row = _video_logical_row(
        running=route_running,
        ownership=ownership(ROUTE_A_SERVICE, route_running),
        pid=route_pid,
        adept_owned_ready=route_owned_ready,
        admission=gpu,
    )
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
            "headless": _headless_comfy_status(),
        },
        "cloudflared": {
            "running": tun_ok,
            "ownership": ownership("cloudflared", tun_ok),
            "pid": st.read_pid("cloudflared").pid if st.read_pid("cloudflared") else None,
            "health": "process",
        },
        "ollama": ol_row,
        "logicalServices": {
            LOGICAL_LOCAL_LLM: ol_row,
            LOGICAL_COMFY: comfy_row,
            LOGICAL_VIDEO: video_row,
        },
        "retired_web_8760": {"started": False, "port": RETIRED_WEB_PORT},
        "minimax_h3_route_a": {
            "running": route_running,
            "ownership": ownership(ROUTE_A_SERVICE, route_running),
            "pid": route_pid,
            "port": H3_COMFY_PORT,
            "adeptOwnedReady": route_owned_ready,
        },
        "gpuAdmission": gpu,
        "state_dir": str(st.state_dir),
    }


def _headless_comfy_status() -> dict[str, Any]:
    try:
        from .headless_comfy.service import status as headless_status

        return headless_status()
    except Exception as exc:
        return {"error": str(exc)}


def _gpu_admission_status() -> dict[str, Any]:
    from .gpu_admission import assess_gpu_admission, classify_comfy_residents, nvidia_snapshot

    return {
        "gpu": nvidia_snapshot(),
        "residents": classify_comfy_residents(),
        "comfyui": assess_gpu_admission("comfyui"),
        ROUTE_A_SERVICE: assess_gpu_admission(ROUTE_A_SERVICE),
    }
