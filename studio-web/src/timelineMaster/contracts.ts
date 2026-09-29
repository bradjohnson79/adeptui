/** Frozen M42 W46 Director Timeline Master contracts (parity with Python). */

export type ModalityMode = "image_planning" | "video_finishing";
export type PromptStrategy = "native" | "compiled" | "split";
export type BatchStatus =
  | "Draft"
  | "Ready"
  | "Queued"
  | "Generating"
  | "Failed"
  | "Cancelled"
  | "CandidateReady"
  | "NeedsDialogueRetake"
  /** Omni infra miss — keep asset; retry QC only (never map to NeedsDialogueRetake). */
  | "QC_Pending"
  | "QC_RetryRequired"
  | "Approved"
  | "ApprovedConfigurationChanged"
  | "RegenerationRecommended";

export type CancelAction =
  | "cancel_pending_batch"
  | "cancel_active_local_job"
  | "request_hosted_cancellation"
  | "stop_remaining_scene_jobs"
  | "preserve_completed_batches"
  | "resume_incomplete_only";

export type HostedCancelSupport = "supported" | "unsupported" | "unknown";
export type RepairOverlapPolicy = "block" | "merge" | "stack_advanced";
export type InPaintStrategy =
  | "native"
  | "keyframe_repair"
  | "range_replacement"
  | "frame_repair_propagation"
  | "complete_batch_retake";

export type ContinuityStrategy =
  | "native_tail"
  | "native_extend"
  | "multi_frame"
  | "last_frame_i2v"
  | "prompt_context"
  | "none";

export type ContinuityBridgeStatus =
  | "Waiting"
  | "Analyzing"
  | "Ready"
  | "Applied"
  | "Failed"
  | "Superseded";

export const CURRENT_CONTINUITY_CONTEXT_VERSION = 1;

export interface DurationState {
  plannedDuration: number;
  generatedDuration?: number | null;
  timelineVisibleDuration?: number | null;
  sourceMediaDuration?: number | null;
}

export interface TimelineVisualAnchor {
  id: string;
  kind: "image" | "video" | "end_frame";
  assetId?: string | null;
  label: string;
  atTime: number;
  strength: number;
}

export interface TimelinePromptSegment {
  id: string;
  start: number;
  length: number;
  text: string;
  role: string;
  strength: number;
  negativePrompt?: string | null;
  anchorIds: string[];
  executionStrategy: PromptStrategy;
  versionId: string;
  legacyPromptSegmentId?: string | null;
  referenceBindingIds?: string[];
  referenceNameBindings?: Array<{
    binding_id?: string;
    bindingId?: string;
    prompt_name?: string;
    promptName?: string;
    type?: "character" | "prop" | "environment";
    tag?: string;
  }>;
  userDirection?: string | null;
  productionPrompt?: string | null;
  dialogue?: string | null;
  movementSegmentRef?: { id: string; segmentNumber: number; alias: string } | null;
  movementSegmentRevision?: number | null;
  temperature?: number;
}

export interface ExecutionSnapshot {
  id: string;
  batchBlockId: string;
  createdAt: string;
  immutable: true;
  compiledPrompts: Record<string, unknown>;
  promptLayerVersionIds: string[];
  references: Record<string, unknown>[];
  selectedGenerator?: string | null;
  capabilityStrategy?: string | null;
  settings: Record<string, unknown>;
  runtime?: string | null;
  providerId?: string | null;
  duration: DurationState;
  sourceAnchors: Record<string, unknown>[];
  continuityState: Record<string, unknown>;
  inPaintStrategy?: InPaintStrategy | null;
  /** Frozen Prompt Intelligence record at generation time. */
  promptIntelligence?: Record<string, unknown> | null;
}

