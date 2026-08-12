"""Question budget + CreativeCuriosityThread continuity."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from .contracts import (
    QUESTION_BUDGET_BY_INITIATIVE,
    CreativeCuriosityThread,
    CreativeOperatingBundle,
    InitiativeLevel,
)


def question_budget(initiative: InitiativeLevel, *, listening_only: bool, user_requested_help: bool) -> int:
    if listening_only:
        return 0
    base = QUESTION_BUDGET_BY_INITIATIVE.get(initiative, 1)
    if user_requested_help and initiative != "QUIET_PARTNER":
        return min(3, max(base, 2))
    return base


def _thread_id(project_id: str, question: str) -> str:
    digest = hashlib.sha1(f"{project_id}:{question.strip().lower()}".encode("utf-8")).hexdigest()[:12]
    return f"cq-{digest}"


def upsert_curiosity_threads(
    bundle: CreativeOperatingBundle,
    *,
    questions: list[tuple[str, str, str]],  # question, why, priority
    source_id: str,
    max_open: int = 5,
) -> list[CreativeCuriosityThread]:
    """Preserve meaningful questions; never treat as facts."""
    existing = {t.question.strip().lower(): t for t in bundle.curiosityThreads}
    for question, why, priority in questions:
        q = (question or "").strip()
        if len(q) < 12:
            continue
        key = q.lower()
        prior = existing.get(key)
        if prior and prior.state in {"DISMISSED", "ANSWERED"}:
            continue
        if prior:
            prior.whyItMatters = why or prior.whyItMatters
            if source_id and source_id not in prior.sourceIds:
                prior.sourceIds = [*prior.sourceIds, source_id][:12]
            continue
        thread = CreativeCuriosityThread(
            id=_thread_id(bundle.projectId, q),
            projectId=bundle.projectId,
            question=q,
            whyItMatters=why or "Answering this would deepen the current material.",
            sourceIds=[source_id] if source_id else [],
            priority=priority if priority in {"HIGH", "MEDIUM", "LOW"} else "MEDIUM",  # type: ignore[arg-type]
        )
        bundle.curiosityThreads.insert(0, thread)
        existing[key] = thread

    # Cap active page questions
    open_threads = [t for t in bundle.curiosityThreads if t.state in {"OPEN", "PARTIALLY_ANSWERED", "DEFERRED"}]
    if len(open_threads) > max_open:
        # Keep highest priority
        rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        open_threads_sorted = sorted(open_threads, key=lambda t: rank.get(t.priority, 9))
        keep_ids = {t.id for t in open_threads_sorted[:max_open]}
        for t in bundle.curiosityThreads:
            if t.state in {"OPEN", "PARTIALLY_ANSWERED", "DEFERRED"} and t.id not in keep_ids:
                t.state = "DEFERRED"
    return bundle.curiosityThreads


def select_surface_question(
    bundle: CreativeOperatingBundle,
    *,
    budget: int,
    user_message: str,
) -> CreativeCuriosityThread | None:
    """Max newly surfaced questions per response = budget (usually 0 or 1)."""
    if budget <= 0:
        return None
    lower = (user_message or "").lower()
    open_threads = [t for t in bundle.curiosityThreads if t.state == "OPEN"]
    if not open_threads:
        return None

    def relevance(t: CreativeCuriosityThread) -> float:
        score = {"HIGH": 3.0, "MEDIUM": 2.0, "LOW": 1.0}.get(t.priority, 1.0)
        tokens = re.findall(r"[a-z0-9]{4,}", t.question.lower())
        hits = sum(1 for tok in tokens if tok in lower)
        score += min(2.0, hits * 0.5)
        if t.lastSurfacedAt:
            score -= 1.5  # avoid mechanical repetition
        return score

    ranked = sorted(open_threads, key=relevance, reverse=True)
    chosen = ranked[0]
    # Only resurface if relevant OR never surfaced and HIGH
    tokens = re.findall(r"[a-z0-9]{4,}", chosen.question.lower())
    relevant = any(tok in lower for tok in tokens) or not chosen.lastSurfacedAt
    if not relevant and chosen.priority != "HIGH":
        return None
    chosen.lastSurfacedAt = datetime.now(timezone.utc).isoformat()
    return chosen


def mark_answered_from_message(bundle: CreativeOperatingBundle, user_message: str) -> None:
    lower = (user_message or "").lower()
    for t in bundle.curiosityThreads:
        if t.state not in {"OPEN", "PARTIALLY_ANSWERED", "DEFERRED"}:
            continue
        tokens = [tok for tok in re.findall(r"[a-z0-9]{4,}", t.question.lower()) if tok not in {"what", "when", "where", "this", "that", "does"}]
        if tokens and sum(1 for tok in tokens if tok in lower) >= max(1, len(tokens) // 2):
            t.state = "PARTIALLY_ANSWERED" if len(lower.split()) < 20 else "ANSWERED"


def dismiss_thread(bundle: CreativeOperatingBundle, thread_id: str) -> bool:
    for t in bundle.curiosityThreads:
        if t.id == thread_id:
            t.state = "DISMISSED"
            return True
    return False
