"""Smart Production Gates — three levels consuming the Production Readiness
Service (SMART_PRODUCTION_GATES).

Levels:
  EXPLORATION        — always allowed (storyboarding, drafts, exploration)
  PRODUCTION_WARNING — final generation allowed but warned (partial readiness)
  PRODUCTION_LOCK    — final generation blocked until readiness satisfied

The gate level is derived from scene readiness + the action scope. Wiring
into generate_scene blocks final generation on PRODUCTION_LOCK while keeping
editing available (provider outage resilience).
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from ..timeline_context.service import build_timeline_context_package

GateLevel = Literal["EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"]

GateDecision = Literal["ALLOW", "ALLOW_WITH_WARNING", "BLOCK"]


def evaluate_smart_gate(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    action_scope: str = "production",
) -> dict[str, Any]:
    """Evaluate the Smart Production Gate for a scene + action scope.

    Returns:
      {
        "ok": True,
        "level": GateLevel,
        "decision": GateDecision,
        "reason": str,
        "readiness": {...},   # consumed from the Readiness Service
        "package": {...},     # the full TimelineContextPackage
      }
    """
    ctx = build_timeline_context_package(db, project_id, scene_id, action_scope=action_scope)
    if not ctx.get("ok") or not ctx.get("package"):
        # Readiness unavailable — do not hard-block exploration; warn for production.
        level: GateLevel = "EXPLORATION" if action_scope == "exploration" else "PRODUCTION_WARNING"
        decision: GateDecision = "ALLOW" if action_scope == "exploration" else "ALLOW_WITH_WARNING"
        return {
            "ok": True,
            "level": level,
            "decision": decision,
            "reason": "Readiness unavailable — proceeding with caution. Editing remains available.",
            "readiness": None,
            "package": None,
        }

    pkg = ctx["package"]
    readiness = pkg.get("readiness", {})
    status = readiness.get("status", "BLOCKED")

    if action_scope == "exploration":
        return {
            "ok": True,
            "level": "EXPLORATION",
            "decision": "ALLOW",
            "reason": "Exploration is always allowed.",
            "readiness": readiness,
            "package": pkg,
        }

    if status == "BLOCKED":
        return {
            "ok": True,
            "level": "PRODUCTION_LOCK",
            "decision": "BLOCK",
            "reason": readiness.get("blockerSummary") or "Scene is not ready for final generation.",
            "readiness": readiness,
            "package": pkg,
        }

    if status == "PARTIAL":
        return {
            "ok": True,
            "level": "PRODUCTION_WARNING",
            "decision": "ALLOW_WITH_WARNING",
            "reason": readiness.get("blockerSummary") or "Scene is partially ready — proceed with caution.",
            "readiness": readiness,
            "package": pkg,
        }

    return {
        "ok": True,
        "level": "EXPLORATION",
        "decision": "ALLOW",
        "reason": "Scene is ready for final generation.",
        "readiness": readiness,
        "package": pkg,
    }


def can_generate_scene(
    db: Session,
    project_id: str,
    scene_id: str,
    *,
    action_scope: str = "production",
) -> tuple[bool, str, dict[str, Any]]:
    """Convenience guard for generate_scene.

    Returns (allowed, reason, gate_result). On BLOCK, generation must not
    proceed; editing remains available.
    """
    gate = evaluate_smart_gate(db, project_id, scene_id, action_scope=action_scope)
    decision = gate.get("decision", "BLOCK")
    if decision == "BLOCK":
        return False, gate.get("reason", "Generation blocked by Smart Production Gate."), gate
    return True, gate.get("reason", ""), gate
