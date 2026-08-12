"""Verified Operator channel — service layer (Co-Director 2.0 Mission A).

The append-only conversation event log (``conversation_events.EventInput`` +
``append_events``) is the single authoritative operator ledger (Law 8). The
in-process ``_OPERATOR_REQUESTS`` dict is a fast-path timeout hint only — it is
never the source of truth.

State machine: ``pending → acknowledged | timeout``. A late ack after timeout is
recorded as an ``operator_late_ack`` event and does NOT upgrade the state.
Timeout (``OPERATOR_TIMEOUT_SEC``) is evaluated lazily on ack/status read and
the durable ``operator_timeout`` event is written when first observed.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...db import CoDirectorConversationEvent
from ..conversation_events import EventInput, append_events
from .contracts import (
    OPERATOR_ACKNOWLEDGED,
    OPERATOR_LATE_ACK,
    OPERATOR_REQUESTED,
    OPERATOR_TIMEOUT,
    OPERATOR_TIMEOUT_SEC,
    OperatorRecord,
)

logger = logging.getLogger(__name__)

_OPERATOR_EVENT_TYPES = frozenset(
    {OPERATOR_REQUESTED, OPERATOR_ACKNOWLEDGED, OPERATOR_TIMEOUT, OPERATOR_LATE_ACK}
)

# Fast-path registry: request_id -> (created_at_monotonic_epoch, origin_session_id).
# Never the source of truth — the event log is. Used only for lazy timeout checks.
_OPERATOR_REQUESTS: dict[str, tuple[float, str]] = {}

_TAB_UNKNOWN = "tab_unknown"


def _tool_result_dict(event: CoDirectorConversationEvent) -> dict[str, Any]:
    raw = event.tool_result_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _origin_session_from_event(event: CoDirectorConversationEvent) -> str:
    payload = _tool_result_dict(event)
    block = payload.get("operator")
    if isinstance(block, dict):
        session = block.get("originSessionId")
        if session:
            return str(session)
    session = payload.get("originSessionId")
    return str(session) if session else _TAB_UNKNOWN


def _latest_operator_event(
    db: Session,
    project_id: str,
    request_id: str,
    event_type: Optional[str],
) -> Optional[CoDirectorConversationEvent]:
    query = (
        db.query(CoDirectorConversationEvent)
        .filter(
            CoDirectorConversationEvent.project_id == project_id,
            CoDirectorConversationEvent.request_id == request_id,
        )
        .order_by(
            CoDirectorConversationEvent.sequence.desc(),
            CoDirectorConversationEvent.created_at.desc(),
        )
    )
    if event_type is None:
        query = query.filter(CoDirectorConversationEvent.event_type.in_(_OPERATOR_EVENT_TYPES))
    else:
        query = query.filter(CoDirectorConversationEvent.event_type == event_type)
    return query.first()


def _fold_operator_state(db: Session, project_id: str, request_id: str) -> str:
    latest = _latest_operator_event(db, project_id, request_id, None)
    if latest is None:
        return "unknown"
    if latest.event_type == OPERATOR_ACKNOWLEDGED:
        return "acknowledged"
    if latest.event_type in (OPERATOR_TIMEOUT, OPERATOR_LATE_ACK):
        return "timeout"
    return "pending"


def _elapsed_seconds(created_at: Optional[datetime]) -> float:
    if created_at is None:
        return float("inf")
    try:
        return (datetime.utcnow() - created_at).total_seconds()
    except TypeError:  # pragma: no cover - defensive
        return float("inf")


def _is_timed_out(db: Session, project_id: str, request_id: str) -> bool:
    """Lazy timeout check — fast path via the in-memory registry, else durable event."""
    entry = _OPERATOR_REQUESTS.get(request_id)
    if entry is not None:
        return time.time() - entry[0] > OPERATOR_TIMEOUT_SEC
    requested = _latest_operator_event(db, project_id, request_id, OPERATOR_REQUESTED)
    if requested is None:
        # Nothing was ever requested for this id — there is nothing left to ack.
        return True
    return _elapsed_seconds(requested.created_at) > OPERATOR_TIMEOUT_SEC


def _record_dict(
    *,
    request_id: str,
    tool_id: Optional[str],
    origin_session_id: Optional[str],
    state: str,
    created_at: Optional[datetime],
    workspace: Optional[str] = None,
    target: Optional[str] = None,
    verified: Optional[bool] = None,
    updated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    return {
        "requestId": request_id,
        "toolId": tool_id,
        "originSessionId": origin_session_id,
        "state": state,
        "createdAt": created_at.isoformat() if created_at else None,
        "workspace": workspace,
        "target": target,
        "verified": verified,
        "updatedAt": updated_at.isoformat() if updated_at else None,
    }


def register_operator_request(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    tool_id: str,
    result: dict[str, Any],
    origin_session_id: Optional[str],
) -> dict[str, Any]:
    """Register an operator request for an executed operator-capable read tool.

    Appends the ``operator_requested`` event (idempotency key
    ``operator-req-{request_id}-{tool_id}``), registers a fast-path timeout
    entry, and returns the ``operator`` block to inject into the handler result
    (the decorated result is what the event carries).
    """
    origin_session = (origin_session_id or _TAB_UNKNOWN).strip() or _TAB_UNKNOWN
    operator_block = {
        "requestId": request_id,
        "originSessionId": origin_session,
        "toolId": tool_id,
        "state": "pending",
    }
    decorated = dict(result or {})
    decorated["operator"] = operator_block
    _OPERATOR_REQUESTS[request_id] = (time.time(), origin_session)
    append_events(
        db,
        project_id,
        [
            EventInput(
                role="assistant",
                event_type=OPERATOR_REQUESTED,
                content="",
                message_id=None,
                client_request_id=f"operator-req-{request_id}-{tool_id}",
                tool_id=tool_id,
                tool_result=decorated,
                request_id=request_id,
            )
        ],
    )
    return operator_block


def acknowledge_operator_request(
    db: Session,
    *,
    project_id: str,
    request_id: str,
    origin_session_id: Optional[str],
    workspace: Optional[str],
    target: Optional[str],
    verified: bool,
) -> dict[str, Any]:
    """Ack an operator request after the frontend confirms the target UI state.

    Checks timeout first. A late ack after timeout is recorded as an
    ``operator_late_ack`` event and does NOT upgrade the state. Otherwise appends
    ``operator_acknowledged`` (idempotency key ``operator-ack-{request_id}``).
    """
    if _is_timed_out(db, project_id, request_id):
        append_events(
            db,
            project_id,
            [
                EventInput(
                    role="assistant",
                    event_type=OPERATOR_LATE_ACK,
                    content="",
                    message_id=None,
                    client_request_id=f"operator-late-ack-{request_id}",
                    tool_result={
                        "originSessionId": origin_session_id,
                        "workspace": workspace,
                        "target": target,
                        "verified": bool(verified),
                    },
                    request_id=request_id,
                )
            ],
        )
        _OPERATOR_REQUESTS.pop(request_id, None)
        return get_operator_record(db, project_id=project_id, request_id=request_id)

    append_events(
        db,
        project_id,
        [
            EventInput(
                role="assistant",
                event_type=OPERATOR_ACKNOWLEDGED,
                content="",
                message_id=None,
                client_request_id=f"operator-ack-{request_id}",
                tool_result={
                    "originSessionId": origin_session_id,
                    "workspace": workspace,
                    "target": target,
                    "verified": bool(verified),
                },
                request_id=request_id,
            )
        ],
    )
    entry = _OPERATOR_REQUESTS.get(request_id)
    created_at_epoch = entry[0] if entry is not None else time.time()
    _OPERATOR_REQUESTS[request_id] = (
        created_at_epoch,
        (origin_session_id or _TAB_UNKNOWN).strip() or _TAB_UNKNOWN,
    )
    return get_operator_record(db, project_id=project_id, request_id=request_id)


def get_operator_record(db: Session, *, project_id: str, request_id: str) -> dict[str, Any]:
    """Return the operator record for a request, folding the event log.

    State is derived from the latest operator event. On first lazy observation
    of a pending request past ``OPERATOR_TIMEOUT_SEC`` the durable
    ``operator_timeout`` event is written (idempotent) and state becomes
    ``timeout``.
    """
    requested = _latest_operator_event(db, project_id, request_id, OPERATOR_REQUESTED)
    if requested is None:
        return _record_dict(
            request_id=request_id,
            tool_id=None,
            origin_session_id=None,
            state="unknown",
            created_at=None,
        )
    created_at = requested.created_at
    origin_session = _origin_session_from_event(requested)
    tool_id = requested.tool_id or ""
    state = _fold_operator_state(db, project_id, request_id)
    if state == "pending" and _elapsed_seconds(created_at) > OPERATOR_TIMEOUT_SEC:
        state = OPERATOR_TIMEOUT
        append_events(
            db,
            project_id,
            [
                EventInput(
                    role="assistant",
                    event_type=OPERATOR_TIMEOUT,
                    content="",
                    message_id=None,
                    client_request_id=f"operator-timeout-{request_id}",
                    tool_result={
                        "requestId": request_id,
                        "toolId": tool_id,
                        "originSessionId": origin_session,
                    },
                    request_id=request_id,
                )
            ],
        )
        _OPERATOR_REQUESTS.pop(request_id, None)
    ack = _latest_operator_event(db, project_id, request_id, OPERATOR_ACKNOWLEDGED)
    workspace: Optional[str] = None
    target: Optional[str] = None
    verified: Optional[bool] = None
    updated_at = created_at
    if ack is not None:
        payload = _tool_result_dict(ack)
        workspace = payload.get("workspace")
        target = payload.get("target")
        verified = payload.get("verified")
        updated_at = ack.created_at
    return _record_dict(
        request_id=request_id,
        tool_id=tool_id,
        origin_session_id=origin_session,
        state=state,
        created_at=created_at,
        workspace=workspace,
        target=target,
        verified=verified,
        updated_at=updated_at,
    )


def has_operator_ack(db: Session, *, project_id: str, request_id: str) -> bool:
    """True when an ``operator_acknowledged`` event exists for the request id."""
    if not project_id or not request_id:
        return False
    return _latest_operator_event(db, project_id, request_id, OPERATOR_ACKNOWLEDGED) is not None


def resolve_operator_project(db: Session, request_id: str) -> Optional[str]:
    """Resolve the project that owns an operator request (latest requested event).

    Used by the ack/status routes, which arrive without a project path segment.
    """
    if not request_id:
        return None
    row = (
        db.query(CoDirectorConversationEvent.project_id)
        .filter(
            CoDirectorConversationEvent.request_id == request_id,
            CoDirectorConversationEvent.event_type == OPERATOR_REQUESTED,
        )
        .order_by(
            CoDirectorConversationEvent.sequence.desc(),
            CoDirectorConversationEvent.created_at.desc(),
        )
        .first()
    )
    return str(row[0]) if row else None
