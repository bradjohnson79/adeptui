"""HTTP API for story entries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .models import StoryEntry, StoryEntryCreate, StoryEntryUpdate, StoryReorderBody
from .store import (
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    reorder_entries,
    update_entry,
)

router = APIRouter(prefix="/projects/{project_id}/story-entries", tags=["story-entries"])


def _row_to_model(row) -> StoryEntry:
    return StoryEntry(
        id=row.id,
        projectId=row.project_id,
        title=row.title,
        entryType=row.entry_type,
        logline=row.logline,
        shortSummary=row.short_summary,
        longSummary=row.long_summary,
        sortOrder=row.sort_order,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
    )


@router.get("", response_model=list[StoryEntry])
def get_entries(project_id: str, db: Session = Depends(get_db)):
    rows = list_entries(db, project_id)
    return [_row_to_model(r) for r in rows]


@router.post("", response_model=StoryEntry, status_code=201)
def create_story_entry(project_id: str, body: StoryEntryCreate, db: Session = Depends(get_db)):
    row = create_entry(db, project_id, body)
    return _row_to_model(row)


@router.get("/{entry_id}", response_model=StoryEntry)
def get_story_entry(project_id: str, entry_id: str, db: Session = Depends(get_db)):
    row = get_entry(db, entry_id)
    if not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Story entry not found")
    return _row_to_model(row)


@router.put("/{entry_id}", response_model=StoryEntry)
def update_story_entry(project_id: str, entry_id: str, body: StoryEntryUpdate, db: Session = Depends(get_db)):
    row = get_entry(db, entry_id)
    if not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Story entry not found")
    updated = update_entry(db, entry_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Story entry not found")
    return _row_to_model(updated)


@router.delete("/{entry_id}")
def delete_story_entry(project_id: str, entry_id: str, db: Session = Depends(get_db)):
    row = get_entry(db, entry_id)
    if not row or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Story entry not found")
    ok = delete_entry(db, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Story entry not found")
    return {"ok": True}


@router.put("/reorder", response_model=list[StoryEntry])
def reorder_story_entries(project_id: str, body: StoryReorderBody, db: Session = Depends(get_db)):
    rows = reorder_entries(db, project_id, body.entryIds)
    return [_row_to_model(r) for r in rows]
