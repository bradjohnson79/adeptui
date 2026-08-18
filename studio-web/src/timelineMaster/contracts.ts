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
  error?: string | null;
  createdAt: string;
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
  volume: number;
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
  audioClips: BatchClip[];
  sfxClips: BatchClip[];
  cameraInstructions: BatchClip[];
  generationJobs: GenerationJobRef[];
  candidateVersions: CandidateVersion[];
  approvedClip?: ApprovedClip | null;
  repairRanges: RepairRange[];
  references: Record<string, unknown>[];
  lora?: { loraId: string; name: string; strength: number } | null;
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

export interface SceneTimelineMaster {
  version: number;
  mode: ModalityMode;
  sceneGeneratorId?: string | null;
  orchestratorMode: string;
  repairOverlapPolicy: RepairOverlapPolicy;
  preflightMode: "off" | "warnings_only" | "strict";
  batchBlocks: BatchBlock[];
  executionSnapshots: Record<string, ExecutionSnapshot>;
  dismissedFailureJobIds?: string[];
  continuityPolicy?: ContinuityPolicy;
  continuityBridges?: ContinuityBridge[];
  migratedFromDirectorJson: boolean;
  migrationNote?: string | null;
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
  return status;
}
