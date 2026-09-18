"""Canonical generation request — production history, not conversation summary."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class InheritAudit(BaseModel):
    inherited: list[str] = Field(default_factory=list)
    overridden: list[str] = Field(default_factory=list)
    recompiled: list[str] = Field(default_factory=list)


class CanonicalGenerationRequest(BaseModel):
    requestId: str
    projectId: str
    conversationId: str = ""
    sourceMessageId: str = ""
    artifactType: str = "image"
    action: str = "image.generate"
    originalUserInstructions: str = ""
    resolvedCreativeBrief: str = ""
    compiledGeneratorPrompt: str = ""
    referenceAssetIds: list[str] = Field(default_factory=list)
    characterIds: list[str] = Field(default_factory=list)
    propIds: list[str] = Field(default_factory=list)
    environmentIds: list[str] = Field(default_factory=list)
    continuityConstraints: str = ""
    negativeConstraints: str = ""
    qualityIntent: str = ""
    route: str = ""
    provider: str = ""
    modelId: str = ""
    aspectRatio: str = ""
    width: int = 0
    height: int = 0
    generationParameters: dict[str, Any] = Field(default_factory=dict)
    workflowKey: str = ""
    providerPayload: dict[str, Any] = Field(default_factory=dict)
    executionId: str = ""
    jobIds: list[str] = Field(default_factory=list)
    resultAssetIds: list[str] = Field(default_factory=list)
    parentRequestId: Optional[str] = None
    revision: int = 1
    createdAt: str = ""
    inheritAudit: Optional[InheritAudit] = None
    lockLevel: str = ""
    lockScope: str = ""
    requestedProvider: str = ""
    requestedModelId: str = ""
    fallbackAudit: dict[str, Any] = Field(default_factory=dict)
    visionFacts: str = ""
    referenceRole: str = ""


class ResolvedRetry(BaseModel):
    prior: Optional[CanonicalGenerationRequest] = None
    next_request: Optional[CanonicalGenerationRequest] = None
    audit: Optional[InheritAudit] = None
    used_chat_inherit: bool = False
    clarification: str = ""
