"""Diagnostics — layered system health probe for Adept UI Beta."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tcp_check(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    start = time.monotonic()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        elapsed = round((time.monotonic() - start) * 1000)
        return {"listening": True, "elapsedMs": elapsed}
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        elapsed = round((time.monotonic() - start) * 1000)
        return {"listening": False, "elapsedMs": elapsed, "error": type(e).__name__}


def _http_get(url: str, timeout: float = 5.0) -> dict[str, Any]:
    import urllib.request
    start = time.monotonic()
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        elapsed = round((time.monotonic() - start) * 1000)
        return {"status": resp.status, "elapsedMs": elapsed}
    except urllib.error.HTTPError as e:
        elapsed = round((time.monotonic() - start) * 1000)
        return {"status": e.code, "elapsedMs": elapsed, "error": str(e)[:200]}
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        elapsed = round((time.monotonic() - start) * 1000)
        return {"status": None, "elapsedMs": elapsed, "error": type(e).__name__}


def _port_owner(port: int) -> dict[str, Any]:
    """Get process info for a listening port (Windows)."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"], text=True, errors="ignore", timeout=5
        )
        needle = f":{port} "
        for line in out.splitlines():
            if "LISTENING" not in line.upper() or needle not in line:
                continue
            parts = line.split()
            pid = int(parts[-1])
            try:
                proc = subprocess.check_output(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                    text=True, errors="ignore", timeout=5
                )
                name = proc.split(",")[0].strip('"') if proc else "unknown"
            except Exception:
                name = "unknown"
            return {"port": port, "listening": True, "pid": pid, "processName": name}
        return {"port": port, "listening": False, "pid": None, "processName": None}
    except Exception:
        return {"port": port, "listening": False, "pid": None, "processName": None}


def _probe_comfy() -> dict[str, Any]:
    tcp = _tcp_check("127.0.0.1", 8188)
    if not tcp["listening"]:
        return {"state": "OFFLINE", "port": 8188, "listening": False, "error": "SERVICE_NOT_LISTENING"}
    http = _http_get("http://127.0.0.1:8188/system_stats", timeout=5.0)
    if http.get("status") == 200:
        return {"state": "ONLINE", "port": 8188, "listening": True, "httpOk": True}
    return {"state": "ERROR", "port": 8188, "listening": True, "httpOk": False, "error": http.get("error")}


@router.get("/run")
def diagnostics_run() -> dict[str, Any]:
    """Layered diagnostic probe — reports system health without causing instability."""

    start_all = time.monotonic()
    result: dict[str, Any] = {"timestamp": _utc_now(), "layers": {}}

    # Layer 1: Port / process state
    ports = [_port_owner(p) for p in [8758, 8760, 8188, 8765]]
    result["layers"]["ports"] = ports

    # Layer 2: Direct API health
    api_tcp = _tcp_check("127.0.0.1", 8758)
    api_healthz = _http_get("http://127.0.0.1:8758/api/healthz", timeout=5.0)
    api_health = _http_get("http://127.0.0.1:8758/api/health", timeout=15.0)
    result["layers"]["apiDirect"] = {
        "tcp": api_tcp,
        "healthz": api_healthz,
        "health": api_health,
    }

    # Layer 3: Proxy (via 8760)
    proxy_healthz = _http_get("http://127.0.0.1:8760/api/healthz", timeout=5.0)
    proxy_health = {"status": None, "elapsedMs": None, "error": "SKIPPED"}
    if proxy_healthz.get("status") == 200:
        proxy_health = _http_get("http://127.0.0.1:8760/api/health", timeout=10.0)
    result["layers"]["proxy"] = {
        "healthz": proxy_healthz,
        "health": proxy_health,
    }

    # Layer 4: Providers
    result["layers"]["providers"] = {
        "comfyui": _probe_comfy(),
    }

    # Layer 5: Production Control (fast check — skip if API still initializing)
    pc = {"available": False, "responseMs": None, "error": "SKIPPED"}
    if api_healthz.get("status") == 200:
        pc = _http_get("http://127.0.0.1:8758/api/production-control/resolved?projectId=_global", timeout=5.0)
    result["layers"]["productionControl"] = {"available": pc.get("status") == 200, "responseMs": pc.get("elapsedMs")}

    # Layer 6: Classification
    total_ms = round((time.monotonic() - start_all) * 1000)
    result["totalMs"] = total_ms

    # Determine primary fault
    if not api_tcp.get("listening"):
        result["classification"] = {"faultDomain": "SERVICE_NOT_LISTENING", "confidence": "CONFIRMED", "evidence": "Port 8758 has no listener"}
    elif api_healthz.get("status") != 200:
        result["classification"] = {"faultDomain": "BACKEND_UNRESPONSIVE", "confidence": "HIGH", "evidence": "TCP open but /healthz did not respond"}
    elif api_health.get("status") != 200:
        result["classification"] = {"faultDomain": "BACKEND_DEGRADED", "confidence": "HIGH", "evidence": "/healthz OK but /api/health failed"}
    elif proxy_healthz.get("status") != 200 and api_healthz.get("status") == 200:
        result["classification"] = {"faultDomain": "PROXY_TIMEOUT", "confidence": "HIGH", "evidence": "Direct API alive but proxy returns errors"}
    else:
        result["classification"] = {"faultDomain": "HEALTHY", "confidence": "CONFIRMED", "evidence": "All checks passed"}

    return result
