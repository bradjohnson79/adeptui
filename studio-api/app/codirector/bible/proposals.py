"""ProposalService: durable propose → approve/reject/request-revision → execute → receipt.

This is the *only* write path that can change a Production Bible on behalf of the model.
Chat/providers may only ever call `create_proposal`; approving, rejecting, or executing is a
separate, explicit, user-triggered action. Execution is idempotent per `(proposal, base
version, payload)` via `operations.compute_input_hash` — approving an already-completed
proposal twice returns the original receipt instead of double-applying.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ...db import (
    CoDirectorApproval,
    CoDirectorExecutionReceipt,
    CoDirectorProposal,
    ProductionBible,
)
from ..errors import (
    APPROVAL_ALREADY_RECORDED,
    EXECUTION_FAILED,
    PROPOSAL_INVALID_STATE,
    PROPOSAL_NOT_FOUND,
    PROPOSAL_STALE,
    PROJECT_SCOPE_VIOLATION,
    RECEIPT_NOT_FOUND,
    CoDirectorError,
)
from . import operations as ops
from .schemas import BibleMutationSet, ExecutionReceiptOut, ProposalOut

_TERMINAL_STATUSES = {"rejected", "completed", "failed", "cancelled"}
_REVIEWABLE_STATUSES = {"pending", "revision_requested", "stale"}


def _payload_from_json(raw: str) -> BibleMutationSet:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        data = {}
    return BibleMutationSet.model_validate(data)


def _is_stale(proposal: CoDirectorProposal, bible: Optional[ProductionBible]) -> bool:
    current_id = bible.current_version_id if bible else None
    return proposal.based_on_version_id != current_id


def _row_to_out(row: CoDirectorProposal, *, is_stale: bool) -> ProposalOut:
    bible_version_number = None
    return ProposalOut(
        id=row.id,
        projectId=row.project_id,
        bibleId=row.bible_id,
        basedOnVersionId=row.based_on_version_id,
        basedOnVersionNumber=bible_version_number,
        proposalType=row.proposal_type,  # type: ignore[arg-type]
        title=row.title,
        summary=row.summary,
        payload=_payload_from_json(row.payload_json),
        status=row.status,  # type: ignore[arg-type]
        requestId=row.request_id,
        createdBy=row.created_by,
        createdAt=row.created_at.isoformat() if row.created_at else "",
        updatedAt=row.updated_at.isoformat() if row.updated_at else "",
        isStale=is_stale,
    )


class ProposalService:
    @staticmethod
    def create_proposal(
        db: Session,
        *,
        project_id: str,
        proposal_type: str,
        title: str,
        summary: str,
        payload: BibleMutationSet,
        request_id: Optional[str] = None,
        created_by: str = "assistant",
    ) -> ProposalOut:
        bible = ops.get_bible(db, project_id)
        now = datetime.utcnow()
        row = CoDirectorProposal(
            id=str(uuid.uuid4()),
            project_id=project_id,
            bible_id=bible.id if bible else None,
            based_on_version_id=bible.current_version_id if bible else None,
            proposal_type=proposal_type,
            title=title,
            summary=summary,
            payload_json=json.dumps(payload.model_dump(mode="json")),
            status="pending",
            request_id=request_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _row_to_out(row, is_stale=False)

    @staticmethod
    def _get_row(db: Session, project_id: str, proposal_id: str) -> CoDirectorProposal:
        row = db.get(CoDirectorProposal, proposal_id)
        if not row:
            raise CoDirectorError(
                PROPOSAL_NOT_FOUND,
                "Proposal not found.",
                details={"proposalId": proposal_id},
                recoverable=False,
                recommended_action="none",
            )
        if row.project_id != project_id:
            raise CoDirectorError(
                PROJECT_SCOPE_VIOLATION,
                "This proposal belongs to a different project.",
                details={"proposalId": proposal_id, "projectId": project_id},
                recoverable=False,
                recommended_action="none",
            )
        return row

    @staticmethod
    def get(db: Session, project_id: str, proposal_id: str) -> ProposalOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        bible = ops.get_bible(db, project_id)
        return _row_to_out(row, is_stale=row.status in _REVIEWABLE_STATUSES and _is_stale(row, bible))

    @staticmethod
    def list(db: Session, project_id: str, status: Optional[str] = None) -> list[ProposalOut]:
        query = db.query(CoDirectorProposal).filter(CoDirectorProposal.project_id == project_id)
        if status:
            query = query.filter(CoDirectorProposal.status == status)
        rows = query.order_by(CoDirectorProposal.created_at.desc()).all()
        bible = ops.get_bible(db, project_id)
        return [_row_to_out(r, is_stale=r.status in _REVIEWABLE_STATUSES and _is_stale(r, bible)) for r in rows]

    @staticmethod
    def preview(db: Session, project_id: str, proposal_id: str) -> dict:
        row = ProposalService._get_row(db, project_id, proposal_id)
        bible = ops.get_bible(db, project_id)
        stale = _is_stale(row, bible)
        payload = _payload_from_json(row.payload_json)

        before_entities = []
        current_version_number = None
        if bible and bible.current_version_id:
            current_version = ops.get_version(db, bible.current_version_id)
            if current_version:
                current_version_number = current_version.version_number
                before_entities = [ops.entity_row_to_schema(r) for r in ops.entities_for_version(db, current_version.id)]

        after_entities = list(before_entities)
        by_key = {e.entityKey: e for e in after_entities}
        for m in payload.entityMutations:
            if m.remove:
                by_key.pop(m.entityKey, None)
            else:
                existing = by_key.get(m.entityKey)
                from .schemas import BibleEntity

                by_key[m.entityKey] = BibleEntity(
                    entityType=m.entityType,
                    entityKey=m.entityKey,
                    displayName=m.displayName if m.displayName is not None else (existing.displayName if existing else ""),
                    data=m.data if m.data is not None else (existing.data if existing else {}),
                )
        after_entities = list(by_key.values())

        entity_diff = ops.diff_entities(before_entities, after_entities)
        fact_diff = [
            {"op": "remove" if fm.remove else "upsert", "factId": fm.factId, "statement": fm.statement}
            for fm in payload.factMutations
        ]

        return {
            "proposal": _row_to_out(row, is_stale=stale).model_dump(mode="json"),
            "currentVersionNumber": current_version_number,
            "wouldCreateVersionNumber": (current_version_number or 0) + 1,
            "entityDiff": entity_diff,
            "factDiff": fact_diff,
            "isStale": stale,
        }

    @staticmethod
    def reject(db: Session, project_id: str, proposal_id: str, *, note: Optional[str], decided_by: str) -> ProposalOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        if row.status not in _REVIEWABLE_STATUSES:
            raise CoDirectorError(
                PROPOSAL_INVALID_STATE,
                f"Proposal cannot be rejected from status '{row.status}'.",
                details={"proposalId": proposal_id, "status": row.status},
                recoverable=False,
                recommended_action="none",
            )
        _record_decision(db, row, decision="rejected", note=note, decided_by=decided_by)
        row.status = "rejected"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _row_to_out(row, is_stale=False)

    @staticmethod
    def request_revision(db: Session, project_id: str, proposal_id: str, *, note: Optional[str], decided_by: str) -> ProposalOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        if row.status not in _REVIEWABLE_STATUSES:
            raise CoDirectorError(
                PROPOSAL_INVALID_STATE,
                f"Proposal cannot be sent back for revision from status '{row.status}'.",
                details={"proposalId": proposal_id, "status": row.status},
                recoverable=False,
                recommended_action="none",
            )
        _record_decision(db, row, decision="revision_requested", note=note, decided_by=decided_by)
        row.status = "revision_requested"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _row_to_out(row, is_stale=False)

    @staticmethod
    def cancel(db: Session, project_id: str, proposal_id: str, *, note: Optional[str], decided_by: str) -> ProposalOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        if row.status in _TERMINAL_STATUSES:
            raise CoDirectorError(
                PROPOSAL_INVALID_STATE,
                f"Proposal is already '{row.status}' and cannot be cancelled.",
                details={"proposalId": proposal_id, "status": row.status},
                recoverable=False,
                recommended_action="none",
            )
        _record_decision(db, row, decision="cancelled", note=note, decided_by=decided_by)
        row.status = "cancelled"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _row_to_out(row, is_stale=False)

    @staticmethod
    def approve(db: Session, project_id: str, proposal_id: str, *, note: Optional[str], decided_by: str) -> ExecutionReceiptOut:
        row = ProposalService._get_row(db, project_id, proposal_id)

        if row.status == "completed":
            raise CoDirectorError(
                APPROVAL_ALREADY_RECORDED,
                "This proposal was already approved and applied.",
                details={"proposalId": proposal_id},
                recoverable=False,
                recommended_action="none",
            )
        if row.status not in _REVIEWABLE_STATUSES:
            raise CoDirectorError(
                PROPOSAL_INVALID_STATE,
                f"Proposal cannot be approved from status '{row.status}'.",
                details={"proposalId": proposal_id, "status": row.status},
                recoverable=False,
                recommended_action="none",
            )

        bible = ops.get_bible(db, project_id)
        if _is_stale(row, bible):
            row.status = "stale"
            row.updated_at = datetime.utcnow()
            db.commit()
            raise CoDirectorError(
                PROPOSAL_STALE,
                "The Production Bible changed since this proposal was created. Preview it again before approving.",
                details={"proposalId": proposal_id},
                recoverable=True,
                recommended_action="preview_again",
            )

        payload = _payload_from_json(row.payload_json)
        input_hash = ops.compute_input_hash(row.id, row.based_on_version_id, payload)

        existing_receipt = (
            db.query(CoDirectorExecutionReceipt)
            .filter(
                CoDirectorExecutionReceipt.proposal_id == row.id,
                CoDirectorExecutionReceipt.input_hash == input_hash,
                CoDirectorExecutionReceipt.status == "success",
            )
            .first()
        )
        if existing_receipt:
            return _receipt_to_out(db, existing_receipt)

        _record_decision(db, row, decision="approved", note=note, decided_by=decided_by)
        row.status = "executing"
        row.updated_at = datetime.utcnow()
        db.commit()

        now = datetime.utcnow()
        try:
            if bible is None:
                bible = ProductionBible(id=str(uuid.uuid4()), project_id=project_id, created_at=now, updated_at=now)
                db.add(bible)
                db.flush()
            base_version = ops.get_current_version(db, bible) if bible.current_version_id else None
            new_version = ops.apply_mutation_set(
                db, bible=bible, base_version=base_version, mutations=payload, created_by=f"proposal:{row.id}"
            )
            receipt = CoDirectorExecutionReceipt(
                id=str(uuid.uuid4()),
                proposal_id=row.id,
                input_hash=input_hash,
                status="success",
                resulting_version_id=new_version.id,
                error_json=None,
                executed_at=datetime.utcnow(),
            )
            db.add(receipt)
            row.bible_id = bible.id
            row.status = "completed"
            row.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(receipt)
            return _receipt_to_out(db, receipt)
        except Exception as exc:  # pragma: no cover - defensive; execution failures are rare
            db.rollback()
            receipt = CoDirectorExecutionReceipt(
                id=str(uuid.uuid4()),
                proposal_id=row.id,
                input_hash=input_hash,
                status="failed",
                resulting_version_id=None,
                error_json=json.dumps({"message": str(exc)}),
                executed_at=datetime.utcnow(),
            )
            db.add(receipt)
            row.status = "failed"
            row.updated_at = datetime.utcnow()
            db.commit()
            raise CoDirectorError(
                EXECUTION_FAILED,
                "Applying this proposal to the Production Bible failed.",
                details={"proposalId": proposal_id, "reason": str(exc)[:200]},
                recoverable=True,
                recommended_action="retry",
            ) from exc

    @staticmethod
    def get_receipt(db: Session, project_id: str, proposal_id: str) -> ExecutionReceiptOut:
        row = ProposalService._get_row(db, project_id, proposal_id)
        receipt = (
            db.query(CoDirectorExecutionReceipt)
            .filter(CoDirectorExecutionReceipt.proposal_id == row.id)
            .order_by(CoDirectorExecutionReceipt.executed_at.desc())
            .first()
        )
        if not receipt:
            raise CoDirectorError(
                RECEIPT_NOT_FOUND,
                "No execution receipt exists for this proposal yet.",
                details={"proposalId": proposal_id},
                recoverable=True,
                recommended_action="none",
            )
        return _receipt_to_out(db, receipt)


def _record_decision(db: Session, row: CoDirectorProposal, *, decision: str, note: Optional[str], decided_by: str) -> None:
    db.add(
        CoDirectorApproval(
            id=str(uuid.uuid4()),
            proposal_id=row.id,
            decision=decision,
            note=note or "",
            decided_by=decided_by,
            decided_at=datetime.utcnow(),
        )
    )


def _receipt_to_out(db: Session, receipt: CoDirectorExecutionReceipt) -> ExecutionReceiptOut:
    version_number = None
    if receipt.resulting_version_id:
        version = ops.get_version(db, receipt.resulting_version_id)
        if version:
            version_number = version.version_number
    error = None
    if receipt.error_json:
        try:
            error = json.loads(receipt.error_json)
        except Exception:
            error = {"message": receipt.error_json}
    return ExecutionReceiptOut(
        id=receipt.id,
        proposalId=receipt.proposal_id,
        inputHash=receipt.input_hash,
        status=receipt.status,
        resultingVersionId=receipt.resulting_version_id,
        resultingVersionNumber=version_number,
        error=error,
        executedAt=receipt.executed_at.isoformat() if receipt.executed_at else "",
    )
