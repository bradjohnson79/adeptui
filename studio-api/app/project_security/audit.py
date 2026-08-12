"""Security audit events — never record passwords or hashes."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import ProjectSecurityAuditRow

SAFE_EVENTS = frozenset(
    {
        "project_password_enabled",
        "project_unlock_succeeded",
        "project_unlock_failed",
        "project_locked",
        "project_password_changed",
        "project_password_reset",
        "project_password_disabled",
        "project_unlock_grants_revoked",
        "protected_project_export_attempted",
        "project_unlock_rate_limited",
    }
)


def record_audit(db: Session, project_id: str, event: str, detail: dict[str, Any] | None = None) -> None:
    if event not in SAFE_EVENTS:
        event = "project_security_event"
    # Strip any accidental sensitive keys
    safe = {}
    for k, v in (detail or {}).items():
        lk = str(k).lower()
        if any(x in lk for x in ("password", "hash", "token", "secret")):
            continue
        safe[k] = v
    db.add(
        ProjectSecurityAuditRow(
            id=str(uuid.uuid4()),
            project_id=project_id,
            event=event,
            detail_json=json.dumps(safe, ensure_ascii=False),
            created_at=datetime.utcnow(),
        )
    )


def list_audit(db: Session, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        db.query(ProjectSecurityAuditRow)
        .filter(ProjectSecurityAuditRow.project_id == project_id)
        .order_by(ProjectSecurityAuditRow.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        try:
            detail = json.loads(r.detail_json or "{}")
        except Exception:
            detail = {}
        out.append(
            {
                "id": r.id,
                "event": r.event,
                "detail": detail,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out
