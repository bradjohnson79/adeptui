"""Production lifecycle state contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

ProductionLifecycleStage = Literal[
    "STORY",
    "SCRIPT",
    "CASTING",
    "PRODUCTION_PLANNING",
    "PRODUCTION",
    "TIMELINE_ASSEMBLY",
    "POST_PRODUCTION",
    "FINAL_QC",
    "COMPLETE",
]

ScriptStatus = Literal["NONE", "DRAFT", "REVISING", "APPROVED", "LOCKED"]
CastingProjectStatus = Literal["NOT_AVAILABLE", "OPEN", "IN_PROGRESS", "CAST_LOCKED"]
ProductionStatus = Literal["BLOCKED", "PLANNING", "IN_PROGRESS", "COMPLETE"]
PostStatus = Literal["NOT_READY", "READY", "IN_PROGRESS", "COMPLETE"]
CharacterCastStatus = Literal[
    "NOT_STARTED",
    "CONCEPTING",
    "CANDIDATES_READY",
    "SELECTED",
    "REFERENCE_SHEET_READY",
    "VOICE_SELECTED",
    "CAST_LOCKED",
]
SceneReadyStatus = Literal["BLOCKED", "PARTIAL", "READY", "IN_PRODUCTION", "COMPLETE"]


class CharacterCastingRecord(BaseModel):
    characterId: str
    characterName: str
    status: CharacterCastStatus = "NOT_STARTED"
    exploratory: bool = False
    selectedPortraitAssetId: str | None = None
    selectedVoiceId: str | None = None
    wikiPageId: str | None = None


class SceneProductionReadiness(BaseModel):
    sceneId: str
    scriptLocked: bool = False
    requiredCharacters: list[str] = Field(default_factory=list)
    castReady: bool = False
    locationReady: bool = False
    wardrobeReady: bool = False
    propsReady: bool = False
    imageReferencesReady: bool = False
    voiceReady: bool = False
    audioPlanReady: bool = False
    generationPlanReady: bool = False
    status: SceneReadyStatus = "BLOCKED"
    blockerSummary: str = ""


class ProjectProductionLifecycle(BaseModel):
    projectId: str
    currentStage: ProductionLifecycleStage = "STORY"
    storyReady: bool = False
    scriptStatus: ScriptStatus = "NONE"
    castingStatus: CastingProjectStatus = "NOT_AVAILABLE"
    productionStatus: ProductionStatus = "BLOCKED"
    postStatus: PostStatus = "NOT_READY"
    finalQcPassed: bool = False
    projectComplete: bool = False
    lockedComplete: bool = False
    formatProfile: str = "narrative_visual"
    characterCasting: list[CharacterCastingRecord] = Field(default_factory=list)
    scenes: list[SceneProductionReadiness] = Field(default_factory=list)
    stageHistory: list[dict] = Field(default_factory=list)
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


HARD_LAWS = (
    "NO_FORMAL_CASTING_WITHOUT_SCRIPT",
    "NO_FORMAL_PRODUCTION_WITHOUT_CAST",
    "NO_FINAL_GENERATION_WITHOUT_SCENE_READINESS",
    "NO_POST_WITHOUT_PRODUCTION_ASSETS",
    "NO_COMPLETE_WITHOUT_FINAL_QC",
)
