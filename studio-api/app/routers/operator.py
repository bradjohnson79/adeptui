"""Verified Operator channel — ack + status routes (Co-Director 2.0 Mission A).

The ack/status routes arrive without a project path segment, so the project id
is resolved from the durable `operator_requested` event (the append-only
event log is the source of truth, Law 8).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..codirector.operator import (
    acknowledge_operator_request,
    get_operator_record,
    resolve_operator_project,
)
from ..db import get_db

router = APIRouter()


class OperatorAckBody(BaseModel):
    originSessionId: Optional[str] = None
    workspace: Optional[str] = None
    target: Optional[str] = None
    verified: bool = False


@router.post("/operator/{request_id}/ack")
def ack_operator_request(
    request_id: str,
    body: OperatorAckBody,
    db: Session = Depends(get_db),
) -> dict:
    """Acknowledge a pending operator request (after frontend UI confirmation)."""
    project_id = resolve_operator_project(db, request_id)
    if not project_id:
        raise HTTPException(status_code=404, detail="Operator request not found.")
    return acknowledge_operator_request(
        db,
        project_id=project_id,
        request_id=request_id,
        origin_session_id=body.originSessionId,
        workspace=body.workspace,
        target=body.target,
        verified=body.verified,
    )


@router.get("/operator/{request_id}")
def get_operator_request_status(
    request_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Return the operator record (state derived by folding the event log)."""
    project_id = resolve_operator_project(db, request_id)
    if not project_id:
        raise HTTPException(status_code=404, detail="Operator request not found.")
    return get_operator_record(db, project_id=project_id, request_id=request_id)
