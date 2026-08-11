"""HTTP API for the Story tool (lightweight story/outline editor)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from .models import StoryDocument, StorySaveRequest
from .store import get_or_create_document, load_document, save_document

router = APIRouter(prefix="/projects/{project_id}/story", tags=["story"])


@router.get("", response_model=StoryDocument)
def get_story(project_id: str, db: Session = Depends(get_db)) -> StoryDocument:
    row = get_or_create_document(db, project_id)
    return StoryDocument(
        id=row.id,
        projectId=row.project_id,
        title=row.title,
        content=row.content,
        wordCount=row.word_count,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


@router.put("", response_model=StoryDocument)
def put_story(
    project_id: str, body: StorySaveRequest, db: Session = Depends(get_db)
) -> StoryDocument:
    row = save_document(db, project_id, body.content, title=body.title)
    return StoryDocument(
        id=row.id,
        projectId=row.project_id,
        title=row.title,
        content=row.content,
        wordCount=row.word_count,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


@router.get("/status")
def story_status(project_id: str, db: Session = Depends(get_db)) -> dict:
    row = load_document(db, project_id)
    if not row:
        return {"exists": False, "wordCount": 0, "updatedAt": None}
    return {
        "exists": True,
        "wordCount": row.word_count,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }
