"""Pydantic schemas for typed Production Bible entity payloads."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ReadinessLevel = Literal["incomplete", "basic", "production_ready", "generation_ready", "locked"]
ReferencePurpose = Literal["identity", "wardrobe", "location", "prop", "style", "negative", "other"]
ReferencePolarity = Literal["positive", "negative"]
RelationshipKind = Literal[
    "family", "friend", "rival", "romantic", "professional", "mentor", "antagonist", "other"
]
CanonStatus = Literal["draft", "approved", "superseded", "disputed"]
ContinuityAspect = Literal["wardrobe", "prop", "injury", "location", "time_of_day", "appearance", "other"]


class ProjectOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    description: str = ""
    genre: str = ""
    tone: str = ""
    logline: str = ""
    engineDefault: str = ""
    aspect: str = ""
    fps: int = 24


class CharacterData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    ageRange: str = ""
    genderPresentation: str = ""
    personality: str = ""
    motivation: str = ""
    backstory: str = ""
    performanceNotes: str = ""
    appearanceSummary: str = ""
    distinguishingFeatures: str = ""
    voiceNotes: str = ""
    profileItemId: Optional[str] = None
    avatarSessionId: Optional[str] = None
    masterSheetId: Optional[str] = None
    readiness: ReadinessLevel = "incomplete"
    notes: str = ""


class LocationData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    parentStableId: Optional[str] = None
    atmosphere: str = ""
    timePeriod: str = ""
    geography: str = ""
    lightingNotes: str = ""
    soundscape: str = ""
    readiness: ReadinessLevel = "incomplete"
    notes: str = ""


class ProductionObjectData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    objectKind: str = "prop"
    significance: str = ""
    ownerStableId: Optional[str] = None
    locationStableId: Optional[str] = None
    state: str = "intact"
    readiness: ReadinessLevel = "incomplete"
    notes: str = ""


class WardrobeData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    characterStableId: str = ""
    sceneIds: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)
    condition: str = ""
    notes: str = ""


class AppearanceStateData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    characterStableId: str = ""
    sceneId: Optional[str] = None
    description: str = ""
    injuries: list[str] = Field(default_factory=list)
    wardrobeStableId: Optional[str] = None
    notes: str = ""


class VisualLanguageData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    colorPalette: str = ""
    lightingStyle: str = ""
    cameraStyle: str = ""
    moodKeywords: list[str] = Field(default_factory=list)
    sceneOverride: bool = False
    sceneId: Optional[str] = None
    notes: str = ""


class CanonRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = ""
    scope: str = "project"
    entityStableId: Optional[str] = None
    sceneId: Optional[str] = None
    status: CanonStatus = "draft"
    supersedesStableId: Optional[str] = None
    rationale: str = ""
    notes: str = ""


class ProductionDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = ""
    rationale: str = ""
    entityStableId: Optional[str] = None
    sceneId: Optional[str] = None
    impact: str = ""
    notes: str = ""


class RelationshipData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fromStableId: str = ""
    toStableId: str = ""
    kind: RelationshipKind = "other"
    label: str = ""
    description: str = ""
    asymmetric: bool = True
    notes: str = ""


class ReferenceLinkData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assetId: str = ""
    targetStableId: str = ""
    purpose: ReferencePurpose = "identity"
    priority: int = 1
    polarity: ReferencePolarity = "positive"
    primary: bool = False
    notes: str = ""


class ContinuityStateData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aspect: ContinuityAspect = "other"
    entityStableId: Optional[str] = None
    sceneId: Optional[str] = None
    fromSceneId: Optional[str] = None
    toSceneId: Optional[str] = None
    expectedValue: str = ""
    actualValue: str = ""
    resolved: bool = False
    notes: str = ""


class ConflictRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conflictType: str = ""
    severity: Literal["info", "warning", "error"] = "warning"
    description: str = ""
    entityStableIds: list[str] = Field(default_factory=list)
    sceneIds: list[str] = Field(default_factory=list)
    resolved: bool = False
    resolutionNotes: str = ""


class TimelineEntryData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = ""
    storyOrder: int = 0
    sceneId: Optional[str] = None
    entityStableIds: list[str] = Field(default_factory=list)
    description: str = ""
    notes: str = ""


_ENTITY_DATA_MODELS: dict[str, type[BaseModel]] = {
    "project_profile": ProjectOverviewData,
    "character": CharacterData,
    "location": LocationData,
    "prop": ProductionObjectData,
    "production_object": ProductionObjectData,
    "wardrobe": WardrobeData,
    "appearance_state": AppearanceStateData,
    "visual_style": VisualLanguageData,
    "visual_language": VisualLanguageData,
    "canon_record": CanonRecordData,
    "production_decision": ProductionDecisionData,
    "relationship": RelationshipData,
    "reference_link": ReferenceLinkData,
    "continuity_state": ContinuityStateData,
    "conflict_record": ConflictRecordData,
    "timeline_entry": TimelineEntryData,
}


_META_DATA_KEYS = frozenset({"stableId", "slug", "lifecycleStatus", "contentRevision", "updatedAt"})


def validate_entity_data(entity_type: str, data: dict[str, Any]) -> dict[str, Any]:
    model = _ENTITY_DATA_MODELS.get(entity_type)
    if model is None:
        return data
    payload = {k: v for k, v in data.items() if k not in _META_DATA_KEYS}
    return model.model_validate(payload).model_dump(mode="json")
