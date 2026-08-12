"""Prompt Intelligence V2 benchmark / certification models."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

BENCHMARK_SCHEMA_VERSION = "benchmark-schema@1"
EVALUATION_SCHEMA_VERSION = "evaluation-schema@1"

BenchmarkStrategy = Literal[
    "creator",
    "refined-english",
    "bilingual-subtle",
    "bilingual-balanced",
    "bilingual-strong",
]

RunStatus = Literal[
    "planned",
    "queued",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
]

SuiteRunStatus = Literal[
    "planned",
    "running",
    "paused",
    "completed",
    "cancelled",
    "failed",
]

CertificationStatusV2 = Literal[
    "not_tested",
    "benchmarking",
    "insufficient_evidence",
    "experimental",
    "certified_subtle",
    "certified_balanced",
    "certified_strong",
    "english_preferred",
    "no_material_difference",
    "bilingual_not_recommended",
    "regressed",
    "disabled",
]

StrategyMode = Literal["manual", "recommend", "automatic_certified"]
ConfidenceLevel = Literal["low", "medium", "high"]
RetentionMode = Literal["keep_all", "keep_winners", "keep_reviewed", "delete_failed"]
PreferredFlag = Literal["preferred", "tie", "fail", "none"]


class ControlSettings(BaseModel):
    seed: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    durationSec: Optional[float] = None
    fps: Optional[int] = None
    aspectRatio: Optional[str] = None
    kind: Optional[str] = None


class BenchmarkCase(BaseModel):
    benchmarkId: str
    category: str
    creatorPrompt: str
    negativePrompt: str = ""
    continuityContext: str = ""
    expectedIntent: str = ""
    lockedTerms: list[str] = Field(default_factory=list)
    providerEligibility: list[str] = Field(default_factory=list)
    evaluationCriteria: list[str] = Field(default_factory=list)
    controlSettings: ControlSettings = Field(default_factory=ControlSettings)


class BenchmarkSuite(BaseModel):
    suiteId: str
    suiteVersion: str = "1"
    domain: str
    matrixMode: Literal["full", "reduced"] = "reduced"
    matrixNote: str = ""
    strategies: list[BenchmarkStrategy] = Field(default_factory=list)
    samplesPerStrategy: int = 1
    certificationSamplesRequired: int = 3
    cases: list[BenchmarkCase] = Field(default_factory=list)
    schemaVersion: str = BENCHMARK_SCHEMA_VERSION


class MatrixCell(BaseModel):
    cellId: str
    suiteId: str
    benchmarkId: str
    category: str
    domain: str
    strategy: BenchmarkStrategy
    sampleIndex: int
    providerId: str
    modelRevision: str = "default"
    creatorPrompt: str
    negativePrompt: str = ""
    lockedTerms: list[str] = Field(default_factory=list)
    continuityContext: str = ""
    controlSettings: ControlSettings = Field(default_factory=ControlSettings)
    evaluationCriteria: list[str] = Field(default_factory=list)


class BenchmarkPlan(BaseModel):
    planId: str
    suiteId: str
    providerId: str
    modelRevision: str = "default"
    domain: str
    cells: list[MatrixCell] = Field(default_factory=list)
    estimatedJobs: int = 0
    estimatedDiskMb: float = 0.0
    matrixMode: str = "reduced"
    schemaVersion: str = BENCHMARK_SCHEMA_VERSION


class AutomatedHealthScores(BaseModel):
    completed: bool = False
    artifactExists: bool = False
    artifactNonEmpty: bool = False
    formatOk: bool = False
    dimsOk: bool = True
    durationOk: bool = True
    blackFrameSuspect: bool = False
    frozenFrameSuspect: bool = False
    clippingSuspect: bool = False
    silenceSuspect: bool = False
    metadataComplete: bool = False
    passed: bool = False
    notes: list[str] = Field(default_factory=list)


class HumanReviewScores(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    overall: float = 0.0
    preferred: PreferredFlag = "none"
    notes: str = ""
    reviewerId: str = "local"


class PromptBenchmarkRun(BaseModel):
    runId: str
    suiteRunId: str = ""
    cellId: str = ""
    suiteId: str
    benchmarkId: str
    category: str
    domain: str
    strategy: BenchmarkStrategy
    sampleIndex: int = 0
    providerId: str
    modelRevision: str = "default"
    workflowRevision: str = "default"
    profileId: str = ""
    profileVersion: str = ""
    controlSettings: ControlSettings = Field(default_factory=ControlSettings)
    seed: Optional[int] = None
    promptRecord: dict[str, Any] = Field(default_factory=dict)
    finalProviderPrompt: str = ""
    jobId: Optional[str] = None
    outputAssetIds: list[str] = Field(default_factory=list)
    outputPaths: list[str] = Field(default_factory=list)
    runtimeMs: Optional[int] = None
    vramPeakMb: Optional[float] = None
    success: bool = False
    status: RunStatus = "planned"
    automatedScores: AutomatedHealthScores = Field(default_factory=AutomatedHealthScores)
    humanScores: Optional[HumanReviewScores] = None
    error: Optional[dict[str, Any]] = None
    dryRun: bool = False
    createdAt: str = ""
    updatedAt: str = ""
    schemaVersion: str = BENCHMARK_SCHEMA_VERSION


class SuiteRun(BaseModel):
    suiteRunId: str
    suiteId: str
    providerId: str
    modelRevision: str = "default"
    domain: str
    status: SuiteRunStatus = "planned"
    planId: str = ""
    runIds: list[str] = Field(default_factory=list)
    cellIds: list[str] = Field(default_factory=list)
    samplesPerStrategy: int = 1
    retentionMode: RetentionMode = "keep_all"
    dryRun: bool = False
    paused: bool = False
    cancelRequested: bool = False
    createdAt: str = ""
    updatedAt: str = ""
    completedAt: Optional[str] = None
    error: Optional[dict[str, Any]] = None
    schemaVersion: str = BENCHMARK_SCHEMA_VERSION


class BlindComparisonItem(BaseModel):
    slotId: str
    runId: str
    # strategy hidden from reviewer until submit
    strategyHidden: bool = True
    outputAssetIds: list[str] = Field(default_factory=list)
    outputPaths: list[str] = Field(default_factory=list)
    domain: str = "video"


class BlindComparison(BaseModel):
    comparisonId: str
    suiteRunId: str
    benchmarkId: str
    category: str
    domain: str
    providerId: str
    modelRevision: str = "default"
    items: list[BlindComparisonItem] = Field(default_factory=list)
    # revealed only after submit
    strategyMap: dict[str, BenchmarkStrategy] = Field(default_factory=dict)
    revealed: bool = False
    submitted: bool = False
    reviews: dict[str, HumanReviewScores] = Field(default_factory=dict)
    createdAt: str = ""
    updatedAt: str = ""
    schemaVersion: str = EVALUATION_SCHEMA_VERSION


class CategoryEvidence(BaseModel):
    providerId: str
    modelRevision: str
    domain: str
    category: str
    workflowRevision: str = "default"
    status: CertificationStatusV2 = "not_tested"
    recommendedStrategy: Optional[BenchmarkStrategy] = None
    confidence: ConfidenceLevel = "low"
    sampleCount: int = 0
    scoresByStrategy: dict[str, float] = Field(default_factory=dict)
    runIds: list[str] = Field(default_factory=list)
    evidenceVersion: str = "1"
    stale: bool = False
    staleReason: Optional[str] = None
    promotedAt: Optional[str] = None
    previousOverlay: Optional[dict[str, Any]] = None
    auditLog: list[dict[str, Any]] = Field(default_factory=list)
    updatedAt: str = ""
    schemaVersion: str = EVALUATION_SCHEMA_VERSION


class PromptStrategyRecommendation(BaseModel):
    strategy: BenchmarkStrategy
    status: CertificationStatusV2
    confidence: ConfidenceLevel = "low"
    sampleCount: int = 0
    reason: str = ""
    evidenceVersion: str = ""
    category: str = ""
    domain: str = ""
    providerId: str = ""
    modelRevision: str = ""
    appliedAutomatically: bool = False


class EvidenceOverlay(BaseModel):
    profileId: str
    profileVersion: str
    recommendations: list[PromptStrategyRecommendation] = Field(default_factory=list)
    updatedAt: str = ""
    schemaVersion: str = EVALUATION_SCHEMA_VERSION


class AnalyzerV2Axes(BaseModel):
    promptQuality: int = 0
    providerCompatibility: int = 0
    recommendedStrategyConfidence: int = 0
    notes: list[str] = Field(default_factory=list)


class FeedbackItem(BaseModel):
    feedbackId: str
    projectId: Optional[str] = None
    domain: str
    category: str = ""
    providerId: str = ""
    modelRevision: str = ""
    strategyApplied: Optional[str] = None
    rating: Optional[int] = None
    notes: str = ""
    optIn: bool = True
    createdAt: str = ""
