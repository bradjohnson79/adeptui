"""Prompt Intelligence request/result models."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ENHANCEMENT_ENGINE_VERSION = "prompt-intelligence@1"

GenerationDomain = Literal["image", "video", "audio", "voice", "music", "sfx"]
LanguageBalance = Literal["subtle", "balanced", "strong"]
PromptLanguageStrategy = Literal[
    "english-only",
    "english-primary-chinese-support",
    "bilingual-balanced",
    "provider-tested-custom",
]
CertificationStatus = Literal["certified", "experimental", "supported", "not_tested", "disabled"]
RecommendationSeverity = Literal["info", "suggest", "important"]


class ModulesEnabled(BaseModel):
    productionRefinement: bool = True
    cinematicRefinement: bool = True
    motionRefinement: bool = True
    audioRefinement: bool = True
    characterContinuity: bool = True
    providerOptimization: bool = True
    languageModules: list[str] = Field(default_factory=lambda: ["en"])


class PromptQualityRecommendation(BaseModel):
    code: str
    message: str
    suggestedModule: Optional[str] = None
    severity: RecommendationSeverity = "suggest"


class PromptQualityReport(BaseModel):
    overall: int = 0
    dimensions: dict[str, int] = Field(default_factory=dict)
    recommendations: list[PromptQualityRecommendation] = Field(default_factory=list)


class PromptIntelligenceRecord(BaseModel):
    creatorPrompt: str = ""
    refinedEnglishPrompt: str = ""
    languageEnhancements: dict[str, str] = Field(default_factory=dict)
    finalProviderPrompt: str = ""
    negativePrompt: Optional[str] = None
    refinementLayers: dict[str, str] = Field(default_factory=dict)
    modulesEnabled: ModulesEnabled = Field(default_factory=ModulesEnabled)
    languageBalance: LanguageBalance = "balanced"
    promptProfileId: str = ""
    promptProfileVersion: str = ""
    enhancementEngineVersion: str = ENHANCEMENT_ENGINE_VERSION
    qualityReport: Optional[PromptQualityReport] = None
    manuallyOverridden: bool = False
    sourcePromptHash: str = ""
    generatedAt: str = ""
    intentSummary: dict[str, str] = Field(default_factory=dict)
    usedEnglishOnlyFallback: bool = False

    # UI convenience aliases
    @property
    def originalPrompt(self) -> str:
        return self.creatorPrompt

    @property
    def chineseEnhancement(self) -> str:
        return self.languageEnhancements.get("zh", "")


class PromptIntelligenceRequest(BaseModel):
    creatorPrompt: str
    domain: GenerationDomain = "video"
    providerId: Optional[str] = None
    modelId: Optional[str] = None
    modelVersion: Optional[str] = None
    engineId: Optional[str] = None
    negativePrompt: Optional[str] = None
    modulesEnabled: ModulesEnabled = Field(default_factory=ModulesEnabled)
    languageBalance: LanguageBalance = "balanced"
    lockedTerms: list[str] = Field(default_factory=list)
    continuityHints: list[str] = Field(default_factory=list)
    characterNames: list[str] = Field(default_factory=list)
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    manuallyOverridden: bool = False
    existingFinalPrompt: Optional[str] = None


class PromptIntelligenceResult(BaseModel):
    ok: bool = True
    record: PromptIntelligenceRecord
    profileRecommendation: Optional[str] = None
    error: Optional[dict[str, Any]] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_prompt_hash(text: str) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()[:16]
