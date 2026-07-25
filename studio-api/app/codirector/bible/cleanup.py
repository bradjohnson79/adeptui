"""Project-scoped cleanup for Production Bible and related Co-Director rows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ...db import (
    BibleAuditEvent,
    CoDirectorApproval,
    CoDirectorExecutionReceipt,
    CoDirectorProposal,
    CoDirectorToolInvocation,
    ProductionBible,
    ProductionBibleEntity,
    ProductionBibleFact,
    ProductionBibleVersion,
)


def delete_bible_for_project(db: Session, project_id: str) -> None:
    bible = db.query(ProductionBible).filter(ProductionBible.project_id == project_id).first()
    if bible:
        version_ids = [v.id for v in db.query(ProductionBibleVersion).filter(ProductionBibleVersion.bible_id == bible.id).all()]
        if version_ids:
            db.query(ProductionBibleEntity).filter(ProductionBibleEntity.bible_version_id.in_(version_ids)).delete(
                synchronize_session=False
            )
            db.query(ProductionBibleFact).filter(ProductionBibleFact.bible_version_id.in_(version_ids)).delete(
                synchronize_session=False
            )
        db.query(ProductionBibleVersion).filter(ProductionBibleVersion.bible_id == bible.id).delete(synchronize_session=False)
        db.delete(bible)

    proposal_ids = [p.id for p in db.query(CoDirectorProposal).filter(CoDirectorProposal.project_id == project_id).all()]
    if proposal_ids:
        db.query(CoDirectorApproval).filter(CoDirectorApproval.proposal_id.in_(proposal_ids)).delete(synchronize_session=False)
        db.query(CoDirectorExecutionReceipt).filter(CoDirectorExecutionReceipt.proposal_id.in_(proposal_ids)).delete(
            synchronize_session=False
        )
    db.query(CoDirectorProposal).filter(CoDirectorProposal.project_id == project_id).delete(synchronize_session=False)
    db.query(CoDirectorToolInvocation).filter(CoDirectorToolInvocation.project_id == project_id).delete(synchronize_session=False)
    db.query(BibleAuditEvent).filter(BibleAuditEvent.project_id == project_id).delete(synchronize_session=False)
