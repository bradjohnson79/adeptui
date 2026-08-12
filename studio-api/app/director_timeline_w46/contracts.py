"""Frozen M42 W46 Director Timeline Master shared contracts.

BatchBlock = stable production container (ID never changes when approved media changes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _nid(prefix: str = "") -> str:
    raw = uuid4().hex[:12]
    return f"{prefix}{raw}" if prefix else raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


ModalityMode = Literal["image_planning", "video_finishing"]
PromptStrategy = Literal["native", "compiled", "split"]
BatchStatus = Literal[
    "Draft",
    "Ready",
    "Queued",
    "Generating",
    "Failed",
    "Cancelled",
    "CandidateReady",
    "Approved",
    "ApprovedConfigurationChanged",
    "RegenerationRecommended",
]
CancelAction = Literal[
    "cancel_pending_batch",
    "cancel_active_local_job",
    "request_hosted_cancellation",
    "stop_remaining_scene_jobs",
    "preserve_completed_batches",
    "resume_incomplete_only",
]
HostedCancelSupport = Literal["supported", "unsupported", "unknown"]
RepairOverlapPolicy = Literal["block", "merge", "stack_advanced"]
InPaintStrategy = Literal[
    "native",
    "keyframe_repair",
    "range_replacement",
    "frame_repair_propagation",
    "complete_batch_retake",
]
OrchestratorMode = Literal[
    "parallel",
    "sequential_continuity",
    "ordered_groups",
    "director_managed",
]
CapabilityLabel = Literal[
    "Certified",
    "Testing",
    "Available",
    "Unavailable",
    "Unsupported",
    "Requires Setup",
    "Loading",
    "Error",
]
AnchorKind = Literal["image", "video", "end_frame"]
RetakeMode = Literal["fast", "directed", "reference", "cross_model", "range"]


class DurationState(BaseModel):
    """Structural timing vs media timing — never a single overloaded duration."""

    plannedDuration: float = 5.0
    generatedDuration: Optional[float] = None
    timelineVisibleDuration: Optional[float] = None
    sourceMediaDuration: Optional[float] = None


class TimelineVisualAnchor(BaseModel):
    id: str = Field(default_factory=lambda: _nid("anc_"))
    kind: AnchorKind = "image"
    assetId: Optional[str] = None
    label: str = ""
    atTime: float = 0.0
    strength: float = 1.0


class TimelinePromptSegment(BaseModel):
    id: str = Field(default_factory=lambda: _nid("ps_"))
    start: float = 0.0
    length: float = 2.0
    text: str = ""
    role: str = "primary"
    strength: float = 1.0
    negativePrompt: Optional[str] = None
    anchorIds: list[str] = Field(default_factory=list)
    executionStrategy: PromptStrategy = "compiled"
    versionId: str = Field(default_factory=lambda: _nid("psv_"))
    legacyPromptSegmentId: Optional[str] = None


class ExecutionSnapshot(BaseModel):
    """Immutable record of what produced a candidate. Never mutated after create."""

    id: str = Field(default_factory=lambda: _nid("snap_"))
    batchBlockId: str
    createdAt: str = Field(default_factory=_now)
    immutable: Literal[True] = True
    compiledPrompts: dict[str, Any] = Field(default_factory=dict)
    promptLayerVersionIds: list[str] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    selectedGenerator: Optional[str] = None
    capabilityStrategy: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)
    runtime: Optional[str] = None
    providerId: Optional[str] = None
    duration: DurationState = Field(default_factory=DurationState)
    sourceAnchors: list[dict[str, Any]] = Field(default_factory=list)
    continuityState: dict[str, Any] = Field(default_factory=dict)
    inPaintStrategy: Optional[InPaintStrategy] = None
    # Prompt Intelligence record frozen at generation time (never rewritten on preference change).
    promptIntelligence: Optional[dict[str, Any]] = None


class GenerationJobRef(BaseModel):
    id: str = Field(default_factory=lambda: _nid("job_"))
    executionSnapshotId: str
    queueJobId: Optional[str] = None
    providerJobId: Optional[str] = None
    generatorId: Optional[str] = None
    status: str = "pending"
    locality: Literal["local", "hosted"] = "local"
    hostedCancelSupport: HostedCancelSupport = "unknown"
    apiUsed: Optional[bool] = None
    progress: float = 0.0
    error: Optional[str] = None
    createdAt: str = Field(default_factory=_now)


class CandidateVersion(BaseModel):
    id: str = Field(default_factory=lambda: _nid("cand_"))
    executionSnapshotId: str
    assetId: Optional[str] = None
    label: str = ""
    generatedDuration: Optional[float] = None
    createdAt: str = Field(default_factory=_now)
    approved: bool = False


class RepairRange(BaseModel):
    id: str = Field(default_factory=lambda: _nid("rr_"))
    start: float = 0.0
    length: float = 1.0
    mode: RetakeMode = "range"
    inPaintStrategy: InPaintStrategy = "range_replacement"
    metadata: dict[str, Any] = Field(default_factory=dict)
    layer: int = 0
    status: str = "draft"
    executionSnapshotId: Optional[str] = None
    candidateId: Optional[str] = None
    label: str = ""


class ApprovedClip(BaseModel):
    assetId: str
    executionSnapshotId: str
    candidateId: Optional[str] = None
    approvedAt: str = Field(default_factory=_now)
    playable: bool = True


class BatchClip(BaseModel):
    """A clip owned by a BatchBlock. Stable unique ID; never re-keyed on reorder.

    Batches own their clips directly so adding media to one batch can never
    mutate or delete another batch's clips (BATCH_OWNED_CLIPS). The legacy
    scene-global tracks remain as a derived/flattened view for NLE rendering.
    """

    id: str = Field(default_factory=lambda: _nid("clip_"))
    kind: Literal["image", "video", "audio", "sfx", "camera"] = "image"
    assetId: Optional[str] = None
    start: float = 0.0
    length: float = 5.0
    trimStart: float = 0.0
    label: str = ""
    role: Optional[str] = None  # e.g. image "start"/"middle"/"end"/"guide"
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    # Camera-specific fields (ignored for non-camera kinds)
    motion_type: Optional[str] = None
    rig: Optional[str] = None
    # Migration metadata: when this clip was migrated from a legacy scene-global
    # clip, the original legacy clip ID is preserved here for audit/reversibility.
    legacyClipId: Optional[str] = None


class BatchBlock(BaseModel):
    """Stable production container — ID never changes when approved media changes.

    BATCH_OWNED_CLIPS: each batch owns its visualClips/audioClips/sfxClips/
    cameraInstructions directly. batchBlockId is immutable identity; `order`
    is mutable presentation/execution order. Reordering must never rewrite IDs
    or break lineage.
    """

    id: str = Field(default_factory=lambda: _nid("bb_"))
    sceneId: str
    order: int = 0
    label: str = "Batch"
    status: BatchStatus = "Draft"
    generatorId: Optional[str] = None
    generatorOverride: bool = False
    duration: DurationState = Field(default_factory=DurationState)
    sourceAnchors: list[TimelineVisualAnchor] = Field(default_factory=list)
    promptSegments: list[TimelinePromptSegment] = Field(default_factory=list)
    # Per-batch owned clips (BATCH_OWNED_CLIPS). Stable IDs; order is by `order`.
    visualClips: list[BatchClip] = Field(default_factory=list)
    audioClips: list[BatchClip] = Field(default_factory=list)
    sfxClips: list[BatchClip] = Field(default_factory=list)
    cameraInstructions: list[BatchClip] = Field(default_factory=list)
    generationJobs: list[GenerationJobRef] = Field(default_factory=list)
    candidateVersions: list[CandidateVersion] = Field(default_factory=list)
    approvedClip: Optional[ApprovedClip] = None
    repairRanges: list[RepairRange] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    configFingerprint: Optional[str] = None
    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)
    legacyImageClipIds: list[str] = Field(default_factory=list)
    # Migration audit metadata: records how legacy scene-global clips were
    # assigned to batches so migration is traceable and reversible.
    migrationMetadata: dict[str, Any] = Field(default_factory=dict)
    # SEQUENTIAL_SUBMISSION_CHAIN: when a sequential Generate Scene stages this
    # batch for later submission, the pre-created immutable snapshot id lives
    # here until the provider slot frees. Cleared on submission.
    pendingSnapshotId: Optional[str] = None


class SceneTimelineMaster(BaseModel):
    version: int = 1
    mode: ModalityMode = "image_planning"
    sceneGeneratorId: Optional[str] = None
    orchestratorMode: OrchestratorMode = "sequential_continuity"
    repairOverlapPolicy: RepairOverlapPolicy = "block"
    preflightMode: Literal["off", "warnings_only", "strict"] = "warnings_only"
    batchBlocks: list[BatchBlock] = Field(default_factory=list)
    executionSnapshots: dict[str, ExecutionSnapshot] = Field(default_factory=dict)
    # Creator-acknowledged terminal failures: the Preview Monitor failed overlay
    # is suppressed for these job ids (job rows and batch status are untouched —
    # history stays honest; a NEW failure with a different id re-shows the overlay).
    dismissedFailureJobIds: list[str] = Field(default_factory=list)
    migratedFromDirectorJson: bool = False
    migrationNote: Optional[str] = None


class CancelRequest(BaseModel):
    action: CancelAction
    batchBlockIds: list[str] = Field(default_factory=list)
    sceneId: Optional[str] = None


class CancelResult(BaseModel):
    ok: bool
    action: CancelAction
    affectedBatchIds: list[str] = Field(default_factory=list)
    preservedCompletedBatchIds: list[str] = Field(default_factory=list)
    hostedCancelSupport: HostedCancelSupport = "unknown"
    message: str = ""
    mock: bool = False


class RepairOverlapDecision(BaseModel):
    ok: bool
    policy: RepairOverlapPolicy
    blocked: bool = False
    merged: bool = False
    stacked: bool = False
    message: str = ""
    ranges: list[RepairRange] = Field(default_factory=list)


class GeneratorCapability(BaseModel):
    id: str
    label: str
    locality: Literal["local", "hosted"]
    providerId: Optional[str] = None
    capabilityLabel: CapabilityLabel = "Available"
    maxDurationSec: Optional[float] = None
    supportsStartEndFrame: bool = False
    supportsContinuation: bool = False
    inPaintStrategies: list[InPaintStrategy] = Field(default_factory=list)
    supportsAudio: bool = False
    executable: bool = False
    notes: str = ""
    # PROVIDER_CAPABILITY_GATING: Timeline UI enables/disables operations based
    # on these flags rather than hardcoding provider names. WAN/Hunyuan report
    # supportsTimelineGeneration=False until a Timeline adapter is registered.
    supportsTimelineGeneration: bool = True
    supportsImageToVideo: bool = True
    supportsBatchOrchestration: bool = True
    supportsInterrupt: bool = True
    supportsRetake: bool = True
    supportsGenerationPreview: bool = True


class PreflightFinding(BaseModel):
    id: str = Field(default_factory=lambda: _nid("pf_"))
    severity: Literal["info", "warning", "error"] = "warning"
    code: str
    message: str
    batchBlockId: Optional[str] = None
    fixProposal: Optional[str] = None


# Gate flag names required for directorTimelineGo (plus dock prereq stamps).
REQUIRED_GATE_FLAGS: tuple[str, ...] = (
    # W46 core (BatchBlock / orchestrator)
    "sharedContractsFrozen",
    "batchBlockIdentityStable",
    "durationStateSeparationPassed",
    "executionSnapshotPassed",
    "immutableProvenancePassed",
    "batchInvalidationPassed",
    "repairOverlapPolicyPassed",
    "sceneCancelResumePassed",
    "migrationIdempotentPassed",
    "promptSegmentsPersisted",
    "capabilityRegistryHonest",
    "assemblyProvenancePassed",
    "retakeLineagePassed",
    "inPaintStrategyDisclosed",
    "razorMultiRangePassed",
    "continuityFindingsOnly",
    "timelineToolsApprovalGated",
    "dualModeUxOperational",
    "playwrightSuitePassed",
    "primaryE2ePassed",
    "attributionPresent",
    "dockerDeferredToW47",
    # W46 addenda — Shell UX (SA26–SA28)
    "timelineMonitorResizePassed",
    "timelineMonitorPersistencePassed",
    "timelineViewportLayoutPassed",
    "timelineTrackStylingPassed",
    "timelineMasterStylingPassed",
    "timelineToolbarReorganizationPassed",
    "timelineContextHelpPassed",
    "timelineTooltipAccessibilityPassed",
    "timelineDockCollisionPassed",
    "timelineResponsivePassed",
    # W46 addenda — Core interaction (SA38–SA43)
    "timelinePlayheadPassed",
    "timelineScrubbingPassed",
    "timelinePlaybackSyncPassed",
    "timelineTrueEmptyTracksPassed",
    "timelineMediaThumbnailPassed",
    "timelinePromptOnImagePassed",
    "timelineGuidancePriorityPassed",
    "timelineSettingsPassed",
    "timelineItemDeletePassed",
    "timelineDeleteUndoPassed",
    "timelineOptionalReferencesPassed",
    "timelineReferenceNonBlockingPassed",
    "timelineAssetNamingPassed",
    "timelineAssetActionClarityPassed",
    "timelineCoDirectorRefinementPassed",
    "timelineSimplicityReviewPassed",
    # W46 addenda — Co-Director E2E (SA29–SA37)
    "codirectorTimelineContextPassed",
    "codirectorTimelineReadToolsPassed",
    "codirectorTimelineMutationGatewayPassed",
    "codirectorTimelineApprovalPassed",
    "codirectorTimelineRevisionSafetyPassed",
    "codirectorTimelineBatchToolsPassed",
    "codirectorTimelinePromptAnchorToolsPassed",
    "codirectorTimelineReferenceToolsPassed",
    "codirectorTimelinePreflightPassed",
    "codirectorTimelineGenerationPassed",
    "codirectorTimelineRetakePassed",
    "codirectorTimelineRazorPassed",
    "codirectorTimelineMultiRangeRepairPassed",
    "codirectorTimelineInpaintPassed",
    "codirectorTimelineBackgroundRepairPassed",
    "codirectorTimelineContinuityPassed",
    "codirectorTimelineUiSyncPassed",
    "codirectorTimelineReceiptsPassed",
    "codirectorTimelineSecurityPassed",
    "codirectorTimelinePlaywrightPassed",
    "codirectorTimelinePrimaryE2EPassed",
    # W46 Timeline UX Rebuild (SA44–SA55) — evidence under artifacts/m42/w46/timeline-ux/
    # (unique names; overlapping addenda flags are re-bound to rebuild artifacts in production_gate)
    "timelineUxArchitecturePassed",
    "timelineProfessionalLayoutPassed",
    "timelineViewerResizePassed",
    "timelineToolbarCompletePassed",
    "timelineButtonsVisiblePassed",
    "timelineProfessionalTrackRendererPassed",
    "timelineScenePromptClarityPassed",
    "timelineTimedInstructionClarityPassed",
    "timelineContextInspectorPassed",
    "timelineSceneNavigationPassed",
    "timelineAssetClarityPassed",
    "timelineGuidanceConsumptionPassed",
    "timelineQueueSimplificationPassed",
    "timelineCoDirectorUiSyncPassed",
    "timelineBeginnerUxPassed",
    "timelineVisualReviewPassed",
    "timelineAccessibilityReviewPassed",
    "timelineMockupParityPassed",
    # W46 Final Addenda SA56–SA78 — evidence under timeline-camera / timeline-viewer / timeline-lipsync-inpaint
    "timelineCameraMotionCatalogPassed",
    "timelineCameraRigCatalogPassed",
    "timelineCameraCapabilityMappingPassed",
    "timelineCameraDropdownUxPassed",
    "timelineCameraPersistencePassed",
    "timelineCameraCoDirectorPassed",
    "timelineFullHeightViewportPassed",
    "timelineBottomGapRemovedPassed",
    "timelineViewportResizePassed",
    "timelineGeneratorBannerPassed",
    "timelineGeneratorBannerReducedMotionPassed",
    "timelineTrackLabelContrastPassed",
    "timelineTrackHeaderReadabilityPassed",
    "timelineTrackLabelsNightPassed",
    "timelineTrackLabelsDayPassed",
    "timelineViewerDominancePassed",
    "timelineViewerLargeDefaultPassed",
    "timelineViewerPresetsPassed",
    "timelineViewerFullscreenPassed",
    "timelineTrackRailCompactPassed",
    "timelineTrackInternalScrollPassed",
    "timelineCenterPageNoScrollPassed",
    "timelineViewerCanvasScalingPassed",
    "timelineDockResponsiveHeightPassed",
    "timelineViewerLayoutPersistencePassed",
    "timelineCoDirectorLayoutPassed",
    "timelineDefaultLipSyncTrackPassed",
    "timelineAdditionalLipSyncTrackPassed",
    "timelineLipSyncClipPassed",
    "timelineLipSyncAudioBindingPassed",
    "timelineLipSyncPersistencePassed",
    "timelineLipSyncToolbarPassed",
    "timelineInpaintVideoFinishingOnlyPassed",
    "timelineInpaintEligibilityPassed",
    "timelineInpaintWorkspacePassed",
    "timelineInpaintMaskPassed",
    "timelineInpaintTrackingPassed",
    "timelineInpaintStrategyDisclosurePassed",
    "timelineInpaintExecutionPassed",
    "timelineInpaintAudioPreservationPassed",
    "timelineInpaintVersionLineagePassed",
    "timelineLipSyncInpaintCoDirectorPassed",
    "timelineLipSyncInpaintAccessibilityPassed",
    "timelineLipSyncInpaintPlaywrightPassed",
    "timelineZoomControlsPassed",
    "timelineToolbarWiringPassed",
    "timelinePlaywrightOperationalPassed",
)

DOCK_PREREQ_FLAGS: tuple[str, ...] = (
    "dockSingleRowPassed",
    "dockNoWrap1280Passed",
    "dockNoWrap1920Passed",
    "dockTimelineCollisionPassed",
)
