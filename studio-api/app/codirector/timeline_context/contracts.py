"""Timeline Context Package contracts.

PRODUCTION_READINESS_OWNED_BY_CODIRECTOR + TIMELINE_CONSUMES_CONTEXT_PACKAGE.

Co-Director produces a single `TimelineContextPackage` object bundling all
relevant Project Bible context (locked canon, approved references, cast,
locations, continuity, wardrobe, production notes, reference assets,
generation constraints) for the Timeline to consume. The Timeline never
requests Bible/Characters/References individually — it consumes this package.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

TimelineGateLevel = Literal["EXPLORATION", "PRODUCTION_WARNING", "PRODUCTION_LOCK"]


class TimelineContextCharacter(BaseModel):
    characterId: str
    name: str
    castStatus: str = "NOT_STARTED"
    portraitAssetId: str | None = None
    voiceId: str | None = None
    wikiPageId: str | None = None
    locked: bool = False


class TimelineContextReference(BaseModel):
    assetId: str
    tag: str = ""
    kind: str = "image"
    filename: str = ""
    role: str = "reference"


class TimelineContextLocation(BaseModel):
    locationId: str
    name: str
    wikiPageId: str | None = None
    ready: bool = False


class TimelineContinuityLocks(BaseModel):
    identity: str = "inherit_project"
    wardrobe: str = "inherit_project"
    environment: str = "inherit_project"
    lighting: str = "inherit_project"
    camera: str = "inherit_project"
    props: str = "inherit_project"
    audio_bed: str = "inherit_project"
    motion_style: str = "inherit_project"


class TimelineGenerationConstraints(BaseModel):
    engine: str = "auto"
    durationSec: float = 5.0
    aspectRatio: str = "16:9"
    fps: int = 0
    fpsMode: str = "auto"
    negativePrompt: str = ""
    globalStylePrompt: str = ""


class TimelineSceneReadiness(BaseModel):
    sceneId: str
    status: str = "BLOCKED"
    blockerSummary: str = ""
    castReady: bool = False
    locationReady: bool = False
    wardrobeReady: bool = False
    propsReady: bool = False
    imageReferencesReady: bool = False
    voiceReady: bool = False
    generationPlanReady: bool = False


class TimelineContextPackage(BaseModel):
    projectId: str
    sceneId: str
    compiledAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Locked canon (story summary + confirmed facts)
    logline: str = ""
    shortSummary: str = ""
    longSummary: str = ""
    themes: list[str] = Field(default_factory=list)
    # Cast
    characters: list[TimelineContextCharacter] = Field(default_factory=list)
    # Approved references (image/video/audio assets tagged for use)
    references: list[TimelineContextReference] = Field(default_factory=list)
    # Locations
    locations: list[TimelineContextLocation] = Field(default_factory=list)
    # Scene continuity locks
    continuity: TimelineContinuityLocks = Field(default_factory=TimelineContinuityLocks)
    # Production notes (camera note, scene prompt)
    productionNotes: dict[str, Any] = Field(default_factory=dict)
    # Reference assets bound to this scene
    referenceAssets: list[TimelineContextReference] = Field(default_factory=list)
    # Generation constraints
    generationConstraints: TimelineGenerationConstraints = Field(
        default_factory=TimelineGenerationConstraints
    )
    # Scene-level readiness (consumed from the Production Readiness Service)
    readiness: TimelineSceneReadiness = Field(default_factory=lambda: TimelineSceneReadiness(sceneId=""))
    # Smart gate level for this scene
    gateLevel: TimelineGateLevel = "EXPLORATION"
    # Scene-level lifecycle status (SCENE_HAS_LIFECYCLE_STATUS)
    sceneStatus: str = "Draft"
    # SceneCraft-ready hierarchy (SCENECRAFT_READY_HIERARCHY). Today a single
    # implicit shot; SceneCraft will add explicit shots without redesign.
    sceneCraft: "SceneCraftHierarchy" = Field(default_factory=lambda: SceneCraftHierarchy(sceneId=""))


SCENE_LIFECYCLE_STATUSES = (
    "Draft",
    "Planning",
    "Ready",
    "Generating",
    "Review",
    "Approved",
    "Locked",
)


# --- SceneCraft-ready hierarchy (SCENECRAFT_READY_HIERARCHY) ---
# The Timeline data model already thinks in terms of Scene -> Shots ->
# Assets -> Timeline so multiple shots per scene can plug in later without a
# redesign. Today a scene maps to a single implicit shot; SceneCraft will add
# explicit shots.


class SceneCraftShot(BaseModel):
    shotId: str
    sceneId: str
    label: str = ""
    """Assets bound to this shot (image/video/audio references)."""
    assetIds: list[str] = Field(default_factory=list)
    """Timeline clip ids produced by/for this shot."""
    timelineClipIds: list[str] = Field(default_factory=list)
    status: str = "Draft"


class SceneCraftHierarchy(BaseModel):
    sceneId: str
    """Today: a single implicit shot representing the whole scene.
    SceneCraft will replace this with N explicit shots."""
    shots: list[SceneCraftShot] = Field(default_factory=list)

    @property
    def shotCount(self) -> int:
        return len(self.shots)


# Resolve the forward reference to SceneCraftHierarchy on TimelineContextPackage.
TimelineContextPackage.model_rebuild()
