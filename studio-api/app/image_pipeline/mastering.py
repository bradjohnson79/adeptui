"""Mastering helpers for the image pipeline foundation."""

from __future__ import annotations

from .contracts import ImageCandidate, ImageMasteringRequest, ImageMasteringResult
from .validation import evaluate_candidate


def build_mastering_result(
    request: ImageMasteringRequest,
    candidate: ImageCandidate,
    *,
    plan=None,
) -> ImageMasteringResult:
    if request.requestedAction == "upscale" and not request.approved:
        return ImageMasteringResult(
            candidateId=candidate.candidateId,
            status="blocked",
            performedAction="none",
            disclosure="Upscale mastering was requested but not approved, so nothing was run.",
        )

    performed_action = request.requestedAction
    disclosure = "Resize-only mastering prepared. No upscale is being claimed."
    if request.requestedAction == "upscale":
        disclosure = "Upscale mastering was explicitly approved, but this foundation layer only records the request."
    elif request.requestedAction == "retouch":
        disclosure = "Retouch mastering was requested, but this foundation layer only records the request."

    result = ImageMasteringResult(
        candidateId=candidate.candidateId,
        status="completed",
        performedAction=performed_action,
        outputCandidateId=candidate.candidateId,
        outputAssetId=candidate.assetId,
        disclosure=disclosure,
    )
    if plan is not None:
        result.postValidation = evaluate_candidate(plan, candidate)
    return result

