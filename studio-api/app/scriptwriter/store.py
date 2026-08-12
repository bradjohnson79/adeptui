"""SQLAlchemy persistence for M4.7 script documents."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from ..db import Base, SessionLocal, engine
from .models import (
    ScriptDocument,
    ScriptElement,
    ScriptNote,
    ScriptRevisionSnapshot,
    ScriptTransaction,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ScriptDocumentRow(Base):
    __tablename__ = "script_documents_v2"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled Script")
    format: Mapped[str] = mapped_column(String(32), default="feature")
    draft_status: Mapped[str] = mapped_column(String(32), default="first-draft")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    revision_set_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    active_revision: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    production_numbers_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    elements_json: Mapped[str] = mapped_column(Text, default="[]")
    scene_sync_json: Mapped[str] = mapped_column(Text, default="{}")
    legacy_doc_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    recovery_json: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default="")
    updated_at: Mapped[str] = mapped_column(String(40), default="")


class ScriptTransactionRow(Base):
    __tablename__ = "script_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(32), default="creator")
    before_revision: Mapped[int] = mapped_column(Integer, default=0)
    after_revision: Mapped[int] = mapped_column(Integer, default=0)
    affected_element_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    reversible: Mapped[bool] = mapped_column(Boolean, default=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default="")


class ScriptRevisionRow(Base):
    __tablename__ = "script_revision_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    revision_set_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    color: Mapped[str] = mapped_column(String(40), default="White")
    note: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    elements_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(40), default="")


class ScriptNoteRow(Base):
    __tablename__ = "script_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    element_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    scene_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="document")
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    author: Mapped[str] = mapped_column(String(80), default="creator")
    created_at: Mapped[str] = mapped_column(String(40), default="")


class ScriptMigrationBackupRow(Base):
    __tablename__ = "script_migration_backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[str] = mapped_column(String(36), index=True)
    backup_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default="")


def ensure_scriptwriter_tables() -> None:
    Base.metadata.create_all(
        bind=engine,
        tables=[
            ScriptDocumentRow.__table__,
            ScriptTransactionRow.__table__,
            ScriptRevisionRow.__table__,
            ScriptNoteRow.__table__,
            ScriptMigrationBackupRow.__table__,
        ],
    )


def _row_to_doc(row: ScriptDocumentRow) -> ScriptDocument:
    elements = [ScriptElement.model_validate(e) for e in json.loads(row.elements_json or "[]")]
    sync = json.loads(row.scene_sync_json or "{}")
    return ScriptDocument(
        id=row.id,
        projectId=row.project_id,
        title=row.title,
        format=row.format,  # type: ignore[arg-type]
        draftStatus=row.draft_status,  # type: ignore[arg-type]
        elements=sorted(elements, key=lambda e: e.order),
        revision=row.revision,
        revisionSetId=row.revision_set_id,
        activeRevision=row.active_revision,
        productionNumbersLocked=bool(row.production_numbers_locked),
        sceneSync=sync,
        legacyDocId=row.legacy_doc_id,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


def save_document(db: Session, doc: ScriptDocument) -> ScriptDocument:
    doc.updatedAt = _utc_now()
    if not doc.createdAt:
        doc.createdAt = doc.updatedAt
    row = db.get(ScriptDocumentRow, doc.id)
    if not row:
        row = ScriptDocumentRow(id=doc.id, project_id=doc.projectId, created_at=doc.createdAt)
        db.add(row)
    row.project_id = doc.projectId
    row.title = doc.title
    row.format = doc.format
    row.draft_status = doc.draftStatus
    row.revision = doc.revision
    row.revision_set_id = doc.revisionSetId
    row.active_revision = doc.activeRevision
    row.production_numbers_locked = doc.productionNumbersLocked
    row.elements_json = json.dumps([e.model_dump(mode="json") for e in doc.elements], ensure_ascii=False)
    row.scene_sync_json = json.dumps(doc.sceneSync, ensure_ascii=False)
    row.legacy_doc_id = doc.legacyDocId
    row.updated_at = doc.updatedAt
    if not row.created_at:
        row.created_at = doc.createdAt
    db.commit()

    try:
        from app.codirector.production_state.invalidation import invalidate_production_state
        invalidate_production_state(db, doc.projectId, affected_domains={"SCRIPT", "TIMELINE"})
    except Exception:
        pass

    return doc


def load_document(db: Session, document_id: str) -> Optional[ScriptDocument]:
    row = db.get(ScriptDocumentRow, document_id)
    return _row_to_doc(row) if row else None


def list_documents(db: Session, project_id: str) -> list[ScriptDocument]:
    rows = (
        db.query(ScriptDocumentRow)
        .filter(ScriptDocumentRow.project_id == project_id)
        .order_by(ScriptDocumentRow.updated_at.desc())
        .all()
    )
    return [_row_to_doc(r) for r in rows]


def save_transaction(db: Session, tx: ScriptTransaction) -> ScriptTransaction:
    if not tx.createdAt:
        tx.createdAt = _utc_now()
    row = ScriptTransactionRow(
        id=tx.id,
        document_id=tx.documentId,
        kind=tx.kind,
        source=tx.source,
        before_revision=tx.beforeRevision,
        after_revision=tx.afterRevision,
        affected_element_ids_json=json.dumps(tx.affectedElementIds),
        reversible=tx.reversible,
        payload_json=json.dumps(tx.payload, ensure_ascii=False),
        created_at=tx.createdAt,
    )
    db.add(row)
    db.commit()
    return tx


def list_transactions(db: Session, document_id: str, *, limit: int = 50) -> list[ScriptTransaction]:
    rows = (
        db.query(ScriptTransactionRow)
        .filter(ScriptTransactionRow.document_id == document_id)
        .order_by(ScriptTransactionRow.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[ScriptTransaction] = []
    for r in rows:
        out.append(
            ScriptTransaction(
                id=r.id,
                documentId=r.document_id,
                kind=r.kind,
                source=r.source,  # type: ignore[arg-type]
                beforeRevision=r.before_revision,
                afterRevision=r.after_revision,
                affectedElementIds=json.loads(r.affected_element_ids_json or "[]"),
                createdAt=r.created_at,
                reversible=bool(r.reversible),
                payload=json.loads(r.payload_json or "{}"),
            )
        )
    return out


def latest_reversible(db: Session, document_id: str) -> Optional[ScriptTransaction]:
    for tx in list_transactions(db, document_id, limit=100):
        if tx.reversible and not tx.payload.get("undone"):
            return tx
    return None


def save_revision(db: Session, snap: ScriptRevisionSnapshot) -> ScriptRevisionSnapshot:
    if not snap.createdAt:
        snap.createdAt = _utc_now()
    db.add(
        ScriptRevisionRow(
            id=snap.id,
            document_id=snap.documentId,
            revision_set_id=snap.revisionSetId,
            name=snap.name,
            color=snap.color,
            note=snap.note,
            revision=snap.revision,
            elements_json=json.dumps([e.model_dump(mode="json") for e in snap.elements], ensure_ascii=False),
            created_at=snap.createdAt,
        )
    )
    db.commit()
    return snap


def list_revisions(db: Session, document_id: str) -> list[ScriptRevisionSnapshot]:
    rows = (
        db.query(ScriptRevisionRow)
        .filter(ScriptRevisionRow.document_id == document_id)
        .order_by(ScriptRevisionRow.created_at.desc())
        .all()
    )
    out: list[ScriptRevisionSnapshot] = []
    for r in rows:
        out.append(
            ScriptRevisionSnapshot(
                id=r.id,
                documentId=r.document_id,
                revisionSetId=r.revision_set_id,
                name=r.name,
                color=r.color,
                note=r.note,
                revision=r.revision,
                elements=[ScriptElement.model_validate(e) for e in json.loads(r.elements_json or "[]")],
                createdAt=r.created_at,
            )
        )
    return out


def load_revision(db: Session, revision_id: str) -> Optional[ScriptRevisionSnapshot]:
    r = db.get(ScriptRevisionRow, revision_id)
    if not r:
        return None
    return ScriptRevisionSnapshot(
        id=r.id,
        documentId=r.document_id,
        revisionSetId=r.revision_set_id,
        name=r.name,
        color=r.color,
        note=r.note,
        revision=r.revision,
        elements=[ScriptElement.model_validate(e) for e in json.loads(r.elements_json or "[]")],
        createdAt=r.created_at,
    )


def set_recovery(db: Session, document_id: str, payload: dict[str, Any]) -> None:
    row = db.get(ScriptDocumentRow, document_id)
    if row:
        row.recovery_json = json.dumps(payload, ensure_ascii=False)
        db.commit()


def get_recovery(db: Session, document_id: str) -> Optional[dict[str, Any]]:
    row = db.get(ScriptDocumentRow, document_id)
    if not row or not (row.recovery_json or "").strip():
        return None
    return json.loads(row.recovery_json)


def clear_recovery(db: Session, document_id: str) -> None:
    row = db.get(ScriptDocumentRow, document_id)
    if row:
        row.recovery_json = ""
        db.commit()


def save_migration_backup(db: Session, project_id: str, document_id: str, backup: dict[str, Any]) -> str:
    bid = str(uuid.uuid4())
    db.add(
        ScriptMigrationBackupRow(
            id=bid,
            project_id=project_id,
            document_id=document_id,
            backup_json=json.dumps(backup, ensure_ascii=False),
            created_at=_utc_now(),
        )
    )
    db.commit()
    return bid


def load_migration_backup(db: Session, backup_id: str) -> Optional[dict[str, Any]]:
    row = db.get(ScriptMigrationBackupRow, backup_id)
    if not row:
        return None
    return json.loads(row.backup_json or "{}")


def with_session():
    return SessionLocal()
