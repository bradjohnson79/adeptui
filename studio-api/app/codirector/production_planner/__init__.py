"""Co-Director Production Planner — evidence + plan compile (not a second brain).

Laws:
- DeliberationDecision remains sole TALK/ASK/ACT/STOP authority.
- Planning speech uses act=TALK + responsePlan.purpose="plan" (no PLAN act enum).
- Classifiers feed IntentEvidence only; never independent final ACT.
- Reconnect Wave4 ProductionPlan + ExecutionPlan + PendingExecution; do not invent a parallel planner service.
"""

from __future__ import annotations

from .intent_evidence import IntentEvidence, build_intent_evidence
from .plan_contracts import (
    PLANNER_SCHEMA_VERSION,
    PlanStep,
    ProductionPlan,
    SelectivePreflight,
)
from .compile import compile_multistep_request, compile_execution_steps
from .pending_brief import (
    PendingBrief,
    PENDING_BRIEF_TTL_SECONDS,
    bind_pending_brief,
    is_pending_fresh,
    pending_from_brief,
    stamp_pending_brief_fields,
)
from .failure_codes import FailureReasonCode, ALL_FAILURE_REASON_CODES
from .evidence_bus import attach_plan_to_decision_fields
from .pack_bridge import (
    bridge_compile_to_execution_steps,
    apply_production_plan_to_pack,
    dependency_blocked_steps,
)
from .retry import build_retry_brief, extract_failed_step
from .wave4_reconnect import link_active_wave4_plan_id, WAVE4_RECONNECT_POLICY

__all__ = [
    "IntentEvidence",
    "build_intent_evidence",
    "PLANNER_SCHEMA_VERSION",
    "PlanStep",
    "ProductionPlan",
    "SelectivePreflight",
    "compile_multistep_request",
    "compile_execution_steps",
    "PendingBrief",
    "PENDING_BRIEF_TTL_SECONDS",
    "bind_pending_brief",
    "is_pending_fresh",
    "pending_from_brief",
    "stamp_pending_brief_fields",
    "FailureReasonCode",
    "ALL_FAILURE_REASON_CODES",
    "attach_plan_to_decision_fields",
    "bridge_compile_to_execution_steps",
    "apply_production_plan_to_pack",
    "dependency_blocked_steps",
    "build_retry_brief",
    "extract_failed_step",
    "link_active_wave4_plan_id",
    "WAVE4_RECONNECT_POLICY",
]
