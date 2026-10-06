"""MIGRATION-ONLY leftover DirectorTimeline bridges.

Product runtime must not import this module. Use SceneTimelineMaster APIs.
"""

from __future__ import annotations

from typing import Any

from .reconcile import (
    batch_time_windows,
    reconcile_legacy_cameras,
    reconcile_legacy_image_anchors,
    reconcile_legacy_prompts,
)
from .contracts import SceneTimelineMaster
from ..director_timeline_bindings import dump_prompt_name_bindings


def reconcile_legacy_to_master(master: SceneTimelineMaster, director_tl: Any) -> bool:
    """One-shot migrate leftover tracks into Master. Not a live product path."""
    if not master.batchBlocks:
        return False
    changed = reconcile_legacy_prompts(master, list(director_tl.prompt_segments or []))
    changed = reconcile_legacy_image_anchors(master, list(director_tl.image_clips or [])) or changed
    changed = reconcile_legacy_cameras(master, list(getattr(director_tl, "camera_clips", None) or [])) or changed
    return changed


def project_prompts_to_legacy(master: SceneTimelineMaster) -> list[dict[str, Any]]:
    """TEST/MIGRATION flatten of Master prompts. Not product persist."""
    out: list[dict[str, Any]] = []
    for batch, w_start, _w_end in batch_time_windows(master):
        for seg in batch.promptSegments:
            if not str(getattr(seg, "text", "") or "").strip():
                continue
            abs_start = w_start + float(seg.start)
            length = float(seg.length)
            seg_id = seg.legacyPromptSegmentId or (
                str(seg.id) if str(seg.id).startswith("ps_") else f"ps_{seg.id}"
            )
            spoken = str(getattr(seg, "dialogue", None) or "").strip()
            out.append(
                {
                    "id": seg_id,
                    "start": round(abs_start, 6),
                    "length": round(float(length), 6),
                    "text": seg.text or "",
                    "weight": float(seg.strength or 1.0),
                    "temperature": float(getattr(seg, "temperature", 1.0) or 1.0),
                    "negative_prompt": seg.negativePrompt,
                    "reference_binding_ids": list(seg.referenceBindingIds or []),
                    "reference_name_bindings": dump_prompt_name_bindings(seg.referenceNameBindings),
                    "user_direction": seg.userDirection,
                    "production_prompt": seg.productionPrompt,
                    "dialogue": spoken or seg.dialogue,
                    "movement_segment_ref": seg.movementSegmentRef,
                    "movement_segment_revision": seg.movementSegmentRevision,
                }
            )
    return out
