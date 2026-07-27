"""Conflict classify + synthesize; DecisionImpact + revision propagation."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .contracts import ProductionDecisionImpact
from .db import ensure_m214_tables
from .honesty import default_honesty
from .store import M214Store, _jid, _now


def detect_conflicts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for m in messages:
        body = (m.get("body") or "").lower()
        if m.get("kind") == "conflict" or "conflict" in body or "disagree" in body:
            conflicts.append(
                {
                    "id": m.get("id"),
                    "classification": "departmental",
                    "from": m.get("from_specialist"),
                    "to": m.get("to_specialist"),
                    "summary": m.get("body"),
                    "honesty": default_honesty(),
                }
            )
    return conflicts


def synthesize_conflicts(conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not conflicts:
        return {
            "hasConflicts": False,
            "synthesis": "No active conflicts.",
            "primaryNextAction": "Continue with primary next action on the UnifiedSceneBrief.",
        }
    lines = [f"- {c['from']} vs {c['to']}: {c['summary']}" for c in conflicts]
    return {
        "hasConflicts": True,
        "synthesis": "Conflicts require user direction:\n" + "\n".join(lines),
        "primaryNextAction": "Choose a conflict resolution in Approval Center",
        "conflicts": conflicts,
    }


def calculate_impact(
    db: Session,
    *,
    project_id: str,
    decision_id: str,
    decision_summary: str,
    scene_id: str = "",
    affected_departments: Optional[list[str]] = None,
    previously_approved: Optional[list[str]] = None,
) -> dict[str, Any]:
    ensure_m214_tables()
    affected = affected_departments or ["storyteller", "sound-producer", "cinematographer"]
    approved = previously_approved or ["story", "bible"]
    # Preserve unaffected approvals
    revalidate = [d for d in affected if d not in {"continuity-analyst"}]
    preserved = [a for a in approved if a not in revalidate]
    impact = ProductionDecisionImpact(
        project_id=project_id,
        scene_id=scene_id,
        decision_id=decision_id,
        decision_summary=decision_summary,
        affected_departments=affected,
        revalidate_keys=revalidate,
        preserved_approvals=preserved,
        impact_summary=f"Decision impacts {', '.join(affected)}; preserved approvals: {', '.join(preserved) or 'none'}",
        payload={"silentMutation": False, "extendsM211Decisions": True},
    )
    db.execute(
        text(
            "INSERT INTO m214_decision_impacts "
            "(id, project_id, scene_id, decision_id, impact_json, created_at) "
            "VALUES (:id, :pid, :sid, :did, :j, :ts)"
        ),
        {
            "id": impact.id,
            "pid": project_id,
            "sid": scene_id,
            "did": decision_id,
            "j": _jid(impact.to_dict()),
            "ts": _now(),
        },
    )
    db.commit()
    M214Store.log_capability(
        db, capability_id="production_team.impact.calculate", action="calculate", project_id=project_id
    )
    M214Store.log_capability(
        db, capability_id="production_team.decision.propagate", action="propagate", project_id=project_id
    )
    M214Store.log_capability(
        db, capability_id="production_team.state.revalidate", action="revalidate", project_id=project_id
    )
    return impact.to_dict()
