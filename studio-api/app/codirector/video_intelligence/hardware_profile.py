"""Creator-facing hardware capability checkmarks for video intelligence."""

from __future__ import annotations

from typing import Any

from .gpu_lease import query_free_vram_gb
from .paths import INTERNVIDEO3_MARKERS, VIDEOCHAT3_MARKERS, internvideo3_dir, model_present, videochat3_dir

DEEP_REVIEW_VRAM_GB = 16.0
FAST_REVIEW_VRAM_GB = 8.0


def hardware_profile() -> dict[str, Any]:
    videochat_ready = model_present(videochat3_dir(), VIDEOCHAT3_MARKERS)
    intern_ready = model_present(internvideo3_dir(), INTERNVIDEO3_MARKERS)
    free = query_free_vram_gb()
    total = None
    try:
        from ...vram_profiles import query_gpu_stats

        stats = query_gpu_stats()
        if stats.get("ok") and stats.get("gpus"):
            total = max(float(g.get("memory_total_mib") or 0) for g in stats["gpus"]) / 1024.0
    except Exception:
        total = None
    deep_ok = intern_ready and (total is None or total >= DEEP_REVIEW_VRAM_GB)
    return {
        "videochat3Installed": videochat_ready,
        "internvideo3Installed": intern_ready,
        "freeVramGb": free,
        "totalVramGb": round(total, 1) if total else None,
        "capabilities": {
            "timelineVisualReview": videochat_ready,
            "automaticReview": videochat_ready,
            "review3Second": videochat_ready,
            "review5Second": videochat_ready,
            "deepSequenceReasoning": deep_ok,
        },
        "messages": {
            "deepSequenceReasoning": None
            if deep_ok
            else "Additional GPU memory recommended"
            if not intern_ready
            else "Additional GPU memory recommended",
        },
    }
