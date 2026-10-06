"""Frozen M42 W46 Director Timeline Master shared contracts.

BatchBlock = stable production container (ID never changes when approved media changes).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ..codirector.video_intelligence.contracts import (
    CoDirectorContinuityPolicy,
    TemporalContinuityPacket,
)
from ..director_timeline_bindings import PromptNameBinding


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
    "NeedsDialogueRetake",
    # P6 hygiene: Omni infra miss — keep asset; retry QC only (never retake).
    "QC_Pending",
    "QC_RetryRequired",
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
ContinuityStrategy = Literal[
    "native_tail",
    "native_extend",
    "multi_frame",
    "last_frame_i2v",
    "prompt_context",
    "none",
]
ContinuityBridgeStatus = Literal[
    "Waiting",
    "Analyzing",
    "Ready",
    "Applied",
    "Failed",
    "Superseded",
]
CURRENT_CONTINUITY_CONTEXT_VERSION = 1


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
    referenceBindingIds: list[str] = Field(default_factory=list)
    referenceNameBindings: list[PromptNameBinding] = Field(default_factory=list)
    # Production-orchestrator provenance: creator original direction and exact
    # dialogue preserved beside the refined production prompt (mission Part 14).
    userDirection: Optional[str] = None
    productionPrompt: Optional[str] = None
    dialogue: Optional[str] = None
    movementSegmentRef: Optional[dict[str, Any]] = None
    movementSegmentRevision: Optional[int] = None
    temperature: float = 1.0


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
    progressGrounded: bool = False
    phase: Optional[str] = None
    phaseLabel: Optional[str] = None
    lastProgressAt: Optional[str] = None
    lastRuntimeEventAt: Optional[str] = None
    elapsedActiveTime: Optional[float] = None
    stalled: bool = False
    currentNode: Optional[str] = None
    error: Optional[str] = None
    createdAt: str = Field(default_factory=_now)
    sceneTakeId: Optional[str] = None
    candidateId: Optional[str] = None
    sceneTakeId: Optional[str] = None
    candidateId: Optional[str] = None


class CandidateVersion(BaseModel):
    id: str = Field(default_factory=lambda: _nid("cand_"))
    executionSnapshotId: str
    assetId: Optional[str] = None
    label: str = ""
    generatedDuration: Optional[float] = None
    createdAt: str = Field(default_factory=_now)
    approved: bool = False
    takeId: str = Field(default_factory=lambda: _nid("take_"))
    parentTakeId: Optional[str] = None
    incomingBridgeId: Optional[str] = None
    continuityAware: bool = False
    reTakeReason: Optional[str] = None
    # Structured Re-Take memory — never collapse into one opaque prompt.
    sequenceMemory: dict[str, Any] = Field(default_factory=dict)
    incomingContinuity: dict[str, Any] = Field(default_factory=dict)
    originalTakeIntent: dict[str, Any] = Field(default_factory=dict)
    takeState: dict[str, Any] = Field(default_factory=dict)
    userCorrection: dict[str, Any] = Field(default_factory=dict)


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
    muted: bool = False
    fade_in: float = 0.0
    fade_out: float = 0.0
    # Camera-specific fields (ignored for non-camera kinds)
    motion_type: Optional[str] = None
    motion_id: Optional[str] = None
    rig: Optional[str] = None
    shot_id: Optional[str] = None
    lens_id: Optional[str] = None
    focus_id: Optional[str] = None
    focus_name: Optional[str] = None
    lighting_id: Optional[str] = None
    text: str = ""
    speed: Optional[float] = None
    distance: Optional[float] = None
    ease: Optional[str] = None
    shake: Optional[float] = None
    intensity: Optional[float] = None
    subject_lock: Optional[float] = None
    # Camera parity with legacy CameraClip: reference bindings + custom labels
    # read by reference_compile (camera leg) and camera_catalog
    # (describe_camera_clip / detect_camera_contradictions) via getattr.
    reference_binding_ids: list[str] = Field(default_factory=list)
    custom_motion_label: Optional[str] = None
    custom_rig_label: Optional[str] = None
    execution_strategy: Optional[str] = None
    # Migration metadata: when this clip was migrated from a legacy scene-global
    # clip, the original legacy clip ID is preserved here for audit/reversibility.
    legacyClipId: Optional[str] = None
    # Generation retake / range metadata (A|Middle|B role, markIn/markOut,
    # priorTrimStart, retakeId, replacementAssetId, referenceImageAssetId,
    # sourceBatchId/sourceAssetId). Mirrors the FE BatchClip contract, which
    # already declares this pass-through field.
    metadata: Optional[dict[str, Any]] = None


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
    # Creator removed this exact video from the Visual lane. The Library asset
    # and the take stay. Placement skips this asset until a new one is deposited.
    dismissedVisualAssetId: Optional[str] = None
    audioClips: list[BatchClip] = Field(default_factory=list)
    sfxClips: list[BatchClip] = Field(default_factory=list)
    cameraInstructions: list[BatchClip] = Field(default_factory=list)
    generationJobs: list[GenerationJobRef] = Field(default_factory=list)
    candidateVersions: list[CandidateVersion] = Field(default_factory=list)
    approvedClip: Optional[ApprovedClip] = None
    repairRanges: list[RepairRange] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    speechWindows: list[dict[str, Any]] = Field(default_factory=list)
    # Co-Director Dialogue Authority: sole dialogue authority for generate/QC/retake.
    dialogueManifest: Optional[dict[str, Any]] = None
    # Shared LoRA registry selection applied to this batch's generations
    # ({loraId, name, strength}). None = no LoRA (baseline behavior).
    lora: Optional[dict[str, Any]] = None
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
    # Continuity-aware take lineage (BatchBlock remains the stable container).
    activeTakeId: Optional[str] = None
    incomingBridgeId: Optional[str] = None
    # Latest generated take (may be unapproved). Retake/range use this, not approvedClip.
    currentTakeId: Optional[str] = None
    currentTakeAssetId: Optional[str] = None
    continuityAwareRetake: bool = False
    # MiniMax H3 megapixel resolution control. None/absent = Auto (back-compat).
    # Shape: {"mode": "auto" | "manual", "megapixels": float}.
    # Width/height are never stored; always derived from the canonical grid.
    h3Resolution: Optional[dict[str, Any]] = None
    # LTX 2.5 Timeline QUALITY tier. None/absent = 720p (adapter finalResolution).
    # Canonical values: "720p" | "1080p" | "2K" | "4K". Independent of h3Resolution.
    # Native 4K is UNAVAILABLE - request_builder must fail honestly, never fake.
    ltxQuality: Optional[str] = None
    # Seedance fal resolution. None = 720p. Values: 480p, 720p, 1080p, 4k.
    # A product that does not offer a tier refuses it instead of substituting.
    seedanceResolution: Optional[str] = None
    downstreamStale: bool = False
    staleFromTakeId: Optional[str] = None


class ContinuityPolicy(BaseModel):
    """Creator-facing Extend / Auto Continuity policy for a scene.

    Extend is the Adept UI capability. ContinuityBridge is the internal handoff.
    Local: autoContinuity locked on, configuredTailDuration=5.
    API: autoContinuity default off; configuredTailDuration in {0, 3, 5}.
    """

    autoContinuity: bool = False
    configuredTailDuration: float = 0.0
    locality: Literal["local", "api"] = "local"
    continuityAwareRetake: bool = False


class ContinuityBridge(BaseModel):
    """Internal Timeline handoff. Not an Extend track.

    Generic enough for future Extend surfaces (1 Frame / 3 Frame / Timeline Generator)
    without coupling those UIs to Timeline.
    """

    bridgeId: str = Field(default_factory=lambda: _nid("cbr_"))
    sceneId: str = ""
    sourceBatchId: str = ""
    targetBatchId: str = ""
    sourceTakeId: Optional[str] = None
    contextVersion: int = CURRENT_CONTINUITY_CONTEXT_VERSION
    configuredTailDuration: float = 5.0
    effectiveTailDuration: float = 5.0
    tailAssetId: Optional[str] = None
    lastFrameAssetId: Optional[str] = None
    continuityStrategy: ContinuityStrategy = "none"
    continuityModel: Optional[str] = None
    continuityState: dict[str, Any] = Field(default_factory=dict)
    status: ContinuityBridgeStatus = "Waiting"
    createdAt: str = Field(default_factory=_now)
    supersededAt: Optional[str] = None
    error: Optional[str] = None


class LongFormCharacterState(BaseModel):
    characterId: Optional[str] = None
    crsAssetId: Optional[str] = None
    label: str = ""
    appearanceState: str = ""
    wardrobeState: str = ""
    position: str = ""
    poseAction: str = ""


class LongFormPropState(BaseModel):
    prsAssetId: Optional[str] = None
    label: str = ""
    holder: str = ""
    location: str = ""
    state: str = ""


class LongFormContinuityState(BaseModel):
    """Compiled long-form continuation state. Not a second Media Intelligence authority.

    Distilled from MediaIntelligencePacket + TemporalContinuityPacket + CRS/ERS/PRS.
    Schema name is long-form-continuity-v1 (creator report: Continuity Packet).
    """

    schemaVersion: str = "long-form-continuity-v1"
    revision: int = 1
    projectId: str = ""
    sceneId: str = ""
    mediaIntelligencePacketId: Optional[str] = None
    temporalPacketId: Optional[str] = None
    characters: list[LongFormCharacterState] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    props: list[LongFormPropState] = Field(default_factory=list)
    camera: dict[str, Any] = Field(default_factory=dict)
    motion: dict[str, Any] = Field(default_factory=dict)
    dialogue: dict[str, Any] = Field(default_factory=dict)
    audio: dict[str, Any] = Field(default_factory=dict)
    endingAnchors: list[dict[str, Any]] = Field(default_factory=list)
    storyState: str = ""
    nextIntent: str = ""
    scores: dict[str, Any] = Field(default_factory=dict)
    stale: bool = False
    staleFromSegmentId: Optional[str] = None
    createdAt: str = Field(default_factory=_now)
    updatedAt: str = Field(default_factory=_now)


class ExtendSegment(BaseModel):
    """One H3 continuation segment. The creator still sees one Timeline scene."""

    segmentId: str = Field(default_factory=lambda: _nid("ext_"))
    batchBlockId: Optional[str] = None
    prompt: str = ""
    compiledPrompt: str = ""
    continuityRevision: int = 0
    inputAnchors: list[str] = Field(default_factory=list)
    referenceAssetIds: list[str] = Field(default_factory=list)
    h3Mode: Literal["i2v", "r2v"] = "r2v"
    durationSec: float = 5.0
    executionId: Optional[str] = None
    outputAssetId: Optional[str] = None
    takeAAssetId: Optional[str] = None
    takeBAssetId: Optional[str] = None
    approvedTake: Optional[Literal["A", "B"]] = None
    status: Literal["planned", "generating", "draft", "approved", "failed", "cancelled"] = "planned"
    createdAt: str = Field(default_factory=_now)




class FinalCheckFinding(BaseModel):
    """One Final Check finding. Dialogue Authority owns dialogue/language/speaker classifiers."""

    category: str
    taxonomy: Optional[Literal["Hard", "Soft", "Creative"]] = None
    code: Optional[str] = None
    severity: Optional[str] = None
    retakeEligible: bool = False
    autoDestroy: bool = False
    acceptanceEligible: bool = False
    creativeTaste: bool = False
    authoritySource: Optional[str] = None
    confidence: Optional[Literal["high", "low"]] = None
    message: Optional[str] = None
    source: Optional[str] = None
    finalCheck: Optional[dict[str, Any]] = None


class FinalCheckCategoryResult(BaseModel):
    category: str
    status: Literal["pass", "fail", "not_run", "uncertain"] = "not_run"
    taxonomy: Optional[Literal["Hard", "Soft", "Creative"]] = None
    findings: list[FinalCheckFinding] = Field(default_factory=list)
    source: Optional[str] = None
    note: Optional[str] = None


class SceneFinalCheckRepairGate(BaseModel):
    runtimeKind: Literal["local", "api"] = "local"
    permission: Literal["not_required", "required", "granted", "declined", "keep_current"] = "not_required"
    apiCallCount: int = 0
    requiresApproval: bool = False
    actions: list[str] = Field(default_factory=list)
    oneApprovalPerCycle: bool = False
    decision: Optional[str] = None
    apiCallsDelta: int = 0
    lifecycleStatus: Optional[str] = None
    creatorVerdict: Optional[str] = None
    note: Optional[str] = None
    reuse: Optional[str] = None


class SceneFinalCheck(BaseModel):
    """Persisted Final Check state on the scene master (reload keeps truth)."""

    lifecycleStatus: str = "FINAL_CHECK"
    creatorVerdict: Optional[str] = None
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None
    categories: list[FinalCheckCategoryResult] = Field(default_factory=list)
    repairGate: Optional[SceneFinalCheckRepairGate] = None
    stitchAssetId: Optional[str] = None
    retakeLoopCount: int = 0
    maxRetakeLoops: int = 3
    unresolvedBlocking: bool = False
    autoRepairEligibleCount: int = 0
    retakePack: Optional[dict[str, Any]] = None
    policy: Optional[str] = "RETAKE_QUALIFICATION_POLICY"

class SceneStitch(BaseModel):
    """One previewable join of approved batch takes. Source batches stay editable."""

    assetId: str
    sourceBatchIds: list[str] = Field(default_factory=list)
    sourceAssetIds: list[str] = Field(default_factory=list)
    incremental: bool = False
    durationSec: Optional[float] = None
    createdAt: str = Field(default_factory=_now)



class ScenePublishState(BaseModel):
    """Library Video Published Master provenance on the scene master (additive)."""

    publishedAssetId: str = ""
    publishedAt: str = ""
    sourceSceneStitchAssetId: str = ""
    lifecycleStatusSnapshot: str = ""
    creatorVerdictSnapshot: Optional[str] = None
    acceptedIssues: bool = False
    contentFingerprint: str = ""
    version: int = 0
    upscaledAssetId: Optional[str] = None
    publishSource: str = "stitch"
    upscalePendingPublish: bool = False
    # Whole-scene Take lineage (Publish the CURRENT take only).
    takeId: Optional[str] = None
    takeLabel: Optional[str] = None
    batchIds: list[str] = Field(default_factory=list)


SceneTakeStatus = Literal["ready", "rendering", "cancelled", "incomplete"]


class SceneTakeBatchMember(BaseModel):
    """One batch's rendered membership inside a whole-scene Take."""

    batchId: str
    order: int = 0
    assetId: Optional[str] = None
    candidateId: Optional[str] = None
    batchTakeId: Optional[str] = None
    durationSec: Optional[float] = None
    status: str = "pending"


