"""FastAPI routes for Co-Director M2.5 vision validation."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ... import feature_flags as feature_flags_mod
from .approval import record_decision
from .corrections import create_correction_proposal
from .engine import run_validation
from .providers import VisionProviderUnavailable
from .schemas import ApproveRejectRequest, CorrectionRequest, ValidateRequest
from .sessions import session_history
from .store import VisionStore

router = APIRouter(prefix="/vision", tags=["codirector-vision"])


def _require_flag() -> None:
    if not feature_flags_mod.feature_flags.vision_validation_v1:
        raise HTTPException(status_code=404, detail="Vision validation is not enabled.")


@router.post("/validate")
def validate_asset(body: ValidateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    try:
        return run_validation(db, body)
    except VisionProviderUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/report/{report_id}")
def get_report(
    report_id: str,
    projectId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    report = VisionStore.get_report(db, report_id, project_id=projectId)
    if not report:
        raise HTTPException(status_code=404, detail="Validation report not found.")
    return report.model_dump(mode="json")


@router.get("/session/{session_id}")
def get_session(
    session_id: str,
    projectId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    session = VisionStore.get_session(db, session_id, project_id=projectId)
    if not session:
        raise HTTPException(status_code=404, detail="Validation session not found.")
    payload = session.model_dump(mode="json")
    if session.reportId:
        report = VisionStore.get_report(db, session.reportId, project_id=projectId or session.projectId)
        payload["report"] = report.model_dump(mode="json") if report else None
    payload["correctionLinks"] = [
        link.model_dump(mode="json") for link in VisionStore.list_correction_links(db, session_id)
    ]
    return payload


@router.post("/approve")
def approve_validation(body: ApproveRejectRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    decision = "override_approve" if body.override else "approved"
    try:
        return record_decision(
            db,
            project_id=body.projectId,
            session_id=body.sessionId,
            decision=decision,
            reviewer=body.reviewer,
            notes=body.notes,
            override=body.override,
            link_to_bible=body.linkToBible,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reject")
def reject_validation(body: ApproveRejectRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    decision = "override_reject" if body.override else "rejected"
    try:
        return record_decision(
            db,
            project_id=body.projectId,
            session_id=body.sessionId,
            decision=decision,
            reviewer=body.reviewer,
            notes=body.notes,
            override=body.override,
            link_to_bible=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/correction")
def propose_correction(body: CorrectionRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    _require_flag()
    session = VisionStore.get_session(db, body.sessionId, project_id=body.projectId)
    if not session or not session.reportId:
        raise HTTPException(status_code=404, detail="Validation session/report not found.")
    report = VisionStore.get_report(db, session.reportId, project_id=body.projectId)
    if not report:
        raise HTTPException(status_code=404, detail="Validation report not found.")
    return create_correction_proposal(
        db,
        project_id=body.projectId,
        report=report,
        finding_validator_ids=body.findingValidatorIds,
        notes=body.notes,
        created_by=body.createdBy,
    )


@router.get("/comparison/{comparison_id}")
def get_comparison(
    comparison_id: str,
    projectId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    comparison = VisionStore.get_comparison(db, comparison_id, project_id=projectId)
    if not comparison:
        raise HTTPException(status_code=404, detail="Validation comparison not found.")
    return comparison.model_dump(mode="json")


@router.get("/history")
def history(
    projectId: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_flag()
    return {"projectId": projectId, "sessions": session_history(db, projectId, limit=limit)}
