"""SQLAlchemy persistence for the Story tool."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..db import Base, engine


_TAG_RE = re.compile(r"<[^>]+>")


def _count_words(html: str) -> int:
    text = _TAG_RE.sub(" ", html or "")
    return len([w for w in text.split() if w])


class StoryDocumentRow(Base):
    __tablename__ = "story_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled Story")
    content: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def ensure_story_tables() -> None:
    Base.metadata.create_all(bind=engine, tables=[StoryDocumentRow.__table__])


def _row_to_doc(row: StoryDocumentRow) -> "object":
    from .models import StoryDocument

    return StoryDocument(
        id=row.id,
        projectId=row.project_id,
        title=row.title,
        content=row.content,
        wordCount=row.word_count,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


def get_or_create_document(db: Session, project_id: str) -> StoryDocumentRow:
    row = (
        db.query(StoryDocumentRow)
        .filter(StoryDocumentRow.project_id == project_id)
        .first()
    )
    if row:
        return row
    now = datetime.utcnow()
    row = StoryDocumentRow(
        id=uuid.uuid4().hex,
        project_id=project_id,
        title="Untitled Story",
        content="",
        word_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def save_document(
    db: Session, project_id: str, content: str, title: Optional[str] = None
) -> StoryDocumentRow:
    row = get_or_create_document(db, project_id)
    row.content = content
    if title is not None:
        row.title = title
    row.word_count = _count_words(content)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def load_document(db: Session, project_id: str) -> Optional[StoryDocumentRow]:
    return (
        db.query(StoryDocumentRow)
        .filter(StoryDocumentRow.project_id == project_id)
        .first()
    )


def load_or_empty_document(db: Session, project_id: str):
    """Return the saved story, or a neutral non-persisted document.

    CDX-054: GET /projects/{id}/story must be side-effect free — it returns an
    empty/neutral state instead of inserting a story_documents row. The row is
    created only by the first explicit PUT (save_document).
    """
    from .models import StoryDocument

    row = load_document(db, project_id)
    if row:
        return _row_to_doc(row)
    now = datetime.utcnow()
    return StoryDocument(
        id=uuid.uuid4().hex,
        projectId=project_id,
        title="Untitled Story",
        content="",
        wordCount=0,
        createdAt=now,
        updatedAt=now,
    )