export interface GenerationJobRef {
  id: string;
  executionSnapshotId: string;
  queueJobId?: string | null;
  providerJobId?: string | null;
  generatorId?: string | null;
  status: string;
  locality: "local" | "hosted";
  hostedCancelSupport: HostedCancelSupport;
  apiUsed?: boolean | null;
  progress?: number;
  progressGrounded?: boolean;
  phase?: string | null;
  phaseLabel?: string | null;
  lastProgressAt?: string | null;
  lastRuntimeEventAt?: string | null;
  elapsedActiveTime?: number | null;
  stalled?: boolean;
  currentNode?: string | null;
  error?: string | null;
  createdAt: string;
  sceneTakeId?: string | null;
  candidateId?: string | null;
}

export interface CandidateVersion {
  id: string;
  executionSnapshotId: string;
  assetId?: string | null;
  label: string;
  generatedDuration?: number | null;
  createdAt: string;
  approved: boolean;
  takeId?: string;
  parentTakeId?: string | null;
  incomingBridgeId?: string | null;
  continuityAware?: boolean;
  reTakeReason?: string | null;
  sequenceMemory?: Record<string, unknown>;
  incomingContinuity?: Record<string, unknown>;
  originalTakeIntent?: Record<string, unknown>;
  takeState?: Record<string, unknown>;
  userCorrection?: Record<string, unknown>;
}

export interface RepairRange {
  id: string;
  start: number;
  length: number;
  mode: string;
  inPaintStrategy: InPaintStrategy;
  metadata?: Record<string, unknown>;
  layer: number;
  status: string;
  executionSnapshotId?: string | null;
  candidateId?: string | null;
  label: string;
}

export interface ApprovedClip {
  assetId: string;
  executionSnapshotId: string;
  candidateId?: string | null;
  approvedAt: string;
  playable: boolean;
}

/** A clip owned by a BatchBlock. Stable unique ID; never re-keyed on reorder. */
export interface BatchClip {
  id: string;
  kind: "image" | "video" | "audio" | "sfx" | "camera";
  assetId?: string | null;
  start: number;
  length: number;
  trimStart: number;
  label: string;
  role?: string | null;
  /** Optional Generation retake / range metadata (pass-through on FE). */
  metadata?: Record<string, unknown>;
  volume: number;
  muted?: boolean;
  fade_in: number;
  fade_out: number;
  motion_type?: string | null;
  rig?: string | null;
  legacyClipId?: string | null;
}

/** Stable production container — ID never changes when approved media changes.
 *  BATCH_OWNED_CLIPS: each batch owns its clips directly. */
export interface BatchBlock {
  id: string;
  sceneId: string;
  order: number;
  label: string;
  status: BatchStatus;
  generatorId?: string | null;
  generatorOverride: boolean;
  duration: DurationState;
  sourceAnchors: TimelineVisualAnchor[];
  promptSegments: TimelinePromptSegment[];
  visualClips: BatchClip[];
  /** Creator removed this exact video from Visual. A new deposit clears it. */
  dismissedVisualAssetId?: string | null;
  audioClips: BatchClip[];
  sfxClips: BatchClip[];
  cameraInstructions: BatchClip[];
  generationJobs: GenerationJobRef[];
  candidateVersions: CandidateVersion[];
  approvedClip?: ApprovedClip | null;
  repairRanges: RepairRange[];
  references: Record<string, unknown>[];
  lora?: { loraId: string; name: string; strength: number } | null;
  h3Resolution?: { mode: "auto" | "manual"; megapixels: number } | null;
  /** LTX 2.5 Timeline QUALITY tier; independent of h3Resolution. Default 720p when absent. */
  ltxQuality?: "720p" | "1080p" | "2K" | "4K" | null;
  /** Seedance fal resolution. Absent means 720p. */
  seedanceResolution?: "480p" | "720p" | "1080p" | "4k" | null;
  configFingerprint?: string | null;
  createdAt: string;
  updatedAt: string;
  legacyImageClipIds: string[];
  migrationMetadata?: Record<string, unknown>;
  pendingSnapshotId?: string | null;
  activeTakeId?: string | null;
  incomingBridgeId?: string | null;
  continuityAwareRetake?: boolean;
  downstreamStale?: boolean;
  staleFromTakeId?: string | null;
}

export interface ContinuityPolicy {
  autoContinuity: boolean;
  configuredTailDuration: number;
  locality: "local" | "api";
  continuityAwareRetake: boolean;
}

