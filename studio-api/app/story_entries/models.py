"""Pydantic models for StoryEntries."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

StoryEntryType = Literal["project_story", "episode", "chapter", "segment", "other"]


class StoryEntry(BaseModel):
    id: str
    projectId: str
    title: str = ""
    entryType: StoryEntryType = "project_story"
    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""
    sortOrder: int = 0
    createdAt: datetime
    updatedAt: datetime


class StoryEntryCreate(BaseModel):
    title: str = ""
    entryType: StoryEntryType = "project_story"
    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""


class StoryEntryUpdate(BaseModel):
    title: Optional[str] = None
    entryType: Optional[StoryEntryType] = None
    logline: Optional[str] = None
    shortSummary: Optional[str] = None
    longSummary: Optional[str] = None
    sortOrder: Optional[int] = None


class StoryReorderBody(BaseModel):
    entryIds: list[str]
