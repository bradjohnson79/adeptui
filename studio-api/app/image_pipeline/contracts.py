"""Pydantic contracts for the Adept Image Pipeline foundation layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

QualityProfile = Literal["quick", "enhanced", "cinematic", "studio-master"]
DeploymentPreference = Literal["local", "api", "best-match"]
CameraStance = Literal["observational", "participatory"]
ScenePurposeClass = Literal[
    "establishing",
    "reveal",
    "suspense",
    "comedy",
    "intimacy",
    "action",
    "horror",
    "observational",
    "other",
]
SymmetryMode = Literal["symmetrical", "asymmetrical", "mixed"]
CharacterLockLevel = Literal["Flexible", "PreserveCore", "Strong", "ProductionLock"]
StagingRecommendation = Literal["poseCraft", "spatialMap", "direct"]
ProjectAutomationPolicy = Literal["Ask", "Automatic", "Manual"]
ApprovalStatus = Literal["not-required", "required", "approved", "blocked"]
PipelineStageStatus = Literal["pending", "ready", "blocked", "skipped", "complete"]
CandidateStatus = Literal["draft", "queued", "ready", "selected", "rejected", "mastered"]
EvaluationStatus = Literal["pass", "warning", "fail", "not-evaluated"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProvenanceRecord(BaseModel):
    createdAt: str = Field(default_factory=utc_now)
    actor: str = "system"
    source: str = "image_pipeline"
    note: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class StageReceipt(BaseModel):
    receiptId: str = Field(default_factory=lambda: str(uuid4()))
    planId: str | None = None
    stageKey: str
    status: PipelineStageStatus = "complete"
    createdAt: str = Field(default_factory=utc_now)
    actor: str = "system"
    note: str | None = None
    provenance: ProvenanceRecord = Field(default_factory=ProvenanceRecord)


class ImageApprovalRequirement(BaseModel):
    requirementId: str = Field(default_factory=lambda: str(uuid4()))
    kind: str
    status: ApprovalStatus = "not-required"
    reason: str | None = None
    creatorTip: str | None = None
    approvedBy: str | None = None
    approvedAt: str | None = None


class ImagePipelineStage(BaseModel):
    stageKey: str
    label: str
    description: str = ""
    enabled: bool = True
    required: bool = True
    status: PipelineStageStatus = "pending"
    summary: str | None = None
    approvalRequirement: ImageApprovalRequirement | None = None
    receipt: StageReceipt | None = None


class ProductionImageRequest(BaseModel):
    projectId: str
    prompt: str
    purpose: str
    qualityProfile: QualityProfile = "enhanced"
    deploymentPreference: DeploymentPreference = "best-match"
    styleProfileId: str | None = None
    allowApiDeployment: bool = False
    candidateCount: int = Field(default=3, ge=1, le=8)
    projectContext: dict[str, Any] = Field(default_factory=dict)
    characterIds: list[str] = Field(default_factory=list)
    referenceAssetIds: list[str] = Field(default_factory=list)
    spatialMapPayload: dict[str, Any] | None = None
    poseControlPayload: dict[str, Any] | None = None
    continuityNotes: list[str] = Field(default_factory=list)
    creatorNotes: str | None = None


class ImageShotIntent(BaseModel):
    prompt: str
    shotType: str = "medium"
    shotSize: str = "medium"
    subjectCount: int = 1
    subjectLabels: list[str] = Field(default_factory=list)
    primaryAction: str | None = None
    environmentType: str | None = None
    complexity: str = "simple"
    motionLevel: str = "still"
    wantsReveal: bool = False
    wantsSuspense: bool = False
    wantsComedy: bool = False
    wantsIntimacy: bool = False
    wantsAction: bool = False
    wantsHorror: bool = False
    wantsEstablishing: bool = False
    stagingSignals: list[str] = Field(default_factory=list)
    clarificationQuestion: str | None = None


class CreativeDirectionPacket(BaseModel):
    scenePurpose: str
    audienceFocus: list[str] = Field(default_factory=list)
    composition: str
    lens: str
    cameraHeight: str
    mood: str
    lighting: str
    color: str
    movementSuggestion: str
    visualPriority: str
    cameraStance: CameraStance = "observational"
    lightingEmotion: str
    scenePurposeClass: ScenePurposeClass = "other"
    symmetry: SymmetryMode = "mixed"
    visualLanguageProfileId: str | None = None
    creatorSummary: str | None = None


class ImageReferenceAssignment(BaseModel):
    assignmentId: str = Field(default_factory=lambda: str(uuid4()))
    assetId: str | None = None
    referenceId: str | None = None
    displayName: str
    semanticRole: str
    semanticRoles: list[str] = Field(default_factory=list)
    sourceType: str = "asset"
    characterId: str | None = None
    lockLevel: CharacterLockLevel = "PreserveCore"
    dominantColorHex: str | None = None
    notes: str | None = None


class ImageContinuityPackage(BaseModel):
    continuityId: str = Field(default_factory=lambda: str(uuid4()))
    characterLockLevel: CharacterLockLevel = "PreserveCore"
    continuityNotes: list[str] = Field(default_factory=list)
    protectedElements: list[str] = Field(default_factory=list)
    lockedReferenceIds: list[str] = Field(default_factory=list)
    figureColorMap: dict[str, str] = Field(default_factory=dict)


class PoseCraftControlPackage(BaseModel):
    controlId: str = Field(default_factory=lambda: str(uuid4()))
    source: str = "fixture"
    fixtureName: str = "posecraft_control_fixture.json"
    creatorModified: bool = False
    figures: list[dict[str, Any]] = Field(default_factory=list)
    camera: dict[str, Any] = Field(default_factory=dict)
    masks: list[dict[str, Any]] = Field(default_factory=list)
    honestyNote: str | None = None
    provenance: ProvenanceRecord = Field(default_factory=ProvenanceRecord)


class SpatialEnvironmentPackage(BaseModel):
    environmentId: str = Field(default_factory=lambda: str(uuid4()))
    source: str = "stub"
    mapId: str | None = None
    mapVersion: str | None = None
    environmentSummary: str = ""
    promptHints: list[str] = Field(default_factory=list)
    cameraAnchors: list[str] = Field(default_factory=list)
    referenceOnly: bool = False
    honestyNote: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceRecord = Field(default_factory=ProvenanceRecord)


class ImageControlPackage(BaseModel):
    controlId: str = Field(default_factory=lambda: str(uuid4()))
    stagingRecommendation: StagingRecommendation = "direct"
    projectPolicy: ProjectAutomationPolicy = "Ask"
    poseCraft: PoseCraftControlPackage | None = None
    spatialEnvironment: SpatialEnvironmentPackage | None = None
    continuity: ImageContinuityPackage | None = None
    honestyNotes: list[str] = Field(default_factory=list)


class ImageModelRoute(BaseModel):
    routeId: str = Field(default_factory=lambda: str(uuid4()))
    workflowKey: str
    modelFamily: str
    providerKind: str = "local"
    provider: str = "comfyui"
    deploymentTarget: str = "local"
    certified: bool = False
    requiresApproval: bool = False
    approvedForUse: bool = False
    approvalReason: str | None = None
    readiness: Literal["ready", "warning", "blocked"] = "ready"
    honestyNote: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class ImageGenerationPlan(BaseModel):
    planId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    request: ProductionImageRequest
    shotIntent: ImageShotIntent
    creativeDirection: CreativeDirectionPacket
    references: list[ImageReferenceAssignment] = Field(default_factory=list)
    continuity: ImageContinuityPackage | None = None
    controlPackage: ImageControlPackage
    modelRoute: ImageModelRoute
    stages: list[ImagePipelineStage] = Field(default_factory=list)
    approvalRequirements: list[ImageApprovalRequirement] = Field(default_factory=list)
    readiness: Literal["ready", "warning", "blocked"] = "warning"
    readinessReasons: list[str] = Field(default_factory=list)
    previewSummary: str = ""
    stageReceipts: list[StageReceipt] = Field(default_factory=list)
    provenance: ProvenanceRecord = Field(default_factory=ProvenanceRecord)


class EvaluationFinding(BaseModel):
    code: str
    status: EvaluationStatus
    message: str
    creatorImpact: str | None = None
    evidence: list[str] = Field(default_factory=list)


class ImageDefect(BaseModel):
    defectType: str
    severity: Literal["low", "medium", "high"] = "medium"
    description: str
    affectedArea: str | None = None
    suggestedFix: str | None = None


class ImageRepairInstruction(BaseModel):
    instructionId: str = Field(default_factory=lambda: str(uuid4()))
    action: str
    reason: str
    promptPatch: str | None = None
    keepWhatWorks: list[str] = Field(default_factory=list)
    avoidChanges: list[str] = Field(default_factory=list)
    blocked: bool = False
    honestyNote: str | None = None


class ImageCandidateEvaluation(BaseModel):
    candidateId: str
    overallStatus: EvaluationStatus = "not-evaluated"
    findings: list[EvaluationFinding] = Field(default_factory=list)
    defects: list[ImageDefect] = Field(default_factory=list)
    summary: str = ""
    recommendedNextStep: str | None = None
    honestyNotes: list[str] = Field(default_factory=list)


class ImageCandidate(BaseModel):
    candidateId: str = Field(default_factory=lambda: str(uuid4()))
    groupId: str
    projectId: str
    planId: str
    label: str
    status: CandidateStatus = "draft"
    jobId: str | None = None
    assetId: str | None = None
    parentCandidateId: str | None = None
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    previewText: str = ""
    explanation: str = ""
    evaluation: ImageCandidateEvaluation | None = None
    creatorSelected: bool = False
    provenance: ProvenanceRecord = Field(default_factory=ProvenanceRecord)


class ImageCandidateGroup(BaseModel):
    groupId: str = Field(default_factory=lambda: str(uuid4()))
    projectId: str
    planId: str
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    status: str = "draft"
    requestedCount: int = 1
    candidates: list[ImageCandidate] = Field(default_factory=list)
    recommendedCandidateId: str | None = None
    selectedCandidateId: str | None = None
    explanation: str | None = None
    stageReceipts: list[StageReceipt] = Field(default_factory=list)


class ImageMasteringRequest(BaseModel):
    candidateId: str
    requestedAction: Literal["resize", "upscale", "retouch"] = "resize"
    targetLongEdgePx: int | None = None
    approved: bool = False
    notes: str | None = None


class ImageMasteringResult(BaseModel):
    candidateId: str
    status: Literal["completed", "blocked", "not-run"] = "not-run"
    performedAction: str
    outputCandidateId: str | None = None
    outputAssetId: str | None = None
    disclosure: str
    postValidation: ImageCandidateEvaluation | None = None

