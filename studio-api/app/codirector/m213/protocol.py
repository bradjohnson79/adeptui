"""SceneProductionPlan A-Z state machine, readiness, dependencies, blockers."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import ensure_m213_tables
from .store import M213Store

STAGES: list[tuple[str, str, str]] = [
    ("A", "Source Intake", "Collect photos/video/import/spin sources"),
    ("B", "Asset Validation", "Validate signatures, size, kinds"),
    ("C", "Route Decision", "Choose reconstruction / import / camera-spin"),
    ("D", "Environment Construction", "Build VirtualEnvironmentRecord"),
    ("E", "Environment Approval", "Persisted approval gate"),
    ("F", "Theme Recommendation", "Recommend VisualThemeProfile"),
    ("G", "Theme Preview", "Preview/compare conditioning passes"),
    ("H", "Theme Approval", "Persisted approval gate"),
    ("I", "Blocking Draft", "Blocking Canvas draft"),
    ("J", "Blocking Refine", "Multi-view merge / presets"),
    ("K", "Blocking Approval", "Persisted approval gate"),
    ("L", "Camera State", "Scene camera state"),
    ("M", "Lighting State", "Scene lighting state"),
    ("N", "Camera/Lighting Approval", "Persisted approval gate"),
    ("O", "Shot Package Build", "Shot packages from plan"),
    ("P", "Shot Package Approval", "Persisted approval gate"),
    ("Q", "Concept Draft", "Draft tier concept"),
    ("R", "Concept Production", "Production / Final Candidate tiers"),
    ("S", "Concept Approval", "Persisted approval gate"),
    ("T", "Draft Stitch", "Stitch draft timeline"),
    ("U", "Timeline Publish", "Publish to DirectorTimeline/editor"),
    ("V", "Selective Regenerate", "Regenerate selected shots"),
    ("W", "Final Candidate", "Final candidate package"),
    ("X", "Bible / Continuity Bind", "Bind + continuity warnings"),
    ("Y", "Readiness Checkpoint", "GO / NO-GO"),
    ("Z", "Final Delivery", "Archive / handoff"),
]

STAGE_IDS = [s[0] for s in STAGES]
MODES = ("guided", "assisted", "producer")

# Stages that require an approval record before advance
APPROVAL_GATES = {
    "E": "environment",
    "H": "theme",
    "K": "blocking",
    "N": "camera_lighting",
    "P": "shot_package",
    "S": "concept",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stage_catalog() -> list[dict[str, Any]]:
    return [
        {"id": sid, "name": name, "description": desc, "requiresApproval": sid in APPROVAL_GATES}
        for sid, name, desc in STAGES
    ]


def create_plan(
    db: Session,
    *,
    project_id: str,
    environment_id: str | None = None,
    mode: str = "guided",
) -> dict[str, Any]:
    ensure_m213_tables()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    pid = str(uuid.uuid4())
    plan = {
        "stages": stage_catalog(),
        "currentStage": "A",
        "mode": mode,
        "vpc": "virtual-production-coordinator",
    }
    deps = [
        {"id": "dep-env", "requires": "E", "blocks": ["I", "L", "M"]},
        {"id": "dep-block", "requires": "K", "blocks": ["O", "Q"]},
        {"id": "dep-cam", "requires": "N", "blocks": ["O", "Q"]},
    ]
    db.execute(
        text(
            "INSERT INTO m213_scene_plans "
            "(id, project_id, environment_id, mode, stage, readiness, plan_json, blockers_json, "
            "dependencies_json, approvals_json, created_at, updated_at) "
            "VALUES (:id, :project_id, :environment_id, :mode, 'A', 'NO-GO', :plan_json, '[]', "
            ":dependencies_json, '{}', :ts, :ts)"
        ),
        {
            "id": pid,
            "project_id": project_id,
            "environment_id": environment_id,
            "mode": mode,
            "plan_json": json.dumps(plan),
            "dependencies_json": json.dumps(deps),
            "ts": _now(),
        },
    )
    db.commit()
    M213Store.log_capability(
        db,
        capability_id="ve.scene_production.plan",
        action="create",
        project_id=project_id,
        payload={"planId": pid, "mode": mode},
    )
    return get_plan(db, pid)  # type: ignore[return-value]


def get_plan(db: Session, plan_id: str) -> Optional[dict[str, Any]]:
    ensure_m213_tables()
    row = db.execute(
        text(
            "SELECT id, project_id, environment_id, mode, stage, readiness, plan_json, "
            "blockers_json, dependencies_json, approvals_json, created_at, updated_at "
            "FROM m213_scene_plans WHERE id = :id"
        ),
        {"id": plan_id},
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "environmentId": row["environment_id"],
        "mode": row["mode"],
        "stage": row["stage"],
        "readiness": row["readiness"],
        "plan": json.loads(row["plan_json"] or "{}"),
        "blockers": json.loads(row["blockers_json"] or "[]"),
        "dependencies": json.loads(row["dependencies_json"] or "[]"),
        "approvals": json.loads(row["approvals_json"] or "{}"),
        "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]),
        "stages": stage_catalog(),
    }


def _require_approval(db: Session, plan: dict[str, Any], stage: str) -> Optional[str]:
    gate = APPROVAL_GATES.get(stage)
    if not gate:
        return None
    approvals = plan.get("approvals") or {}
    if approvals.get(gate):
        return None
    # also check persisted approvals table for environment subject
    return f"Approval gate '{gate}' not satisfied for stage {stage}"


def advance_plan(
    db: Session,
    *,
    plan_id: str,
    to_stage: str | None = None,
    record_approval_gate: str | None = None,
    subject_id: str | None = None,
    actor: str = "user",
    note: str = "",
) -> dict[str, Any]:
    """Advance only with explicit call; never silent. Approval gates must be persisted."""
    plan = get_plan(db, plan_id)
    if not plan:
        raise LookupError("plan not found")
    if record_approval_gate:
        if not subject_id:
            raise ValueError("subject_id required when recording approval gate")
        M213Store.record_approval(
            db,
            project_id=plan["projectId"],
            gate=record_approval_gate,
            subject_id=subject_id,
            approved=True,
            actor=actor,
            note=note,
        )
        approvals = dict(plan["approvals"])
        approvals[record_approval_gate] = {
            "subjectId": subject_id,
            "actor": actor,
            "note": note,
            "at": _now(),
        }
        db.execute(
            text("UPDATE m213_scene_plans SET approvals_json = :a, updated_at = :ts WHERE id = :id"),
            {"a": json.dumps(approvals), "ts": _now(), "id": plan_id},
        )
        db.commit()
        plan = get_plan(db, plan_id)
        assert plan is not None

    current = plan["stage"]
    if to_stage is None:
        idx = STAGE_IDS.index(current)
        if idx >= len(STAGE_IDS) - 1:
            to_stage = current
        else:
            to_stage = STAGE_IDS[idx + 1]
    if to_stage not in STAGE_IDS:
        raise ValueError(f"invalid stage {to_stage}")
    # Cannot skip past unmet approval for current stage if leaving an approval stage
    if current in APPROVAL_GATES and STAGE_IDS.index(to_stage) > STAGE_IDS.index(current):
        err = _require_approval(db, plan, current)
        if err:
            blockers = list(plan["blockers"])
            blockers.append({"stage": current, "reason": err, "at": _now()})
            db.execute(
                text("UPDATE m213_scene_plans SET blockers_json = :b, readiness = 'NO-GO', updated_at = :ts WHERE id = :id"),
                {"b": json.dumps(blockers), "ts": _now(), "id": plan_id},
            )
            db.commit()
            out = get_plan(db, plan_id)
            assert out is not None
            out["advanced"] = False
            out["blocker"] = err
            out["silentAdvance"] = False
            return out

    readiness = "GO" if to_stage in {"Y", "Z"} and not plan["blockers"] else plan["readiness"]
    if to_stage == "Y":
        readiness = "GO" if not plan["blockers"] and plan["approvals"] else "NO-GO"
    db.execute(
        text(
            "UPDATE m213_scene_plans SET stage = :stage, readiness = :readiness, updated_at = :ts WHERE id = :id"
        ),
        {"stage": to_stage, "readiness": readiness, "ts": _now(), "id": plan_id},
    )
    db.commit()
    # Emit M2.12 feedback event hook (no auto global lessons)
    try:
        from ..m212.bridge import collect_m211_reject_signals  # type: ignore
    except Exception:
        collect_m211_reject_signals = None  # noqa: F841
    try:
        from ..m212 import bridge as m212_bridge

        if hasattr(m212_bridge, "emit_feedback_event"):
            m212_bridge.emit_feedback_event(  # type: ignore[attr-defined]
                db,
                project_id=plan["projectId"],
                kind="m213_stage_advance",
                payload={"planId": plan_id, "from": current, "to": to_stage},
                auto_global_lesson=False,
            )
    except Exception:
        # Soft hook — never block production protocol on learning bridge absence
        M213Store.log_capability(
            db,
            capability_id="ve.vpc.coordinate",
            action="feedback_hook",
            project_id=plan["projectId"],
            payload={
                "planId": plan_id,
                "from": current,
                "to": to_stage,
                "autoGlobalLesson": False,
                "emitted": False,
            },
        )

    out = get_plan(db, plan_id)
    assert out is not None
    out["advanced"] = True
    out["fromStage"] = current
    out["silentAdvance"] = False
    return out


def add_blocker(db: Session, *, plan_id: str, reason: str, stage: str | None = None) -> dict[str, Any]:
    plan = get_plan(db, plan_id)
    if not plan:
        raise LookupError("plan not found")
    blockers = list(plan["blockers"])
    blockers.append({"stage": stage or plan["stage"], "reason": reason, "at": _now()})
    db.execute(
        text(
            "UPDATE m213_scene_plans SET blockers_json = :b, readiness = 'NO-GO', updated_at = :ts WHERE id = :id"
        ),
        {"b": json.dumps(blockers), "ts": _now(), "id": plan_id},
    )
    db.commit()
    return get_plan(db, plan_id)  # type: ignore[return-value]


def coordination_dashboard(plan: dict[str, Any]) -> dict[str, Any]:
    """Status categories from Product addendum §40 (honest scaffold)."""
    stage = plan.get("stage", "A")
    idx = STAGE_IDS.index(stage) if stage in STAGE_IDS else 0
    return {
        "planId": plan.get("id"),
        "mode": plan.get("mode"),
        "currentStage": stage,
        "readiness": plan.get("readiness"),
        "categories": {
            "intake": "complete" if idx >= 2 else "active" if idx < 2 else "pending",
            "environment": "complete" if idx >= 5 else "active" if idx >= 2 else "pending",
            "theme": "complete" if idx >= 8 else "active" if idx >= 5 else "pending",
            "blocking": "complete" if idx >= 11 else "active" if idx >= 8 else "pending",
            "cameraLighting": "complete" if idx >= 14 else "active" if idx >= 11 else "pending",
            "shots": "complete" if idx >= 16 else "active" if idx >= 14 else "pending",
            "concepts": "complete" if idx >= 19 else "active" if idx >= 16 else "pending",
            "timeline": "complete" if idx >= 21 else "active" if idx >= 19 else "pending",
            "delivery": "complete" if idx >= 25 else "active" if idx >= 21 else "pending",
        },
        "blockers": plan.get("blockers") or [],
        "dependencies": plan.get("dependencies") or [],
        "approvals": plan.get("approvals") or {},
        "vpcSpecialist": "virtual-production-coordinator",
    }
