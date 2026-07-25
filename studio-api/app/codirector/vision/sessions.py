"""Validation session lifecycle helpers."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .schemas import ValidationSession
from .store import VisionStore

TERMINAL_ENGINE_STATUSES = frozenset({"completed", "failed"})
TERMINAL_HUMAN_STATUSES = frozenset({"approved", "rejected"})


def is_engine_terminal(status: str) -> bool:
    return status in TERMINAL_ENGINE_STATUSES


def is_human_terminal(status: str) -> bool:
    return status in TERMINAL_HUMAN_STATUSES


def get_session(db: Session, session_id: str, *, project_id: Optional[str] = None) -> ValidationSession | None:
    return VisionStore.get_session(db, session_id, project_id=project_id)


def session_history(db: Session, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    sessions = VisionStore.list_sessions_for_project(db, project_id, limit=limit)
    return [s.model_dump(mode="json") for s in sessions]
