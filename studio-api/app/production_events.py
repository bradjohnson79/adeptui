"""Project-scoped production event stream (Co-Director production orchestrator).

A lightweight, append-only record of production changes - spatial map,
cameras, ERS, scene-creator candidates, library, timeline, jobs - so
Co-Director can know what happened even when it did not initiate the
change (mission parts 2, 27, 39-42).

Design constraints:
- One table, one writer, bounded readers. No event bus, no broker.
- Recording is best-effort and must never break the operation that
  triggered it (every public writer is exception-contained by default).
- Events are project-scoped; project isolation law (frozen contract #5).
- The "actor" distinguishes user (manual UI), codirector (agent tool
  path), and system (background workers).

The module is intentionally importable from any app subsystem without
pulling Co-Director packages (timeline, spatial, scene creator, library,
queue_worker all emit here).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ACTOR_USER = "user"
ACTOR_CODIRECTOR = "codirector"
ACTOR_SYSTEM = "system"

_MAX_SUMMARY = 400


class ProductionEventRow:
    """Minimal row projection (avoids importing app.db ORM models in hot paths)."""

    __slots__ = (
        "id",
        "project_id",
        "scene_id",
        "event_type",
        "actor",
        "actor_detail",
        "subject_kind",
        "subject_id",
        "summary",
        "payload",
        "created_at",
    )

    def __init__(self, row: Any) -> None:
        self.id = str(getattr(row, "id", "") or "")
        self.project_id = str(getattr(row, "project_id", "") or "")
        self.scene_id = str(getattr(row, "scene_id", "") or "") or None
        self.event_type = str(getattr(row, "event_type", "") or "")
        self.actor = str(getattr(row, "actor", "") or "system")
        self.actor_detail = str(getattr(row, "actor_detail", "") or "")
        self.subject_kind = str(getattr(row, "subject_kind", "") or "")
        self.subject_id = str(getattr(row, "subject_id", "") or "")
        self.summary = str(getattr(row, "summary", "") or "")
        raw = getattr(row, "payload_json", None)
        payload: Any = None
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = None
        self.payload = payload
        self.created_at = getattr(row, "created_at", None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "sceneId": self.scene_id,
            "eventType": self.event_type,
            "actor": self.actor,
            "actorDetail": self.actor_detail,
            "subjectKind": self.subject_kind,
            "subjectId": self.subject_id,
            "summary": self.summary,
            "payload": self.payload,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


def record_production_event(
    db: Session,
    *,
    project_id: str,
    event_type: str,
    scene_id: Optional[str] = None,
    actor: str = ACTOR_SYSTEM,
    actor_detail: str = "",
    subject_kind: str = "",
    subject_id: str = "",
    summary: str = "",
    payload: Optional[dict[str, Any]] = None,
    commit: bool = True,
) -> Optional[str]:
    """Append one production event. Best-effort: never raises to callers.

    ``commit=False`` lets a caller fold the insert into its own transaction.
    """
    event_id: Optional[str] = None
    try:
        from .db import ProductionEvent  # local import keeps module importable everywhere

        row = ProductionEvent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            scene_id=scene_id,
            event_type=str(event_type)[:80],
            actor=str(actor)[:16],
            actor_detail=str(actor_detail)[:64],
            subject_kind=str(subject_kind)[:32],
            subject_id=str(subject_id)[:64],
            summary=str(summary or "")[:_MAX_SUMMARY],
            payload_json=json.dumps(payload, default=str) if payload is not None else None,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        if commit:
            # SQLite writes can hit "database is locked" under the web UI's
            # polling load; retry briefly so awareness is not silently lost
            # (mission Part 2 - CD must know what happened).
            last_error: Optional[BaseException] = None
            for attempt in range(4):
                try:
                    db.commit()
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    db.rollback()
                    if attempt < 3:
                        time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                raise last_error
        event_id = row.id
    except Exception:  # noqa: BLE001 - event recording must never break production
        logger.warning("record_production_event failed (event_type=%s)", event_type, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    return event_id


def list_production_events(
    db: Session,
    project_id: str,
    *,
    scene_id: Optional[str] = None,
    limit: int = 50,
    event_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Read recent events newest-first, optionally filtered by scene/type."""
    try:
        from .db import ProductionEvent

        query = db.query(ProductionEvent).filter(ProductionEvent.project_id == project_id)
        if scene_id:
            query = query.filter(ProductionEvent.scene_id == scene_id)
        if event_types:
            query = query.filter(ProductionEvent.event_type.in_(event_types))
        rows = (
            query.order_by(ProductionEvent.created_at.desc(), ProductionEvent.id.desc())
            .limit(max(1, min(int(limit), 500)))
            .all()
        )
        return [ProductionEventRow(r).to_dict() for r in rows]
    except Exception:  # noqa: BLE001
        logger.warning("list_production_events failed", exc_info=True)
        return []


def recent_production_events(
    db: Session,
    project_id: str,
    *,
    scene_id: Optional[str] = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Compact recent events for prompt injection (oldest-first for reading)."""
    rows = list_production_events(db, project_id, scene_id=scene_id, limit=limit)
    rows.reverse()
    return rows


def recent_production_events_block(
    db: Session,
    project_id: str,
    *,
    scene_id: Optional[str] = None,
    limit: int = 8,
) -> str:
    """Render recent events as a bounded prompt block (empty string when none)."""
    rows = recent_production_events(db, project_id, scene_id=scene_id, limit=limit)
    if not rows:
        return ""
    out = ["Recent production activity:"]
    for row in rows:
        stamp = ""
        created = row.get("createdAt") or ""
        if created:
            stamp = created[11:19] if len(created) >= 19 else created
        who = row.get("actor") or "system"
        summary = str(row.get("summary") or row.get("eventType") or "")[:160]
        out.append(f"- [{stamp}] {who}: {summary}")
    return "\n".join(out)