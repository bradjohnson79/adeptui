"""Wave E — conversation event log audit and repair helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..db import CoDirectorConversation, CoDirectorConversationEvent
from .conversation_events import current_revision, fold_events


def audit_conversation(db: Session, project_id: str) -> dict[str, Any]:
    """Check sequence monotonicity, message_id uniqueness, revision, and fold count."""

    rows = (
        db.query(CoDirectorConversationEvent)
        .filter(CoDirectorConversationEvent.project_id == project_id)
        .order_by(CoDirectorConversationEvent.sequence.asc())
        .all()
    )
    sequences = [int(r.sequence) for r in rows]
    sequence_monotonic = all(sequences[i] < sequences[i + 1] for i in range(len(sequences) - 1))

    message_ids = [r.message_id for r in rows if r.message_id]
    unique_message_ids = len(message_ids) == len(set(message_ids))

    header = db.get(CoDirectorConversation, project_id)
    revision_present = header is not None
    revision = int(header.revision) if header is not None else current_revision(db, project_id)

    folded = fold_events(db, project_id)
    healthy = sequence_monotonic and unique_message_ids and revision_present

    return {
        "projectId": project_id,
        "healthy": healthy,
        "sequenceMonotonic": sequence_monotonic,
        "uniqueMessageIds": unique_message_ids,
        "revisionPresent": revision_present,
        "revision": revision,
        "eventCount": len(rows),
        "foldCount": len(folded),
    }


def rebuild_fold(db: Session, project_id: str) -> dict[str, Any]:
    """No-op when healthy; returns fresh audit either way."""

    return audit_conversation(db, project_id)


__all__ = ["audit_conversation", "rebuild_fold"]
