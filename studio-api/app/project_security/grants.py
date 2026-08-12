"""Short-lived project unlock grants."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .hashing import hash_token, new_grant_token
from .models import ProjectUnlockGrantRow

REMEMBER_DURATIONS = {
    "session": timedelta(hours=12),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
}


def create_grant(
    db: Session,
    *,
    project_id: str,
    password_version: int,
    remember_for: str = "session",
    session_id: str = "",
    user_id: str = "local",
) -> tuple[str, ProjectUnlockGrantRow]:
    token = new_grant_token()
    delta = REMEMBER_DURATIONS.get(remember_for) or REMEMBER_DURATIONS["session"]
    row = ProjectUnlockGrantRow(
        id=str(uuid.uuid4()),
        project_id=project_id,
        token_hash=hash_token(token),
        session_id=session_id or "",
        user_id=user_id,
        password_version=password_version,
        expires_at=datetime.utcnow() + delta,
        created_at=datetime.utcnow(),
        revoked_at=None,
    )
    db.add(row)
    return token, row


def find_valid_grant(db: Session, *, project_id: str, token: str, password_version: int) -> Optional[ProjectUnlockGrantRow]:
    if not token:
        return None
    th = hash_token(token)
    now = datetime.utcnow()
    row = (
        db.query(ProjectUnlockGrantRow)
        .filter(
            ProjectUnlockGrantRow.project_id == project_id,
            ProjectUnlockGrantRow.token_hash == th,
            ProjectUnlockGrantRow.revoked_at.is_(None),
            ProjectUnlockGrantRow.expires_at > now,
            ProjectUnlockGrantRow.password_version == password_version,
        )
        .first()
    )
    return row


def revoke_grants(db: Session, project_id: str) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(ProjectUnlockGrantRow)
        .filter(
            ProjectUnlockGrantRow.project_id == project_id,
            ProjectUnlockGrantRow.revoked_at.is_(None),
        )
        .all()
    )
    for r in rows:
        r.revoked_at = now
    return len(rows)
