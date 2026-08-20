"""Sequential GPU lease: generation first, then perception, then unload."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MIN_FAST_VISION_VRAM_GB = 6.0


def query_free_vram_gb() -> float | None:
    try:
        from ...vram_profiles import query_gpu_stats

        stats = query_gpu_stats()
        if not stats.get("ok") or not stats.get("gpus"):
            return None
        free_mib = max(float(g.get("memory_free_mib") or 0) for g in stats["gpus"])
        if free_mib <= 0:
            return None
        return round(free_mib / 1024.0, 2)
    except Exception:
        return None


def best_effort_free_generator() -> dict[str, Any]:
    evidence: dict[str, Any] = {"comfyFreeRequested": False, "vramFullyReleased": False}
    try:
        import httpx

        from ...config import settings

        url = str(settings.comfy_url).rstrip("/") + "/free"
        response = httpx.post(
            url,
            json={"unload_models": True, "free_memory": True},
            timeout=30.0,
        )
        evidence["comfyFreeRequested"] = response.status_code < 400
        evidence["comfyFreeStatus"] = response.status_code
    except Exception as exc:
        evidence["comfyFreeError"] = str(exc)[:240]
        logger.info("temporal vision: Comfy /free skipped: %s", evidence["comfyFreeError"])
    # Honesty: a free request is not proof the GPU is idle.
    return evidence


def preflight_for_review(*, min_gb: float = MIN_FAST_VISION_VRAM_GB) -> dict[str, Any]:
    free = query_free_vram_gb()
    if free is None:
        return {"ok": True, "freeVramGb": None, "reason": None, "unknownVram": True}
    if free < min_gb:
        return {
            "ok": False,
            "freeVramGb": free,
            "reason": "INSUFFICIENT_VRAM",
            "unknownVram": False,
        }
    return {"ok": True, "freeVramGb": free, "reason": None, "unknownVram": False}
