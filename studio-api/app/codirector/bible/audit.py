"""Append-only Bible audit event ledger."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import BibleAuditEvent


def record_audit_event(
    db: Session,
    *,
    project_id: str,
    event_type: str,
    summary: str = "",
    actor: str = "user",
    entity_stable_id: Optional[str] = None,
    entity_key: Optional[str] = None,
    entity_type: Optional[str] = None,
    bible_version_id: Optional[str] = None,
    bible_version_number: Optional[int] = None,
    proposal_id: Optional[str] = None,
    receipt_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> BibleAuditEvent:
    now = datetime.utcnow()
    row = BibleAuditEvent(
        id=str(uuid.uuid4()),
        project_id=project_id,
        event_type=event_type,
        entity_stable_id=entity_stable_id,
        entity_key=entity_key,
        entity_type=entity_type,
        bible_version_id=bible_version_id,
        bible_version_number=bible_version_number,
        proposal_id=proposal_id,
        receipt_id=receipt_id,
        actor=actor,
        summary=summary,
        details_json=json.dumps(details or {}),
        created_at=now,
    )
    db.add(row)
    db.flush()
    return row


def list_audit_events(db: Session, project_id: str, *, limit: int = 100) -> list[BibleAuditEvent]:
    return (
        db.query(BibleAuditEvent)
        .filter(BibleAuditEvent.project_id == project_id)
        .order_by(BibleAuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )


def audit_event_to_dict(row: BibleAuditEvent) -> dict[str, Any]:
    try:
        details = json.loads(row.details_json or "{}")
    except Exception:
        details = {}
    return {
        "id": row.id,
        "projectId": row.project_id,
        "eventType": row.event_type,
        "entityStableId": row.entity_stable_id,
        "entityKey": row.entity_key,
        "entityType": row.entity_type,
        "bibleVersionId": row.bible_version_id,
        "bibleVersionNumber": row.bible_version_number,
        "proposalId": row.proposal_id,
        "receiptId": row.receipt_id,
        "actor": row.actor,
        "summary": row.summary or "",
        "details": details,
        "createdAt": row.created_at.isoformat() if row.created_at else "",
    }
