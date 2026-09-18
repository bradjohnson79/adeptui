"""Three-layer VideoGeneratorKnowledgeProfile (not a single blob)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

UNAVAILABLE_MESSAGE = "generator-specific prompting unavailable"


class CapabilityLayer(BaseModel):
    supportsTextToVideo: bool = False
    supportsImageToVideo: bool = False
    supportsStartFrame: bool = False
    supportsEndFrame: bool = False
    supportsNegativePrompt: bool = False
    supportsSeed: bool = False
    nativeAudio: bool = False
    nativeThreeKeyframe: bool = False
    durationsSec: list[float] = Field(default_factory=list)
    resolution: Optional[str] = None
    maxImagesTextToVideo: Optional[int] = None
    maxImagesImageToVideo: Optional[int] = None
    imageSlots: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class PromptLayer(BaseModel):
    dialect: str
    sourcePack: Optional[str] = None
    inheritPromptFromPack: Optional[str] = None
    positiveAppend: list[str] = Field(default_factory=list)
    negativeBase: list[str] = Field(default_factory=list)
    frameRoles: list[str] = Field(default_factory=list)
    subjectTags: bool = False
    nativeThreeKeyframe: bool = False
    threeFrameStrategy: Optional[str] = None
    disclosure: Optional[str] = None
    supportsNegativePrompt: bool = False


class WorkflowVersionNote(BaseModel):
    requiredComponents: list[str] = Field(default_factory=list)
    submitParams: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkflowLayer(BaseModel):
    adapterId: str
    aliases: list[str] = Field(default_factory=list)
    engineId: Optional[str] = None
    versionNotes: dict[str, WorkflowVersionNote] = Field(default_factory=dict)


class VideoGeneratorKnowledgeProfile(BaseModel):
    profileId: str
    displayName: str
    productionControlIds: list[str] = Field(default_factory=list)
    capability: CapabilityLayer
    prompt: PromptLayer
    workflow: WorkflowLayer
