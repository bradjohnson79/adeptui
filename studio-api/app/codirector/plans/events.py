"""Append-only plan event helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .schemas import PlanEvent

EVENT_TYPES = (
    "PLAN_CREATED",
    "PLAN_PROPOSED",
    "PLAN_APPROVED",
    "PLAN_REJECTED",
    "PLAN_REVISED",
    "PLAN_PAUSED",
    "PLAN_RESUMED",
    "PLAN_CANCELLED",
    "PLAN_ARCHIVED",
    "STEP_ADDED",
    "STEP_UPDATED",
    "STEP_REORDERED",
    "BLOCKER_ADDED",
    "BLOCKER_RESOLVED",
    "APPROVAL_REQUIRED",
    "APPROVAL_GRANTED",
    "APPROVAL_REJECTED",
    "CAPABILITY_SNAPSHOT_UPDATED",
    "RECOVERY_PERFORMED",
)


def make_event(
    *,
    plan_id: str,
    project_id: str,
    plan_version: int,
    event_type: str,
    request_id: str,
    summary: str,
    changes: Optional[dict[str, Any]] = None,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> PlanEvent:
    return PlanEvent(
        eventId=str(uuid.uuid4()),
        planId=plan_id,
        projectId=project_id,
        planVersion=plan_version,
        eventType=event_type,
        actorType=actor_type,  # type: ignore[arg-type]
        actorId=actor_id,
        requestId=request_id,
        summary=summary,
        changes=changes or {},
        createdAt=datetime.now(timezone.utc).isoformat(),
    )
