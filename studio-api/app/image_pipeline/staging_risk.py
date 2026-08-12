"""Staging recommendations for pose/spatial/direct image planning."""

from __future__ import annotations

from .contracts import (
    CreativeDirectionPacket,
    ImageApprovalRequirement,
    ImageShotIntent,
    ProjectAutomationPolicy,
    StagingRecommendation,
)


def recommend_staging(
    shot_intent: ImageShotIntent,
    creative_direction: CreativeDirectionPacket,
    project_policy: ProjectAutomationPolicy = "Ask",
) -> dict[str, object]:
    reasons: list[str] = []
    recommendation: StagingRecommendation = "direct"

    if shot_intent.subjectCount >= 3 or shot_intent.complexity == "complex":
        recommendation = "poseCraft"
        reasons.append("Multiple characters benefit from explicit figure blocking.")
    if "architectural-anchor" in shot_intent.stagingSignals or creative_direction.scenePurposeClass == "establishing":
        recommendation = "spatialMap" if recommendation == "direct" else recommendation
        reasons.append("The shot depends on clear environmental geography.")
    if shot_intent.motionLevel == "dynamic" and recommendation == "direct":
        recommendation = "poseCraft"
        reasons.append("Action-heavy motion needs pose guidance to stay readable.")

    approval = ImageApprovalRequirement(
        kind="staging-control",
        status="not-required" if project_policy == "Automatic" else "required",
        reason="Creator confirmation is needed before applying extra staging controls."
        if project_policy != "Automatic"
        else None,
        creatorTip="Review the staging helper before generation so the image still feels like your shot."
        if project_policy != "Automatic"
        else None,
    )
    if recommendation == "direct":
        approval.status = "not-required"
        approval.reason = None
        approval.creatorTip = None

    return {
        "recommendation": recommendation,
        "projectPolicy": project_policy,
        "reasons": reasons or ["The prompt is simple enough to generate directly."],
        "approvalRequirement": approval,
    }

