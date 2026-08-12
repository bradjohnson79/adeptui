"""Refine Wiki creator-correction contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

CorrectionType = Literal[
    "REWRITE",
    "ADD",
    "REMOVE",
    "MERGE",
    "RENAME",
    "RECLASSIFY",
    "MOVE",
    "CANON_CORRECTION",
    "SUMMARY_CORRECTION",
    "RELATIONSHIP_CORRECTION",
    "TIMELINE_CORRECTION",
    "SCRIPT_CORRECTION",
]

# Entity types a record can be reclassified into (character-section purity).
EntityType = Literal[
    "character",
    "location",
    "organization",
    "attribute",
    "wardrobe",
    "prop",
    "timeline_event",
    "world_rule",
    "story",
    "note",
]


class CorrectionTarget(BaseModel):
    pageId: str | None = None
    sectionId: str | None = None
    pageType: str | None = None
    recordId: str | None = None
    label: str = ""  # human-readable, e.g. "Story / Short Summary"


class EntityReclassification(BaseModel):
    """A single entity the creator says is misclassified."""

    name: str
    fromType: str = "character"
    toType: EntityType = "note"
    attachTo: str | None = None  # for attributes: the person they belong to


class ProposedChange(BaseModel):
    area: str  # "Story" | "Characters" | "Notes" | "Story Summary Editor" | ...
    description: str
    recordId: str | None = None
    changeType: str = ""  # human-readable: "Rewrite", "Move", "Merge", ...


class CorrectionPreview(BaseModel):
    previewId: str
    projectId: str
    instruction: str
    correctionType: CorrectionType = "CANON_CORRECTION"
    targets: list[CorrectionTarget] = Field(default_factory=list)
    affectedPages: list[str] = Field(default_factory=list)
    affectedRecords: list[str] = Field(default_factory=list)
    proposedChanges: list[ProposedChange] = Field(default_factory=list)
    notesMoves: list[str] = Field(default_factory=list)
    summaryRecompile: bool = False
    entityReclassifications: list[EntityReclassification] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    learnedRule: str = ""
    requiresConfirmation: bool = True
    clarificationQuestion: str | None = None
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CreatorWikiCorrection(BaseModel):
    """Durable record of an applied creator correction."""

    id: str
    projectId: str
    targetPageIds: list[str] = Field(default_factory=list)
    targetSectionIds: list[str] = Field(default_factory=list)
    instruction: str
    correctionType: str = "CANON_CORRECTION"
    supersededRecordIds: list[str] = Field(default_factory=list)
    createdRecordIds: list[str] = Field(default_factory=list)
    affectedPageIds: list[str] = Field(default_factory=list)
    creatorConfirmed: bool = True
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revisionId: str = ""


class CoDirectorLearnedCorrection(BaseModel):
    """Project-scoped learned guidance from an accepted creator correction."""

    id: str
    projectId: str
    correctionType: str = "CANON_CORRECTION"
    instruction: str = ""
    learnedRule: str = ""
    affectedEntities: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    targetSections: list[str] = Field(default_factory=list)
    entityTypeOverrides: dict[str, str] = Field(default_factory=dict)  # name -> entity type
    sourceRevisionId: str = ""
    active: bool = True
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


__all__ = [
    "CorrectionType",
    "EntityType",
    "CorrectionTarget",
    "EntityReclassification",
    "ProposedChange",
    "CorrectionPreview",
    "CreatorWikiCorrection",
    "CoDirectorLearnedCorrection",
]
