"""M3.0e Model Intelligence Layer — schemas and normalized intent contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    OFFICIAL = "OFFICIAL"
    VERIFIED_INTERNAL = "VERIFIED_INTERNAL"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    COMMUNITY_UNVERIFIED = "COMMUNITY_UNVERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class PackStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    QUARANTINED = "QUARANTINED"


class CapabilitySupport(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ProductionReadiness(str, Enum):
    PRODUCTION = "production"
    EXPERIMENTAL = "experimental"
    NOT_PRODUCTION_READY = "not_production_ready"
    CONFIGURATION_REQUIRED = "configuration_required"
    PRODUCT_APPROVAL_REQUIRED = "product_approval_required"
    UNAVAILABLE = "unavailable"


class AudioChannelPolicy(str, Enum):
    REQUIRED = "required"
    ALLOWED = "allowed"
    PROHIBITED = "prohibited"


class AudioMode(str, Enum):
    NONE = "none"
    DIALOGUE_ONLY = "dialogue_only"
    AMBIENCE_ONLY = "ambience_only"
    SOUND_EFFECTS_ONLY = "sound_effects_only"
    MUSIC_ONLY = "music_only"
    DIALOGUE_AND_AMBIENCE = "dialogue_and_ambience"
    DIALOGUE_AMBIENCE_AND_EFFECTS = "dialogue_ambience_and_effects"
    FULL_MIX = "full_mix"
    EXTERNAL_AUDIO_PIPELINE = "external_audio_pipeline"


class PreflightStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"


class OverrideDisposition(str, Enum):
    APPLIED = "applied"
    ADJUSTED = "adjusted"
    REJECTED = "rejected"


class ProvenanceClaim(BaseModel):
    sourceType: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    sourceReference: str = ""
    modelVersion: str = ""
    knowledgePackVersion: str = ""
    verifiedAt: Optional[str] = None
    confidence: float = 0.0
    notes: str = ""


class PackManifest(BaseModel):
    schemaVersion: int = 1
    modelId: str
    providerId: str
    engineId: str
    displayName: str
    modelVersion: str
    knowledgePackVersion: str
    status: PackStatus = PackStatus.DRAFT
    runtimeStatus: ProductionReadiness = ProductionReadiness.EXPERIMENTAL
    media: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    documentation: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, Any] = Field(default_factory=dict)
    licensing: dict[str, Any] = Field(default_factory=dict)
    maintainers: list[str] = Field(default_factory=list)


class AudioIntent(BaseModel):
    audioMode: AudioMode = AudioMode.NONE
    music: AudioChannelPolicy = AudioChannelPolicy.PROHIBITED
    dialogue: AudioChannelPolicy = AudioChannelPolicy.ALLOWED
    ambience: AudioChannelPolicy = AudioChannelPolicy.ALLOWED
    soundEffects: AudioChannelPolicy = AudioChannelPolicy.ALLOWED


class NormalizedGenerationIntent(BaseModel):
    creativeIntent: dict[str, Any] = Field(default_factory=dict)
    projectContext: dict[str, Any] = Field(default_factory=dict)
    sceneContext: dict[str, Any] = Field(default_factory=dict)
    shotContext: dict[str, Any] = Field(default_factory=dict)
    subjects: list[Any] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    cinematography: dict[str, Any] = Field(default_factory=dict)
    performance: dict[str, Any] = Field(default_factory=dict)
    motion: dict[str, Any] = Field(default_factory=dict)
    audioIntent: AudioIntent = Field(default_factory=AudioIntent)
    continuityConstraints: list[str] = Field(default_factory=list)
    mustInclude: list[str] = Field(default_factory=list)
    mustAvoid: list[str] = Field(default_factory=list)
    technicalRequirements: dict[str, Any] = Field(default_factory=dict)
    userOverrides: dict[str, Any] = Field(default_factory=dict)
    userPrompt: str = ""
    negativePromptHint: str = ""
    mode: str = "image_to_video"
    mediaType: str = "video"
    durationSec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    hasSourceImage: bool = False
    referenceCount: int = 0
    forceModelId: Optional[str] = None
    preserveExactWording: bool = False


class AppliedRule(BaseModel):
    ruleId: str
    description: str
    provenance: ProvenanceClaim = Field(default_factory=ProvenanceClaim)


class CompileResult(BaseModel):
    modelId: str
    providerId: str
    engineId: str
    compiledPrompt: str
    negativePrompt: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    appliedRules: list[AppliedRule] = Field(default_factory=list)
    excludedRules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    fallbackRecommendations: list[str] = Field(default_factory=list)
    knowledgePackVersion: str = ""
    modelVersion: str = ""
    audioPlanSummary: str = ""
    limitations: list[str] = Field(default_factory=list)
    status: str = "ok"
    overrideDispositions: dict[str, OverrideDisposition] = Field(default_factory=dict)


class ModelRecommendation(BaseModel):
    recommendedModel: str
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    requiresApproval: bool = False
    scores: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class PreflightResult(BaseModel):
    status: PreflightStatus
    modelId: str
    engineId: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    costEstimate: Optional[str] = None
    compile: Optional[CompileResult] = None
    recommendation: Optional[ModelRecommendation] = None


class EvaluationResult(BaseModel):
    band: Literal["PASS", "PASS_WITH_WARNINGS", "REVIEW_REQUIRED", "REJECT"] = "REVIEW_REQUIRED"
    findings: list[str] = Field(default_factory=list)
    modelId: str = ""
    failureCodes: list[str] = Field(default_factory=list)


class RevisionPlan(BaseModel):
    actions: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""
    preventPaidLoop: bool = True
    originalFailureCodes: list[str] = Field(default_factory=list)


class ExperienceRecord(BaseModel):
    id: str
    modelId: str
    modelVersion: str = ""
    providerId: str = ""
    knowledgePackVersion: str = ""
    projectId: Optional[str] = None
    sceneId: Optional[str] = None
    shotId: Optional[str] = None
    requestType: str = ""
    compiledRuleIds: list[str] = Field(default_factory=list)
    parameterSummary: dict[str, Any] = Field(default_factory=dict)
    generationStatus: str = ""
    userAccepted: Optional[bool] = None
    userRejected: Optional[bool] = None
    revisionRequested: Optional[bool] = None
    visionScore: Optional[float] = None
    continuityScore: Optional[float] = None
    failureCodes: list[str] = Field(default_factory=list)
    generationTimeMs: Optional[int] = None
    estimatedCost: Optional[str] = None
    actualCostWhereKnown: Optional[str] = None
    userFeedback: str = ""
    createdAt: str = ""
