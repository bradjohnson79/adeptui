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
    GpuInfo,
    OllamaStatus,
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


def _collect() -> dict:
    from runtime_supervisor.services import collect_status

    return collect_status()


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
    snap = await asyncio.to_thread(_collect)
    row = snap.get("studio_api") or {}
    ok = bool(row.get("running")) or await _probe(f"{_STUDIO_API_URL}/api/healthz", timeout=5.0)
    return StudioApiStatus(
        status=ServiceStatus.RUNNING if ok else ServiceStatus.STOPPED,
        ownership=_ownership(row.get("ownership")),
    )


async def get_ollama_status() -> OllamaStatus:
    snap = await asyncio.to_thread(_collect)
    row = snap.get("ollama") or {}
    data = await _probe_json(f"{_OLLAMA_URL}/api/tags", timeout=4.0)
    running = data is not None or bool(row.get("running"))
    return OllamaStatus(
        status=ServiceStatus.RUNNING if running else ServiceStatus.STOPPED,
        ownership=ServiceOwnership.EXTERNAL if running else _ownership(row.get("ownership")),
    )


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
    pc = await _probe_json(f"{_STUDIO_API_URL}/api/production-control/status", timeout=8.0)
    if pc:
        gpu = pc.get("gpu") or {}
        status = (gpu.get("status") or "").lower()
        if status in ("available", "healthy", "ok", "ready"):
            return GpuInfo(
                detected=True,
                name=gpu.get("device") or gpu.get("name") or "GPU",
            )
    health = await _probe_json(f"{_STUDIO_API_URL}/api/comfy/health", timeout=10.0)
    if health and health.get("gpu"):
        return GpuInfo(detected=True, name=str(health["gpu"]))
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


def _start_sync() -> str:
    from runtime_supervisor.services import LifecycleError, start_all

    try:
        report = start_all()
        return "\n".join(report.lines())
    except LifecycleError as exc:
        return f"ERROR: {exc}"


def _stop_sync() -> str:
    from runtime_supervisor.services import LifecycleError, stop_all

    try:
        results = stop_all(force=True)
        return "\n".join(f"{r.service}: {'OK' if r.ok else 'FAIL'} {r.message}" for r in results)
    except LifecycleError as exc:
        return f"ERROR: {exc}"


def _restart_sync() -> str:
    from runtime_supervisor.services import LifecycleError, restart_all

    try:
        report = restart_all(force=True)
        return "\n".join(report.lines())
    except LifecycleError as exc:
        return f"ERROR: {exc}"


async def start_services() -> str:
    return await asyncio.to_thread(_start_sync)


async def stop_services() -> str:
    return await asyncio.to_thread(_stop_sync)


async def restart_services() -> str:
    return await asyncio.to_thread(_restart_sync)
