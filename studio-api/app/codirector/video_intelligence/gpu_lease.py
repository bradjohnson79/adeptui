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
    evidence: dict[str, Any] = {
        "comfyFreeRequested": False,
        "vramFullyReleased": False,
        "vramBeforeFreeGb": query_free_vram_gb(),
    }
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
        evidence["comfyFreeStatus"] = int(response.status_code)
    except Exception as exc:
        evidence["comfyFreeError"] = str(exc)[:240]
        logger.info("temporal vision: Comfy /free skipped: %s", evidence["comfyFreeError"])
    evidence["vramAfterFreeGb"] = query_free_vram_gb()
    after = evidence["vramAfterFreeGb"]
    if after is not None and after >= MIN_FAST_VISION_VRAM_GB:
        evidence["vramFullyReleased"] = True
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


def probe_comfy_generation_ready() -> dict[str, Any]:
    """Distinguish SOCKET_PRESENT / HTTP_RESPONSIVE / WORKFLOW_READY. Port listen is not ready."""
    import socket

    from ...config import settings

    raw = str(settings.comfy_url or "http://127.0.0.1:8188").rstrip("/")
    host = "127.0.0.1"
    port = 8188
    try:
        from urllib.parse import urlparse

        parsed = urlparse(raw)
        host = parsed.hostname or host
        port = int(parsed.port or 8188)
    except Exception:
        pass
    evidence: dict[str, Any] = {
        "url": raw,
        "tier": "DOWN",
        "socketPresent": False,
        "httpResponsive": False,
        "workflowReady": False,
    }
    try:
        with socket.create_connection((host, port), timeout=2.0):
            evidence["socketPresent"] = True
            evidence["tier"] = "SOCKET_PRESENT"
    except OSError as exc:
        evidence["socketError"] = str(exc)[:160]
        return evidence
    try:
        import httpx

        stats = httpx.get(f"{raw}/system_stats", timeout=8.0)
        evidence["systemStatsStatus"] = int(stats.status_code)
        if stats.status_code < 400:
            evidence["httpResponsive"] = True
            evidence["tier"] = "HTTP_RESPONSIVE"
        info = httpx.get(f"{raw}/object_info", timeout=12.0)
        evidence["objectInfoStatus"] = int(info.status_code)
        payload = info.json() if info.status_code < 400 else {}
        nodes = payload if isinstance(payload, dict) else {}
        evidence["objectInfoKeys"] = len(nodes)
        if info.status_code < 400 and len(nodes) > 0:
            evidence["workflowReady"] = True
            evidence["tier"] = "WORKFLOW_READY"
    except Exception as exc:
        evidence["httpError"] = str(exc)[:240]
    return evidence
