"""MAGI quarantine shelf for LatentSync / legacy lipsync engines.

Timeline Preview and Re-Take Visual authority MUST NOT import this module for
playback decisions. Composed Visual = director `video_clips` / Hop 6
`replace_visual_range` (`rtclip_*`). `lipsync_output_path` is not Preview
Visual or dialogue authority.

Reusable LatentSync/Qwen builders remain available here for a future MAGI path.
Do not delete `lipsync_builder` / `lipsync_runtime`; route Timeline away.
"""

from __future__ import annotations

import os
from typing import Any


def timeline_may_use_lipsync_playback() -> bool:
    """Timeline Preview must not use LatentSync/lipsync tracks when False (default)."""
    return os.environ.get("STUDIO_TIMELINE_LIPSYNC_PLAYBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def shelved_latentsync_builders() -> dict[str, Any]:
    """Lazy import of LatentSync builders for MAGI — not for Timeline Preview."""
    from .lipsync_builder import (
        build_latentsync_workflow,
        lipsync_available_hint,
        preferred_lipsync_node,
    )
    from . import lipsync_runtime

    return {
        "build_latentsync_workflow": build_latentsync_workflow,
        "lipsync_available_hint": lipsync_available_hint,
        "preferred_lipsync_node": preferred_lipsync_node,
        "run_latentsync_direct": getattr(lipsync_runtime, "run_latentsync_direct", None),
        "note": "MAGI shelf only — Timeline Preview uses video_clips / replace_visual_range",
    }
