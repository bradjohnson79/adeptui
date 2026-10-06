"""In-memory Auto Previz plans. Execute requires a stored, approved plan."""

from __future__ import annotations

import threading
import uuid
from typing import Any

_LOCK = threading.Lock()
_PLANS: dict[str, dict[str, Any]] = {}


def store_plan(project_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(plan.get("planId") or f"previz-{uuid.uuid4()}")
    stored = {**plan, "planId": plan_id, "projectId": project_id, "approved": bool(plan.get("approved"))}
    with _LOCK:
        _PLANS[plan_id] = stored
    return stored


def get_plan(plan_id: str) -> dict[str, Any] | None:
    with _LOCK:
        plan = _PLANS.get(plan_id)
        return dict(plan) if plan else None


def approve_plan(plan_id: str, project_id: str) -> dict[str, Any] | None:
    with _LOCK:
        plan = _PLANS.get(plan_id)
        if plan is None or plan.get("projectId") != project_id:
            return None
        plan["approved"] = True
        return dict(plan)
