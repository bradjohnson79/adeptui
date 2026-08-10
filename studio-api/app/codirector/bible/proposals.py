"""ProposalService: durable propose → approve/reject/request-revision → execute → receipt.

This is the *only* write path the model can reach on behalf of a user, for either flavour of
proposal:

- **Bible proposals** (`proposal_type` in `BIBLE_PROPOSAL_TYPES`) carry a `BibleMutationSet` and
  apply through `operations.apply_mutation_set`.
- **Tool proposals** (`proposal_type == "tool_call"`, M2.2) carry a server-owned
  `ToolCallPayload` and apply through `ToolExecutionService.execute_approved_proposal`.

Chat/providers may only ever *create* a proposal; approving, rejecting, or executing is a
separate, explicit, user-triggered action. `approve()` branches on flavour exactly once — the
decision record, the terminal-state guards, the staleness gate, and the execution receipt are
shared, so there is one approval system rather than two. Execution is idempotent per
`(proposal, base state, payload)`: approving an already-completed proposal twice returns the
original receipt instead of double-applying.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

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
from .schemas import (
    TOOL_CALL_PROPOSAL_TYPE,
    BibleMutationSet,
    ExecutionReceiptOut,
    ProposalOut,
)

_TERMINAL_STATUSES = {"rejected", "completed", "failed", "cancelled"}
_REVIEWABLE_STATUSES = {"pending", "revision_requested", "stale"}


def _payload_from_json(raw: str) -> BibleMutationSet:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        data = {}
    return BibleMutationSet.model_validate(data)


def _raw_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_tool_proposal(row: CoDirectorProposal) -> bool:
    return row.proposal_type == TOOL_CALL_PROPOSAL_TYPE


def _is_stale(proposal: CoDirectorProposal, bible: Optional[ProductionBible]) -> bool:
    """Bible staleness: the proposal's base version is no longer the current one."""

    current_id = bible.current_version_id if bible else None
    return proposal.based_on_version_id != current_id


def _is_tool_proposal_stale(db: Session, row: CoDirectorProposal) -> bool:
    """Tool staleness: any resource the proposal pinned has moved since it was created."""

    from ..tools.execution import ToolExecutionService

    try:
        payload = ToolExecutionService.parse_payload(row.payload_json)
    except CoDirectorError:
        # An unreadable payload can never be applied safely; treat it as stale so the only
        # available action is cancel.
        return True
    return ToolExecutionService.is_stale(db, project_id=row.project_id, payload=payload)


def _stale_for_row(db: Session, row: CoDirectorProposal, bible: Optional[ProductionBible]) -> bool:
    if row.status not in _REVIEWABLE_STATUSES:
        return False
    if is_tool_proposal(row):
        return _is_tool_proposal_stale(db, row)
    return _is_stale(row, bible)


