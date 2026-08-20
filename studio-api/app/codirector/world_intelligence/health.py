"""Health probes for world intelligence worker."""

from __future__ import annotations

from .paths import vjepa2_present, vjepa2_21_present
from .worker_client import cached_cuda_probe, health as worker_health_check


def world_intelligence_status(*, probe: bool = True) -> dict:
    """Aggregated health status. Files on disk never count as live-ready."""
    model_vjepa2 = vjepa2_present()
    model_vjepa2_21 = vjepa2_21_present()
    installed = bool(model_vjepa2 or model_vjepa2_21)
    if probe:
        worker = worker_health_check()
    else:
        cached = cached_cuda_probe()
        worker = {
            "ok": bool(cached and cached.get("ok") and installed),
            "installed": installed,
            "reason": None if cached and cached.get("ok") else (cached or {}).get("reason") or "NOT_PROBED",
        }
    live = bool(worker.get("ok"))
    return {
        "available": live,
        "installed": installed or bool(worker.get("installed")),
        "workerOk": live,
        "workerError": worker.get("reason") if not live else None,
        "models": {
            "vjepa2-vitl-fpc64-256": model_vjepa2,
            "vjepa2.1-vitl-384": model_vjepa2_21,
        },
        "activeModel": worker.get("modelId") if live else None,
        "policy": "automatic",
        "advisoryOnly": True,
    }