export type ReviewCadence = "automatic" | "interval_3" | "interval_5" | "every_batch";
export type ProtectionLevel = "standard" | "strong";
export type PacketAvailability = "ready" | "unavailable" | "low_confidence";

export interface CoDirectorContinuityPolicy {
  enabled: boolean;
  reviewCadence: ReviewCadence;
  protection: ProtectionLevel;
  fastVisionModel?: string;
  deepReview?: "auto" | "off" | "on";
  showDebugState?: boolean;
  rejectedPacketIds?: string[];
  creatorNextBatchNote?: string;
}

export interface ImportantEvent {
  label: string;
  approxTimeSec?: number | null;
  phase?: "early" | "mid" | "late" | "unknown";
  detail?: string;
}

export interface VisualAnchor {
  kind: string;
  label: string;
  detail?: string;
  assetId?: string | null;
  identityId?: string | null;
}

export interface ExitState {
  summary?: string;
  characterStates?: string[];
  cameraState?: string | null;
  environmentState?: string | null;
}

export interface RollingSceneDigest {
  schemaVersion?: string;
  preserve?: string[];
  continue?: string[];
  avoid?: string[];
  importantEvents?: ImportantEvent[];
  visualAnchors?: VisualAnchor[];
  exitState?: ExitState;
  sourcePacketIds?: string[];
  updatedAt?: string;
}

export interface TemporalContinuityPacket {
  schemaVersion?: string;
  packetId: string;
  availability: PacketAvailability;
  reason?: string | null;
  source?: {
    batchId?: string;
    targetBatchId?: string | null;
    reviewCadence?: ReviewCadence;
    perceptionModelId?: string | null;
    startTime?: number;
    endTime?: number;
  };
  creatorMarker?: string | null;
  decision?: string;
  continuation?: {
    preserve?: string[];
    continue?: string[];
    avoid?: string[];
    nextBatchDirectives?: string[];
    creatorRejected?: boolean;
  };
  importantEvents?: ImportantEvent[];
  visualAnchors?: VisualAnchor[];
  exitState?: ExitState | null;
  rollingSceneDigest?: RollingSceneDigest | null;
  extras?: Record<string, unknown>;
}

export interface ContinuityBridge {
  bridgeId: string;
  sceneId: string;
  sourceBatchId: string;
  targetBatchId: string;
  sourceTakeId?: string | null;
  contextVersion: number;
  configuredTailDuration: number;
  effectiveTailDuration: number;
  tailAssetId?: string | null;
  lastFrameAssetId?: string | null;
  continuityStrategy: ContinuityStrategy;
  continuityModel?: string | null;
  continuityState: Record<string, unknown>;
  status: ContinuityBridgeStatus;
  createdAt: string;
  supersededAt?: string | null;
  error?: string | null;
}


export type FinalCheckTaxonomy = "Hard" | "Soft" | "Creative";

export interface FinalCheckFinding {
  category: string;
  taxonomy?: FinalCheckTaxonomy | null;
  code?: string | null;
  severity?: string | null;
  retakeEligible?: boolean;
  autoDestroy?: boolean;
  acceptanceEligible?: boolean;
  creativeTaste?: boolean;
  authoritySource?: string | null;
  confidence?: "high" | "low" | null;
  message?: string | null;
  source?: string | null;
  finalCheck?: {
    retakeEligible: boolean;
    autoDestroy: boolean;
    acceptanceEligible: boolean;
    creativeTaste: boolean;
    authoritySource: string;
    note?: string;
  } | null;
}

export interface FinalCheckCategoryResult {
  category: string;
  status: "pass" | "fail" | "not_run" | "uncertain";
  taxonomy?: FinalCheckTaxonomy | null;
  findings?: FinalCheckFinding[];
  source?: string | null;
  note?: string | null;
}

export interface SceneFinalCheckRepairGate {
  runtimeKind: "local" | "api";
  permission: "not_required" | "required" | "granted" | "declined" | "keep_current";
  apiCallCount: number;
  requiresApproval?: boolean;
  actions?: string[];
  oneApprovalPerCycle?: boolean;
  decision?: string | null;
  apiCallsDelta?: number;
  lifecycleStatus?: string | null;
  creatorVerdict?: string | null;
  note?: string | null;
  reuse?: string | null;
}

