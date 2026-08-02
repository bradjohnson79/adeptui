"""Pydantic schemas for Voice Performance — provider-neutral."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ParseMarkupBody(BaseModel):
    projectId: str
    characterId: str
    sourceText: str
    sceneId: Optional[str] = None
    shotId: Optional[str] = None
    timelineId: Optional[str] = None
    scriptSourceId: Optional[str] = None
    voiceVersionId: Optional[str] = None


class CreatePlanBody(BaseModel):
    projectId: str
    characterId: str
    sourceText: str
    sceneId: Optional[str] = None
    shotId: Optional[str] = None
    timelineId: Optional[str] = None
    scriptSourceId: Optional[str] = None
    voiceVersionId: Optional[str] = None
    providerPreferences: list[str] = Field(default_factory=lambda: ["qwen3-tts", "kokoro"])
    createdBy: str = "owner"
    # When true, bind a draft/testing voice for evaluation — does not imply canonical approve.
    testingMode: bool = False


class GeneratePlanBody(BaseModel):
    allowKokoroFallback: bool = False
    allowTestingVoice: bool = False


class RefineSegmentBody(BaseModel):
    refinement: str = ""
    text: Optional[str] = None


class PlaceOnTimelineBody(BaseModel):
    timelineId: Optional[str] = None
    trackId: Optional[str] = None
    startMs: int = 0


class PerformanceSegmentOut(BaseModel):
    id: str
    orderIndex: int
    segmentType: str
    text: Optional[str] = None
    emotion: Optional[dict[str, Any]] = None
    delivery: Optional[dict[str, Any]] = None
    pace: Optional[Any] = None
    volume: Optional[Any] = None
    pitch: Optional[Any] = None
    emphasis: list[dict[str, Any]] = Field(default_factory=list)
    pronunciationOverrides: list[dict[str, Any]] = Field(default_factory=list)
    reactionKey: Optional[str] = None
    pauseMs: Optional[int] = None
    beatType: Optional[str] = None
    breathType: Optional[str] = None
    overlapGroup: Optional[str] = None
    interruptTarget: Optional[str] = None
    expectedDurationMs: Optional[int] = None
    relationshipContext: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    status: str = "pending"
    outputAssetId: Optional[str] = None
    provider: Optional[str] = None
    supportMode: Optional[str] = None  # Native | Translated | Prompt-guided | Pre-rendered asset | Unsupported
    error: Optional[str] = None
    retryOf: Optional[str] = None
    version: int = 1


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error", "blocked"]
    message: str
    sourceRange: Optional[dict[str, int]] = None
    tagKey: Optional[str] = None


class ParseResultOut(BaseModel):
    ok: bool
    status: Literal["resolved", "resolved_with_warning", "needs_review", "blocked"]
    sourceText: str
    speaker: Optional[str] = None
    characterId: Optional[str] = None
    voiceVersionId: Optional[str] = None
    segments: list[PerformanceSegmentOut] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    appliedDefaults: dict[str, Any] = Field(default_factory=dict)
    mock: bool = False


class PlanOut(BaseModel):
    id: str
    projectId: str
    sceneId: Optional[str] = None
    characterId: str
    characterProfileVersionId: str = ""
    voiceVersionId: str = ""
    performanceBibleVersionId: Optional[str] = None
    emotionProfileVersionId: Optional[str] = None
    pronunciationProfileVersionId: Optional[str] = None
    reactionLibraryVersionId: Optional[str] = None
    sourceText: str
    segments: list[PerformanceSegmentOut] = Field(default_factory=list)
    providerPreferences: list[str] = Field(default_factory=list)
    status: str = "draft"
    compilerVersion: str = "w44.1"
    schemaVersion: int = 1
    createdBy: str = "owner"
    createdAt: str = ""
    issues: list[ValidationIssue] = Field(default_factory=list)
    appliedDefaults: dict[str, Any] = Field(default_factory=dict)
    immutable: bool = False
    mock: bool = False
