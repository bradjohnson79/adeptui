"""Candidate validation with honest pass/warning/fail/not-evaluated states."""

from __future__ import annotations

from .contracts import (
    EvaluationFinding,
    ImageCandidate,
    ImageCandidateEvaluation,
    ImageDefect,
    ImageGenerationPlan,
)


def evaluate_candidate(plan: ImageGenerationPlan, candidate: ImageCandidate) -> ImageCandidateEvaluation:
    findings: list[EvaluationFinding] = []
    defects: list[ImageDefect] = []
    honesty_notes: list[str] = []
    status = "pass"

    if candidate.status in {"draft", "queued"} and not candidate.assetId:
        status = "not-evaluated"
        honesty_notes.append("The candidate has not produced a final asset yet, so visual quality cannot be scored honestly.")
        findings.append(
            EvaluationFinding(
                code="asset_pending",
                status="not-evaluated",
                message="Generation is still pending or only a draft slot exists.",
            )
        )

    if plan.modelRoute.readiness == "blocked":
        status = "fail"
        findings.append(
            EvaluationFinding(
                code="route_blocked",
                status="fail",
                message="The plan is blocked by routing or approval requirements.",
            )
        )
        defects.append(
            ImageDefect(
                defectType="route_block",
                severity="high",
                description="A blocked route prevents this candidate from being considered production-ready.",
                suggestedFix="Approve the route or choose a local-certified option.",
            )
        )

    if candidate.previewText and plan.creativeDirection.mood.lower() not in candidate.previewText.lower():
        if status == "pass":
            status = "warning"
        findings.append(
            EvaluationFinding(
                code="mood_unverified",
                status="warning",
                message="The candidate summary does not clearly confirm the planned mood yet.",
            )
        )
        honesty_notes.append("Mood alignment is inferred from metadata, not image vision analysis.")

    summary = {
        "pass": "The candidate aligns with the available plan checks.",
        "warning": "The candidate is usable, but some creative goals are still only partially verified.",
        "fail": "The candidate misses a required readiness or quality condition.",
        "not-evaluated": "The candidate cannot be judged honestly until an image asset exists.",
    }[status]
    next_step = {
        "pass": "Use this for recommendation or creator review.",
        "warning": "Review the candidate manually and repair only the weak points.",
        "fail": "Fix the blocking issue before selecting this version.",
        "not-evaluated": "Wait for generation or produce a real asset before review.",
    }[status]

    return ImageCandidateEvaluation(
        candidateId=candidate.candidateId,
        overallStatus=status,  # type: ignore[arg-type]
        findings=findings,
        defects=defects,
        summary=summary,
        recommendedNextStep=next_step,
        honestyNotes=honesty_notes,
    )