def _row_to_out(row: CoDirectorProposal, *, is_stale: bool) -> ProposalOut:
    bible_version_number = None
    tool_call = _raw_payload(row.payload_json) if is_tool_proposal(row) else None
    return ProposalOut(
        id=row.id,
        projectId=row.project_id,
        bibleId=row.bible_id,
        basedOnVersionId=row.based_on_version_id,
        basedOnVersionNumber=bible_version_number,
        proposalType=row.proposal_type,  # type: ignore[arg-type]
        title=row.title,
        summary=row.summary,
        payload=BibleMutationSet() if tool_call is not None else _payload_from_json(row.payload_json),
        toolCall=tool_call,
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
    def create_tool_proposal(
        db: Session,
        *,
        project_id: str,
        payload: Any,
        title: str,
        summary: str,
        request_id: Optional[str] = None,
        created_by: str = "assistant",
    ) -> ProposalOut:
        """Persist a `tool_call` proposal.

        `payload` is a `tools.definitions.ToolCallPayload`, built entirely server-side. It is
        typed loosely here only to keep `bible` from importing `tools` at module scope (the tool
        package imports this module to reach `ProposalService`).
        """

        bible = ops.get_bible(db, project_id)
        now = datetime.utcnow()
        row = CoDirectorProposal(
            id=str(uuid.uuid4()),
            project_id=project_id,
            bible_id=bible.id if bible else None,
            based_on_version_id=bible.current_version_id if bible else None,
            proposal_type=TOOL_CALL_PROPOSAL_TYPE,
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
        # c2/D10: surface staleness at creation time, not only at approval. The
        # pinned base_resource_versions were just captured from the current
        # state, so this is normally False here — but computing it makes the
        # `isStale` field authoritative from the moment the proposal exists and
        # lets the chat path emit a `proposal_stale` event at propose time
        # instead of waiting for approval.
        is_stale = _is_tool_proposal_stale(db, row) if row.status in _REVIEWABLE_STATUSES else False
        return _row_to_out(row, is_stale=is_stale)

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
        return _row_to_out(row, is_stale=_stale_for_row(db, row, bible))

    @staticmethod
    def list(db: Session, project_id: str, status: Optional[str] = None) -> list[ProposalOut]:
        query = db.query(CoDirectorProposal).filter(CoDirectorProposal.project_id == project_id)
        if status:
            query = query.filter(CoDirectorProposal.status == status)
        rows = query.order_by(CoDirectorProposal.created_at.desc()).all()
        bible = ops.get_bible(db, project_id)
        return [_row_to_out(r, is_stale=_stale_for_row(db, r, bible)) for r in rows]

    @staticmethod
    def preview(db: Session, project_id: str, proposal_id: str) -> dict:
        row = ProposalService._get_row(db, project_id, proposal_id)
        bible = ops.get_bible(db, project_id)

        if is_tool_proposal(row):
            # A tool proposal's preview was computed server-side when it was created; re-deriving
            # it here would let a since-changed world silently rewrite what the user is agreeing
            # to. Staleness is reported instead, and the stored preview is shown as-is.
            stale = _is_tool_proposal_stale(db, row)
            payload_dict = _raw_payload(row.payload_json)
            return {
                "proposal": _row_to_out(row, is_stale=stale).model_dump(mode="json"),
                "currentVersionNumber": None,
                "wouldCreateVersionNumber": None,
                "entityDiff": [],
                "factDiff": [],
                "toolPreview": payload_dict.get("preview"),
                "isStale": stale,
            }

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
            existing_receipt = (
                db.query(CoDirectorExecutionReceipt)
                .filter(
                    CoDirectorExecutionReceipt.proposal_id == row.id,
                    CoDirectorExecutionReceipt.status == "success",
                )
                .order_by(CoDirectorExecutionReceipt.executed_at.desc())
                .first()
            )
            if existing_receipt:
                out = _receipt_to_out(db, existing_receipt)
                if is_tool_proposal(row):
                    _attach_tool_details(db, row, out)
                return out
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
        tool_flavoured = is_tool_proposal(row)
        if _is_tool_proposal_stale(db, row) if tool_flavoured else _is_stale(row, bible):
            row.status = "stale"
            row.updated_at = datetime.utcnow()
            db.commit()
            raise CoDirectorError(
                PROPOSAL_STALE,
                (
                    "The project changed since this action was proposed. Ask Co-Director again "
                    "so it can propose against the current state."
                    if tool_flavoured
                    else "The Production Bible changed since this proposal was created. Preview it again before approving."
                ),
                details={"proposalId": proposal_id, "proposalType": row.proposal_type},
                recoverable=True,
                recommended_action="preview_again",
            )

        if tool_flavoured:
            return ProposalService._approve_tool_proposal(db, row, note=note, decided_by=decided_by)

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
    def _approve_tool_proposal(
        db: Session, row: CoDirectorProposal, *, note: Optional[str], decided_by: str
    ) -> ExecutionReceiptOut:
        """Record the decision, then let the *server* run the tool the user approved.

        Structurally identical to the Bible branch: idempotency check → decision row →
        `executing` → apply → receipt. Only the "apply" step differs.
        """

        from ..tools.execution import ToolExecutionService

        payload = ToolExecutionService.parse_payload(row.payload_json)
        input_hash = payload.inputHash or ""

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

        try:
            outcome = ToolExecutionService.execute_approved_proposal(
                db, proposal=row, payload=payload, decided_by=decided_by
            )
        except CoDirectorError as err:
            receipt = CoDirectorExecutionReceipt(
                id=str(uuid.uuid4()),
                proposal_id=row.id,
                input_hash=input_hash,
                status="failed",
                resulting_version_id=None,
                error_json=json.dumps(err.to_dict()),
                executed_at=datetime.utcnow(),
            )
            db.add(receipt)
            row.status = "failed"
            row.updated_at = datetime.utcnow()
            db.commit()
            raise

        invocation = outcome["invocation"]
        receipt = CoDirectorExecutionReceipt(
            id=str(uuid.uuid4()),
            proposal_id=row.id,
            input_hash=input_hash,
            status="success",
            resulting_version_id=outcome.get("resultingVersionId"),
            error_json=None,
            executed_at=datetime.utcnow(),
        )
        db.add(receipt)
        row.status = "completed"
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(receipt)

        out = _receipt_to_out(db, receipt)
        out.toolId = payload.toolId
        out.toolInvocationId = invocation.id
        out.toolResult = outcome.get("result")
        out.toolResultTruncated = bool(outcome.get("resultTruncated"))
        return out

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
        out = _receipt_to_out(db, receipt)
        if is_tool_proposal(row):
            _attach_tool_details(db, row, out)
        return out


def _attach_tool_details(db: Session, row: CoDirectorProposal, out: ExecutionReceiptOut) -> None:
    """Fill a receipt's tool fields from the invocation ledger (read-only enrichment)."""

    from ...db import CoDirectorToolInvocation

    out.toolId = _raw_payload(row.payload_json).get("toolId")
    invocation = (
        db.query(CoDirectorToolInvocation)
        .filter(CoDirectorToolInvocation.proposal_id == row.id)
        .order_by(CoDirectorToolInvocation.created_at.desc())
        .first()
    )
    if not invocation:
        return
    out.toolInvocationId = invocation.id
    out.toolResultTruncated = bool(invocation.result_truncated)
    if invocation.result_json:
        try:
            out.toolResult = json.loads(invocation.result_json)
        except Exception:
            out.toolResult = None


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
