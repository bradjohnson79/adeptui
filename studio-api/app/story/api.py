"""HTTP API for the Story tool (lightweight story/outline editor)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .models import StoryDocument, StorySaveRequest
from .store import load_document, load_or_empty_document, save_document

router = APIRouter(prefix="/projects/{project_id}/story", tags=["story"])


@router.get("", response_model=StoryDocument)
def get_story(project_id: str, db: Session = Depends(get_db)) -> StoryDocument:
    # CDX-054: reads are side-effect free — no story_documents row is created
    # here; the row is created by the first explicit PUT (save_document).
    return load_or_empty_document(db, project_id)  # type: ignore[return-value]


@router.put("", response_model=StoryDocument)
def put_story(
    project_id: str, body: StorySaveRequest, db: Session = Depends(get_db)
) -> StoryDocument:
    # CDX-060: the legacy story_documents store is migration-only. Once a
    # project has canonical story_entries (the source the Wiki / Co-Director
    # actually reads), legacy writes are rejected with 410 so residual writers
    # can no longer create story_documents content the Wiki never sees. Reads
    # (GET /story, /story/status, and migrate_from_legacy) remain available and
    # the store itself is not deleted.
    from ..story_entries.store import list_entries

    if list_entries(db, project_id):
        raise HTTPException(
            status_code=410,
            detail="legacy_story_writes_disabled_story_entries_active",
        )

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
