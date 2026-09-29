"""Continuation strategy selection.

ShotState is always applied by the orchestrator. This module only names the
strongest mechanism the selected model already declares.

Motion-context latent continuation is not selected. ComfyUI-H3-Motion-Context
is not installed, its license is not cleared, and no baseline-versus-enhanced
seam comparison has shown a gain over reference video, ShotState, the last
frame, and the tail packet. LTX Continue uses the installed LTXVImgToVideo
start image. The builder's extra end-image batch is not connected to that
node, so first/last-frame conditioning is not a live path.
"""

from __future__ import annotations

from typing import Any

MOTION_CONTEXT_AVAILABLE = False


def choose_strategy(
    capabilities: Any,
    *,
    has_previous_video: bool,
    has_last_frame: bool,
    has_references: bool,
) -> str:
    if MOTION_CONTEXT_AVAILABLE and has_previous_video:
        return "motion_context"
    if bool(getattr(capabilities, "supportsVideoReferences", False)) and has_previous_video:
        return "reference_video"
    if (
        bool(getattr(capabilities, "supportsImageToVideo", False))
        and bool(getattr(capabilities, "supportsStartFrame", False))
        and has_last_frame
    ):
        return "last_frame_chain"
    if bool(getattr(capabilities, "supportsEndFrame", False)) and has_last_frame:
        return "first_last_frame"
    if bool(getattr(capabilities, "supportsReferenceToVideo", False)) and (has_last_frame or has_references):
        return "reference_set"
    if has_references:
        return "reference_set"
    if has_last_frame:
        return "last_frame_chain"
    return "reference_set"
