"""Story Summary Editor contracts — evidence source + compiled result."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

Coverage = Literal["MINIMAL", "PARTIAL", "SUBSTANTIAL", "MATURE"]


class PreviousApprovedSummary(BaseModel):
    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""


class StorySummarySource(BaseModel):
    """Curated evidence for the Story Summary Editor — not raw Notes."""

    projectId: str
    confirmedFacts: list[str] = Field(default_factory=list)
    approvedScriptSummaries: list[str] = Field(default_factory=list)
    creatorStatedInterpretations: list[str] = Field(default_factory=list)
    specialistInterpretations: list[str] = Field(default_factory=list)
    confirmedCharacterRoles: list[str] = Field(default_factory=list)
    confirmedTimelineEvents: list[str] = Field(default_factory=list)
    confirmedWorldRules: list[str] = Field(default_factory=list)
    inferredThemes: list[str] = Field(default_factory=list)
    unresolvedQuestions: list[str] = Field(default_factory=list)
    sourceIds: list[str] = Field(default_factory=list)
    formatProfile: str = "narrative_visual"
    previousApprovedSummary: PreviousApprovedSummary | None = None


class CompiledStorySummary(BaseModel):
    """Creator-facing compiled Story summary with per-section readiness."""

    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""
    themes: list[str] = Field(default_factory=list)
    centralConflicts: list[str] = Field(default_factory=list)
    narrativeFrame: str = ""
    unresolvedQuestions: list[str] = Field(default_factory=list)
    sourceRecordIds: list[str] = Field(default_factory=list)
    lastCompiledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    loglineCoverage: Coverage = "MINIMAL"
    shortSummaryCoverage: Coverage = "MINIMAL"
    longSummaryCoverage: Coverage = "MINIMAL"
    requiresCreatorReview: bool = False
    editorMode: Literal["llm", "deterministic"] = "deterministic"
    revisionDelta: str = ""

    # Back-compat: old callers read `knowledgeCoverage`.
    @property
    def knowledgeCoverage(self) -> Coverage:
        return self.longSummaryCoverage


__all__ = [
    "Coverage",
    "PreviousApprovedSummary",
    "StorySummarySource",
    "CompiledStorySummary",
]
