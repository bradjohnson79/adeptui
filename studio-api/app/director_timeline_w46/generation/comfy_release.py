"""Timeline-owned Comfy VRAM/cache unload after each scene-batch generation.

POST ``{comfy_url}/free`` with unload_models + free_memory. This is not a
restart, adopt, or supervisor action. Failures are recorded and never raised
into the complete/fail path.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def release_comfy_after_timeline_generation(*, reason: str = "") -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "ok": False,
        "reason": reason or "timeline-generation-complete",
        "comfyFreeRequested": False,
    }
    try:
        import httpx

        from ...config import settings

        url = str(getattr(settings, "comfy_url", "") or "http://127.0.0.1:8188").rstrip("/") + "/free"
        evidence["url"] = url
        response = httpx.post(
            url,
            json={"unload_models": True, "free_memory": True},
            timeout=30.0,
        )
        evidence["comfyFreeRequested"] = True
        evidence["comfyFreeStatus"] = int(response.status_code)
        evidence["ok"] = response.status_code < 400
        if not evidence["ok"]:
            logger.warning(
                "Timeline Comfy /free returned %s reason=%s",
                response.status_code,
                evidence["reason"],
            )
    except Exception as exc:  # noqa: BLE001 — never fail the batch complete path
        evidence["comfyFreeError"] = str(exc)[:240]
        logger.warning("Timeline Comfy /free skipped: %s", evidence["comfyFreeError"])
    return evidence