export interface SceneFinalCheck {
  lifecycleStatus: string;
  creatorVerdict?: string | null;
  openedAt?: string | null;
  closedAt?: string | null;
  categories: FinalCheckCategoryResult[];
  repairGate?: SceneFinalCheckRepairGate | null;
  stitchAssetId?: string | null;
  retakeLoopCount?: number;
  maxRetakeLoops?: number;
  unresolvedBlocking?: boolean;
  autoRepairEligibleCount?: number;
  retakePack?: Record<string, unknown> | null;
  policy?: string | null;
}


export interface ScenePublishState {
  publishedAssetId: string;
  publishedAt: string;
  sourceSceneStitchAssetId: string;
  lifecycleStatusSnapshot: string;
  creatorVerdictSnapshot?: string | null;
  acceptedIssues?: boolean;
  contentFingerprint: string;
  version: number;
  upscaledAssetId?: string | null;
  publishSource?: string;
  upscalePendingPublish?: boolean;
  takeId?: string | null;
  takeLabel?: string | null;
  batchIds?: string[];
}

export type SceneTakeStatus = "ready" | "rendering" | "cancelled" | "incomplete";

export interface SceneTakeBatchMember {
  batchId: string;
  order: number;
  assetId?: string | null;
  candidateId?: string | null;
  batchTakeId?: string | null;
  durationSec?: number | null;
  status?: string;
}

export interface SceneTakeQuality {
  generatorId?: string | null;
  h3Mode?: string | null;
  h3Megapixels?: number | null;
  width?: number | null;
  height?: number | null;
  ltxQuality?: string | null;
  seedanceResolution?: string | null;
  durationSec?: number | null;
  batchCount?: number;
}

export interface SceneTake {
  id: string;
  label: string;
  letterIndex: number;
  status: SceneTakeStatus;
  createdAt: string;
  completedAt?: string | null;
  generationSnapshot?: Record<string, unknown>;
  quality?: SceneTakeQuality;
  batches: SceneTakeBatchMember[];
  resultAssetId?: string | null;
  publishedAssetId?: string | null;
  retakeIds?: string[];
}

export interface SceneStitch {
  assetId: string;
  sourceBatchIds: string[];
  sourceAssetIds: string[];
  incremental?: boolean;
  durationSec?: number | null;
  createdAt?: string;
}

export interface LongFormContinuityState {
  schemaVersion?: string;
  revision: number;
  projectId: string;
  sceneId: string;
  mediaIntelligencePacketId?: string | null;
  temporalPacketId?: string | null;
  characters?: Array<{
    characterId?: string | null;
    crsAssetId?: string | null;
    label?: string;
    appearanceState?: string;
    wardrobeState?: string;
    position?: string;
    poseAction?: string;
  }>;
  environment?: Record<string, unknown>;
  props?: Array<{
    prsAssetId?: string | null;
    label?: string;
    holder?: string;
    location?: string;
    state?: string;
  }>;
  camera?: Record<string, unknown>;
  motion?: Record<string, unknown>;
  dialogue?: Record<string, unknown>;
  audio?: Record<string, unknown>;
  endingAnchors?: Array<Record<string, unknown>>;
  storyState?: string;
  nextIntent?: string;
  scores?: Record<string, unknown>;
  stale?: boolean;
  staleFromSegmentId?: string | null;
}

export interface ExtendSegment {
  segmentId: string;
  batchBlockId?: string | null;
  prompt: string;
  compiledPrompt?: string;
  continuityRevision?: number;
  inputAnchors?: string[];
  referenceAssetIds?: string[];
  h3Mode?: "i2v" | "r2v";
  durationSec?: number;
  executionId?: string | null;
  outputAssetId?: string | null;
  takeAAssetId?: string | null;
  takeBAssetId?: string | null;
  approvedTake?: "A" | "B" | null;
  status?: "planned" | "generating" | "draft" | "approved" | "failed" | "cancelled";
}

