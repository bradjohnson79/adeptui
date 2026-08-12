"""Wave B — conversation compaction via summary events."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from .conversation_events import EventInput, append_events, current_revision


def compact_conversation(
    db: Session,
    project_id: str,
    *,
    before_sequence: int,
    summary_text: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Append a compaction summary event covering events through `before_sequence`."""

    rid = request_id or str(uuid.uuid4())
    summary = EventInput(
        role="system",
        content=summary_text.strip(),
        event_type="summary",
        message_id=f"summary-{rid}",
        attachments=[
            {
                "kind": "compaction",
                "compactedThroughSequence": before_sequence,
            }
        ],
        actor="system",
        request_id=rid,
    )
    batch = append_events(db, project_id, [summary])
    return {
        "projectId": project_id,
        "requestId": rid,
        "compactedThroughSequence": before_sequence,
        "appendedCount": batch.appended_count,
        "duplicateCount": batch.duplicate_count,
        "revision": batch.revision,
    }


def revision_after_compact(db: Session, project_id: str) -> int:
    return current_revision(db, project_id)


__all__ = ["compact_conversation", "revision_after_compact"]
