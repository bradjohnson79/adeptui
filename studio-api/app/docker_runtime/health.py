"""Runtime health checks from manifest."""

from __future__ import annotations

import time
import urllib.request

from .contracts import RuntimeHealthStatus
from .manager import get_manager
from .registry import get_runtime


def check_health(runtime_id: str) -> RuntimeHealthStatus:
    desc = get_runtime(runtime_id)
    if not desc:
        return RuntimeHealthStatus(ok=False, lifecycle="absent", detail="runtime_not_found")
    if desc.disabled:
        return RuntimeHealthStatus(ok=False, lifecycle=desc.lifecycle, detail="disabled")
    if desc.executionClass == "native_local":
        # Host Comfy probe when applicable
        if desc.id == "core-comfyui":
            try:
                from ..config import settings

                url = getattr(settings, "comfy_url", "http://127.0.0.1:8188").rstrip("/") + "/system_stats"
                t0 = time.time()
                with urllib.request.urlopen(url, timeout=3) as resp:
                    ok = 200 <= resp.status < 300
                return RuntimeHealthStatus(
                    ok=ok,
                    lifecycle="running" if ok else "stopped",
                    detail="comfy_system_stats",
                    latencyMs=round((time.time() - t0) * 1000, 1),
                )
            except Exception as exc:
                return RuntimeHealthStatus(ok=False, lifecycle="stopped", detail=str(exc)[:200])
        return RuntimeHealthStatus(ok=desc.healthOk, lifecycle=desc.lifecycle, detail="native_seed")

    mgr = get_manager()
    if mgr._simulate():  # noqa: SLF001
        ok = desc.lifecycle == "running"
        return RuntimeHealthStatus(ok=ok, lifecycle=desc.lifecycle, detail="simulated_health")

    if desc.lifecycle != "running" or not desc.hostPort:
        return RuntimeHealthStatus(ok=False, lifecycle=desc.lifecycle, detail="not_running")
    endpoint = "/system_stats"
    if desc.manifest and desc.manifest.health:
        endpoint = desc.manifest.health.endpoint or endpoint
        timeout = desc.manifest.health.timeoutSeconds or 30
    else:
        timeout = 30
    url = f"http://127.0.0.1:{desc.hostPort}{endpoint}"
    try:
        t0 = time.time()
        with urllib.request.urlopen(url, timeout=min(timeout, 10)) as resp:
            ok = 200 <= resp.status < 300
        return RuntimeHealthStatus(
            ok=ok, lifecycle=desc.lifecycle, detail="http_health", latencyMs=round((time.time() - t0) * 1000, 1)
        )
    except Exception as exc:
        return RuntimeHealthStatus(ok=False, lifecycle=desc.lifecycle, detail=str(exc)[:200])
