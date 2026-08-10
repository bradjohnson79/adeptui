"""Runtime Manager service layer.

Aggregates health from existing endpoints, tracks ownership,
and invokes PowerShell scripts for lifecycle actions.
"""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

import httpx

from .schemas import (
    ComfyUiStatus,
    GpuInfo,
    OllamaStatus,
    RuntimeManagerStatus,
    ServiceOwnership,
    ServiceStatus,
    StudioApiStatus,
    TunnelStatus,
)
from .preferences import load_preferences

logger = logging.getLogger(__name__)

_STUDIO_API_URL = "http://127.0.0.1:8758"
_COMFY_URL = "http://127.0.0.1:8188"
_OLLAMA_URL = "http://127.0.0.1:11434"
_TUNNEL_HOSTNAME = "api-beta.adeptui.org"
_TUNNEL_URL = f"https://{_TUNNEL_HOSTNAME}/api/healthz"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _script(name: str) -> Path:
    return _repo_root() / name


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
        pass
    return None


async def get_comfyui_status() -> ComfyUiStatus:
    data = await _probe_json(f"{_COMFY_URL}/system_stats", timeout=8.0)
    if data:
        devices = data.get("devices")
        if isinstance(devices, list) and len(devices) > 0:
            dev = devices[0]
        elif isinstance(devices, dict):
            dev = devices
        else:
            dev = {}
        return ComfyUiStatus(
            status=ServiceStatus.RUNNING,
            ownership=ServiceOwnership.REUSED,
            version=data.get("system", {}).get("comfyui_version", ""),
            device=str(dev.get("name", "")).split(":")[0] if dev.get("name") else None,
            vram_total=dev.get("vram_total") if isinstance(dev, dict) else None,
        )
    return ComfyUiStatus(status=ServiceStatus.STOPPED)


async def get_studio_api_status() -> StudioApiStatus:
    ok = await _probe(f"{_STUDIO_API_URL}/api/healthz", timeout=5.0)
    if ok:
        return StudioApiStatus(
            status=ServiceStatus.RUNNING,
            ownership=ServiceOwnership.REUSED,
        )
    return StudioApiStatus(status=ServiceStatus.STOPPED)


async def get_ollama_status() -> OllamaStatus:
    data = await _probe_json(f"{_OLLAMA_URL}/api/tags", timeout=4.0)
    if data is not None:
        return OllamaStatus(
            status=ServiceStatus.RUNNING,
            ownership=ServiceOwnership.EXTERNAL,
        )
    return OllamaStatus(status=ServiceStatus.STOPPED)


async def get_tunnel_status() -> TunnelStatus:
    ok = await _probe(_TUNNEL_URL, timeout=8.0)
    if ok:
        return TunnelStatus(
            status=ServiceStatus.RUNNING,
            ownership=ServiceOwnership.REUSED,
            hostname=_TUNNEL_HOSTNAME,
        )
    return TunnelStatus(status=ServiceStatus.STOPPED)


async def get_gpu_info() -> GpuInfo:
    pc = await _probe_json(f"{_STUDIO_API_URL}/api/production-control/status", timeout=8.0)
    if pc:
        gpu = pc.get("gpu") or {}
        status = (gpu.get("status") or "").lower()
        if status in ("available", "healthy", "ok", "ready"):
            return GpuInfo(
                detected=True,
                name=gpu.get("device") or gpu.get("name") or "GPU",
            )
    health = await _probe_json(f"{_STUDIO_API_URL}/api/health", timeout=10.0)
    if health:
        operator = health.get("operator") or {}
        comfy_block = health.get("comfy") or {}
        if comfy_block.get("gpu"):
            return GpuInfo(detected=True, name=str(comfy_block["gpu"]))
        if operator.get("gpu"):
            return GpuInfo(detected=True, name=str(operator["gpu"]))
    return GpuInfo(detected=False)


async def get_status() -> RuntimeManagerStatus:
    prefs = load_preferences()

    async def safe_probe(coro, label: str, default):
        try:
            return await coro
        except Exception as exc:
            logger.warning("Runtime manager %s probe failed: %s", label, exc)
            return default

    comfyui = await safe_probe(get_comfyui_status(), "comfyui", ComfyUiStatus(status=ServiceStatus.ERROR))
    studio_api = await safe_probe(get_studio_api_status(), "api", StudioApiStatus(status=ServiceStatus.ERROR))
    ollama = await safe_probe(get_ollama_status(), "ollama", OllamaStatus(status=ServiceStatus.ERROR))
    tunnel = await safe_probe(get_tunnel_status(), "tunnel", TunnelStatus(status=ServiceStatus.ERROR))
    gpu = await safe_probe(get_gpu_info(), "gpu", GpuInfo(detected=False))

    return RuntimeManagerStatus(
        comfyui=comfyui,
        studioApi=studio_api,
        ollama=ollama,
        tunnel=tunnel,
        gpu=gpu,
        preferences=prefs,
    )


async def start_services() -> str:
    script = _script("Start-AdeptRuntime.ps1")
    if not script.exists():
        return "Start script not found"
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:500]
            logger.warning("Start-AdeptRuntime.ps1 exited %d: %s", proc.returncode, err)
        return output
    except asyncio.TimeoutError:
        proc.kill()
        return "Start timed out after 120s"


async def stop_services() -> str:
    script = _script("Stop-AdeptRuntime.ps1")
    if not script.exists():
        return "Stop script not found"
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-Force",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        output = stdout.decode("utf-8", errors="replace")
        return output
    except asyncio.TimeoutError:
        proc.kill()
        return "Stop timed out after 60s"


async def restart_services() -> str:
    script = _script("Restart-AdeptRuntime.ps1")
    if not script.exists():
        return "Restart script not found"
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(script), "-Force",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180.0)
        output = stdout.decode("utf-8", errors="replace")
        return output
    except asyncio.TimeoutError:
        proc.kill()
        return "Restart timed out after 180s"
