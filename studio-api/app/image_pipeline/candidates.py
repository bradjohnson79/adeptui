"""Candidate helpers for image pipeline draft selection."""

from __future__ import annotations

from .contracts import (
    ImageCandidate,
    ImageCandidateEvaluation,
    ImageCandidateGroup,
    ImageGenerationPlan,
    utc_now,
)


def create_candidate_group(plan: ImageGenerationPlan, requested_count: int) -> ImageCandidateGroup:
    candidates = [
        ImageCandidate(
            groupId="pending",
            projectId=plan.projectId,
            planId=plan.planId,
            label=f"Candidate {index + 1}",
            previewText=plan.previewSummary,
            explanation="Draft slot created from the prepared plan.",
        )
        for index in range(requested_count)
    ]
    group = ImageCandidateGroup(
        projectId=plan.projectId,
        planId=plan.planId,
        requestedCount=requested_count,
        candidates=[],
        status="draft",
    )
    for candidate in candidates:
        candidate.groupId = group.groupId
        group.candidates.append(candidate)
    return group


def add_candidate(group: ImageCandidateGroup, candidate: ImageCandidate) -> ImageCandidateGroup:
    candidate.groupId = group.groupId
    candidate.updatedAt = utc_now()
    group.candidates.append(candidate)
    group.updatedAt = utc_now()
    return group


def recommend_candidate(group: ImageCandidateGroup) -> tuple[ImageCandidate | None, str]:
    if not group.candidates:
        explanation = "There are no candidates yet, so nothing can be recommended."
        group.explanation = explanation
        return None, explanation

    ranked = sorted(
        group.candidates,
        key=lambda item: (
            0 if item.status in {"ready", "selected", "mastered"} else 1,
            0
            if item.evaluation and item.evaluation.overallStatus == "pass"
            else 1
            if item.evaluation and item.evaluation.overallStatus == "warning"
            else 2,
            item.label,
        ),
    )
    winner = ranked[0]
    evaluation_note = "has not been fully reviewed yet"
    if winner.evaluation:
        evaluation_note = f"earned a {winner.evaluation.overallStatus} review"
    explanation = (
        f"{winner.label} is the best next pick because it is the most production-ready option and {evaluation_note}. "
        f"Choose it if the framing and mood already feel closest to the plan."
    )
    group.recommendedCandidateId = winner.candidateId
    group.explanation = explanation
    group.updatedAt = utc_now()
    return winner, explanation


def select_candidate(group: ImageCandidateGroup, candidate_id: str) -> ImageCandidateGroup:
    found = False
    for candidate in group.candidates:
        selected = candidate.candidateId == candidate_id
        candidate.creatorSelected = selected
        if selected:
            candidate.status = "selected"
            found = True
        elif candidate.status == "selected":
            candidate.status = "ready" if candidate.jobId or candidate.assetId else "draft"
        candidate.updatedAt = utc_now()
    if not found:
        raise ValueError(f"Candidate not found: {candidate_id}")
    group.selectedCandidateId = candidate_id
    group.updatedAt = utc_now()
    group.status = "selected"
    return group


def attach_evaluation(
    group: ImageCandidateGroup,
    candidate_id: str,
    evaluation: ImageCandidateEvaluation,
) -> ImageCandidateGroup:
    for candidate in group.candidates:
        if candidate.candidateId == candidate_id:
            candidate.evaluation = evaluation
            candidate.updatedAt = utc_now()
            break
    group.updatedAt = utc_now()
    return group

