"""Intuitive key-question engine — scores hidden; flow-safe deferral."""

from __future__ import annotations

from ..relationship.schemas import CoDirectorRelationshipProfile
from .schemas import (
    ContextualQuestionCandidate,
    PartnershipProjectBundle,
    ProjectDestination,
    QuestionCategory,
)


def _score(q: ContextualQuestionCandidate) -> float:
    action_dep = 0.8 if q.required_before_action else 0.2
    return (q.information_value + q.urgency + action_dep) - (q.interruption_cost + 0.3)


def select_questions(
    bundle: PartnershipProjectBundle,
    *,
    relationship: CoDirectorRelationshipProfile,
    creative_stage: str,
    continue_explaining: bool,
    substantive: bool,
    user_message: str,
    question_budget: int,
) -> tuple[list[ContextualQuestionCandidate], list[ContextualQuestionCandidate]]:
    """Returns (ask_now, deferred). Never expose scores in UI."""
    candidates: list[ContextualQuestionCandidate] = []
    msg = (user_message or "").lower()
    flow_risk = (
        continue_explaining
        or relationship.narration_mode == "LISTEN_FIRST"
        or creative_stage == "EMERGENCE"
        or "keep listening" in msg
        or "keep developing" in msg
    )

    if substantive and bundle.vision.primary_destination == ProjectDestination.UNDECIDED:
        # Vision only when idea has shape — not first fragile sentence
        word_count = len((user_message or "").split())
        if word_count >= 40 or creative_stage in {"FORMATION", "EVALUATION", "PRODUCTION"} or "destination" in msg or "audience" in msg:
            candidates.append(
                ContextualQuestionCandidate(
                    project_id=bundle.journey.project_id,
                    question=(
                        "What is the larger vision for this project? Personal, online release, festival piece, "
                        "proof of concept, or something you eventually want to pitch professionally?"
                    ),
                    category=QuestionCategory.VISION,
                    why_it_matters="Destination shapes format, pitch language, and release strategy.",
                    required_before_action=False,
                    information_value=0.85,
                    interruption_cost=0.7 if flow_risk else 0.35,
                    urgency=0.4,
                    can_defer=True,
                )
            )

    if "treatment" in msg or "screenplay" in msg or "script" in msg:
        candidates.append(
            ContextualQuestionCandidate(
                project_id=bundle.journey.project_id,
                question=(
                    "How would you like to approach this—should I draft, write it with you, "
                    "or remain advisory while you write?"
                ),
                category=QuestionCategory.OWNERSHIP,
                why_it_matters="Authorship preference prevents unwanted rewriting.",
                required_before_action=True,
                information_value=0.9,
                interruption_cost=0.25,
                urgency=0.8,
                can_defer=False,
            )
        )

    ask_now: list[ContextualQuestionCandidate] = []
    deferred: list[ContextualQuestionCandidate] = list(bundle.deferred_questions)

    for q in candidates:
        if flow_risk and q.can_defer and _score(q) < 1.2:
            q.deferred = True
            deferred.append(q)
            continue
        if _score(q) >= 0.9:
            ask_now.append(q)
        elif q.can_defer:
            q.deferred = True
            deferred.append(q)

    # Pull deferred when budget and not in flow
    if not flow_risk and question_budget > 0:
        for q in list(deferred):
            if len(ask_now) >= max(1, question_budget):
                break
            if _score(q) >= 1.0:
                ask_now.append(q)
                deferred.remove(q)

    return ask_now[: max(0, question_budget)], deferred[-20:]
