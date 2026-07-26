"""M2.9 Director Timeline Generation propose/apply (approval-aware)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import ensure_m29_tables


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class TimelineService:
    @staticmethod
    def propose(
        db: Session,
        *,
        project_id: str,
        scene_id: str | None = None,
        clips: list[dict[str, Any]] | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        ensure_m29_tables()
        pid = uuid.uuid4().hex
        proposal = {
            "clips": clips
            or [
                {"clipId": "clip-1", "assetId": None, "start": 0, "length": 4, "track": "video"},
            ],
            "notes": notes,
            "requiresApproval": True,
        }
        now = _now()
        db.execute(
            text(
                "INSERT INTO m29_timeline_proposals "
                "(id, project_id, scene_id, status, proposal_json, created_at, updated_at) "
                "VALUES (:id, :pid, :sid, :status, :pj, :c, :u)"
            ),
            {
                "id": pid,
                "pid": project_id,
                "sid": scene_id,
                "status": "pending",
                "pj": json.dumps(proposal),
                "c": now,
                "u": now,
            },
        )
        db.commit()
        return {
            "id": pid,
            "projectId": project_id,
            "sceneId": scene_id,
            "status": "pending",
            "proposal": proposal,
            "requiresApproval": True,
        }

    @staticmethod
    def get(db: Session, proposal_id: str) -> dict[str, Any] | None:
        ensure_m29_tables()
        row = db.execute(
            text(
                "SELECT id, project_id, scene_id, status, proposal_json, created_at, updated_at "
                "FROM m29_timeline_proposals WHERE id = :id"
            ),
            {"id": proposal_id},
        ).mappings().first()
        if not row:
            return None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sceneId": row["scene_id"],
            "status": row["status"],
            "proposal": json.loads(row["proposal_json"] or "{}"),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "requiresApproval": True,
        }

    @staticmethod
    def approve(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        if prop["status"] != "pending":
            raise PermissionError(f"proposal not pending: {prop['status']}")
        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "approved", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "approved"
        prop["approvedBy"] = actor
        return prop

    @staticmethod
    def reject(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "rejected", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "rejected"
        prop["rejectedBy"] = actor
        return prop

    @staticmethod
    def apply(db: Session, proposal_id: str, *, actor: str = "user") -> dict[str, Any]:
        """Apply only after human approval — never silent timeline mutation."""
        prop = TimelineService.get(db, proposal_id)
        if not prop:
            raise KeyError(proposal_id)
        if prop["status"] != "approved":
            raise PermissionError("timeline apply blocked: human approval required")
        db.execute(
            text(
                "UPDATE m29_timeline_proposals SET status = :s, updated_at = :u WHERE id = :id"
            ),
            {"s": "applied", "u": _now(), "id": proposal_id},
        )
        db.commit()
        prop["status"] = "applied"
        prop["appliedBy"] = actor
        prop["applied"] = True
        return prop
