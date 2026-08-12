"""Internal quality scoring for a deterministic conversation turn."""

from __future__ import annotations

import re

from .schemas import ConversationPlan, ConversationSuccessScore, ProjectIntelligenceSnapshot

_QUESTION_RE = re.compile(r"\?")
_SPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _SPACE_RE.sub(" ", (text or "").strip().lower())


def _has_repetition(reply: str) -> bool:
    parts = [part.strip() for part in re.split(r"[.!?]", reply) if part.strip()]
    normalized = [_clean(part) for part in parts]
    return len(normalized) != len(set(normalized))


def evaluate_success(
    user_message: str,
    reply: str,
    plan: ConversationPlan,
    snapshot_before: ProjectIntelligenceSnapshot,
    snapshot_after: ProjectIntelligenceSnapshot,
) -> ConversationSuccessScore:
    """Score basic conversation quality checks without exposing chain of thought."""

    checks: dict[str, bool] = {}
    notes: list[str] = []

    user_is_question = _clean(user_message).endswith("?")
    checks["answered"] = (not user_is_question) or (bool(reply.strip()) and not plan.shouldAskQuestion)
    checks["acknowledged"] = bool(reply.strip())
    checks["one_or_zero_questions"] = len(_QUESTION_RE.findall(reply)) <= 1
    checks["no_repetition"] = not _has_repetition(reply)

    if plan.shouldWriteWiki:
        before_ids = {entry.id for entry in snapshot_before.knowledgeEntries}
        after_ids = {entry.id for entry in snapshot_after.knowledgeEntries}
        checks["wiki_correct"] = bool(after_ids - before_ids) or any(
            before.state != after.state
            for before in snapshot_before.knowledgeEntries
            for after in snapshot_after.knowledgeEntries
            if before.id == after.id
        )
    else:
        checks["wiki_correct"] = True

    if plan.responseMode == "recommend_next_step":
        recommendation = (plan.recommendedNextStep or "").lower()
        checks["useful_recommendation"] = bool(recommendation) and recommendation[:24] in reply.lower()
    else:
        checks["useful_recommendation"] = True

    checks["stayed_on_stage"] = snapshot_after.currentStage == plan.creativeStage

    for key, value in checks.items():
        if not value:
            notes.append(f"check_failed:{key}")

    overall = sum(1.0 for value in checks.values() if value) / float(len(checks) or 1)
    return ConversationSuccessScore(overall=round(overall, 3), checks=checks, notes=notes)
