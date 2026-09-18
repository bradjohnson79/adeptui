"""Wave4 PlanService reconnect policy.

Low-risk path: if an active Wave4 ProductionPlan already exists for the project,
stamp its planId onto the planner ProductionPlan.wave4PlanId (join key only).

create_draft auto-persist is SKIPPED: Wave4 drafts carry their own approval
state machine and would compete as a second durable plan authority when the
planner stub is still deliberation-facing TALK+purpose=plan. Persist only after
creator Go / explicit Wave4 propose — out of scope for this phase.
"""

from __future__ import annotations

from typing import Any, Optional

WAVE4_RECONNECT_POLICY = {
    "mode": "link_active_only",
    "create_draft": "SKIPPED",
    "reason": (
        "Auto create_draft would dual-write Wave4 durable plans on every planning "
        "TALK turn, competing with DeliberationDecision + PendingExecution. "
        "Link active Wave4 planId when present; otherwise leave wave4PlanId empty."
    ),
}


def link_active_wave4_plan_id(
    db: Any,
    project_id: str,
    production_plan: Any,
) -> tuple[Any, dict[str, Any]]:
    """Stamp wave4PlanId from active Wave4 plan when available. Never creates."""
    meta = {
        "policy": WAVE4_RECONNECT_POLICY["mode"],
        "createDraft": WAVE4_RECONNECT_POLICY["create_draft"],
        "linked": False,
        "wave4PlanId": "",
        "skipReason": "",
    }
    if not project_id or db is None or production_plan is None:
        meta["skipReason"] = "missing_db_or_project_or_plan"
        return production_plan, meta
    try:
        from app.codirector.plans.service import PlanService

        active = PlanService.active_plan(db, project_id)
    except Exception as exc:
        meta["skipReason"] = f"active_plan_error:{type(exc).__name__}"
        return production_plan, meta
    if active is None:
        meta["skipReason"] = WAVE4_RECONNECT_POLICY["reason"]
        return production_plan, meta
    wid = str(getattr(active, "planId", "") or "")
    if not wid:
        meta["skipReason"] = "active_plan_missing_id"
        return production_plan, meta
    if hasattr(production_plan, "wave4PlanId"):
        production_plan.wave4PlanId = wid
    elif isinstance(production_plan, dict):
        production_plan["wave4PlanId"] = wid
    meta["linked"] = True
    meta["wave4PlanId"] = wid
    return production_plan, meta