export interface SceneTimelineMaster {
  version: number;
  /** Spoken-language authority for this scene (never UI locale). */
  sceneLanguage?: string | null;
  spokenLanguage?: {
    sceneLanguage?: string | null;
    language?: string | null;
    source?: string | null;
    projectLanguage?: string | null;
  } | null;
  mode: ModalityMode;
  sceneGeneratorId?: string | null;
  turboLora?: boolean;
  orchestratorMode: string;
  repairOverlapPolicy: RepairOverlapPolicy;
  preflightMode: "off" | "warnings_only" | "strict";
  batchBlocks: BatchBlock[];
  executionSnapshots: Record<string, ExecutionSnapshot>;
  dismissedFailureJobIds?: string[];
  continuityPolicy?: ContinuityPolicy;
  continuityBridges?: ContinuityBridge[];
  coDirectorContinuityPolicy?: CoDirectorContinuityPolicy;
  temporalPackets?: TemporalContinuityPacket[];
  coDirectorRollingSceneDigest?: RollingSceneDigest | Record<string, unknown> | null;
  migratedFromDirectorJson: boolean;
  migrationNote?: string | null;
  sceneStitch?: SceneStitch | null;
  sceneFinalCheck?: SceneFinalCheck | null;
  scenePublish?: ScenePublishState | null;
  longFormContinuity?: LongFormContinuityState | null;
  extendSegments?: ExtendSegment[];
  lastMediaIntelligencePacketId?: string | null;
  sceneTakes?: SceneTake[];
  currentSceneTakeId?: string | null;
  activeSceneTakeId?: string | null;
  /** FE-facing multi-batch progress attached by workspace() — read-only; FE never writes status. */
  generationProgress?: {
    /** 1-based active batch index (BE compute_generation_progress). */
    currentBatchIndex: number;
    totalBatches: number;
    /** QC-eligible completes (excludes NeedsDialogueRetake). */
    completedBatches?: number;
    /** Render-complete count for overall K/N (includes NeedsDialogueRetake). */
    renderCompletedBatches?: number;
    batchStatus: string;
    /** Fraction 0..1 from jobs. */
    batchProgress: number;
    sceneStatus: string;
    currentBatchId?: string | null;
    message?: string;
    overallBatchesLabel?: string;
    statusLines?: string[];
    phase?: string | null;
    phaseLabel?: string | null;
    progressGrounded?: boolean;
    lastProgressAt?: string | null;
    lastRuntimeEventAt?: string | null;
    elapsedActiveTime?: number | null;
    stalled?: boolean;
    currentNode?: string | null;
    stallLabel?: string | null;
    gpuActive?: boolean | null;
    comfyMessage?: string | null;
    sceneFinished?: boolean;
    dialogueNeedsRetake?: number;
    dialogueQcLabel?: string | null;
    renderingTakeLabel?: string | null;
    /** Co-Director Final Check lifecycle (extends render chrome; does not replace it). */
    lifecycleStatus?: string | null;
    sceneFinishedWithAcceptedIssues?: boolean;
    sceneFinalCheck?: SceneFinalCheck | null;
  } | null;
}

export const REQUIRED_GATE_FLAGS = [
  "executionSnapshotPassed",
  "batchInvalidationPassed",
  "durationStateSeparationPassed",
  "repairOverlapPolicyPassed",
  "sceneCancelResumePassed",
  "immutableProvenancePassed",
] as const;

/** Creator-facing batch status label — single shared humanizer so the
 * Master panel and Inspector never diverge (audit UI-D5). */
export function formatBatchStatus(status: BatchStatus | string): string {
  if (status === "ApprovedConfigurationChanged") return "Approved — Configuration Changed";
  if (status === "RegenerationRecommended") return "Regeneration Recommended";
  if (status === "NeedsDialogueRetake") return "Needs Dialogue Retake";
  if (status === "QC_Pending") return "QC Pending";
  if (status === "QC_RetryRequired") return "QC Retry Required";
  return status;
}
