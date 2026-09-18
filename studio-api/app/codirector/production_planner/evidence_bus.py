"""Evidence bus helpers — attach planner fields onto DeliberationDecision dumps.

Not a second brain. No TalkAskAct decisions here.
"""

from __future__ import annotations

from typing import Any, Optional

from .intent_evidence import IntentEvidence
from .plan_contracts import ProductionPlan, SelectivePreflight


def attach_plan_to_decision_fields(
    *,
    intent_evidence: Optional[IntentEvidence] = None,
    production_plan: Optional[ProductionPlan] = None,
    selective_preflight: Optional[SelectivePreflight] = None,
    pending_brief: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Serialize planner attachments for DeliberationDecision additive fields."""
    out: dict[str, Any] = {}
    if intent_evidence is not None:
        out["intentEvidence"] = intent_evidence.model_dump(mode="json")
    if production_plan is not None:
        out["productionPlan"] = production_plan.model_dump(mode="json")
    if selective_preflight is not None:
        out["selectivePreflight"] = selective_preflight.model_dump(mode="json")
    if pending_brief is not None:
        out["pendingBrief"] = dict(pending_brief)
    return out


def build_selective_preflight(
    *,
    production_plan: Optional[ProductionPlan] = None,
    strictness: str = "UNLOCKED",
    expensive_capabilities: Optional[set[str]] = None,
) -> SelectivePreflight:
    expensive_capabilities = expensive_capabilities or {
        "video.generate",
        "image.generate_batch",
        "storyboard.generate",
        "ers.generate",
    }
    multi = bool(production_plan and len(production_plan.steps) > 1)
    caps = list(production_plan.capability_ids()) if production_plan else []
    expensive = any(c in expensive_capabilities for c in caps) or multi
    strict = str(strictness or "").upper() == "STRICT"
    required = expensive or strict or multi
    checks: list[str] = []
    if strict:
        checks.append("strict_route_lock")
    if multi:
        checks.append("multi_step_dependencies")
    if expensive:
        checks.append("expensive_capability")
    runtime = list(production_plan.runtimeNeeds) if production_plan else []
    return SelectivePreflight(
        required=required,
        expensive=expensive,
        strict=strict,
        multiStep=multi,
        checks=checks,
        notes=[],
        runtimeNeeds=runtime,
    )
