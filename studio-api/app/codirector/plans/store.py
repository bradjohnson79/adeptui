"""ORM persistence for Wave 4 production plans (head + versions + events + idempotency)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import (
    CoDirectorPlanCommandIdempotency,
    CoDirectorProductionPlan,
    CoDirectorProductionPlanEvent,
    CoDirectorProductionPlanVersion,
    Project,
)
from ..errors import PLAN_ACCESS_DENIED, PLAN_NOT_FOUND, PROJECT_NOT_FOUND, PROJECT_REQUIRED, CoDirectorError
from .schemas import PlanEvent, ProductionPlan


def require_project(db: Session, project_id: Optional[str]) -> Project:
    if not project_id:
        raise CoDirectorError(
            PROJECT_REQUIRED,
            "An explicit project is required for production plans.",
            recoverable=False,
            recommended_action="select_project",
        )
    project = db.get(Project, project_id)
    if not project:
        raise CoDirectorError(
            PROJECT_NOT_FOUND,
            "Project not found.",
            details={"projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )
    return project


def get_head(db: Session, project_id: str, plan_id: str) -> CoDirectorProductionPlan:
    row = db.get(CoDirectorProductionPlan, plan_id)
    if not row:
        raise CoDirectorError(
            PLAN_NOT_FOUND,
            "Production plan not found.",
            details={"planId": plan_id, "projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )
    if row.project_id != project_id:
        raise CoDirectorError(
            PLAN_ACCESS_DENIED,
            "Plan belongs to a different project.",
            details={"planId": plan_id, "projectId": project_id},
            recoverable=False,
            recommended_action="none",
        )
    return row


def row_to_plan(row: CoDirectorProductionPlan) -> ProductionPlan:
    data = json.loads(row.plan_json or "{}")
    # Prefer head columns for lifecycle fields when present
    data.setdefault("planId", row.id)
    data.setdefault("projectId", row.project_id)
    data["state"] = row.status or data.get("state") or "draft"
    data["version"] = int(getattr(row, "version", None) or data.get("version") or 1)
    data["title"] = row.title or data.get("title") or ""
    data["requestId"] = row.request_id or data.get("requestId")
    data["playbookId"] = row.playbook_id or data.get("playbookId")
    data["conversationId"] = getattr(row, "conversation_id", None) or data.get("conversationId")
    data["activeStepId"] = getattr(row, "active_step_id", None) or data.get("activeStepId")
    data["parentVersionId"] = getattr(row, "parent_version_id", None) or data.get("parentVersionId")
    data["revisionReason"] = getattr(row, "revision_reason", None) or data.get("revisionReason")
    if getattr(row, "paused_at", None):
        data["pausedAt"] = row.paused_at.isoformat()
    if getattr(row, "cancelled_at", None):
        data["cancelledAt"] = row.cancelled_at.isoformat()
    if getattr(row, "archived_at", None):
        data["archivedAt"] = row.archived_at.isoformat()
    if getattr(row, "completed_at", None):
        data["completedAt"] = row.completed_at.isoformat()
    data["createdAt"] = row.created_at.isoformat() if row.created_at else data.get("createdAt") or ""
    data["updatedAt"] = row.updated_at.isoformat() if row.updated_at else data.get("updatedAt") or ""
    data["unapproved"] = data.get("state") in {"draft", "proposed", "awaiting_approval"} or bool(data.get("unapproved", True))
    if data.get("state") in {"approved", "ready", "blocked", "paused"}:
        data["unapproved"] = False
    # Migrate legacy intelligence shape
    if "objective" not in data and data.get("summary"):
        data["objective"] = data.get("summary") or ""
    if data.get("steps") and isinstance(data["steps"], list):
        normalized = []
        for i, s in enumerate(data["steps"]):
            if not isinstance(s, dict):
                continue
            step = dict(s)
            step.setdefault("stepId", step.get("stepId") or f"step-{i+1}")
            step.setdefault("planId", row.id)
            step.setdefault("order", step.get("order", i + 1))
            step.setdefault("title", step.get("title") or f"Step {i+1}")
            step.setdefault("category", step.get("category") or "system")
            step.setdefault("state", step.get("status") or step.get("state") or "pending")
            step.setdefault("dependsOn", step.get("dependsOn") or [])
            step.setdefault("blockedBy", step.get("blockedBy") or [])
            step.setdefault("requiresApproval", step.get("requiresApproval", True))
            step.setdefault("approvalRequirementIds", step.get("approvalRequirementIds") or [])
            step.setdefault("requiredCapabilities", step.get("requiredCapabilities") or ([step["capability"]] if step.get("capability") else []))
            step.setdefault("requiredInputs", step.get("requiredInputs") or [])
            step.setdefault("expectedOutputs", step.get("expectedOutputs") or [])
            step.setdefault("proposedToolId", step.get("proposedToolId") or step.get("toolId"))
            step.setdefault("executionAvailability", step.get("executionAvailability") or "deferred")
            normalized.append(step)
        data["steps"] = normalized
    if data.get("blockers") and data["blockers"] and isinstance(data["blockers"][0], str):
        data["blockers"] = [
            {
                "blockerId": f"legacy-{i}",
                "planId": row.id,
                "category": "system",
                "severity": "warning",
                "title": b,
                "description": b,
                "sourceType": "legacy",
                "resolutionType": "user_action",
                "state": "open",
                "createdAt": data.get("createdAt") or "",
            }
            for i, b in enumerate(data["blockers"])
        ]
    return ProductionPlan.model_validate(data)


def list_heads(db: Session, project_id: str, *, limit: int = 50) -> list[CoDirectorProductionPlan]:
    return (
        db.query(CoDirectorProductionPlan)
        .filter(CoDirectorProductionPlan.project_id == project_id)
        .order_by(CoDirectorProductionPlan.updated_at.desc())
        .limit(limit)
        .all()
    )


def find_active(db: Session, project_id: str) -> Optional[CoDirectorProductionPlan]:
    active_states = ("draft", "proposed", "awaiting_approval", "approved", "ready", "blocked", "paused", "in_progress")
    return (
        db.query(CoDirectorProductionPlan)
        .filter(
            CoDirectorProductionPlan.project_id == project_id,
            CoDirectorProductionPlan.status.in_(active_states),
        )
        .order_by(CoDirectorProductionPlan.updated_at.desc())
        .first()
    )


def get_idempotency(db: Session, project_id: str, request_id: str) -> Optional[dict[str, Any]]:
    if not request_id:
        return None
    row = (
        db.query(CoDirectorPlanCommandIdempotency)
        .filter(
            CoDirectorPlanCommandIdempotency.project_id == project_id,
            CoDirectorPlanCommandIdempotency.request_id == request_id,
        )
        .first()
    )
    if not row:
        return None
    try:
        return json.loads(row.result_json or "{}")
    except Exception:
        return None


def list_versions(db: Session, project_id: str, plan_id: str) -> list[CoDirectorProductionPlanVersion]:
    get_head(db, project_id, plan_id)
    return (
        db.query(CoDirectorProductionPlanVersion)
        .filter(
            CoDirectorProductionPlanVersion.plan_id == plan_id,
            CoDirectorProductionPlanVersion.project_id == project_id,
        )
        .order_by(CoDirectorProductionPlanVersion.version.desc())
        .all()
    )


def get_version_snapshot(db: Session, project_id: str, plan_id: str, version: int) -> ProductionPlan:
    get_head(db, project_id, plan_id)
    row = (
        db.query(CoDirectorProductionPlanVersion)
        .filter(
            CoDirectorProductionPlanVersion.plan_id == plan_id,
            CoDirectorProductionPlanVersion.project_id == project_id,
            CoDirectorProductionPlanVersion.version == version,
        )
        .first()
    )
    if not row:
        raise CoDirectorError(
            PLAN_NOT_FOUND,
            "Plan version not found.",
            details={"planId": plan_id, "version": version},
            recoverable=False,
            recommended_action="none",
        )
    return ProductionPlan.model_validate(json.loads(row.snapshot_json or "{}"))


def list_events(db: Session, project_id: str, plan_id: str, *, limit: int = 100) -> list[PlanEvent]:
    get_head(db, project_id, plan_id)
    rows = (
        db.query(CoDirectorProductionPlanEvent)
        .filter(
            CoDirectorProductionPlanEvent.plan_id == plan_id,
            CoDirectorProductionPlanEvent.project_id == project_id,
        )
        .order_by(CoDirectorProductionPlanEvent.created_at.asc())
        .limit(limit)
        .all()
    )
    out: list[PlanEvent] = []
    for r in rows:
        out.append(
            PlanEvent(
                eventId=r.id,
                planId=r.plan_id,
                projectId=r.project_id,
                planVersion=r.plan_version,
                eventType=r.event_type,
                actorType=r.actor_type,  # type: ignore[arg-type]
                actorId=r.actor_id,
                requestId=r.request_id,
                summary=r.summary or "",
                changes=json.loads(r.changes_json or "{}"),
                createdAt=r.created_at.isoformat() if r.created_at else "",
            )
        )
    return out


def apply_head_fields(row: CoDirectorProductionPlan, plan: ProductionPlan) -> None:
    row.status = plan.state
    row.title = plan.title
    row.version = plan.version
    row.request_id = plan.requestId or row.request_id or ""
    row.playbook_id = plan.playbookId or ""
    row.conversation_id = plan.conversationId
    row.active_step_id = plan.activeStepId
    row.parent_version_id = plan.parentVersionId
    row.revision_reason = plan.revisionReason
    row.plan_json = json.dumps(plan.model_dump(mode="json"), default=str)
    row.updated_at = datetime.utcnow()
    # timestamp columns
    def _parse(iso: Optional[str]) -> Optional[datetime]:
        if not iso:
            return None
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    row.paused_at = _parse(plan.pausedAt)
    row.resumed_at = _parse(plan.resumedAt)
    row.cancelled_at = _parse(plan.cancelledAt)
    row.archived_at = _parse(plan.archivedAt)
    row.completed_at = _parse(plan.completedAt)


def add_version_row(db: Session, plan: ProductionPlan) -> CoDirectorProductionPlanVersion:
    ver = CoDirectorProductionPlanVersion(
        id=str(uuid.uuid4()),
        plan_id=plan.planId,
        project_id=plan.projectId,
        version=plan.version,
        state=plan.state,
        snapshot_json=json.dumps(plan.model_dump(mode="json"), default=str),
        revision_reason=plan.revisionReason,
        parent_version_id=plan.parentVersionId,
        created_at=datetime.utcnow(),
    )
    db.add(ver)
    return ver


def add_event_row(db: Session, event: PlanEvent) -> CoDirectorProductionPlanEvent:
    row = CoDirectorProductionPlanEvent(
        id=event.eventId,
        plan_id=event.planId,
        project_id=event.projectId,
        plan_version=event.planVersion,
        event_type=event.eventType,
        actor_type=event.actorType,
        actor_id=event.actorId,
        request_id=event.requestId or "",
        summary=event.summary,
        changes_json=json.dumps(event.changes or {}, default=str),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    return row


def add_idempotency_row(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    command: str,
    plan_id: Optional[str],
    result: dict[str, Any],
) -> CoDirectorPlanCommandIdempotency:
    row = CoDirectorPlanCommandIdempotency(
        id=str(uuid.uuid4()),
        project_id=project_id,
        request_id=request_id,
        command=command,
        plan_id=plan_id,
        result_json=json.dumps(result, default=str),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    return row
