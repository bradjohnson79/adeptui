"""HTTP surface for the Project Foundation Status service."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .schemas import FoundationStatus
from .service import get_foundation_status

router = APIRouter(prefix="/projects/{project_id}/foundation", tags=["foundation"])


@router.get("", response_model=FoundationStatus)
def get_foundation(project_id: str, db: Session = Depends(get_db)) -> FoundationStatus:
    return get_foundation_status(db, project_id)
