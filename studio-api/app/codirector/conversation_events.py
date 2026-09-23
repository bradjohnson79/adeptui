"""Co-Director persistent memory — append-only conversation event store (Wave A).

The server owns BOTH creator and assistant/tool events. The client never
replaces the authoritative transcript; it only appends (creator turns) and
reconciles by id. This module is the single source of truth for conversation
durability.

Design:
- `codirector_conversation_events` is append-only. One row per message/tool event.
- `sequence` is server-assigned and strictly increasing per project.
- Idempotency: a unique index on `(project_id, client_request_id)` makes a
  retried creator append return the original event instead of duplicating. A
  unique index on `(project_id, message_id)` dedupes server-side assistant
  events that share a stable message id.
- Optimistic concurrency: the thin `codirector_conversations` header carries a
  `revision` that bumps on every append. The deprecated full-replace path
  (`save_conversation`) must present the revision it read or get a 409.
- `fold_events` reconstructs the `{projectId, messages, model, providerId,
  updatedAt}` shape the existing `GET /conversations/{project_id}` contract
  returns, so the client sees no shape change.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import CoDirectorConversation, CoDirectorConversationEvent


# -----------------------------------------------------------------------
# Public data shapes
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class AppendResult:
    """Outcome of an append attempt for a single event."""

    appended: bool  # True if a new event row was inserted
    duplicate: bool  # True if an idempotency key matched an existing event
    event: Optional[dict[str, Any]]  # the event row (existing or new) as a dict
    conflict: bool  # True if optimistic concurrency rejected the batch
    conflict_revision: Optional[int]  # the server's current revision on conflict


@dataclass(frozen=True)
class AppendBatchResult:
    """Outcome of appending a batch of events in one request."""

    events: tuple[dict[str, Any], ...]  # canonical events (existing + new), in order
    appended_count: int
    duplicate_count: int
    revision: int  # the new header revision after the append
    conflict: bool
    conflict_revision: Optional[int]


# -----------------------------------------------------------------------
# Folding events -> messages
# -----------------------------------------------------------------------


def _attachments_json_to_list(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def event_to_message(event: CoDirectorConversationEvent) -> dict[str, Any]:
    """Reconstruct the legacy message dict shape from an event row."""

    attachments = _attachments_json_to_list(event.attachments_json)
    msg: dict[str, Any] = {
        "id": event.message_id or event.id,
        "role": event.role,
        "content": event.content or "",
        "created_at": (event.created_at.isoformat() if event.created_at else None),
    }
    # Preserve attachment_ids + attachments for client normalization.
    asset_ids = [
        str(a.get("assetId") or a.get("asset_id") or "")
        for a in attachments
        if isinstance(a, dict) and (a.get("assetId") or a.get("asset_id"))
    ]
    if asset_ids:
        msg["attachment_ids"] = asset_ids
    if attachments:
        msg["attachments"] = attachments
    if event.message_type:
        msg["messageType"] = event.message_type
    if event.status:
        msg["status"] = event.status
    for item in attachments:
        if isinstance(item, dict) and item.get("kind") == "execution":
            payload = item.get("execution")
            if isinstance(payload, dict) and payload.get("execution_id"):
                msg["execution"] = payload
            break
    return msg


def _compaction_cutoff(rows: Iterable[CoDirectorConversationEvent]) -> int:
    """Highest sequence covered by a compaction summary event."""

    cutoff = -1
    for row in rows:
        if row.event_type != "summary":
            continue
        for att in _attachments_json_to_list(row.attachments_json):
            if not isinstance(att, dict):
                continue
            if att.get("kind") != "compaction":
                continue
            try:
                cutoff = max(cutoff, int(att.get("compactedThroughSequence", -1)))
            except (TypeError, ValueError):
                continue
    return cutoff


def _should_skip_compacted(row: CoDirectorConversationEvent, cutoff: int) -> bool:
    """Skip user/assistant message rows covered by a compaction summary."""

    if cutoff < 0:
        return False
    if row.sequence > cutoff:
        return False
    if row.event_type in ("tool_call", "tool_result", "summary"):
        return False
    if row.event_type == "message" and row.role in ("user", "assistant"):
        return True
    # Legacy rows without explicit event_type still fold as messages.
    if row.event_type == "message" or (not row.event_type and row.role in ("user", "assistant")):
        return row.role in ("user", "assistant")
    return False


def fold_events(db: Session, project_id: str) -> list[dict[str, Any]]:
    """Return the ordered message list for a project from the event log."""

    rows = _load_event_rows(db, project_id)
    cutoff = _compaction_cutoff(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        if _should_skip_compacted(row, cutoff):
            continue
        out.append(event_to_message(row))
    return out


# Message kinds that are EXECUTION/WORKFLOW state, never conversational memory.
# They are stored durably (for UI cards / reload recovery) but must never be
# replayed into the LLM as if they were the assistant's conversational thought.
EXECUTION_MESSAGE_TYPES: frozenset[str] = frozenset({"execution_status", "completion", "error"})


def _is_llm_visible_event(row: CoDirectorConversationEvent) -> bool:
    """True when an event row belongs in the LLM's conversational memory window.

    LLM-visible: user/assistant conversational message rows (any non-execution
    message_type, including legacy rows without one) and compaction summaries.
    NOT LLM-visible: tool_call/tool_result rows (machine state; production
    results reach the model through dedicated context blocks), operator_* rows,
    and execution_status/completion/error assistant rows (machine/workflow
    state — Co-Director Intelligence Law: execution status is not the
    assistant's conversational memory).
    """

    event_type = row.event_type or "message"
    if event_type in ("tool_call", "tool_result"):
        return False
    if event_type.startswith("operator_"):
        return False
    if event_type == "summary":
        return True
    if event_type != "message":
        return False
    if row.role not in ("user", "assistant"):
        return False
    message_type = (row.message_type or "").strip()
    return message_type not in EXECUTION_MESSAGE_TYPES


def _load_event_rows(db: Session, project_id: str) -> list[CoDirectorConversationEvent]:
    return (
        db.query(CoDirectorConversationEvent)
        .filter(CoDirectorConversationEvent.project_id == project_id)
        .order_by(CoDirectorConversationEvent.sequence.asc(), CoDirectorConversationEvent.created_at.asc())
        .all()
    )


def fold_events_for_llm(db: Session, project_id: str) -> list[dict[str, Any]]:
    """Return the LLM-visible conversational memory for a project.

    This is the server-authoritative history for Co-Director turns: user and
    assistant conversation only. Execution status, tool traffic, and operator
    events are durable (the UI fold keeps them) but excluded here so they can
    never masquerade as the assistant's prior conversational thought.
    """

    rows = _load_event_rows(db, project_id)
    cutoff = _compaction_cutoff(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        if _should_skip_compacted(row, cutoff):
            continue
        if not _is_llm_visible_event(row):
            continue
        out.append(event_to_message(row))
    return out


def conversation_to_dict(db: Session, row: CoDirectorConversation) -> dict[str, Any]:
    """Build the legacy `GET /conversations/{project_id}` shape from events."""

    messages = fold_events(db, row.project_id)
    messages = hydrate_execution_messages(db, row.project_id, messages)
    return {
        "projectId": row.project_id,
        "messages": messages,
        "model": row.model_id,
        "providerId": row.provider_id,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "revision": row.revision,
    }


def hydrate_execution_messages(
    db: Session,
    project_id: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay durable execution packs onto chat cards. Pack is the authority."""
    try:
        from .execution.advance import advance_execution_pack
        from .execution.pack_store import list_packs_raw, load_pack
        from .execution.status_messenger import (
            _build_execution_status_text,
            _message_kind_for_status,
            _serialize_plan_summary,
        )
    except Exception:
        return messages

    used: set[str] = set()

    def apply_pack(msg: dict[str, Any], execution_id: str) -> None:
        plan = advance_execution_pack(db, project_id, execution_id) or load_pack(
            db, project_id, execution_id
        )
        if plan is None:
            return
        summary = _serialize_plan_summary(plan)
        msg["execution"] = summary
        msg["content"] = _build_execution_status_text(summary)
        msg["messageType"] = _message_kind_for_status(summary.get("status") or "")
        used.add(execution_id)

    for msg in messages:
        raw = msg.get("execution") if isinstance(msg.get("execution"), dict) else {}
        execution_id = str((raw or {}).get("execution_id") or "").strip()
        if execution_id:
            apply_pack(msg, execution_id)

    orphans = [
        msg
        for msg in messages
        if str(msg.get("messageType") or "") in {"execution_status", "completion", "error"}
        and not str((msg.get("execution") or {}).get("execution_id") or "").strip()
    ]
    if not orphans:
        return messages
    try:
        packs = [
            pack
            for pack in list_packs_raw(db, project_id)
            if pack.execution_id not in used
        ]
    except Exception:
        return messages
    for msg, pack in zip(reversed(orphans), packs):
        apply_pack(msg, pack.execution_id)
    return messages


# -----------------------------------------------------------------------
# Header helpers
# -----------------------------------------------------------------------


def _ensure_header(db: Session, project_id: str) -> CoDirectorConversation:
    row = db.get(CoDirectorConversation, project_id)
    if row is None:
        row = CoDirectorConversation(project_id=project_id, revision=0)
        db.add(row)
        db.flush()
    return row


def _next_sequence(db: Session, project_id: str) -> int:
    last = (
        db.query(CoDirectorConversationEvent.sequence)
        .filter(CoDirectorConversationEvent.project_id == project_id)
        .order_by(CoDirectorConversationEvent.sequence.desc())
        .first()
    )
    return (int(last[0]) + 1) if last else 0


def _existing_by_idempotency(
    db: Session, project_id: str, *, client_request_id: Optional[str], message_id: Optional[str]
) -> Optional[CoDirectorConversationEvent]:
    """Find an existing event matching an idempotency key, if any."""

    if client_request_id:
        row = (
            db.query(CoDirectorConversationEvent)
            .filter(
                CoDirectorConversationEvent.project_id == project_id,
                CoDirectorConversationEvent.client_request_id == client_request_id,
            )
            .first()
        )
        if row is not None:
            return row
    if message_id:
        row = (
            db.query(CoDirectorConversationEvent)
            .filter(
                CoDirectorConversationEvent.project_id == project_id,
                CoDirectorConversationEvent.message_id == message_id,
            )
            .first()
        )
        if row is not None:
            return row
    return None


# -----------------------------------------------------------------------
# Append API
# -----------------------------------------------------------------------


@dataclass
class EventInput:
    """One event to append. Used by both creator and server-side paths."""

    role: str
    content: str = ""
    event_type: str = "message"
    message_id: Optional[str] = None
    client_request_id: Optional[str] = None
    message_type: Optional[str] = None
    status: Optional[str] = None
    attachments: Optional[list[dict[str, Any]]] = None
    tool_id: Optional[str] = None
    tool_arguments: Optional[dict[str, Any]] = None
    tool_result: Optional[dict[str, Any]] = None
    request_id: Optional[str] = None
    actor: str = "user"
    created_at: Optional[datetime] = None

    def to_row(self, project_id: str, sequence: int) -> CoDirectorConversationEvent:
        return CoDirectorConversationEvent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            sequence=sequence,
            event_type=self.event_type,
            role=self.role,
            message_id=self.message_id,
            client_request_id=self.client_request_id,
            content=self.content,
            message_type=self.message_type,
            status=self.status,
            attachments_json=json.dumps(self.attachments or []),
            tool_id=self.tool_id,
            tool_arguments_json=json.dumps(self.tool_arguments) if self.tool_arguments is not None else None,
            tool_result_json=json.dumps(self.tool_result) if self.tool_result is not None else None,
            request_id=self.request_id,
            actor=self.actor,
            created_at=self.created_at or datetime.utcnow(),
        )


