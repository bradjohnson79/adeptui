"""Compiled Wiki page contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

PageType = Literal[
    "PROJECT",
    "STORY",
    "CHARACTER",
    "EPISODE",
    "SCENE",
    "LOCATION",
    "WORLD",
    "TIMELINE",
    "REFERENCES",
]


class CompiledWikiSection(BaseModel):
    id: str
    title: str
    body: str = ""
    bullets: list[str] = Field(default_factory=list)


class CompiledWikiPage(BaseModel):
    pageId: str
    pageType: PageType
    title: str
    summary: str = ""
    sections: list[CompiledWikiSection] = Field(default_factory=list)
    relatedPageIds: list[str] = Field(default_factory=list)
    sourceRecordIds: list[str] = Field(default_factory=list)
    canonState: str = "CONFIRMED"
    compiledRevision: int = 1
    questionsToExplore: list[str] = Field(default_factory=list)
    castingLink: str | None = None


class CompiledStorySummary(BaseModel):
    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""
    themes: list[str] = Field(default_factory=list)
    centralConflicts: list[str] = Field(default_factory=list)
    narrativeFrame: str = ""
    unresolvedQuestions: list[str] = Field(default_factory=list)
    sourceRecordIds: list[str] = Field(default_factory=list)
    lastCompiledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Per-section readiness (independent) and editor provenance.
    loglineCoverage: str = "MINIMAL"
    shortSummaryCoverage: str = "MINIMAL"
    longSummaryCoverage: str = "MINIMAL"
    requiresCreatorReview: bool = False
    editorMode: str = "deterministic"
    revisionDelta: str = ""

    @property
    def knowledgeCoverage(self) -> str:
        return self.longSummaryCoverage


class CompiledWikiTocNode(BaseModel):
    key: str
    label: str
    count: int = 0
    children: list[dict[str, Any]] = Field(default_factory=list)


class CompiledWikiBundle(BaseModel):
    projectId: str
    compiledRevision: int = 1
    lastCompiledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    projection: str = "compiled_bible_v1"
    toc: list[CompiledWikiTocNode] = Field(default_factory=list)
    pages: list[CompiledWikiPage] = Field(default_factory=list)
    storySummary: CompiledStorySummary = Field(default_factory=CompiledStorySummary)
    readabilityOk: bool = True
    readabilityIssues: list[str] = Field(default_factory=list)


def new_section(title: str, body: str = "", bullets: list[str] | None = None) -> CompiledWikiSection:
    return CompiledWikiSection(
        id=f"sec-{uuid4().hex[:8]}",
        title=title,
        body=body,
        bullets=list(bullets or []),
    )
