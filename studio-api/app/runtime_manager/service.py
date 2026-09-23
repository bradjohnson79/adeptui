"""Runtime Manager service layer.

Aggregates health and delegates lifecycle to the Python Runtime Supervisor.
Does not invoke PowerShell launchers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from .preferences import load_preferences
from .schemas import (
    ComfyUiStatus,
    GpuAdmission,
    GpuInfo,
    OllamaStatus,
    RouteAStatus,
    RuntimeConfigValidation,
    RuntimeManagerStatus,
    ServiceOwnership,
    ServiceStatus,
    StudioApiStatus,
    TunnelStatus,
)

logger = logging.getLogger(__name__)

_STUDIO_API_URL = "http://127.0.0.1:8758"
_COMFY_URL = "http://127.0.0.1:8188"
_OLLAMA_URL = "http://127.0.0.1:11434"
_TUNNEL_HOSTNAME = "api-beta.adeptui.org"


def _ownership(raw: str | None) -> ServiceOwnership:
    key = (raw or "").lower()
    if key == "owned":
        return ServiceOwnership.OWNED
    if key == "reused":
        return ServiceOwnership.REUSED
    return ServiceOwnership.EXTERNAL


def _collect(*, assume_local_api: bool = True, include_gpu: bool = False) -> dict:
    from runtime_supervisor.services import collect_status

    return collect_status(assume_local_api=assume_local_api, include_gpu=include_gpu)


async def _probe(url: str, timeout: float = 5.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        return False


async def _probe_json(url: str, timeout: float = 8.0) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        return None
    return None


async def get_comfyui_status() -> ComfyUiStatus:
    snap = await asyncio.to_thread(_collect)
    row = snap.get("comfyui") or {}
    data = await _probe_json(f"{_COMFY_URL}/system_stats", timeout=8.0)
    if data:
        devices = data.get("devices")
        if isinstance(devices, list) and devices:
            dev = devices[0]
        elif isinstance(devices, dict):
            dev = devices
        else:
            dev = {}
        return ComfyUiStatus(
            status=ServiceStatus.RUNNING,
            ownership=_ownership(row.get("ownership")),
            version=data.get("system", {}).get("comfyui_version", ""),
            device=str(dev.get("name", "")).split(":")[0] if isinstance(dev, dict) and dev.get("name") else None,
            vram_total=dev.get("vram_total") if isinstance(dev, dict) else None,
        )
    return ComfyUiStatus(
        status=ServiceStatus.STOPPED,
        ownership=_ownership(row.get("ownership")),
    )


async def get_studio_api_status() -> StudioApiStatus:
    snap = await asyncio.to_thread(_collect, assume_local_api=True)
    row = snap.get("studio_api") or {}
    # This handler runs inside Studio API. Never HTTP-get :8758 (single-worker deadlock).
    ok = True if row.get("running") is None else bool(row.get("running"))
    return StudioApiStatus(
        status=ServiceStatus.RUNNING if ok else ServiceStatus.STOPPED,
        ownership=_ownership(row.get("ownership") or "owned"),
    )


def _ollama_from_row(row: dict) -> OllamaStatus:
    running = bool(row.get("running") or row.get("daemonOnline"))
    starting = bool(row.get("starting"))
    configured = bool(row.get("configured"))
    if running:
        status = ServiceStatus.RUNNING
    elif starting:
        status = ServiceStatus.STARTING
    elif not configured:
        status = ServiceStatus.NOT_CONFIGURED
    else:
        status = ServiceStatus.STOPPED
    models = row.get("models") if isinstance(row.get("models"), list) else []
    return OllamaStatus(
        status=status,
        ownership=_ownership(row.get("ownership")),
        logicalId=str(row.get("logicalId") or "runtime.local_llm"),
        configured=configured,
        daemonOnline=running,
        modelReady=bool(row.get("modelReady")),
        requiredModel=str(row.get("requiredModel") or "") or None,
        models=[str(m) for m in models if m],
        pid=row.get("pid") if isinstance(row.get("pid"), int) else None,
        message=(
            None
            if running
            else "Local AI Runtime is starting"
            if starting
            else "Local AI Runtime is not installed"
            if not configured
            else "Local AI Runtime is offline"
        ),
    )


async def get_ollama_status() -> OllamaStatus:
    snap = await asyncio.to_thread(_collect)
    return _ollama_from_row(snap.get("ollama") or {})


async def get_tunnel_status() -> TunnelStatus:
    snap = await asyncio.to_thread(_collect)
    row = snap.get("cloudflared") or {}
    running = bool(row.get("running"))
    return TunnelStatus(
        status=ServiceStatus.RUNNING if running else ServiceStatus.STOPPED,
        ownership=_ownership(row.get("ownership")),
        hostname=_TUNNEL_HOSTNAME,
    )


async def get_gpu_info() -> GpuInfo:
    def _snap() -> dict:
        from runtime_supervisor.gpu_admission import nvidia_snapshot

        return nvidia_snapshot()

    gpu = await asyncio.to_thread(_snap)
    if gpu.get("ok"):
        total = gpu.get("memoryTotalMiB")
        used = gpu.get("memoryUsedMiB")
        free = (int(total) - int(used)) if isinstance(total, int) and isinstance(used, int) else None
        return GpuInfo(
            detected=True,
            name=str(gpu.get("name") or "GPU"),
            vram_total_mib=total if isinstance(total, int) else None,
            vram_used_mib=used if isinstance(used, int) else None,
            vram_free_mib=free,
            source="nvidia-smi",
        )
    return GpuInfo(detected=False, source="nvidia-smi")


async def get_status() -> RuntimeManagerStatus:
    prefs = load_preferences()

    def _view_and_snap():
        from runtime_supervisor.service_status import collect_runtime_view

        view = collect_runtime_view(assume_local_api=True)
        snap = _collect(assume_local_api=True, include_gpu=False)
        return view, snap

    view, snap = await asyncio.to_thread(_view_and_snap)
    comfy_state = str(view.get("comfyState") or "")
    comfyui = ComfyUiStatus(
        status=(
            ServiceStatus.RUNNING
            if comfy_state in {"ready", "busy"}
            else ServiceStatus.STARTING
            if comfy_state == "starting"
            else ServiceStatus.ERROR
            if comfy_state == "port_conflict"
            else ServiceStatus.NOT_CONFIGURED
            if comfy_state == "offline" and not view.get("configured")
            else ServiceStatus.STOPPED
        ),
        ownership=_ownership(view.get("ownership")),
        logicalId="runtime.comfy",
    )
    studio_api = StudioApiStatus(
        status=ServiceStatus.RUNNING,
        ownership=_ownership("owned" if view.get("studioApiOwned") else (snap.get("studio_api") or {}).get("ownership")),
    )
    ol_row = snap.get("ollama") or {}
    ollama = _ollama_from_row(ol_row)
    tun_row = snap.get("cloudflared") or {}
    tunnel = TunnelStatus(
        status=ServiceStatus.RUNNING if tun_row.get("running") else ServiceStatus.STOPPED,
        ownership=_ownership(tun_row.get("ownership")),
        hostname=_TUNNEL_HOSTNAME,
    )
    gpu = await get_gpu_info()
    route_row = snap.get("minimax_h3_route_a") or {}
    route_running = bool(route_row.get("running"))
    route_a = RouteAStatus(
        status=ServiceStatus.RUNNING if route_running else ServiceStatus.STOPPED,
        ownership=_ownership(route_row.get("ownership")),
        logicalId="runtime.video",
        port=int(route_row.get("port") or 8192),
        adeptOwnedReady=bool(route_row.get("adeptOwnedReady")),
        message="External Route A — Adept did not start this stack"
        if route_running and not route_row.get("adeptOwnedReady")
        else None,
    )
    admission_raw = snap.get("gpuAdmission") or {}
    residents = admission_raw.get("residents") or {}
    comfy_adm = admission_raw.get("comfyui") or {}
    route_adm = admission_raw.get("minimax_h3_route_a") or {}
    gpu_admission = GpuAdmission(
        dualResident=bool(residents.get("dualResident")),
        comfyuiAllowed=bool(comfy_adm.get("allowed", True)),
        routeAAllowed=bool(route_adm.get("allowed", True)),
        reason=str(route_adm.get("reason") or comfy_adm.get("reason") or "") or None,
    )

    from runtime_supervisor.windows_task import list_legacy_owners, query_task
    from .schemas import AdeptRuntimeServiceStatus

    task_on = bool(query_task().exists)
    legacy_owners = list_legacy_owners()
    windows_startup = task_on or bool(legacy_owners)
    prefs.startWithWindows = task_on
    comfy_state = str(view.get("comfyState") or "")
    if comfy_state in {"ready", "busy"}:
        comfyui.status = ServiceStatus.RUNNING
    elif comfy_state == "starting":
        comfyui.status = ServiceStatus.STARTING
    elif comfy_state == "port_conflict":
        comfyui.status = ServiceStatus.ERROR
    elif comfy_state == "offline" and not view.get("configured"):
        comfyui.status = ServiceStatus.NOT_CONFIGURED
    from .schemas import ChildRuntimeStatus

    api_child_raw = view.get("studioApi") if isinstance(view.get("studioApi"), dict) else {}
    adept = AdeptRuntimeServiceStatus(
        configured=bool(view.get("configured")),
        taskRegistered=bool(view.get("taskRegistered")),
        startWithWindows=task_on,
        windowsStartupPresent=windows_startup,
        legacyOwners=legacy_owners,
        canonicalTask="AdeptRuntimeService",
        serviceState=str(view.get("serviceState") or "offline"),
        comfyState=str(view.get("comfyState") or "offline"),
        worker=str(view.get("worker") or "idle"),
        falConnected=view.get("falConnected"),
        creatorMessage=(
            "An older Windows startup task is still registered. "
            "Adept Background Services is not the Start with Windows owner."
            if legacy_owners and not task_on
            else str(view.get("creatorMessage") or "")
        ),
        comfyPid=view.get("comfyPid") if isinstance(view.get("comfyPid"), int) else None,
        owned=bool(view.get("owned")),
        managerPid=view.get("managerPid") if isinstance(view.get("managerPid"), int) else None,
        studioApiPid=view.get("studioApiPid") if isinstance(view.get("studioApiPid"), int) else None,
        studioApiOwned=bool(view.get("studioApiOwned")),
        studioApiHealth=str(view.get("studioApiHealth") or "unknown"),
        studioApiStartedAt=str(view.get("studioApiStartedAt") or "") or None,
        studioApiChild=ChildRuntimeStatus(
            pid=api_child_raw.get("pid") if isinstance(api_child_raw.get("pid"), int) else None,
            owned=bool(api_child_raw.get("owned")),
            startedAt=str(api_child_raw.get("startedAt") or "") or None,
            health=str(api_child_raw.get("health") or "unknown"),
            port=int(api_child_raw.get("port") or 8758),
            lastExit=str(api_child_raw.get("lastExit") or "") or None,
            restartCount=int(api_child_raw.get("restartCount") or 0),
            lastRestartReason=str(api_child_raw.get("lastRestartReason") or "") or None,
            logPath=str(api_child_raw.get("logPath") or "") or None,
        ),
        comfyChild=ChildRuntimeStatus(
            pid=view.get("comfyPid") if isinstance(view.get("comfyPid"), int) else None,
            owned=bool(view.get("owned")),
            startedAt=str(view.get("comfyStartedAt") or "") or None,
            health=str(view.get("comfyState") or "offline"),
            port=8188,
        ),
    )

    logical = snap.get("logicalServices") if isinstance(snap.get("logicalServices"), dict) else {}
    return RuntimeManagerStatus(
        comfyui=comfyui,
        studioApi=studio_api,
        ollama=ollama,
        tunnel=tunnel,
        gpu=gpu,
        routeA=route_a,
        gpuAdmission=gpu_admission,
        preferences=prefs,
        adeptRuntime=adept,
        logicalServices=logical,
    )


def _proxy(method: str, path: str, *, timeout: float = 30.0) -> str:
    from runtime_supervisor.control_client import call_control, control_plane_reachable
    from runtime_supervisor.windows_task import start_task, task_exists

    if not control_plane_reachable() and path == "/start" and task_exists():
        try:
            start_task()
        except Exception as exc:
            return f"ERROR: {exc}"
    remote = call_control(method, path, timeout=timeout)
    if remote.get("ok"):
        return str(remote.get("message") or remote.get("creatorMessage") or "ok")
    return f"ERROR: {remote.get('error') or remote.get('message') or remote.get('creatorMessage') or 'Runtime Service unavailable'}"


def _start_sync() -> str:
    return _proxy("POST", "/start")


def _stop_sync() -> str:
    return _proxy("POST", "/stop")


def _restart_sync() -> str:
    # Legacy /restart is not API recycle and must not restart Comfy.
    from runtime_supervisor.control_client import control_plane_reachable
    from runtime_supervisor.windows_task import start_task, task_exists

    if control_plane_reachable():
        return "Runtime Service already running — use Restart Studio API or Restart Comfy."
    if task_exists():
        try:
            start_task()
            return "Runtime Service start requested — Comfy was not force-restarted."
        except Exception as exc:
            return f"ERROR: {exc}"
    return "ERROR: AdeptRuntimeService is not registered. Enable Recommended Background Services first."


def _proxy_later(path: str) -> str:
    """Fire-and-forget control-plane call so this API process can return before it is replaced."""
    import threading

    from runtime_supervisor.control_client import call_control, control_plane_reachable

    if not control_plane_reachable():
        return "ERROR: Background Services manager is not running."

    def _run() -> None:
        try:
            call_control("POST", path, timeout=180.0)
        except Exception:
            return

    threading.Timer(0.4, _run).start()
    return f"Requested {path}."


def _restart_api_sync() -> str:
    return _proxy_later("/restart-api")


def _restart_comfy_sync() -> str:
    return _proxy("POST", "/restart-comfy")


def _route_a_state_and_paths():
    from runtime_supervisor.paths import discover_paths
    from runtime_supervisor.state import SupervisorState

    paths = discover_paths()
    return paths, SupervisorState.from_env(paths.repo_root)


def _start_route_a_sync() -> str:
    # Execute current supervisor service code in-process. The long-lived
    # control-plane process cannot be recycled without risking Comfy :8188
    # (it is a child of that tree). Prepare-on-Generate must use the fixed
    # spawn (no DETACHED_PROCESS) and IP Helper port lookup (no NETSTAT.EXE).
    from runtime_supervisor.services import start_route_a_on_demand

    paths, state = _route_a_state_and_paths()
    result = start_route_a_on_demand(paths, state, spawn=True)
    if result.ok:
        return result.message
    return f"ERROR: {result.message}"


def _stop_route_a_sync() -> str:
    from runtime_supervisor.services import stop_route_a

    _paths, state = _route_a_state_and_paths()
    result = stop_route_a(state, force=False)
    if result.ok:
        return result.message
    return f"ERROR: {result.message}"


def _restart_route_a_sync() -> str:
    stopped = _stop_route_a_sync()
    if stopped.startswith("ERROR:"):
        return stopped
    return _start_route_a_sync()


def _start_ollama_sync() -> str:
    return _proxy("POST", "/start-ollama")


def _stop_ollama_sync() -> str:
    return _proxy("POST", "/stop-ollama")


def _restart_ollama_sync() -> str:
    return _proxy("POST", "/restart-ollama")


def _repair_sync() -> str:
    from runtime_supervisor.bootstrap import repair_services

    report = repair_services()
    return report.message if report.ok else f"ERROR: {report.message}"


def _enable_sync(start_with_windows: bool) -> str:
    from runtime_supervisor.bootstrap import enable_recommended

    report = enable_recommended(start_with_windows=start_with_windows)
    return report.message if report.ok else f"ERROR: {report.message}"


async def start_services() -> str:
    return await asyncio.to_thread(_start_sync)


async def stop_services() -> str:
    return await asyncio.to_thread(_stop_sync)


async def restart_services() -> str:
    return await asyncio.to_thread(_restart_sync)


async def enable_recommended_services(start_with_windows: bool = True) -> str:
    return await asyncio.to_thread(_enable_sync, start_with_windows)


async def restart_api_service() -> str:
    return await asyncio.to_thread(_restart_api_sync)


async def restart_comfy_service() -> str:
    return await asyncio.to_thread(_restart_comfy_sync)


async def start_route_a_service() -> str:
    return await asyncio.to_thread(_start_route_a_sync)


async def stop_route_a_service() -> str:
    return await asyncio.to_thread(_stop_route_a_sync)


async def restart_route_a_service() -> str:
    return await asyncio.to_thread(_restart_route_a_sync)


async def start_ollama_service() -> str:
    return await asyncio.to_thread(_start_ollama_sync)


async def stop_ollama_service() -> str:
    return await asyncio.to_thread(_stop_ollama_sync)


async def restart_ollama_service() -> str:
    return await asyncio.to_thread(_restart_ollama_sync)


async def repair_background_services() -> str:
    return await asyncio.to_thread(_repair_sync)


def _validate_config_sync() -> RuntimeConfigValidation:
    from runtime_supervisor.canonical_config import (
        build_discovered_config,
        try_load_runtime_config,
        validate_runtime_config,
    )

    source = "saved"
    cfg = try_load_runtime_config()
    if cfg is None:
        source = "discovered"
        cfg = build_discovered_config()
    errors = validate_runtime_config(cfg)
    if not errors:
        return RuntimeConfigValidation(
            ok=True,
            message="Runtime configuration looks good.",
            errors=[],
            source=source,
        )
    return RuntimeConfigValidation(
        ok=False,
        message="Runtime configuration needs attention.",
        errors=errors,
        source=source,
    )


async def validate_runtime_configuration() -> RuntimeConfigValidation:
    """Check saved or discovered paths only. Does not start or stop services."""
    return await asyncio.to_thread(_validate_config_sync)