def append_events(
    db: Session,
    project_id: str,
    events: Iterable[EventInput],
    *,
    expected_revision: Optional[int] = None,
    model: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> AppendBatchResult:
    """Append a batch of events with idempotency + optimistic concurrency.

    On a revision mismatch, no events are inserted and a conflict result is
    returned (the caller maps it to HTTP 409). On idempotent re-send, the
    existing event is returned in place and `duplicate_count` is incremented.
    """

    header = _ensure_header(db, project_id)
    if expected_revision is not None and expected_revision != header.revision:
        return AppendBatchResult(
            events=(),
            appended_count=0,
            duplicate_count=0,
            revision=header.revision,
            conflict=True,
            conflict_revision=header.revision,
        )

    seq = _next_sequence(db, project_id)
    out: list[dict[str, Any]] = []
    appended = 0
    duplicated = 0

    for ev in events:
        existing = _existing_by_idempotency(
            db, project_id, client_request_id=ev.client_request_id, message_id=ev.message_id
        )
        if existing is not None:
            out.append(event_to_message(existing))
            duplicated += 1
            continue
        row = ev.to_row(project_id, seq)
        db.add(row)
        db.flush()
        out.append(event_to_message(row))
        seq += 1
        appended += 1

    if appended:
        header.revision = (header.revision or 0) + appended
        header.updated_at = datetime.utcnow()
        if model is not None:
            header.model_id = model
        if provider_id is not None:
            header.provider_id = provider_id
    db.commit()
    for row in db.query(CoDirectorConversationEvent).filter(
        CoDirectorConversationEvent.project_id == project_id
    ).all():
        db.refresh(row)
    header = db.get(CoDirectorConversation, project_id) or header
    return AppendBatchResult(
        events=tuple(out),
        appended_count=appended,
        duplicate_count=duplicated,
        revision=header.revision or 0,
        conflict=False,
        conflict_revision=None,
    )


def append_single(
    db: Session,
    project_id: str,
    event: EventInput,
    *,
    expected_revision: Optional[int] = None,
    model: Optional[str] = None,
    provider_id: Optional[str] = None,
) -> AppendResult:
    """Convenience wrapper for a single event append."""

    batch = append_events(
        db,
        project_id,
        [event],
        expected_revision=expected_revision,
        model=model,
        provider_id=provider_id,
    )
    if batch.conflict:
        return AppendResult(
            appended=False,
            duplicate=False,
            event=None,
            conflict=True,
            conflict_revision=batch.conflict_revision,
        )
    ev = batch.events[0] if batch.events else None
    return AppendResult(
        appended=batch.appended_count == 1,
        duplicate=batch.duplicate_count == 1,
        event=ev,
        conflict=False,
        conflict_revision=None,
    )


def current_revision(db: Session, project_id: str) -> int:
    row = db.get(CoDirectorConversation, project_id)
    return int(row.revision) if row is not None else 0


def delete_all_events(db: Session, project_id: str) -> int:
    """Delete every event for a project (used by DELETE conversation)."""

    rows = (
        db.query(CoDirectorConversationEvent)
        .filter(CoDirectorConversationEvent.project_id == project_id)
        .all()
    )
    count = len(rows)
    for r in rows:
        db.delete(r)
    header = db.get(CoDirectorConversation, project_id)
    if header is not None:
        header.revision = 0
        header.updated_at = datetime.utcnow()
    db.commit()
    return count


__all__ = [
    "AppendBatchResult",
    "AppendResult",
    "EventInput",
    "EXECUTION_MESSAGE_TYPES",
    "append_events",
    "append_single",
    "conversation_to_dict",
    "current_revision",
    "delete_all_events",
    "event_to_message",
    "fold_events",
    "fold_events_for_llm",
]
