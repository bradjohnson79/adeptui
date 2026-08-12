"""Creator-safe plan builder for MiniMax H3."""

from __future__ import annotations

from .contracts import AdeptMiniMaxH3Request, H3AudioPlan, H3GenerationPlan
from .three_frame import build_segmented_plan, creator_disclosure


def _summary_for_mode(request: AdeptMiniMaxH3Request) -> str:
    if request.mode == "text-to-video":
        return "Create a motion draft from your written direction."
    if request.mode == "one-frame":
        return "Create motion that starts from one guide frame."
    if request.mode == "first-last":
        return "Guide motion between a start frame and an end frame."
    if request.mode == "three-frame":
        return "Guide motion across Start, Middle, and End using a two-part assembly plan."
    return "Create a reference-guided motion draft from the selected materials."


def _disclosure_for_mode(request: AdeptMiniMaxH3Request) -> str:
    if request.mode == "three-frame":
        return creator_disclosure()
    if request.mode == "first-last":
        return "MiniMax H3 will use the first and last frame only. Additional references stay as guidance."
    if request.mode == "one-frame":
        return "MiniMax H3 will use your single guide frame plus the prompt."
    if request.mode == "reference":
        return "Reference images stay attached as guidance rather than hidden technical controls."
    return "This plan stores direction honestly before any generation request is approved."


def build_plan(request: AdeptMiniMaxH3Request) -> H3GenerationPlan:
    three_frame_plan = None
    if request.mode == "three-frame":
        try:
            three_frame_plan = build_segmented_plan(request)
        except ValueError:
            three_frame_plan = None
    audio_plan = H3AudioPlan(assetId=request.audioAssetId)
    return H3GenerationPlan(
        projectId=request.projectId,
        sourceSurface=request.sourceSurface,
        mode=request.mode,
        deployment=request.deployment,
        request=request,
        creatorSummary=_summary_for_mode(request),
        creatorDisclosure=_disclosure_for_mode(request),
        referenceAssignments=list(request.referenceAssignments),
        timelineContext=request.timelineContext,
        threeFramePlan=three_frame_plan,
        audioPlan=audio_plan,
        advancedMetadata={
            "surface": "minimax_h3",
            "threeFrameNative": False,
            "threeFrameStrategyDefault": "segmented-a",
        },
    )
