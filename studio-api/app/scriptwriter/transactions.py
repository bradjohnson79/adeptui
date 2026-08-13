"""Named undoable ScriptTransaction commit layer."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from .errors import SCRIPT_NOT_REVERSIBLE, SCRIPT_TRANSACTION_FAILED, ScriptwriterError
from .models import ScriptDocument, ScriptElement, ScriptTransaction, TransactionSource
from .store import latest_reversible, list_transactions, load_document, save_document, save_transaction


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def commit_transaction(
    db: Session,
    doc: ScriptDocument,
    *,
    kind: str,
    source: TransactionSource,
    mutate: Callable[[ScriptDocument], list[str]],
    reversible: bool = True,
    extra_payload: Optional[dict[str, Any]] = None,
) -> tuple[ScriptDocument, ScriptTransaction]:
    """Apply mutate(doc) → save → record transaction with before snapshot for undo."""
    before_rev = doc.revision
    before_elements = [e.model_dump(mode="json") for e in doc.elements]
    before_sync = copy.deepcopy(doc.sceneSync)
    before_html = doc.contentHtml
    before_ctype = doc.contentType
    try:
        affected = mutate(doc) or []
    except ScriptwriterError:
        raise
    except Exception as exc:
        raise ScriptwriterError(SCRIPT_TRANSACTION_FAILED, str(exc), recovery_action="retry") from exc

    # Normalize orders
    for i, el in enumerate(sorted(doc.elements, key=lambda e: e.order)):
        el.order = i
    doc.elements = sorted(doc.elements, key=lambda e: e.order)
    doc.revision = before_rev + 1
    save_document(db, doc)

    tx = ScriptTransaction(
        id=str(uuid.uuid4()),
        documentId=doc.id,
        kind=kind,
        source=source,
        beforeRevision=before_rev,
        afterRevision=doc.revision,
        affectedElementIds=list(affected),
        createdAt=_now_iso(),
        reversible=reversible,
        payload={
            "beforeElements": before_elements,
            "beforeSceneSync": before_sync,
            "beforeContentHtml": before_html,
            "beforeContentType": before_ctype,
            **(extra_payload or {}),
        },
    )
    save_transaction(db, tx)
    return doc, tx


def undo_last(db: Session, document_id: str) -> tuple[ScriptDocument, ScriptTransaction]:
    doc = load_document(db, document_id)
    if not doc:
        raise ScriptwriterError("SCRIPT_LOAD_FAILED", "Document not found.", recovery_action="reload")
    tx = latest_reversible(db, document_id)
    if not tx or not tx.reversible:
        raise ScriptwriterError(SCRIPT_NOT_REVERSIBLE, "No reversible transaction.", recovery_action="none")
    before = tx.payload.get("beforeElements")
    if before is None:
        raise ScriptwriterError(SCRIPT_NOT_REVERSIBLE, "Transaction lacks reverse payload.", recovery_action="none")

    def mutate(d: ScriptDocument) -> list[str]:
        d.elements = [ScriptElement.model_validate(e) for e in before]
        sync = tx.payload.get("beforeSceneSync")
        if isinstance(sync, dict):
            d.sceneSync = sync  # type: ignore[assignment]
        before_html = tx.payload.get("beforeContentHtml")
        before_ctype = tx.payload.get("beforeContentType")
        d.contentHtml = before_html if isinstance(before_html, str) else None
        d.contentType = before_ctype if before_ctype in ("html", "elements") else "elements"  # type: ignore[assignment]
        return [e.id for e in d.elements]

    # Mark original undone via a follow-up system tx and restore
    new_doc, undo_tx = commit_transaction(
        db,
        doc,
        kind="restore_revision",
        source="system",
        mutate=mutate,
        reversible=False,
        extra_payload={"undoOf": tx.id},
    )
    # Flag original
    from .store import ScriptTransactionRow

    row = db.get(ScriptTransactionRow, tx.id)
    if row:
        payload = dict(tx.payload)
        payload["undone"] = True
        import json

        row.payload_json = json.dumps(payload, ensure_ascii=False)
        db.commit()
    return new_doc, undo_tx


def history(db: Session, document_id: str, limit: int = 50) -> list[ScriptTransaction]:
    return list_transactions(db, document_id, limit=limit)
