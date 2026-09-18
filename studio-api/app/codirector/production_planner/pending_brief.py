"""PendingBrief — planner-facing view over PendingExecution (reconnect, not parallel store).

When ACT would wait for confirm OR a plan is ready for Go:
- persist pending via existing pending_store
- "Do it" / "Go ahead" binds only to a fresh (unexpired) pending brief
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

PENDING_BRIEF_TTL_SECONDS = 30 * 60  # 30 minutes

# Invalidation rules (machine-readable)
INVALIDATION_RULES = (
    "EXPIRED",
    "PROJECT_SWITCHED",
    "PLAN_REVISED",
    "STEP_CANCELLED",
    "EXPLICIT_CANCEL",
    "SUPERSEDED",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class PendingBrief(BaseModel):
    """Structured pending brief for planner confirm / Go-ahead binding."""

    briefId: str = Field(default_factory=lambda: f"brief-{uuid4().hex[:12]}")
    planId: str = ""
    stepId: str = ""
    summary: str = ""
    projectId: str = ""
    capability: str = ""
    expiresAt: str = ""
    invalidationRules: list[str] = Field(
        default_factory=lambda: list(INVALIDATION_RULES)
    )
    state: str = "AWAITING_CONFIRMATION"
    createdAt: str = Field(default_factory=lambda: _iso(_now()))
    productionPlanSnapshot: dict[str, Any] = Field(default_factory=dict)
    reasonCodes: list[str] = Field(default_factory=list)


def default_expires_at(ttl_seconds: int = PENDING_BRIEF_TTL_SECONDS) -> str:
    return _iso(_now() + timedelta(seconds=ttl_seconds))


def is_pending_fresh(
    pending: Any,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """True only when pending awaits confirmation and is unexpired."""
    if pending is None:
        return False
    state = ""
    expires = ""
    if hasattr(pending, "state"):
        state = str(getattr(pending, "state", "") or "")
        expires = str(getattr(pending, "expires_at", "") or getattr(pending, "expiresAt", "") or "")
    elif isinstance(pending, dict):
        state = str(pending.get("state") or "")
        expires = str(pending.get("expires_at") or pending.get("expiresAt") or "")
    fresh_states = {
        "AWAITING_CONFIRMATION",
        "PENDING",
        "AWAITING",
        "PLANNING",
        "AWAITING_REQUIRED_INPUT",
    }
    if state.upper() not in fresh_states:
        return False
    if not expires:
        # Legacy pending without expires_at: treat as fresh (backward compatible)
        return True
    try:
        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except Exception:
        return False
    ref = now or _now()
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    return ref <= exp_dt


def bind_pending_brief(
    *,
    user_message: str,
    pending: Any,
    commitment_explicit: bool,
) -> tuple[bool, list[str]]:
    """Return (bound, reason_codes). Binds only fresh pending + explicit commitment."""
    reasons: list[str] = []
    if not commitment_explicit:
        return False, reasons
    msg = (user_message or "").strip().lower()
    confirmish = bool(
        msg in {"do it", "do it.", "go ahead", "go ahead.", "yes", "yes.", "yes, proceed", "yes proceed"}
        or msg.startswith("do it")
        or msg.startswith("go ahead")
        or "yes, proceed" in msg
        or "yes proceed" in msg
    )
    if not confirmish and commitment_explicit:
        # normalize_commitment already said EXPLICIT — still require pending
        confirmish = True
    if not confirmish:
        return False, reasons
    if pending is None:
        reasons.append("PENDING_BRIEF_MISSING")
        return False, reasons
    if not is_pending_fresh(pending):
        reasons.append("PENDING_BRIEF_EXPIRED")
        return False, reasons
    reasons.append("PENDING_BRIEF_BOUND")
    return True, reasons


def stamp_pending_brief_fields(
    pending: Any,
    brief: PendingBrief,
) -> Any:
    """Stamp planId/stepId/summary/expiresAt onto an existing PendingExecution-like object."""
    if pending is None:
        return pending
    if hasattr(pending, "plan_id"):
        pending.plan_id = brief.planId
        pending.step_id = brief.stepId
        pending.summary = brief.summary
        pending.expires_at = brief.expiresAt or default_expires_at()
        pending.invalidation_rules = list(brief.invalidationRules)
        if hasattr(pending, "requested_parameters") and isinstance(pending.requested_parameters, dict):
            pending.requested_parameters = {
                **pending.requested_parameters,
                "pending_brief": brief.model_dump(mode="json"),
            }
        return pending
    if isinstance(pending, dict):
        pending["plan_id"] = brief.planId
        pending["step_id"] = brief.stepId
        pending["summary"] = brief.summary
        pending["expires_at"] = brief.expiresAt or default_expires_at()
        pending["invalidation_rules"] = list(brief.invalidationRules)
        return pending
    return pending


def pending_from_brief(
    brief: PendingBrief,
    *,
    unified_intent: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a PendingExecution-compatible dict from a PendingBrief."""
    return {
        "execution_id": brief.briefId,
        "capability": brief.capability,
        "project_id": brief.projectId,
        "intent": "EXECUTION",
        "unified_intent": unified_intent or {},
        "requested_parameters": {"pending_brief": brief.model_dump(mode="json")},
        "resolved_context": {"planId": brief.planId, "stepId": brief.stepId},
        "confirmation_required": True,
        "confirmation_question": brief.summary or "Proceed with the planned steps?",
        "state": brief.state or "AWAITING_CONFIRMATION",
        "plan_id": brief.planId,
        "step_id": brief.stepId,
        "summary": brief.summary,
        "expires_at": brief.expiresAt or default_expires_at(),
        "invalidation_rules": list(brief.invalidationRules),
    }


def make_brief_for_plan(
    *,
    plan_id: str,
    step_id: str = "",
    summary: str = "",
    project_id: str = "",
    capability: str = "",
    plan_snapshot: Optional[dict[str, Any]] = None,
    ttl_seconds: int = PENDING_BRIEF_TTL_SECONDS,
) -> PendingBrief:
    return PendingBrief(
        planId=plan_id,
        stepId=step_id,
        summary=summary or "Plan ready — say Go ahead / Do it to run.",
        projectId=project_id,
        capability=capability,
        expiresAt=default_expires_at(ttl_seconds),
        state="AWAITING_CONFIRMATION",
        productionPlanSnapshot=dict(plan_snapshot or {}),
        reasonCodes=["PENDING_BRIEF_READY"],
    )
