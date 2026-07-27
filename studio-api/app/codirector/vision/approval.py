"""Human approve/reject/override records for vision validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .corrections import create_bible_link_proposal
from .schemas import ValidationApproval
from .store import VisionStore


def record_decision(
    db: Session,
    *,
    project_id: str,
    session_id: str,
    decision: str,
    reviewer: str = "user",
    notes: str = "",
    override: bool = False,
    override_reason: str = "",
    link_to_bible: bool = False,
) -> dict[str, Any]:
    session = VisionStore.get_session(db, session_id, project_id=project_id)
    if not session:
        raise ValueError("Validation session not found.")

    # B19: reject / corrections_required bands cannot be silently "approved".
    # Callers must pass override=true (decision becomes override_approve).
    report = None
    band = ""
    if session.reportId:
        report = VisionStore.get_report(db, session.reportId, project_id=project_id)
        band = (getattr(report, "band", None) or "").strip().lower() if report else ""

    if decision == "approved" and not override and band in ("reject", "corrections_required"):
        raise ValueError(
            f"Vision report band is '{band}'; approval requires override=true "
            "(recorded as override_approve)."
        )

    # M3.0d: override of a reject-band result requires an explicit reason.
    reason = (override_reason or notes or "").strip()
    if override and band in ("reject", "corrections_required") and not reason:
        raise ValueError(
            f"Vision report band is '{band}'; override requires a non-empty overrideReason."
        )

    approval_notes = notes
    if override and reason:
        approval_notes = (
            f"[overrideReason] {reason}"
            if not notes
            else f"{notes}\n[overrideReason] {reason}"
        )

    approval = ValidationApproval(
        approvalId=str(uuid.uuid4()),
        sessionId=session_id,
        reportId=session.reportId,
        projectId=project_id,
        decision=decision,  # type: ignore[arg-type]
        reviewer=reviewer,
        notes=approval_notes,
        override=override,
        createdAt=datetime.utcnow().isoformat() + "Z",
    )
    VisionStore.save_approval(db, approval)

    approved = decision in ("approved", "override_approve")
    terminal_status = "approved" if approved else "rejected"
    VisionStore.update_session_status(db, session_id, terminal_status)

    if session.assetId:
        VisionStore.update_asset_validation(
            db,
            session.assetId,
            lifecycle=terminal_status,
            result="passed" if approved else "rejected",
            production_approval="approved" if approved else "rejected",
        )

    bible_link: Optional[dict[str, Any]] = None
    if approved and link_to_bible:
        bible_link = create_bible_link_proposal(
            db,
            project_id=project_id,
            session_id=session_id,
            asset_id=session.assetId,
            report_id=session.reportId,
            created_by=reviewer,
        )

    return {
        "approval": approval.model_dump(mode="json"),
        "sessionId": session_id,
        "status": terminal_status,
        "bibleLinkProposal": bible_link,
    }
