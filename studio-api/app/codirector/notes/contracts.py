"""Notes layer contracts — working desk, never canon."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

NoteCategory = Literal[
    "Story",
    "Character",
    "Location",
    "World",
    "Research",
    "Production",
    "Question",
    "Idea",
    "Continuity",
    "Asset",
    "Unresolved",
]

NoteSource = Literal[
    "conversation",
    "uploaded_script",
    "storyboard",
    "inference",
    "specialist",
    "web_research",
    "creator",
]

NotePromotionStatus = Literal[
    "RAW",
    "REVIEWED",
    "WIKI_CANDIDATE",
    "PROMOTED",
    "DISMISSED",
    "SUPERSEDED",
]

NOTE_CATEGORIES: tuple[str, ...] = (
    "Story",
    "Character",
    "Location",
    "World",
    "Research",
    "Production",
    "Question",
    "Idea",
    "Continuity",
    "Asset",
    "Unresolved",
)

NOTE_STATUSES: tuple[str, ...] = (
    "RAW",
    "REVIEWED",
    "WIKI_CANDIDATE",
    "PROMOTED",
    "DISMISSED",
    "SUPERSEDED",
)


class WorkingNote(BaseModel):
    id: str = Field(default_factory=lambda: f"note-{uuid4().hex[:12]}")
    projectId: str = ""
    text: str
    category: NoteCategory = "Unresolved"
    source: NoteSource = "conversation"
    confidence: float = 0.5
    canonRelationship: str = "none"  # none | supports | conflicts | supersedes
    linkedEntityIds: list[str] = Field(default_factory=list)
    linkedAssetIds: list[str] = Field(default_factory=list)
    promotionStatus: NotePromotionStatus = "RAW"
    authority: str = "MODEL_INFERRED_WIKI_CANDIDATE"  # or USER_EXPLICIT_WIKI_WRITE
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promotedPageId: str | None = None
