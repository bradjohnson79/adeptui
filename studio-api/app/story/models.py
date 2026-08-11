"""Story tool models: lightweight story/outline document (TipTap HTML)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StoryDocument(BaseModel):
    id: str
    projectId: str
    title: str = "Untitled Story"
    content: str = ""
    wordCount: int = 0
    createdAt: datetime
    updatedAt: datetime


class StorySaveRequest(BaseModel):
    content: str = ""
    title: Optional[str] = None
