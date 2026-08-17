"""Durable store for Wiki correction previews (CDX-061).

Previews previously lived only in an in-process module dict
("routers/codirector._CORRECTION_PREVIEWS"), so a server restart between
"preview" and "apply" returned 404 "preview_not_found". This store persists
each CorrectionPreview row as JSON in a dedicated lightweight table so
apply survives restarts (CREATOR_APPROVES is unchanged: apply still requires a
prior preview; the preview simply no longer lives in process memory).

Bounded storage: per project the most recent _KEEP_PER_PROJECT previews are
retained and rows older than _TTL are purged on every write.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from ....db import Base

#: Per-project cap on retained previews (oldest are purged first).
_KEEP_PER_PROJECT = 20
#: Preview rows older than this are purged on the next write for the project.
_TTL = timedelta(hours=48)


class WikiCorrectionPreviewRow(Base):
    """One persisted correction preview (JSON payload)."""

    __tablename__ = "wiki_correction_previews"

    preview_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def _ensure_table(db: Session) -> None:
    """Create the table on the session's bind (idempotent).

    Uses ``db.get_bind()`` so tests running against an in-memory engine create
    the table there instead of touching the production engine (Build Law: no
    writes to studio.db from tests).
    """
    Base.metadata.create_all(bind=db.get_bind(), tables=[WikiCorrectionPreviewRow.__table__])


def save_preview(db: Session, preview) -> None:
    """Persist (upsert) a CorrectionPreview and enforce bounds."""
    _ensure_table(db)
    row = db.get(WikiCorrectionPreviewRow, preview.previewId)
    now = datetime.utcnow()
    if row is None:
        row = WikiCorrectionPreviewRow(
            preview_id=preview.previewId,
            project_id=preview.projectId,
            payload_json=preview.model_dump_json(),
            created_at=now,
        )
        db.add(row)
    else:
        row.project_id = preview.projectId
        row.payload_json = preview.model_dump_json()
        row.created_at = now
    db.commit()
    _purge(db, preview.projectId)


def load_preview(db: Session, preview_id: str):
    """Return the persisted CorrectionPreview, or None."""
    from .contracts import CorrectionPreview

    _ensure_table(db)
    row = db.get(WikiCorrectionPreviewRow, preview_id)
    if row is None:
        return None
    try:
        return CorrectionPreview.model_validate_json(row.payload_json)
    except Exception:  # noqa: BLE001 - a corrupt row degrades to "not found"
        return None


def delete_preview(db: Session, preview_id: str) -> None:
    """Consume a preview after a successful apply (single-use)."""
    _ensure_table(db)
    row = db.get(WikiCorrectionPreviewRow, preview_id)
    if row is not None:
        db.delete(row)
        db.commit()


def _purge(db: Session, project_id: str) -> None:
    """Keep only the most recent _KEEP_PER_PROJECT rows per project and
    drop rows older than _TTL - storage stays bounded."""
    rows = (
        db.query(WikiCorrectionPreviewRow)
        .filter(WikiCorrectionPreviewRow.project_id == project_id)
        .order_by(
            WikiCorrectionPreviewRow.created_at.desc(),
            WikiCorrectionPreviewRow.preview_id.desc(),
        )
        .all()
    )
    cutoff = datetime.utcnow() - _TTL
    stale: list[WikiCorrectionPreviewRow] = []
    for index, row in enumerate(rows):
        if index >= _KEEP_PER_PROJECT or row.created_at < cutoff:
            stale.append(row)
    if stale:
        for row in stale:
            db.delete(row)
        db.commit()


__all__ = [
    "WikiCorrectionPreviewRow",
    "save_preview",
    "load_preview",
    "delete_preview",
]
