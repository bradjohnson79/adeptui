"""Stills perception GPU preflight.

Reads Revision A lease helpers without mutating gpu_lease.py.
"""

from __future__ import annotations

from typing import Any

MIN_STILLS_VISION_VRAM_GB = 6.0


def preflight_for_stills(*, min_gb: float = MIN_STILLS_VISION_VRAM_GB) -> dict[str, Any]:
    from ..video_intelligence.gpu_lease import query_free_vram_gb

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


def request_generator_release() -> dict[str, Any]:
    from ..video_intelligence.gpu_lease import best_effort_free_generator

    return best_effort_free_generator()
