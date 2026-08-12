"""Queue / GPU scheduling hooks for Docker Local runtimes (W47 / Law 27).

Jobs that target ``executionClass=docker_local`` must wait for the runtime and
GPU — never silently substitute another model.
"""

from __future__ import annotations

from typing import Any, Optional


# Soft VRAM reservation ledger (process-local; sufficient for single-worker beta).
_VRAM_RESERVED_GB: dict[str, float] = {}


def parse_runtime_id(model_id: str | None) -> Optional[str]:
    if not model_id:
        return None
    if model_id.startswith("docker-runtime:"):
        return model_id.split(":", 1)[1]
    return None


def ensure_docker_runtime_ready(model_id: str | None) -> dict[str, Any]:
    """Return queue stage + readiness for a docker_local model selection.

    Stages: ready | waiting_for_runtime | waiting_for_gpu | loading | blocked
    """
    runtime_id = parse_runtime_id(model_id)
    if not runtime_id:
        return {"ok": True, "stage": "ready", "docker": False}

    from .gpu_preflight import check_gpu
    from .health import check_health
    from .manager import get_manager
    from .registry import get_runtime

    desc = get_runtime(runtime_id)
    if not desc:
        return {
            "ok": False,
            "stage": "blocked",
            "docker": True,
            "runtimeId": runtime_id,
            "message": "Docker runtime not registered",
            "noSilentFallback": True,
        }
    if desc.disabled:
        return {
            "ok": False,
            "stage": "blocked",
            "docker": True,
            "runtimeId": runtime_id,
            "message": "Docker runtime disabled — enable in Runtime Manager",
            "noSilentFallback": True,
        }
    if desc.lifecycle != "running":
        # Attempt start-if-needed (backend only)
        mgr = get_manager()
        start = mgr.start(runtime_id)
        if not start.get("ok"):
            return {
                "ok": False,
                "stage": "waiting_for_runtime",
                "docker": True,
                "runtimeId": runtime_id,
                "message": "Container Stopped — Start Runtime",
                "noSilentFallback": True,
            }
        return {
            "ok": False,
            "stage": "loading",
            "docker": True,
            "runtimeId": runtime_id,
            "message": "Runtime starting — health check pending",
            "noSilentFallback": True,
        }

    health = check_health(runtime_id)
    if not health.ok:
        return {
            "ok": False,
            "stage": "waiting_for_runtime",
            "docker": True,
            "runtimeId": runtime_id,
            "message": "Requires Repair — health check failed",
            "noSilentFallback": True,
        }

    gpu = check_gpu(runtime_id)
    if not (gpu.frameworkAccelerator or gpu.cudaAvailable):
        return {
            "ok": False,
            "stage": "waiting_for_gpu",
            "docker": True,
            "runtimeId": runtime_id,
            "message": "Waiting for GPU — CUDA/framework not ready in container",
            "noSilentFallback": True,
            "gpu": gpu.model_dump(mode="json"),
        }

    return {
        "ok": True,
        "stage": "running",
        "docker": True,
        "runtimeId": runtime_id,
        "imageDigest": desc.imageDigest,
        "classification": desc.classification,
        "gpu": gpu.model_dump(mode="json"),
        "noSilentFallback": True,
        "provenance": {
            "runtimeId": runtime_id,
            "imageDigest": desc.imageDigest,
            "classification": desc.classification,
            "executionClass": "docker_local",
            "fallbackUsed": False,
        },
    }


def reserve_vram(runtime_id: str, gb: float) -> bool:
    _VRAM_RESERVED_GB[runtime_id] = _VRAM_RESERVED_GB.get(runtime_id, 0.0) + max(0.0, gb)
    return True


def release_vram(runtime_id: str, gb: float) -> None:
    cur = _VRAM_RESERVED_GB.get(runtime_id, 0.0) - max(0.0, gb)
    if cur <= 0:
        _VRAM_RESERVED_GB.pop(runtime_id, None)
    else:
        _VRAM_RESERVED_GB[runtime_id] = cur


def uninstall_blocked_by_active_jobs(runtime_id: str, active_runtime_ids: set[str]) -> bool:
    """True when uninstall must wait (cancel-aware block)."""
    return runtime_id in active_runtime_ids or runtime_id in _VRAM_RESERVED_GB