class SceneTakeQuality(BaseModel):
    """Frozen quality of the Take at launch — never overwritten by later scene settings."""

    generatorId: Optional[str] = None
    h3Mode: Optional[str] = None
    h3Megapixels: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ltxQuality: Optional[str] = None
    seedanceResolution: Optional[str] = None
    durationSec: Optional[float] = None
    batchCount: int = 0


class SceneTake(BaseModel):
    """Whole-scene Take: one complete multi-batch render of the scene."""

    id: str = Field(default_factory=lambda: _nid("stk_"))
    label: str = "A"
    letterIndex: int = 1
    status: SceneTakeStatus = "ready"
    createdAt: str = Field(default_factory=_now)
    completedAt: Optional[str] = None
    generationSnapshot: dict[str, Any] = Field(default_factory=dict)
    quality: SceneTakeQuality = Field(default_factory=SceneTakeQuality)
    batches: list[SceneTakeBatchMember] = Field(default_factory=list)
    resultAssetId: Optional[str] = None
    publishedAssetId: Optional[str] = None
    retakeIds: list[str] = Field(default_factory=list)


class SceneTimelineMaster(BaseModel):
    version: int = 1
    # Spoken-language authority for this scene (never UI locale).
    sceneLanguage: Optional[str] = None
    spokenLanguage: Optional[dict[str, Any]] = None
    mode: ModalityMode = "image_planning"
    sceneGeneratorId: Optional[str] = None
    turboLora: bool = False
    orchestratorMode: OrchestratorMode = "sequential_continuity"
    repairOverlapPolicy: RepairOverlapPolicy = "block"
    preflightMode: Literal["off", "warnings_only", "strict"] = "warnings_only"
    batchBlocks: list[BatchBlock] = Field(default_factory=list)
    executionSnapshots: dict[str, ExecutionSnapshot] = Field(default_factory=dict)
    # Creator-acknowledged terminal failures: the Preview Monitor failed overlay
    # is suppressed for these job ids (job rows and batch status are untouched —
    # history stays honest; a NEW failure with a different id re-shows the overlay).
    dismissedFailureJobIds: list[str] = Field(default_factory=list)
    continuityPolicy: ContinuityPolicy = Field(default_factory=ContinuityPolicy)
    continuityBridges: list[ContinuityBridge] = Field(default_factory=list)
    coDirectorContinuityPolicy: CoDirectorContinuityPolicy = Field(default_factory=CoDirectorContinuityPolicy)
    temporalPackets: list[TemporalContinuityPacket] = Field(default_factory=list)
    # Accumulated Co-Director scene digest across approved shots (not a second authority).
    coDirectorRollingSceneDigest: Optional[dict[str, Any]] = None
    migratedFromDirectorJson: bool = False
    migrationNote: Optional[str] = None
    # Migration-Completion Marker Law: one-shot legacy→Master migrate is
    # idempotent and one-way. Once set, loads must never re-import legacy
    # prompt_segments / clip arrays even if those keys remain on disk.
    migration: Optional[dict[str, Any]] = None
    # Additive scene-level join of approved batch takes. Never deletes batches.
    sceneStitch: Optional[SceneStitch] = None
    # Co-Director Final Check (lifecycle + category shell). Additive; reload-safe.
    sceneFinalCheck: Optional[SceneFinalCheck] = None
    # Explicit Video Published Master (never auto-set from stitch/pass).
    scenePublish: Optional[ScenePublishState] = None
    # Long-form Review & Extend (compiled Continuity Packet + segment ledger).
    longFormContinuity: Optional[LongFormContinuityState] = None
    extendSegments: list[ExtendSegment] = Field(default_factory=list)
    lastMediaIntelligencePacketId: Optional[str] = None
    # Process that explicitly started the current render chain.
    # A different Studio API session must not continue it.
    renderSessionId: Optional[str] = None
    # Whole-scene Takes (scene render history). Not per-batch candidates.
    sceneTakes: list[SceneTake] = Field(default_factory=list)
    currentSceneTakeId: Optional[str] = None
    activeSceneTakeId: Optional[str] = None


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
    cancelledJobIds: list[str] = Field(default_factory=list)
    cancelledTakeId: Optional[str] = None
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
    qualityControl: Optional[str] = None
    executable: bool = False
    notes: str = ""
    # PROVIDER_CAPABILITY_GATING: Timeline UI enables/disables operations based
    # on these flags rather than hardcoding provider names. Retired local
    # generators are not products and must not appear as Timeline rows.
    supportsTimelineGeneration: bool = True
    supportsImageToVideo: bool = True
    # R2V (MiniMax H3 Timeline etc.): Visual image-frame / CRS refs are valid
    # without classic start-frame I2V. Predicates must check this flag — do not
    # treat supportsImageToVideo=False as "text-to-video only".
    supportsReferenceToVideo: bool = False
    # HONESTY: True T2V (no start frame). Local MiniMax H3 Timeline and LTX 2.5
    # are R2V/I2V → False. Surfaced to UI dropdowns so the Txt2Vid surface does not
    # offer R2V/I2V engines as true Text-to-Video production paths.
    supportsTextToVideo: bool = False
    requiresLastFrame: bool = False
    supportsBatchOrchestration: bool = True
    supportsInterrupt: bool = False
    supportsRetake: bool = True
    supportsGenerationPreview: bool = False
    draftPathway: str = "none"
    supportsQueuedCancel: bool = False
    supportsRunningCancel: bool = False
    supportsLivePreview: bool = False
    supportsHonestProgress: bool = False
    supportsIntermediateFrames: bool = False
    remoteCancelCostNote: Optional[str] = None
    finalRequiresNewGeneration: bool = True
    draftResolution: Optional[str] = None
    finalResolution: Optional[str] = None
    supportsVideoReferences: bool = False
    supportsImageAndVideoTogether: bool = False
    maximumReferenceVideos: int = 0
    supportedAspectRatios: list[str] = Field(default_factory=list)
    readiness: str = ""
    disabledReason: str = ""
    timelineAdapterId: Optional[str] = None
    supportsTurboLora: bool = False
    usesFastQuality: bool = False
    # Per-surface CREATE truth. Timeline adapter flags must not strip this.
    workflowCapabilities: Optional[dict[str, dict[str, Any]]] = None


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
