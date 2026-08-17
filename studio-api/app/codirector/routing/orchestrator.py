"""Phase 3 — Canonical RouteDecision orchestrator.

Ties deterministic classifier → semantic fallback → stage/context adjustment
→ lane selection → observability. Single entry point for the chat turn.

CDX-091 (Phase 7) — INTENT CLASSIFICATION (documented transitional hybrid):
This orchestrator deliberately stacks FOUR classifiers — deterministic
(routing/deterministic.py), semantic LLM fallback (routing/semantic.py),
foundation (conversation/foundation/intent.py), and the unified vocabulary
(routing/unified_intent.py classify_intent) — as a DOCUMENTED TRANSITIONAL
HYBRID. Consolidating them into a single classifier is ARCHITECTURAL and
out of scope (Phase 7 master decision). The convergence property — the
classifiers agree on EXECUTION vs non-EXECUTION over the routing corpus
(tests/fixtures/codirector2_route_cases.json), with a frozen set of
documented divergence exceptions (approve/reject lanes handled outside
execution dispatch; foundation REQUEST_ACTION overriding a proposal-class
deterministic result) — is locked by tests/test_engine_ownership.py.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from .contracts import RouteActionClass, RouteDecision
from .context import (
    CapabilityGate,
    RouterContext,
    StageSensitiveRouter,
    build_router_context,
)
from .deterministic import classify_deterministic
from .semantic import route_with_semantic_fallback
from .unified_intent import UnifiedIntent, classify_intent

logger = logging.getLogger(__name__)


def _observe(decision: RouteDecision, request_id: str, project_id: str, unified_intent: Optional[UnifiedIntent] = None) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": "route_decision",
        "requestId": request_id,
        "projectId": project_id,
        "actionClass": decision.actionClass.value if decision.actionClass else "UNKNOWN",
        "target": decision.target,
        "confidence": decision.confidence,
        "classifierSource": decision.classifierSource,
        "ambiguity": bool(decision.ambiguity),
        "executionLane": decision.executionLane,
        "writeAllowed": decision.writeAllowed,
        "capabilityAvailable": decision.capabilityAvailable,
        "destructive": decision.destructive,
        "evidence": decision.evidence,
    }
    if unified_intent is not None:
        event["unifiedIntent"] = {
            "intent": unified_intent.intent.value,
            "capability": unified_intent.capability,
            "confidence": unified_intent.confidence,
            "dispatch": unified_intent.dispatch.value,
            "classifierSource": unified_intent.classifier_source,
            "curatedToolIds": list(unified_intent.curated_tool_ids),
            "requiresClarification": unified_intent.requires_clarification,
            "evidence": list(unified_intent.evidence),
        }
    return event


def _select_lane(decision: RouteDecision) -> str:
    mapping: dict[RouteActionClass, str] = {
        RouteActionClass.DISCUSS: "discuss",
        RouteActionClass.NAVIGATE: "operator",
        RouteActionClass.READ_INSPECT: "read",
        RouteActionClass.MODIFY_KNOWLEDGE: "proposal",
        RouteActionClass.PROPOSE_CREATIVE_CHANGE: "proposal",
        RouteActionClass.EXECUTE_PRODUCTION: "proposal",
        RouteActionClass.APPROVE: "approve",
        RouteActionClass.REJECT: "reject",
        RouteActionClass.CLARIFY: "discuss",
        RouteActionClass.AMBIGUOUS: "discuss",
        RouteActionClass.UNKNOWN: "discuss",
    }
    return mapping.get(decision.actionClass, "discuss")


async def route_turn(
    message: str,
    db: Session,
    project_id: str,
    request_id: str,
    *,
    conversation_focus: Optional[str] = None,
    active_workspace: Optional[str] = None,
    session_context: Optional[dict[str, Any]] = None,
) -> tuple[RouteDecision, dict[str, Any]]:
    """Single entry point — resolve a user message to a RouteDecision.

    Returns (decision, observability_event). The observability event now
    also carries a `unifiedIntent` payload (Workstream B). Existing callers
    that unpack only (decision, event) continue to work unchanged.
    """
    decision, _unified, event = await route_turn_with_unified(
        message,
        db,
        project_id,
        request_id,
        conversation_focus=conversation_focus,
        active_workspace=active_workspace,
        session_context=session_context,
    )
    return decision, event


async def route_turn_with_unified(
    message: str,
    db: Session,
    project_id: str,
    request_id: str,
    *,
    conversation_focus: Optional[str] = None,
    active_workspace: Optional[str] = None,
    session_context: Optional[dict[str, Any]] = None,
) -> tuple[RouteDecision, UnifiedIntent, dict[str, Any]]:
    """Like `route_turn`, but also returns the `UnifiedIntent`.

    Returns (decision, unified_intent, observability_event). Used by
    `service.py` (Workstream B) to decide the dispatch branch. The unified
    intent wraps the existing deterministic + foundation classifiers — it
    does NOT replace them.
    """
    ctx: RouterContext = build_router_context(
        message,
        db,
        project_id,
        conversation_focus=conversation_focus,
        active_workspace=active_workspace,
        session_context=session_context,
    )
    deterministic = classify_deterministic(
        message,
        active_workspace=ctx.active_workspace,
        derived_stage=ctx.derived_stage,
        pending_proposal_ids=ctx.pending_proposal_ids,
        available_workspaces=ctx.available_workspaces,
    )
    stage_sensitive = StageSensitiveRouter()
    if deterministic:
        deterministic = stage_sensitive.adjust_for_stage(deterministic, ctx)
    decision = await route_with_semantic_fallback(
        message,
        deterministic_result=deterministic,
        context={
            "derived_stage": ctx.derived_stage,
            "conversation_focus": ctx.conversation_focus,
            "active_workspace": ctx.active_workspace,
            "available_action_classes": ctx.available_action_classes,
            "available_targets": ctx.available_targets,
            "stage_evidence": ctx.stage_evidence,
        },
    )
    decision = stage_sensitive.adjust_for_stage(decision, ctx)
    capability_gate = CapabilityGate()
    decision = capability_gate.check(decision, ctx)
    decision.executionLane = _select_lane(decision)

    # Wrap the existing classifiers into the unified vocabulary. The
    # foundation intent is best-effort — failure to import or run it just
    # falls back to the deterministic decision alone.
    foundation_intent: Optional[Any] = None
    try:
        from ..conversation.foundation.intent import analyze_intent

        foundation_intent = analyze_intent(message)
    except Exception:  # noqa: BLE001
        foundation_intent = None
    unified = classify_intent(
        message,
        {
            "derived_stage": ctx.derived_stage,
            "conversation_focus": ctx.conversation_focus,
            "active_workspace": ctx.active_workspace,
        },
        route_decision=decision,
        foundation_intent=foundation_intent,
    )
    event = _observe(decision, request_id, project_id, unified_intent=unified)
    return decision, unified, event
