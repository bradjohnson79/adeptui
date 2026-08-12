"""Opt-in production feedback queue — never auto-certifies."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from .benchmark_models import FeedbackItem
from .benchmark_store import enqueue_feedback, list_feedback
from .models import utc_now_iso


def submit_feedback(
    *,
    domain: str,
    category: str = "",
    provider_id: str = "",
    model_revision: str = "",
    strategy_applied: Optional[str] = None,
    rating: Optional[int] = None,
    notes: str = "",
    project_id: Optional[str] = None,
    opt_in: bool = True,
) -> dict[str, Any]:
    if not opt_in:
        return {"ok": False, "error": {"code": "FEEDBACK_OPT_IN_REQUIRED", "message": "Feedback requires opt-in."}}
    item = FeedbackItem(
        feedbackId=f"fb_{uuid.uuid4().hex[:12]}",
        projectId=project_id,
        domain=domain,
        category=category,
        providerId=provider_id,
        modelRevision=model_revision,
        strategyApplied=strategy_applied,
        rating=rating,
        notes=notes,
        optIn=True,
        createdAt=utc_now_iso(),
    )
    enqueue_feedback(item)
    return {
        "ok": True,
        "feedback": item.model_dump(mode="json"),
        "note": "Queued for human review only — never auto-certifies.",
    }


def list_queued_feedback() -> dict[str, Any]:
    items = list_feedback()
    return {"ok": True, "items": [i.model_dump(mode="json") for i in items], "count": len(items)}
