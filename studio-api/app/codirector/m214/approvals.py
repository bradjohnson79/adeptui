"""Unified Approval Center aggregation (story, bible, env, blocking, camera, lighting, media, timeline, export)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .store import M214Store


APPROVAL_CATEGORIES: tuple[str, ...] = (
    "story",
    "bible",
    "environment",
    "blocking",
    "camera",
    "lighting",
    "media",
    "timeline",
    "export",
)


def approval_center(
    db: Session,
    project_id: str,
    *,
    pending: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Aggregate pending approvals; does not silently approve anything."""
    items = []
    source = pending or {}
    for cat in APPROVAL_CATEGORIES:
        entry = source.get(cat) or {"status": "none", "items": []}
        items.append(
            {
                "category": cat,
                "status": entry.get("status", "none"),
                "items": entry.get("items") or [],
                "wires": {
                    "proposalCard": True,
                    "m211Decisions": True,
                    "m213Gates": cat in {"environment", "blocking", "camera", "lighting"},
                },
            }
        )
    M214Store.log_capability(
        db,
        capability_id="production_team.readiness.evaluate",
        action="approval_center",
        project_id=project_id,
    )
    pending_count = sum(1 for i in items if i["status"] in {"pending", "blocked"})
    return {
        "projectId": project_id,
        "categories": items,
        "pendingCount": pending_count,
        "primaryNextAction": "Review pending approvals" if pending_count else "No pending approvals",
        "silentApproval": False,
        "honesty": "scaffolded",
    }
