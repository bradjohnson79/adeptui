"""SQLAlchemy persistence for story entries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..db import Base, engine
from .models import StoryEntryCreate, StoryEntryUpdate


class StoryEntryRow(Base):
    __tablename__ = "story_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    entry_type: Mapped[str] = mapped_column(String(50), default="project_story")
    logline: Mapped[str] = mapped_column(Text, default="")
    short_summary: Mapped[str] = mapped_column(Text, default="")
    long_summary: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_story_entries_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[StoryEntryRow.__table__])


def _row_to_dict(row: StoryEntryRow) -> dict:
    return {
        "id": row.id,
        "projectId": row.project_id,
        "title": row.title,
        "entryType": row.entry_type,
        "logline": row.logline,
        "shortSummary": row.short_summary,
        "longSummary": row.long_summary,
        "sortOrder": row.sort_order,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def list_entries(db: Session, project_id: str) -> list[StoryEntryRow]:
    return (
        db.query(StoryEntryRow)
        .filter(StoryEntryRow.project_id == project_id)
        .order_by(StoryEntryRow.sort_order)
        .all()
    )


def get_entry(db: Session, entry_id: str) -> Optional[StoryEntryRow]:
    return db.get(StoryEntryRow, entry_id)


def create_entry(db: Session, project_id: str, data: StoryEntryCreate) -> StoryEntryRow:
    now = datetime.utcnow()
    row = StoryEntryRow(
        id=uuid.uuid4().hex,
        project_id=project_id,
        title=data.title,
        entry_type=data.entryType,
        logline=data.logline,
        short_summary=data.shortSummary,
        long_summary=data.longSummary,
        sort_order=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _invalidate_wiki(db, project_id)

    return row


def update_entry(db: Session, entry_id: str, data: StoryEntryUpdate) -> Optional[StoryEntryRow]:
    row = db.get(StoryEntryRow, entry_id)
    if not row:
        return None

    if data.title is not None:
        row.title = data.title
    if data.entryType is not None:
        row.entry_type = data.entryType
    if data.logline is not None:
        row.logline = data.logline
    if data.shortSummary is not None:
        row.short_summary = data.shortSummary
    if data.longSummary is not None:
        row.long_summary = data.longSummary
    if data.sortOrder is not None:
        row.sort_order = data.sortOrder
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)

    _invalidate_wiki(db, row.project_id)

    return row


def delete_entry(db: Session, entry_id: str) -> bool:
    row = db.get(StoryEntryRow, entry_id)
    if not row:
        return False
    project_id = row.project_id
    db.delete(row)
    db.commit()

    _invalidate_wiki(db, project_id)

    return True


def reorder_entries(db: Session, project_id: str, entry_ids: list[str]) -> list[StoryEntryRow]:
    rows = []
    for idx, eid in enumerate(entry_ids):
        row = db.get(StoryEntryRow, eid)
        if row and row.project_id == project_id:
            row.sort_order = idx
            row.updated_at = datetime.utcnow()
            rows.append(row)
    db.commit()
    for r in rows:
        db.refresh(r)

    _invalidate_wiki(db, project_id)

    return rows


def migrate_from_legacy(db: Session, project_id: str) -> bool:
    existing = (
        db.query(StoryEntryRow)
        .filter(StoryEntryRow.project_id == project_id)
        .first()
    )
    if existing:
        return False

    try:
        from ..story.store import load_document

        doc = load_document(db, project_id)
        if doc:
            now = datetime.utcnow()
            row = StoryEntryRow(
                id=uuid.uuid4().hex,
                project_id=project_id,
                title=getattr(doc, "title", "") or "",
                entry_type="project_story",
                logline="",
                short_summary="",
                long_summary=getattr(doc, "content", "") or "",
                sort_order=0,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            return True
    except Exception:
        pass

    return False


def _invalidate_wiki(db: Session, project_id: str) -> None:
    try:
        from ..codirector.production_state.contracts import ProjectionDomain
        from ..codirector.production_state.invalidation import invalidate_production_state

        invalidate_production_state(db, project_id, affected_domains={ProjectionDomain.WIKI})
    except Exception:
        pass
