import type {
  Capability,
  CapabilitySnapshot,
  ComfyHealth,
  WorkflowDescriptor,
  WorkflowReadiness,
} from "./capabilities";
import { resolveMiniMaxH3Territory } from "./core/minimaxH3Territory";
import { getProjectUnlockToken, projectIdFromApiPath } from "./projectSecurity.ts";
import type { Asset, EngineName, Health, Job, Project, Scene, SceneSetup, SpatialMap } from "./types";
import type {
  CertifiedRecipe,
  ComponentDiagnosticResult,
  DownloadSourcesResponse,
  DownloadOperation,
  InstallHistoryEntry,
  InstallReceipt,
  LifecycleCloudProvider,
  LifecycleInstallPlan,
  MonitorFinding,
  ProviderLifecycleState,
  SetupCheckpointAnswer,
  SetupLegacyActionResult,
  SetupLegacyDetection,
  SetupLegacyState,
  SetupOperation,
  SetupStatusResponse,
  SetupUpdateDismissal,
  SourceManagerOverview,
  SourceVerificationResult,
  StudioPreparationPlan,
} from "./setup/types";
import type { InstallJob } from "./contracts/installJobs";
import type {
  VoicePerformanceCapabilities,
  VoicePerformanceComparison,
  VoicePerformanceEmotionPreset,
  VoicePerformanceLipsyncResult,
  VoicePerformanceRecord,
  VoicePerformanceRecordList,
  VoicePerformanceRuntimeStatus,
  VoicePerformanceTakeList,
  VoicePerformanceTimelinePlacement,
} from "./contracts/voicePerformanceM410";
import type {
  SpatialAssignSceneBody,
  SpatialCameraCreateBody,
  SpatialCameraUpdateBody,
  SpatialCapturePlanBody,
  SpatialCapturePlanResponse,
  SpatialCharacterPlacementBody,
  SpatialCharacterPlacementUpdateBody,
  SpatialCollageCreateBody,
  SpatialConsistencyCheckResponse,
  SpatialMapCreateBody,
  SpatialMapDocumentResponse,
  SpatialMapListResponse,
  SpatialMapUpdateBody,
  SpatialMovementPathCreateBody,
  SpatialPropPlacementBody,
  SpatialPropPlacementUpdateBody,
  SpatialReferenceBundleResponse,
  Spatial360ViewUpsertBody,
  SpatialVariantCreateBody,
} from "./contracts/spatialMapM411";
import type { AvatarProjectJob } from "./avatar/types";
import type { StatusRegistryCheck, StatusRun } from "./codirector/status/types";

const BASE = "";

export interface ApiErrorDetailShape {
  code?: string;
  error_code?: string;
  category?: string;
  message?: string;
  details?: Record<string, unknown>;
  recoverable?: boolean;
  retryable?: boolean;
  recommendedAction?: string;
  recommended_action?: string;
  project_id?: string | null;
  provider?: string | null;
  model?: string | null;
  technical_evidence?: Record<string, unknown>;
  partial_work_created?: boolean;
}

export class ApiError extends Error {
  status: number;
  /** Structured error code from a Co-Director-style `{code,message,...}` detail payload, if present. */
  code?: string;
  details?: Record<string, unknown>;
  recoverable?: boolean;
  recommendedAction?: string;
  category?: string;
  retryable?: boolean;
  project_id?: string | null;
  provider?: string | null;
  model?: string | null;
  technical_evidence?: Record<string, unknown>;
  partial_work_created?: boolean;

  constructor(
    message: string,
    status: number,
    opts?: {
      code?: string;
      details?: Record<string, unknown>;
      recoverable?: boolean;
      recommendedAction?: string;
      category?: string;
      retryable?: boolean;
      project_id?: string | null;
      provider?: string | null;
      model?: string | null;
      technical_evidence?: Record<string, unknown>;
      partial_work_created?: boolean;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = opts?.code;
    this.details = opts?.details;
    this.recoverable = opts?.recoverable;
    this.recommendedAction = opts?.recommendedAction;
    this.category = opts?.category;
    this.retryable = opts?.retryable;
    this.project_id = opts?.project_id;
    this.provider = opts?.provider;
    this.model = opts?.model;
    this.technical_evidence = opts?.technical_evidence;
    this.partial_work_created = opts?.partial_work_created;
  }
}

/** Backend-agnostic "couldn't reach the service" code used when fetch itself throws. */
export const BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE";
/** Highest-level Studio API / proxy connectivity codes (prefer over provider errors). */
export const STUDIO_API_OFFLINE = "STUDIO_API_OFFLINE";
export const STUDIO_API_CONNECTION_RESET = "STUDIO_API_CONNECTION_RESET";
export const API_PROXY_UNAVAILABLE = "API_PROXY_UNAVAILABLE";
export const OLLAMA_EMPTY_RESPONSE = "OLLAMA_EMPTY_RESPONSE";

export interface ClassifiedError {
  code: string;
  error_code?: string;
  category?: string;
  message: string;
  details?: Record<string, unknown>;
  recommendedAction?: string;
  recommended_action?: string;
  recoverable: boolean;
  retryable?: boolean;
  project_id?: string | null;
  provider?: string | null;
  model?: string | null;
  technical_evidence?: Record<string, unknown>;
  partial_work_created?: boolean;
}

export interface ProjectWikiEntry {
  id: string;
  text: string;
  state:
    | "confirmed"
    | "proposed"
    | "unresolved"
    | "approved"
    | "rejected"
    | "superseded"
    | "reference-only";
  sourceMessageId?: string;
  inferred?: boolean;
  referenceKind?: string;
  assetId?: string;
}

export interface ProjectWikiSection {
  summary?: string;
  entries: ProjectWikiEntry[];
  emptyState?: string;
}

export interface CoDirectorProjectWiki {
  projectId: string;
  title: string;
  projectType?: string | null;
  status: "initialized" | "developing" | "production";
  overview: string;
  hasContent?: boolean;
  emptyState?: string;
  sections: {
    knownDetails: ProjectWikiSection;
    creativeFoundation: ProjectWikiSection;
    characters: ProjectWikiSection;
    worldAndSetting: ProjectWikiSection;
    storyAndEpisodes: ProjectWikiSection;
    visualIdentity: ProjectWikiSection;
    productionDecisions: ProjectWikiSection;
    openQuestions: ProjectWikiSection;
    references: ProjectWikiSection;
  };
  updatedAt: string;
  toc?: { key: string; label: string; count: number }[];
  professionalToc?: {
    key: string;
    label: string;
    count: number;
    children?: { id?: string; label: string; canonState?: string; entityType?: string }[];
  }[];
  compiledToc?: {
    key: string;
    label: string;
    count: number;
    children?: { id?: string; label: string; canonState?: string; entityType?: string; pageId?: string }[];
  }[];
  compiledPages?: Array<{
    pageId: string;
    pageType: string;
    title: string;
    summary?: string;
    sections?: Array<{ id: string; title: string; body?: string; bullets?: string[] }>;
    questionsToExplore?: string[];
    castingLink?: string | null;
    relatedPageIds?: string[];
  }>;
  compiledStorySummary?: {
    logline?: string;
    shortSummary?: string;
    longSummary?: string;
    themes?: string[];
    unresolvedQuestions?: string[];
  };
  compiledRevision?: number;
  readabilityOk?: boolean;
  sourceOfTruth?: string;
  projection?: string;
}

export interface CoDirectorProjectPlanLookup {
  ok: boolean;
  status: string;
  plan: Record<string, unknown> | null;
}

/** Bounded excerpt of the Production Bible injected into a chat turn's context (M2.1). */
export interface CoDirectorContextManifest {
  projectId: string;
  bibleVersionId?: string | null;
  bibleVersionNumber?: number | null;
  includedEntityKeys: string[];
  includedFactIds: string[];
  tokenBudget: number;
  estimatedTokens: number;
  truncated: boolean;
}

export interface CoDirectorBibleEntity {
  entityType: string;
  entityKey: string;
  displayName: string;
  data: Record<string, unknown>;
  stableId?: string | null;
  slug?: string | null;
  lifecycleStatus?: string;
  contentRevision?: number;
  updatedAt?: string | null;
  readiness?: string;
}

export interface BibleDomainSummary {
  projectId: string;
  bibleVersionNumber?: number | null;
  bibleVersionId?: string | null;
  health?: {
    entityCount: number;
    byType: Record<string, number>;
    readiness: Record<string, number>;
    lockedCount: number;
    incompleteCount: number;
  };
  conflictCount?: number;
  conflicts?: Record<string, unknown>[];
}

export interface BibleAuditEvent {
  id: string;
  eventType: string;
  entityStableId?: string | null;
  entityKey?: string | null;
  summary: string;
  createdAt: string;
}

export interface CoDirectorBibleFact {
  entityKey?: string | null;
  factType: string;
  statement: string;
  data: Record<string, unknown>;
}

export interface CoDirectorBibleDiscoveryAsset {
  assetId: string;
  tag: string;
  kind: string;
  filename: string;
}

export interface CoDirectorBibleDiscoveryItem {
  id: string;
  kind: "entity" | "fact";
  title: string;
  subtitle: string;
  entityKey?: string | null;
  factIndex?: number | null;
  entityType?: string | null;
  included: boolean;
  needsReview: boolean;
  reasons: string[];
  referenceAssets: CoDirectorBibleDiscoveryAsset[];
}

function presentCoDirectorError(err: ApiError): string {
  const code = (err.code || "").toUpperCase();
  if (code === "TOOL_NOT_FOUND") {
    return "That change could not be saved yet because this Beta build is missing one of Co-Director's save actions.";
  }
  if (code === "TOOL_EXECUTION_FAILED") {
    return "That change was not saved. You can retry the same action.";
  }
  return err.message || "The Co-Director backend returned an unexpected error.";
}

export interface CoDirectorBibleDiscoveryGroup {
  id: string;
  title: string;
  description: string;
  items: CoDirectorBibleDiscoveryItem[];
}

export interface CoDirectorBibleImportPreview {
  projectId: string;
  entities: CoDirectorBibleEntity[];
  facts: CoDirectorBibleFact[];
  summary: string;
  warnings: string[];
  discoveries: CoDirectorBibleDiscoveryGroup[];
}

export interface CoDirectorBibleMutationSet {
  entityMutations: {
    entityType: string;
    entityKey: string;
    displayName?: string | null;
    data?: Record<string, unknown> | null;
    remove?: boolean;
  }[];
  factMutations: {
    factId?: string | null;
    entityKey?: string | null;
    factType: string;
    statement: string;
    data?: Record<string, unknown> | null;
    remove?: boolean;
  }[];
  summary: string;
  changeReason: string;
}

export type CoDirectorProposalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "revision_requested"
  | "executing"
  | "completed"
  | "failed"
  | "cancelled"
  | "stale";

/** Server-computed description of what a mutating tool would do (M2.2). */
export interface CoDirectorToolPreview {
  summary: string;
  lines: string[];
  resourceKind?: string | null;
  resourceId?: string | null;
  warnings: string[];
}

/** The server-owned payload of a `tool_call` proposal. The browser only ever reads this. */
export interface CoDirectorToolCall {
  toolId: string;
  toolSchemaVersion: number;
  arguments: Record<string, unknown>;
  capabilitySnapshot: Record<string, unknown>;
  preview: CoDirectorToolPreview;
  inputHash: string;
  baseResourceVersions: Record<string, string | null>;
}

export interface CoDirectorProposal {
  id: string;
  projectId: string;
  bibleId?: string | null;
  basedOnVersionId?: string | null;
  basedOnVersionNumber?: number | null;
  proposalType: string;
  title: string;
  summary: string;
  payload: CoDirectorBibleMutationSet;
  /** Present only when `proposalType === "tool_call"`. */
  toolCall?: CoDirectorToolCall | null;
  status: CoDirectorProposalStatus;
  requestId?: string | null;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  isStale: boolean;
}

export interface CoDirectorExecutionReceipt {
  id: string;
  proposalId: string;
  inputHash: string;
  status: string;
  resultingVersionId?: string | null;
  resultingVersionNumber?: number | null;
  error?: Record<string, unknown> | null;
  executedAt: string;
  toolId?: string | null;
  toolInvocationId?: string | null;
  toolResult?: Record<string, unknown> | null;
  toolResultTruncated?: boolean;
}

export interface CoDirectorToolDefinition {
  toolId: string;
  toolSchemaVersion: number;
  kind: "read" | "mutating";
  title: string;
  description: string;
  capability: string;
  parameters: {
    name: string;
    type: string;
    required: boolean;
    description: string;
    maxLength?: number;
    minimum?: number;
    maximum?: number;
    choices?: string[];
  }[];
  requiresApproval: boolean;
  pinnedResources: string[];
  resultCharBudget: number;
}

export interface CoDirectorToolAvailability {
  toolId: string;
  available: boolean;
  capability: string;
  capabilityStatus: string;
  reason?: string | null;
  errorCode?: string | null;
}

export interface CoDirectorToolInvocation {
  id: string;
  projectId: string;
  toolId: string;
  toolSchemaVersion: number;
  kind: "read" | "mutating";
  status: "succeeded" | "failed" | "blocked" | string;
  arguments: Record<string, unknown>;
  /** Wave 3: canonical retrieval envelope when status=succeeded for read tools. */
  result?: Record<string, unknown> | null;
  resultTruncated: boolean;
  resultHash?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  proposalId?: string | null;
  requestId?: string | null;
  durationMs: number;
  createdBy: string;
  createdAt: string;
}

export interface CoDirectorRetrievalEnvelope {
  requestId?: string | null;
  toolId: string;
  toolVersion?: string | number;
  projectId?: string | null;
  status: "success" | "partial" | "empty" | "failed";
  summary: string;
  data?: unknown;
  evidence?: Array<{
    sourceType: string;
    sourceId: string;
    sourceName?: string | null;
    repository: string;
  }>;
  warnings?: Array<{ code: string; message: string; section?: string | null }>;
  retrievedAt?: string;
}

export interface CoDirectorBibleVersion {
  id: string;
  bibleId: string;
  versionNumber: number;
  parentVersionId?: string | null;
  summary: string;
  changeReason: string;
  createdBy: string;
  createdAt: string;
  entities: CoDirectorBibleEntity[];
  facts: CoDirectorBibleFact[];
}

export interface CoDirectorBible {
  projectId: string;
  currentVersion: CoDirectorBibleVersion | null;
  versionCount: number;
}

/** SSE events emitted by POST /api/codirector/chat/stream. Additive union — new `type`
 * values may appear over time; unknown types must be safely ignorable by callers. */
export type CoDirectorStreamEvent =
  | { type: "request_started"; requestId: string }
  | { type: "provider_connected"; requestId: string; providerId: string }
  | { type: "token"; requestId: string; content: string; replace?: boolean }
  | {
      type: "inference_trace";
      requestId: string;
      trace: {
        selected_model?: string;
        actual_model?: string;
        selected_provider?: string;
        actual_provider?: string;
        fallback_used?: boolean;
        fallback_reason?: string | null;
        mode?: string;
        primary_intent?: string;
        evidence_spans?: string[];
        question_budget?: number;
        workflow_advance_policy?: string;
      };
    }
  | {
      type: "conversation_state";
      requestId: string;
      state: {
        mode?: string | null;
        activeGoal?: string | null;
        workflowHold?: boolean;
        preferenceExplainBeforeProduction?: boolean;
        evidenceSpans?: string[];
        companionNeed?: string | null;
        creativePosture?: string | null;
        advisoryDecision?: string | null;
        advisoryStrength?: string | null;
        changeStatus?: string | null;
        waitingForConfirmation?: boolean;
        canonUpdated?: boolean;
        toolsSummary?: string | null;
        roleEmphasis?: string | null;
        assistantName?: string | null;
        userPreferredName?: string | null;
        creativeStage?: string | null;
        wikiCandidates?: number | null;
        confirmedWrites?: number | null;
        discoveryQuestions?: number | null;
        researchStatus?: string | null;
        documentationReason?: string | null;
        whatChanged?: string[];
        projectPulse?: Record<string, unknown> | null;
        processingStages?: string[];
        onboardingNeeded?: boolean;
      };
    }
  | { type: "processing_stage"; requestId: string; stage: string }
  | { type: "what_changed"; requestId: string; lines?: string[] }
  | { type: "project_pulse"; requestId: string; pulse?: Record<string, unknown> }
  | { type: "conversation_actions"; requestId: string; actions?: { id: string; label: string }[] }
  | { type: "documentation_result"; requestId: string; result?: Record<string, unknown> }
  | {
      type: "background_job";
      requestId: string;
      jobType?: string;
      status?: string;
      result?: Record<string, unknown>;
      error?: string;
      prematureClaim?: boolean;
    }
  | {
      type: "wiki_status";
      requestId: string;
      verification?: Record<string, unknown>;
      prematureClaim?: boolean;
      message?: string | null;
    }
  | {
      type: "next_step_options";
      requestId: string;
      options?: {
        id: string;
        type: string;
        label: string;
        shortDescription?: string | null;
        whyNow?: string | null;
        readiness?: string;
        ownershipRequired?: boolean;
        priority?: number;
        previewSpine?: string | null;
      }[];
      intro?: string;
    }
  | {
      type: "momentum_resume";
      requestId: string;
      resume?: string;
      momentum?: Record<string, unknown> | null;
    }
  | {
      type: "creative_momentum";
      requestId: string;
      momentum?: Record<string, unknown> | null;
    }
  | {
      type: "creative_confidence";
      requestId: string;
      confidence?: Record<string, unknown> | null;
      insight?: string | null;
    }
  | {
      type: "conversation_timings";
      requestId: string;
      timings?: Record<string, unknown>;
    }
  | { type: "response_evidence"; requestId: string; evidence?: Record<string, unknown> }
  | { type: "intrigue"; requestId: string; assessment?: Record<string, unknown> }
  | { type: "discovery_questions"; requestId: string; questions?: Record<string, unknown>[] }
  | { type: "artifact_readiness"; requestId: string; assessments?: Record<string, unknown>[] }
  | { type: "deliverable"; requestId: string; deliverable?: Record<string, unknown> }
  | { type: "journey_state"; requestId: string; journey?: Record<string, unknown> }
  | { type: "vision_profile"; requestId: string; vision?: Record<string, unknown> }
  | { type: "pitch_package"; requestId: string; pitch?: Record<string, unknown> }
  | { type: "marketing_strategy"; requestId: string; marketing?: Record<string, unknown> }
  | { type: "collaboration_profile"; requestId: string; collaboration?: Record<string, unknown> }
  | {
      type: "completed";
      requestId: string;
      content: string;
      modelId?: string;
      model?: string;
      providerId?: string;
      sceneSetup?: SceneSetup | null;
      suggestedPrompt?: string | null;
      responseType?: string;
      structuredRecommendation?: Record<string, unknown> | null;
      messageId?: string;
      fallbackUsed?: boolean;
    }
  | { type: "cancelled"; requestId: string }
  | { type: "error"; requestId: string; error: ApiErrorDetailShape }
  | { type: "context_manifest"; requestId: string; manifest: CoDirectorContextManifest }
  | { type: "proposal_created"; requestId: string; proposal: CoDirectorProposal }
  | { type: "proposal_updated"; requestId: string; proposal: CoDirectorProposal }
  | { type: "approval_required"; requestId: string; proposal: CoDirectorProposal }
  | { type: "approval_recorded"; requestId: string; proposalId: string; decision: string }
  | { type: "execution_started"; requestId: string; proposalId: string }
  | { type: "execution_completed"; requestId: string; proposalId: string; receipt: CoDirectorExecutionReceipt }
  | { type: "execution_failed"; requestId: string; proposalId: string; error: ApiErrorDetailShape }
  | { type: "bible_version_created"; requestId: string; projectId: string; versionNumber: number }
  // M2.2 tool lifecycle. `tool_requested` arrives while the assistant bubble is still
  // streaming the request itself, so the UI replaces that bubble with a status line.
  | { type: "tool_requested"; requestId: string; toolId: string; kind: "read" | "mutating" }
  | { type: "tool_started"; requestId: string; toolId: string; title: string }
  | { type: "tool_completed"; requestId: string; toolId: string; invocation: CoDirectorToolInvocation }
  | {
      type: "tool_failed";
      requestId: string;
      toolId: string;
      kind?: "read" | "mutating";
      arguments?: Record<string, unknown>;
      error: ApiErrorDetailShape;
    }
  | { type: "tool_result_truncated"; requestId: string; toolId: string; invocationId: string }
  | { type: "tool_proposal_created"; requestId: string; toolId: string; proposal: CoDirectorProposal }
  | {
      type: "capability_blocked";
      requestId: string;
      toolId: string;
      kind?: "read" | "mutating";
      arguments?: Record<string, unknown>;
      capability?: string | null;
      error: ApiErrorDetailShape;
    }
  // M2.4 production intelligence progress and artifacts.
  | {
      type: "intelligence_progress";
      requestId: string;
      stage: string;
      message?: string;
      promptVersions?: Record<string, string>;
      specialists?: string[];
      intent?: Record<string, unknown>;
    }
  | {
      type: "intelligence_result";
      requestId: string;
      synthesis: Record<string, unknown>;
      promptVersions?: Record<string, string>;
    }
  | {
      type: "intelligence_plan";
      requestId: string;
      plan: Record<string, unknown>;
    }
  | {
      type: "intelligence_proposal";
      requestId: string;
      proposal: CoDirectorProposal;
    };

/**
 * Turn any thrown value from a Co-Director request into a structured, user-safe
 * classification. Never surfaces a bare `TypeError: Failed to fetch`.
 */
export function classifyCoDirectorError(err: unknown): ClassifiedError {
  if (err instanceof ApiError) {
    const code = err.code || "UNKNOWN_PROVIDER_ERROR";
    // Priority law: Studio API connectivity beats provider-level diagnosis.
    if (
      code === STUDIO_API_OFFLINE
      || code === STUDIO_API_CONNECTION_RESET
      || code === API_PROXY_UNAVAILABLE
    ) {
      return {
        code,
        error_code: code,
        category: "runtime",
        message:
          code === STUDIO_API_CONNECTION_RESET
            ? "Studio API connection was reset. Your message is preserved and can be retried when the service reconnects."
            : "Co-Director lost connection to Studio API. Your message is preserved and can be retried when the service reconnects.",
        details: { ...(err.details || {}), rawMessage: err.message || "" },
        recommendedAction: "retry_or_check_service",
        recommended_action: "retry_or_check_service",
        recoverable: true,
        retryable: true,
        project_id: err.project_id ?? null,
        provider: null,
        model: null,
        technical_evidence: err.technical_evidence,
        partial_work_created: false,
      };
    }
    const retryable = err.retryable ?? err.recoverable ?? true;
    return {
      code,
      error_code: code,
      category: err.category,
      message: presentCoDirectorError(err),
      details: { ...(err.details || {}), rawMessage: err.message || "" },
      recommendedAction: err.recommendedAction,
      recommended_action: err.recommendedAction,
      recoverable: err.recoverable ?? true,
      retryable,
      project_id: err.project_id ?? null,
      provider: err.provider ?? null,
      model: err.model ?? null,
      technical_evidence: err.technical_evidence,
      partial_work_created: err.partial_work_created ?? false,
    };
  }
  if (err instanceof TypeError && /failed to fetch|networkerror when attempting to fetch|load failed/i.test(err.message)) {
    return {
      code: STUDIO_API_OFFLINE,
      error_code: STUDIO_API_OFFLINE,
      category: "runtime",
      message:
        "Co-Director lost connection to Studio API. Your message is preserved and can be retried when the service reconnects.",
      recommendedAction: "retry_or_check_service",
      recommended_action: "retry_or_check_service",
      recoverable: true,
      retryable: true,
      partial_work_created: false,
    };
  }
  return {
    code: "UNKNOWN_PROVIDER_ERROR",
    error_code: "UNKNOWN_PROVIDER_ERROR",
    category: "runtime",
    message: err instanceof Error ? err.message : String(err),
    recoverable: true,
    retryable: true,
    partial_work_created: false,
  };
}

/** True for intentional request cancellation (unmount / navigation). */
export function isAbortError(error: unknown): boolean {
  if (!error) return false;
  if (typeof DOMException !== "undefined" && error instanceof DOMException) {
    return error.name === "AbortError";
  }
  if (error instanceof Error) {
    return error.name === "AbortError" || /The operation was aborted|aborted/i.test(error.message);
  }
  return false;
}

/**
 * True when a fetch failed because the browser tore down the connection
 * (SPA navigation / tab close). Not a substitute for AbortError — use with a
 * mounted/aborted check so real outages still surface while mounted.
 */
export function isNavigationFetchFailure(error: unknown): boolean {
  return (
    error instanceof TypeError
    && /failed to fetch|networkerror when attempting to fetch|load failed/i.test(error.message)
  );
}

/** Credential status for the fal.ai key. Never carries the key itself — only a masked hint. */
export type FalKeyStatus = {
  configured: boolean;
  hint?: string | null;
  fingerprint?: string | null;
  state: "missing" | "unverified" | "verified" | "invalid";
  verified?: boolean | null;
  verifiedAt?: string | null;
  message: string;
};

/** A string body with no content type is sent as text/plain, which FastAPI rejects outright. */
function withJsonContentType(init?: RequestInit): RequestInit | undefined {
  if (!init || typeof init.body !== "string") return init;
  const headers = new Headers(init.headers);
  if (headers.has("Content-Type")) return init;
  headers.set("Content-Type", "application/json");
  return { ...init, headers };
}

function withProjectUnlock(path: string, init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  const pid = projectIdFromApiPath(path);
  if (pid) {
    const token = getProjectUnlockToken(pid);
    if (token && !headers.has("X-Adept-Project-Unlock")) {
      headers.set("X-Adept-Project-Unlock", token);
    }
  }
  return { ...init, headers, credentials: init?.credentials ?? "include" };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, withProjectUnlock(path, withJsonContentType(init)));
  } catch (error) {
    // Preserve AbortError so callers can ignore expected cancellations.
    if (isAbortError(error) || init?.signal?.aborted) {
      throw error instanceof Error ? error : new DOMException("Aborted", "AbortError");
    }
    // Lazy import avoids circular init; notify shared outage coordinator.
    void import("./runtime/studioApiConnection").then((m) => {
      m.noteStudioApiTransportError(error);
      m.ensureStudioApiConnectionMonitor();
    });
    throw new ApiError(
      "Studio API is currently unavailable. Co-Director and production services are paused while Adept UI reconnects.",
      0,
      {
        code: STUDIO_API_OFFLINE,
        category: "runtime",
        recoverable: true,
        retryable: true,
        recommendedAction: "retry_or_check_service",
      },
    );
  }
  if (!res.ok) {
    const text = await res.text();
    let detail: unknown;
    try {
      const payload = JSON.parse(text) as { detail?: unknown; error?: unknown };
      detail = payload.detail ?? payload.error;
    } catch {
      detail = undefined;
    }
    if (detail && typeof detail === "object") {
      const d = detail as ApiErrorDetailShape;
      const code = d.error_code || d.code;
      const err = new ApiError(d.message || text || res.statusText, res.status, {
        code,
        details: d.details,
        recoverable: d.recoverable ?? d.retryable,
        recommendedAction: d.recommendedAction || d.recommended_action,
        category: d.category,
        retryable: d.retryable ?? d.recoverable,
        project_id: d.project_id,
        provider: d.provider,
        model: d.model,
        technical_evidence: d.technical_evidence,
        partial_work_created: d.partial_work_created,
      });
      if (
        code === STUDIO_API_OFFLINE
        || code === STUDIO_API_CONNECTION_RESET
        || code === API_PROXY_UNAVAILABLE
        || code === BACKEND_UNAVAILABLE
      ) {
        void import("./runtime/studioApiConnection").then((m) => {
          m.noteStudioApiTransportError(err);
          m.ensureStudioApiConnectionMonitor();
        });
      }
      throw err;
    }
    if (typeof detail === "string" && detail.trim()) {
      throw new ApiError(detail, res.status);
    }
    throw new ApiError(text || res.statusText, res.status);
  }
  // Successful API traffic clears outage state (health probes also mark healthy).
  if (path === "/api/health" || path.startsWith("/api/health?")) {
    void import("./runtime/studioApiConnection").then((m) => m.markStudioApiHealthy());
  }
  return res.json();
}

function parseFilename(disposition: string | null, fallback: string): string {
  const match = /filename="?([^"]+)"?/i.exec(disposition || "");
  return match?.[1] || fallback;
}

async function reqBlob(path: string, init?: RequestInit): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}${path}`, withProjectUnlock(path, withJsonContentType(init)));
  if (!res.ok) {
    const text = await res.text();
    let detail: unknown;
    try {
      const payload = JSON.parse(text) as { detail?: unknown; error?: unknown };
      detail = payload.detail ?? payload.error;
    } catch {
      detail = undefined;
    }
    if (detail && typeof detail === "object") {
      const d = detail as ApiErrorDetailShape;
      throw new ApiError(d.message || text || res.statusText, res.status, {
        code: d.error_code || d.code,
        details: d.details,
        recoverable: d.recoverable ?? d.retryable,
        recommendedAction: d.recommendedAction || d.recommended_action,
        category: d.category,
        retryable: d.retryable ?? d.recoverable,
      });
    }
    throw new ApiError(text || res.statusText, res.status);
  }
  return {
    blob: await res.blob(),
    filename: parseFilename(res.headers.get("Content-Disposition"), "download.bin"),
  };
}

export interface ImageProductFamily {
  family: string;
  label: string;
  status: string;
  executable: boolean;
  estimates: {
    generationTimeSec?: number;
    vramGb?: number | null;
    costUsd?: number;
    costLabel?: string;
    providerKind?: string;
  };
}

export interface ImageProductRecommendation {
  recommendedFamily: string;
  executionFamily: string;
  status: string;
  executable: boolean;
  fallbackApplied?: boolean;
  whyThisModel: string;
  estimates: ImageProductFamily["estimates"];
  executionEstimates?: ImageProductFamily["estimates"];
  alternatives?: {
    family: string;
    status: string;
    executable: boolean;
    whyThisModel: string;
    estimates: ImageProductFamily["estimates"];
  }[];
  overridable?: boolean;
  quality?: string;
}

export interface ImageProductPreset {
  presetId: string;
  name: string;
  builtin?: boolean;
  preferredModelFamily?: string;
  aspectRatio?: string;
  qualityPreset?: string;
  resolution?: string;
  guidance?: number;
  promptTemplate?: string;
  defaultReferenceAssetTypes?: string[];
}

export interface ImageProductGenerateResult {
  ok: boolean;
  queued: boolean;
  jobId?: string | null;
  jobs?: { jobId: string; workflowKey?: string; kind: string }[];
  recommendation?: ImageProductRecommendation;
  promptIntel?: Record<string, unknown>;
  imageRuntime?: Record<string, unknown>;
  imageIntent?: Record<string, unknown>;
  disclosure?: string;
}

export interface ImageProductEditRecommendation extends ImageProductRecommendation {
  operation?: string;
  requiredInputs?: string[];
  optionalInputs?: string[];
  maskStrategy?: string;
  hasMasks?: boolean;
  hasReferences?: boolean;
  sourceAssetCount?: number;
  fallback?: {
    family?: string;
    workflowKey?: string;
    reason?: string;
    requiresUserApproval?: boolean;
  };
  candidateWorkflowKeys?: string[];
  readinessStatus?: string;
  resolverIntent?: string;
}

export interface ImageProductRecipe {
  recipeId: string;
  name: string;
  builtin?: boolean;
  operation: string;
  maskDefaults?: Record<string, unknown>;
  recommendedWorkflowFamily?: string;
  referenceRequirements?: { role: string; required?: boolean }[];
  preserveToggles?: Record<string, boolean>;
  outputPreset?: Record<string, unknown>;
  promptTemplate?: string;
}

export interface ImageProductMask {
  maskId: string;
  sourceAssetId: string;
  role?: string;
  path?: string;
  dimensions?: { width: number; height: number };
  creator?: string;
  createdAt?: string;
}

export interface ImageProductVersion {
  versionId: string;
  projectId?: string;
  sourceAssetId: string;
  parentVersionId?: string | null;
  outputAssetId?: string | null;
  name: string;
  state: string;
  reviewNotes?: { author: string; text: string; createdAt?: string }[];
  children?: string[];
  childrenNodes?: ImageProductVersion[];
  createdAt?: string;
  modifiedAt?: string;
}

export interface ImageProductEditEnqueueResult {
  ok: boolean;
  queued: boolean;
  jobId?: string;
  workflowKey?: string;
  kind?: string;
  operation?: string;
  imageEditIntent?: Record<string, unknown>;
  imageIntent?: Record<string, unknown>;
  imageRuntime?: Record<string, unknown>;
  recommendation?: ImageProductEditRecommendation;
  promptIntel?: Record<string, unknown>;
  disclosure?: string;
  jobs?: { jobId: string; workflowKey?: string; kind: string; sourceAssetId?: string }[];
}

export interface DirectorTimelineCameraCatalogEntry {
  id: string;
  label: string;
  category: string;
  aliases: string[];
  description: string;
  capability: "Native" | "Compiled Prompt Guidance" | "Workflow-Mapped" | "Approximate" | "Unsupported";
  defaults: {
    speed: number;
    intensity: number;
    subjectLock: number;
  };
  native_motion_type?: string | null;
  native_rig?: string | null;
  workflow_motion_type?: string | null;
  workflow_rig?: string | null;
}

export interface DirectorTimelineCameraCatalogGroup {
  category: string;
  items: DirectorTimelineCameraCatalogEntry[];
}

export interface DirectorTimelineCameraCatalog {
  version: string;
  motions: DirectorTimelineCameraCatalogEntry[];
  motionGroups: DirectorTimelineCameraCatalogGroup[];
  rigs: DirectorTimelineCameraCatalogEntry[];
  rigGroups: DirectorTimelineCameraCatalogGroup[];
  contradictionRules: Array<{
    id: string;
    motion_ids?: string[];
    rig_ids?: string[];
    severity: "warning" | "error";
    message: string;
    fix_proposal: string;
  }>;
  mock: boolean;
}

export const api = {
  health: () => req<Health>("/api/health"),
  betaRuntimeStatus: () =>
    req<{
      active?: boolean;
      state?: string;
      message?: string;
      services?: Record<string, { ok?: boolean; role?: string; url?: string }>;
      uiUrl?: string;
      apiUrl?: string;
      logsDir?: string;
      updatedAt?: string;
    }>("/api/runtime/beta"),
  listProjects: (init?: RequestInit) => req<Project[]>("/api/projects", init),
  createProject: (
    name: string,
    opts?: {
      primary_project_type?: string;
      project_traits?: string[];
      profile_overrides?: Record<string, unknown>;
      width?: number;
      height?: number;
      fps?: number;
    }
  ) =>
    req<Project>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        width: opts?.width ?? 1280,
        height: opts?.height ?? 720,
        fps: opts?.fps ?? 24,
        preset: "quality",
        vram_gb: 32,
        primary_project_type: opts?.primary_project_type,
        project_traits: opts?.project_traits || [],
        profile_overrides: opts?.profile_overrides || {},
      }),
    }),
  getProject: (id: string, init?: RequestInit) => req<Project>(`/api/projects/${id}`, init),
  getProjectProfile: (id: string) => req<any>(`/api/projects/${id}/project-profile`),
  previewProjectTypeChange: (
    id: string,
    body: { primaryProjectType: string; projectTraits?: string[]; overrides?: Record<string, unknown> }
  ) =>
    req<any>(`/api/projects/${id}/project-type/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  applyProjectTypeChange: (
    id: string,
    body: {
      primaryProjectType: string;
      projectTraits?: string[];
      overrides?: Record<string, unknown>;
      applyDimensionDefaults?: boolean;
    }
  ) =>
    req<any>(`/api/projects/${id}/project-type`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listProjectTypes: (primaryOnly = true) =>
    req<{ types: any[] }>(`/api/templates-presets/project-types?primaryOnly=${primaryOnly ? "true" : "false"}`),
  saveCustomProjectType: (body: { projectId: string; slug: string; displayName?: string }) =>
    req<any>("/api/templates-presets/project-types/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateProject: (id: string, body: Partial<Project> & { apply_vram_profile?: boolean }) =>
    req<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  vramPresets: () =>
    req<
      {
        vram_gb: number;
        label: string;
        width: number;
        height: number;
        fps: number;
        max_duration_sec: number;
        max_frames: number;
        steps_draft: number;
        steps_quality: number;
        image_tool_size: number;
        lipsync_size: number;
        lipsync_steps: number;
        assist_chunk_frames: number;
        recommended_engine: string;
        summary: string;
        assists: string[];
      }[]
    >("/api/vram-presets"),
  vramDetect: () =>
    req<{ detected_gb: number | null; tier: number | null; message: string }>("/api/vram-detect"),
  gpuStats: () =>
    req<{
      ok: boolean;
      message: string;
      gpus: {
        index: number;
        name: string;
        driver_version: string;
        memory_total_mib?: number | null;
        memory_used_mib?: number | null;
        memory_free_mib?: number | null;
        memory_used_pct?: number | null;
        temperature_c?: number | null;
        utilization_gpu_pct?: number | null;
        utilization_memory_pct?: number | null;
        power_draw_w?: number | null;
        fan_speed_pct?: number | null;
      }[];
      primary_index: number;
      recommended_tier: number | null;
    }>("/api/gpu/stats"),
  deleteProject: (id: string) => req(`/api/projects/${id}`, { method: "DELETE" }),
  listEngines: () => req<{ id: string; label: string; group: string }[]>("/api/engines"),
  falModels: () =>
    req<
      {
        engine: string;
        label: string;
        provider: string;
        model_id: string;
        mode: string;
        media_type: string;
        durations: number[];
        default_duration: number;
        supports_end_image: boolean;
        description: string;
      }[]
    >("/api/fal/models"),
  hostedProvidersCatalog: () => req<any>("/api/hosted-providers"),
  hostedProvidersRegistry: () => req<any>("/api/hosted-providers/registry"),
  hostedProvidersConnect: (providerId: string, api_key: string) =>
    req<any>(`/api/hosted-providers/${encodeURIComponent(providerId)}/key`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    }),
  hostedProvidersTest: (providerId: string) =>
    req<any>(`/api/hosted-providers/${encodeURIComponent(providerId)}/test`, { method: "POST" }),
  hostedProvidersClear: (providerId: string) =>
    req<any>(`/api/hosted-providers/${encodeURIComponent(providerId)}/key`, { method: "DELETE" }),
  hostedProvidersSetPreferred: (preferredProvider: "kie" | "wavespeed" | "fal" | "automatic") =>
    req<any>("/api/hosted-providers/preferences/preferred", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preferredProvider }),
    }),
  hostedProvidersDiscover: (providerId?: string) =>
    req<any>(
      providerId
        ? `/api/hosted-providers/discovery?providerId=${encodeURIComponent(providerId)}`
        : "/api/hosted-providers/discovery",
      { method: "POST" },
    ),
  hostedProvidersDiscoveryStatus: () => req<any>("/api/hosted-providers/discovery"),
  hostedProvidersDiscoveredModels: (modality?: string) =>
    req<any>(
      modality
        ? `/api/hosted-providers/discovered-models?modality=${encodeURIComponent(modality)}`
        : "/api/hosted-providers/discovered-models",
    ),
  hostedProvidersResolve: (body: { capability?: string; canonicalModel?: string }) =>
    req<any>("/api/hosted-providers/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  hostedProvidersGetPreferences: () => req<any>("/api/hosted-providers/preferences"),
  hostedProvidersPutPreferences: (body: {
    preferredProvider?: "kie" | "wavespeed" | "fal" | "automatic";
    budgetPreference?: "low_cost" | "balanced" | "quality" | string;
  }) =>
    req<any>("/api/hosted-providers/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preferredProvider: body.preferredProvider ?? "automatic",
        budgetPreference: body.budgetPreference,
      }),
    }),
  hostedProvidersListOpenAICompatible: () => req<any>("/api/hosted-providers/openai-compatible"),
  hostedProvidersConnectOpenAICompatible: (body: {
    displayName?: string;
    baseUrl: string;
    api_key: string;
    modelsPath?: string;
    chatPath?: string;
    billingCurrency?: string;
    endpointId?: string;
  }) =>
    req<any>("/api/hosted-providers/openai-compatible", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  hostedProvidersDeleteOpenAICompatible: (endpointId: string) =>
    req<any>(`/api/hosted-providers/openai-compatible/${encodeURIComponent(endpointId)}`, {
      method: "DELETE",
    }),
  modelStorageGet: () => req<any>("/api/model-storage"),
  modelStoragePutRoot: (category: string, path: string) =>
    req<any>("/api/model-storage/roots", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, path }),
    }),
  modelStorageRegisterFolder: (body: {
    path: string;
    runtimeType?: string;
    label?: string;
    category?: string;
    importIntoLibrary?: boolean;
  }) =>
    req<any>("/api/model-storage/folders/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  modelStorageRefreshFolder: (folderId: string) =>
    req<any>(`/api/model-storage/folders/${encodeURIComponent(folderId)}/refresh`, { method: "POST" }),
  modelStorageUnregisterFolder: (folderId: string) =>
    req<any>(`/api/model-storage/folders/${encodeURIComponent(folderId)}`, { method: "DELETE" }),
  modelStorageClassify: (path: string) =>
    req<any>("/api/model-storage/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
  modelStorageValidate: (path: string, runtimeType?: string) =>
    req<any>("/api/model-storage/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, runtimeType }),
    }),
  providerUsageSummary: (projectId?: string, providerId?: string) => {
    const q = new URLSearchParams();
    if (projectId) q.set("projectId", projectId);
    if (providerId) q.set("providerId", providerId);
    const qs = q.toString();
    return req<any>(`/api/provider-usage/summary${qs ? `?${qs}` : ""}`);
  },
  providerUsageDock: (projectId?: string) =>
    req<any>(`/api/provider-usage/dock${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`),
  providerUsageBudgets: () => req<any>("/api/provider-usage/budgets"),
  providerUsagePutBudgets: (body: Record<string, unknown>) =>
    req<any>("/api/provider-usage/budgets", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  providerUsagePreflight: (body: {
    providerId: string;
    capability?: string;
    units?: number;
    projectId?: string;
    estimatedCost?: number;
    approved?: boolean;
  }) =>
    req<any>("/api/provider-usage/preflight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  providerUsageRecord: (body: Record<string, unknown>) =>
    req<any>("/api/provider-usage/records", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  falKeyStatus: () => req<FalKeyStatus>("/api/fal/key"),
  falKeySet: (api_key: string) =>
    req<FalKeyStatus>("/api/fal/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    }),
  falKeyValidate: () => req<FalKeyStatus>("/api/fal/key/validate", { method: "POST" }),
  falKeyClear: () =>
    req<FalKeyStatus>("/api/fal/key", {
      method: "DELETE",
    }),
  falUsage: (days = 30) =>
    req<{
      ok: boolean;
      configured: boolean;
      username?: string | null;
      balance?: number | null;
      currency: string;
      period_days: number;
      usage_units: number;
      usage_unit_label: string;
      spend: number;
      request_count: number;
      top_endpoints: { endpoint_id: string; quantity: number; unit: string; cost: number; currency: string }[];
      manage_url: string;
      billing_url: string;
      keys_url: string;
      login_url: string;
      message: string;
      needs_admin_key: boolean;
    }>(`/api/fal/usage?days=${days}`),
  addScene: (projectId: string, body: Partial<Scene>) =>
    req<Scene>(`/api/projects/${projectId}/scenes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateScene: (projectId: string, sceneId: string, body: Partial<Scene>) =>
    req<Scene>(`/api/projects/${projectId}/scenes/${sceneId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteScene: (projectId: string, sceneId: string) =>
    req(`/api/projects/${projectId}/scenes/${sceneId}`, { method: "DELETE" }),
  uploadAsset: async (
    projectId: string,
    file: File,
    tag: string,
    kind: string,
    opts?: { signal?: AbortSignal },
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tag", tag);
    fd.append("kind", kind);
    return req<Asset>(`/api/projects/${projectId}/assets`, { method: "POST", body: fd, signal: opts?.signal });
  },
  getSpatial: (projectId: string) => req<SpatialMap>(`/api/projects/${projectId}/spatial`),
  putSpatial: (projectId: string, body: SpatialMap) =>
    req<SpatialMap>(`/api/projects/${projectId}/spatial`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  render: (
    projectId: string,
    kind: "scene" | "shot" | "timeline" | "batch_timeline" | "editor_mix",
    sceneId?: string,
    extras?: {
      reference_method?: string;
      sheet_id?: string;
      strength_preset?: string;
      strength?: number;
      ingredients_ic_lora?: boolean;
      /** Absolute path to primary video for editor_mix (optional). */
      primary_video_path?: string;
      /** Wave 6P production intent id when compiled client-side / via Co-Director. */
      productionIntentId?: string;
      shot_id?: string;
    },
  ) =>
    req<Job>(`/api/projects/${projectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind,
        scene_id: sceneId ?? null,
        retake: kind === "scene" || kind === "shot",
        ...(extras || {}),
      }),
    }),
  videoRuntimeWave6pGate: () => req<Record<string, unknown>>(`/api/video-runtime/wave6p-gate`),
  referenceCapabilities: (projectId: string) =>
    req<any>(`/api/projects/${projectId}/references/capabilities`),
  listReferenceIngredients: (projectId: string) =>
    req<{ items: any[] }>(`/api/projects/${projectId}/references/ingredients`),
  upsertReferenceIngredient: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/references/ingredients`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  buildReferenceSheet: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/references/sheets/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getReferenceSheet: (projectId: string, sheetId: string) =>
    req<any>(`/api/projects/${projectId}/references/sheets/${sheetId}`),
  validateReferenceSheet: (projectId: string, sheetId: string) =>
    req<any>(`/api/projects/${projectId}/references/sheets/${sheetId}/validate`, {
      method: "POST",
    }),
  listReferencePresets: (projectId: string) =>
    req<{ items: any[] }>(`/api/projects/${projectId}/references/presets`),
  saveReferencePreset: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/references/presets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  reuseReferencePreset: (projectId: string, presetId: string) =>
    req<any>(`/api/projects/${projectId}/references/presets/${presetId}/reuse`, {
      method: "POST",
    }),
  assetReferencesUsed: (projectId: string, assetId: string) =>
    req<any>(`/api/projects/${projectId}/assets/${assetId}/references-used`),
  lipsync: (projectId: string, sceneId: string, audioAssetId?: string) =>
    req<Job>(`/api/projects/${projectId}/lipsync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scene_id: sceneId, audio_asset_id: audioAssetId ?? null }),
    }),
  exportPack: (projectId: string) =>
    req<Job>(`/api/projects/${projectId}/export`, { method: "POST" }),
  listJobs: (projectId: string) => req<Job[]>(`/api/projects/${projectId}/jobs`),
  getJob: (jobId: string) => req<Job>(`/api/jobs/${jobId}`),
  cancelJob: (jobId: string) => req(`/api/jobs/${jobId}/cancel`, { method: "POST" }),
  characterSheet: (
    projectId: string,
    body: {
      source_asset_id: string;
      character_name?: string;
      seed?: number;
      width?: number;
      height?: number;
      extra_prompt?: string;
    }
  ) =>
    req<Job>(`/api/projects/${projectId}/tools/character-sheet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  multiAngle: (
    projectId: string,
    body: {
      source_asset_id: string;
      character_name?: string;
      seed?: number;
      width?: number;
      height?: number;
      extra_prompt?: string;
      angle_prompts?: string[];
    }
  ) =>
    req<Job>(`/api/projects/${projectId}/tools/multi-angle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getLipSyncTracks: (projectId: string, sceneId: string) =>
    req<{ tracks: any[] }>(`/api/projects/${projectId}/scenes/${sceneId}/lipsync-tracks`),
  putLipSyncTracks: (projectId: string, sceneId: string, body: { tracks: any[] }) =>
    req<{ tracks: any[] }>(`/api/projects/${projectId}/scenes/${sceneId}/lipsync-tracks`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  bakeLipSyncTracks: (projectId: string, sceneId: string) =>
    req<{ ok: boolean; tracks: { tracks: any[] }; preview_dir?: string }>(
      `/api/projects/${projectId}/scenes/${sceneId}/lipsync-tracks/bake`,
      { method: "POST" }
    ),
  applyLipSyncTracks: (projectId: string, sceneId: string) =>
    req<Job>(`/api/projects/${projectId}/scenes/${sceneId}/lipsync-tracks/apply`, { method: "POST" }),
  getDirector: (projectId: string, sceneId: string) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director`),
  getTimelineReferences: (projectId: string, sceneId: string, itemId: string) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references`),
  addTimelineReference: (projectId: string, sceneId: string, itemId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchTimelineReference: (
    projectId: string,
    sceneId: string,
    itemId: string,
    bindingId: string,
    body: Record<string, unknown>
  ) =>
    req<any>(
      `/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references/${bindingId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),
  deleteTimelineReference: (projectId: string, sceneId: string, itemId: string, bindingId: string) =>
    req<any>(
      `/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references/${bindingId}`,
      { method: "DELETE" }
    ),
  clearTimelineReferences: (projectId: string, sceneId: string, itemId: string) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }),
  getTimelineReferencePackage: (projectId: string, sceneId: string, itemId: string) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/reference-package`),
  continuityPreviousReference: (projectId: string, sceneId: string, itemId: string) =>
    req<any>(
      `/api/projects/${projectId}/scenes/${sceneId}/director/items/${itemId}/references/continuity-previous`,
      { method: "POST" }
    ),
  listTimelineReferencePresets: (projectId: string) =>
    req<any[]>(`/api/projects/${projectId}/reference-presets`),
  putDirector: (projectId: string, sceneId: string, body: any) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/director`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  recommendEngine: (projectId: string, sceneId: string) =>
    req<{
      engineId: string;
      confidence: number;
      reasons: string[];
      warnings: string[];
      local: boolean;
      vram_tier: number;
      profile_engine: string;
    }>(`/api/projects/${projectId}/scenes/${sceneId}/recommend-engine`, { method: "POST" }),
  proposeTimeline: (projectId: string, brief: string) =>
    req<{
      summary: string;
      scenes: {
        name: string;
        prompt: string;
        duration_sec: number;
        engine?: EngineName | null;
        camera_note?: string;
      }[];
      warnings: string[];
    }>(`/api/projects/${projectId}/timeline/propose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief }),
    }),
  applyTimeline: (
    projectId: string,
    body: {
      scenes: {
        name: string;
        prompt: string;
        duration_sec: number;
        engine?: EngineName | null;
        camera_note?: string;
      }[];
      replace_existing?: boolean;
      enqueue_render?: boolean;
    }
  ) =>
    req<{ ok: boolean; created_scene_ids: string[]; replaced: boolean; job_id?: string | null }>(
      `/api/projects/${projectId}/timeline/apply`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),
  assistantHealth: () =>
    req<{ ok: boolean; ollama_reachable: boolean; model: string; available_models: string[]; message: string }>(
      "/api/assistant/health"
    ),
  assistantChat: (body: {
    messages: { role: string; content: string }[];
    project_id?: string;
    scene_id?: string;
    model?: string;
    mode?: "chat" | "prompt" | "guide" | "setup";
  }) =>
    req<{
      reply: string;
      model: string;
      suggested_prompt?: string | null;
      scene_setup?: SceneSetup | null;
    }>("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  assistantApplySetup: (body: {
    project_id: string;
    scene_id: string;
    setup: SceneSetup;
  }) =>
    req<{
      ok: boolean;
      applied: string[];
      warnings: string[];
      scene_id: string;
      project_id: string;
    }    >("/api/assistant/apply-setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorProviders: () =>
    req<{ providers: { id: string; displayName: string; active: boolean }[] }>("/api/codirector/providers"),
  codirectorHealth: (providerId: string = "active") =>
    req<{
      providerId: string;
      displayName: string;
      status: string;
      reachable: boolean;
      endpoint: string;
      selectedModel: string | null;
      modelAvailable: boolean;
      intelligenceEnabled?: boolean;
      visionValidationEnabled?: boolean;
      productionExecutiveEnabled?: boolean;
      productionIntelligenceEnabled?: boolean;
      modelRadarEnabled?: boolean;
      sandboxRuntimeEnabled?: boolean;
      virtualStageEnabled?: boolean;
      virtualEnvironmentStudioEnabled?: boolean;
      unifiedExperienceEnabled?: boolean;
      audioProductionEnabled?: boolean;
      directorTimelineEnabled?: boolean;
      shotProfilesEnabled?: boolean;
      productionRecipeEnabled?: boolean;
      locationSpinEnabled?: boolean;
  timelineReferencesEnabled?: boolean;
      models: {
        id: string;
        name: string;
        sizeBytes?: number | null;
        modifiedAt?: string | null;
        family?: string | null;
        parameterSize?: string | null;
        quantization?: string | null;
      }[];
      message: string;
      code?: string | null;
      recommendedAction?: string | null;
      testOnly?: boolean;
      honesty?: string | null;
      ok: boolean;
    }>(`/api/codirector/providers/${encodeURIComponent(providerId)}/health`),
  codirectorSessionContext: (opts?: { projectId?: string; sceneId?: string; workspace?: string }) => {
    const params = new URLSearchParams();
    if (opts?.projectId) params.set("project_id", opts.projectId);
    if (opts?.sceneId) params.set("scene_id", opts.sceneId);
    if (opts?.workspace) params.set("workspace", opts.workspace);
    const q = params.toString();
    return req<{
      projectId?: string | null;
      projectName?: string | null;
      activeDocumentId?: string | null;
      activeSceneId?: string | null;
      activeWorkspace?: string | null;
      selectedAssets: string[];
      provider?: string | null;
      model?: string | null;
      activeProductionPlan?: Record<string, unknown> | null;
      activePlanId?: string | null;
      activePlanVersion?: number | null;
      activePlanState?: string | null;
      sessionStatus: string;
      lastSuccessfulToolAction?: string | null;
      unresolvedBlockers: string[];
    }>(`/api/codirector/session-context${q ? `?${q}` : ""}`);
  },
  codirectorStatusRegistry: () =>
    req<{
      checks: StatusRegistryCheck[];
      modes: Record<string, { default: boolean; description: string }>;
    }>("/api/codirector/status/registry"),
  codirectorStatusCheck: (body: {
    projectId?: string;
    sceneId?: string;
    workspace?: string;
    checkIds?: string[];
  }) =>
    req<StatusRun>("/api/codirector/status/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorStatusCheckComponent: (
    checkId: string,
    body: {
      projectId?: string;
      sceneId?: string;
      workspace?: string;
      checkIds?: string[];
    },
  ) =>
    req<StatusRun>(`/api/codirector/status/check/${encodeURIComponent(checkId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorDeepDiagnostic: (body: {
    projectId?: string;
    sceneId?: string;
    workspace?: string;
    checkIds?: string[];
    confirm: boolean;
  }) =>
    req<StatusRun>("/api/codirector/status/deep-diagnostic", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorStatusLatest: (opts?: { projectId?: string; sceneId?: string }) => {
    const params = new URLSearchParams();
    if (opts?.projectId) params.set("projectId", opts.projectId);
    if (opts?.sceneId) params.set("sceneId", opts.sceneId);
    const q = params.toString();
    return req<{ run: StatusRun | null }>(`/api/codirector/status/latest${q ? `?${q}` : ""}`);
  },
  codirectorStatusHistory: (opts?: { projectId?: string; sceneId?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.projectId) params.set("projectId", opts.projectId);
    if (opts?.sceneId) params.set("sceneId", opts.sceneId);
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    const q = params.toString();
    return req<{ runs: StatusRun[] }>(`/api/codirector/status/history${q ? `?${q}` : ""}`);
  },
  codirectorModels: (providerId: string = "active") =>
    req<{ models: { id: string; name: string }[] }>(
      `/api/codirector/providers/${encodeURIComponent(providerId)}/models`,
    ),
  codirectorChat: (
    body: {
      messages: { role: string; content: string }[];
      project_id?: string;
      scene_id?: string;
      model?: string;
      provider_id?: string;
      mode?: "chat" | "prompt" | "guide" | "setup";
      request_id?: string;
      attachment_ids?: string[];
    },
    opts?: { signal?: AbortSignal },
  ) =>
    req<{
      requestId: string;
      reply: string;
      model: string;
      providerId: string;
      suggestedPrompt?: string | null;
      sceneSetup?: SceneSetup | null;
    }>("/api/codirector/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: opts?.signal,
    }),
  codirectorChatStream: async (
    body: {
      messages: { role: string; content: string }[];
      project_id?: string;
      scene_id?: string;
      model?: string;
      provider_id?: string;
      mode?: "chat" | "prompt" | "guide" | "setup";
      request_id?: string;
      origin_session_id?: string;
      attachment_ids?: string[];
    },
    opts: { signal?: AbortSignal; onEvent: (event: CoDirectorStreamEvent) => void },
  ): Promise<void> => {
    let res: Response;
    try {
      res = await fetch(`${BASE}/api/codirector/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (error) {
      if (isAbortError(error) || opts.signal?.aborted) {
        throw error instanceof Error ? error : new DOMException("Aborted", "AbortError");
      }
      throw error;
    }
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      let detail: unknown;
      try {
        const payload = JSON.parse(text) as { detail?: unknown; error?: unknown };
        detail = payload.detail ?? payload.error;
      } catch {
        detail = undefined;
      }
      if (detail && typeof detail === "object") {
        const d = detail as ApiErrorDetailShape;
        const code = d.error_code || d.code;
        throw new ApiError(d.message || text || res.statusText, res.status, {
          code,
          details: d.details,
          recoverable: d.recoverable ?? d.retryable,
          recommendedAction: d.recommendedAction || d.recommended_action,
          category: d.category,
          retryable: d.retryable ?? d.recoverable,
          project_id: d.project_id,
          provider: d.provider,
          model: d.model,
          technical_evidence: d.technical_evidence,
          partial_work_created: d.partial_work_created,
        });
      }
      throw new ApiError(text || res.statusText, res.status);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx: number;
        // SSE frames are separated by a blank line.
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
          if (!dataLine) continue;
          const jsonStr = dataLine.slice(5).trim();
          if (!jsonStr) continue;
          try {
            opts.onEvent(JSON.parse(jsonStr) as CoDirectorStreamEvent);
          } catch {
            /* ignore malformed SSE frame */
          }
        }
      }
    } catch (error) {
      if (isAbortError(error) || opts.signal?.aborted) {
        throw error instanceof Error ? error : new DOMException("Aborted", "AbortError");
      }
      throw error;
    }
  },
  codirectorCancel: (requestId: string) =>
    req<{ requestId: string; cancelled: boolean; taskCancelled: boolean }>("/api/codirector/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId }),
    }),
  codirectorDeferNextStep: (
    projectId: string,
    body: { optionType: string; userReason?: string; reconsiderAfterStage?: string },
  ) =>
    req<{ ok: boolean; projectId: string }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/next-steps/defer`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  codirectorConfig: () =>
    req<{ endpoint: string; selectedModel: string | null; timeoutSec: number }>("/api/codirector/config"),
  codirectorUpdateConfig: (body: { endpoint?: string; selectedModel?: string | null; timeoutSec?: number }) =>
    req<{ endpoint: string; selectedModel: string | null; timeoutSec: number }>("/api/codirector/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorGetConversation: (projectId: string) =>
    req<{
      projectId: string;
      messages: { id?: string; role: string; content: string; created_at?: string }[];
      model: string | null;
      providerId: string | null;
      updatedAt: string | null;
      revision?: number;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`),
  codirectorAppendConversationEvents: (
    projectId: string,
    body: {
      events: Array<{
        role: string;
        content?: string;
        event_type?: string;
        message_id?: string;
        client_request_id?: string;
        message_type?: string;
        status?: string;
        attachments?: Array<{ assetId?: string; asset_id?: string; name?: string; mimeType?: string; mime_type?: string; source?: string; kind?: string }>;
        tool_id?: string;
        tool_arguments?: Record<string, unknown>;
        tool_result?: Record<string, unknown>;
        request_id?: string;
        actor?: string;
        created_at?: string;
      }>;
      expected_revision?: number | null;
      model?: string | null;
      provider_id?: string | null;
    },
  ) =>
    req<{
      projectId: string;
      appendedCount: number;
      duplicateCount: number;
      revision: number;
      events: Array<{ id?: string; role: string; content: string; created_at?: string }>;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorSaveConversation: (
    projectId: string,
    body: { messages: { id?: string; role: string; content: string; created_at?: string }[]; model?: string | null; provider_id?: string | null; expected_revision?: number | null; allow_admin_replace?: boolean },
  ) =>
    req<{
      projectId: string;
      messages: { id?: string; role: string; content: string; created_at?: string }[];
      model: string | null;
      providerId: string | null;
      updatedAt: string | null;
      revision?: number;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorDeleteConversation: (projectId: string) =>
    req<{ ok: boolean; projectId: string }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }),
  codirectorGetConversationRevision: (projectId: string) =>
    req<{ projectId: string; revision: number; updatedAt: string | null }>(
      `/api/codirector/conversations/${encodeURIComponent(projectId)}/revision`,
    ),
  codirectorCompactConversation: (
    projectId: string,
    body: { beforeSequence: number; summaryText: string; requestId?: string },
  ) =>
    req<{
      projectId: string;
      requestId: string;
      compactedThroughSequence: number;
      appendedCount: number;
      duplicateCount: number;
      revision: number;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}/compact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorMemoryExport: (projectId: string) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/memory/export`),
  codirectorMemoryImport: (projectId: string, bundle: Record<string, unknown>) =>
    req<{
      projectId: string;
      appendedCount: number;
      duplicateCount: number;
      revision: number;
      restored: string[];
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/memory/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bundle }),
    }),
  codirectorIntelligenceSnapshot: (projectId: string) =>
    req<{ projectId: string; snapshot: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/intelligence/snapshot`,
    ),
  getCoDirectorRelationship: (projectId: string) =>
    req<{
      projectId: string;
      relationship: Record<string, unknown>;
      creator: Record<string, unknown>;
      brief: Record<string, unknown>;
      pulse: Record<string, unknown>;
      wikiCandidateCount: number;
      discoveryQuestions: Record<string, unknown>[];
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/relationship`),
  updateCoDirectorRelationship: (
    projectId: string,
    body: {
      skip?: boolean;
      assistantPreferredName?: string;
      userPreferredName?: string;
      primaryRole?: string;
      initiativeLevel?: string;
      feedbackStyle?: string;
      narrationMode?: string;
      documentationMode?: string;
      researchPermission?: string;
      defaultOwnership?: string;
      relationshipScope?: string;
    },
  ) =>
    req<{ projectId: string; relationship: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/relationship`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  getCreativeOperating: (projectId: string) =>
    req<{
      ok: boolean;
      projectId: string;
      initiativeLevel: string;
      initiativeLabel?: string;
      initiativeTips?: Record<string, string>;
      creativeStage?: string;
      projectFormat?: string;
      curiosityThreads?: Record<string, unknown>[];
      forwardSuggestions?: Record<string, unknown>[];
      lastDecision?: Record<string, unknown> | null;
      lastDisagreement?: Record<string, unknown> | null;
      episodeProgression?: Record<string, unknown> | null;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating`),
  setCreativeInitiative: (projectId: string, initiativeLevel: string) =>
    req<{ ok: boolean; projectId: string; initiativeLevel: string }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/initiative`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initiativeLevel }),
      },
    ),
  postCreativeDecision: (
    projectId: string,
    body: { message: string; specialistPositions?: Record<string, string> },
  ) =>
    req<{
      ok: boolean;
      projectId: string;
      decision: Record<string, unknown>;
      curiosityThreads?: Record<string, unknown>[];
      forwardSuggestions?: Record<string, unknown>[];
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  dismissCreativeForward: (projectId: string, suggestionId: string) =>
    req<{ ok: boolean }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/forward/dismiss`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suggestionId }),
      },
    ),
  answerCreativeCuriosity: (projectId: string, threadId: string, dismiss = false) =>
    req<{ ok: boolean }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/curiosity/answer`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ threadId, dismiss }),
      },
    ),
  correctCreativeIdentity: (
    projectId: string,
    body: { surfaces: string[]; canonicalName: string },
  ) =>
    req<{ ok: boolean; preview?: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/identity/correct`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  analyzeCreativeScript: (
    projectId: string,
    body: { text: string; filename?: string; installmentHint?: string },
  ) =>
    req<{
      ok: boolean;
      role: string;
      breakdown: Record<string, unknown>;
      installment: Record<string, unknown>;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/creative-operating/script/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getCoDirectorPartnership: (projectId: string) =>
    req<{ projectId: string; partnership: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/partnership`,
    ),
  partnershipDeliverableAction: (
    projectId: string,
    body: { action: string; deliverableId?: string; content?: string },
  ) =>
    req<{
      projectId: string;
      ok: boolean;
      deliverable?: Record<string, unknown> | null;
      partnership?: Record<string, unknown>;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/partnership/deliverables`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorConversationAudit: (projectId: string) =>
    req<{
      projectId: string;
      healthy: boolean;
      sequenceMonotonic: boolean;
      uniqueMessageIds: boolean;
      revisionPresent: boolean;
      revision: number;
      eventCount: number;
      foldCount: number;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}/audit`),
  codirectorRebuildFold: (projectId: string) =>
    req<{
      projectId: string;
      healthy: boolean;
      sequenceMonotonic: boolean;
      uniqueMessageIds: boolean;
      revisionPresent: boolean;
      revision: number;
      eventCount: number;
      foldCount: number;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}/repair/rebuild-fold`, {
      method: "POST",
    }),
  codirectorOperatorAck: (
    requestId: string,
    payload: { originSessionId: string; workspace: string; target?: string; verified: boolean },
  ) =>
    req<{ ok: boolean; state: string }>(
      `/api/operator/${encodeURIComponent(requestId)}/ack`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    ),
  codirectorOperatorStatus: (requestId: string) =>
    req<{
      requestId: string;
      state: string;
      createdAt: string;
      originSessionId?: string;
      workspace?: string;
      target?: string;
      verified?: boolean;
    }>(`/api/operator/${encodeURIComponent(requestId)}`),
  setupDetect: () => req<SetupLegacyDetection>("/api/setup/detect"),
  setupState: () => req<SetupLegacyState>("/api/setup/state"),
  setupStatus: () => req<SetupStatusResponse>("/api/setup/status"),
  setupLifecycleComponents: (query = "", group?: string) => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    if (group?.trim()) params.set("group", group.trim());
    const qs = params.toString();
    return req<{ count: number; items: Array<{ componentId: string; name: string; statusLabel: string; group?: string; subgroup?: string; capabilityTags?: string[]; reason?: string }> }>(
      `/api/setup/lifecycle/components${qs ? `?${qs}` : ""}`
    );
  },
  setupLifecycleComponent: (componentId: string) =>
    req<{
      component: Record<string, unknown>;
      lifecycle: ProviderLifecycleState;
      metadata: Record<string, unknown>;
      installPlan: LifecycleInstallPlan;
      source: Record<string, unknown>;
    }>(`/api/setup/lifecycle/components/${encodeURIComponent(componentId)}`),
  setupLifecycleCompare: (componentIds: string[]) =>
    req<{ count: number; items: Record<string, unknown>[] }>("/api/setup/lifecycle/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ componentIds }),
    }),
  setupLifecycleRecipes: () => req<{ recipes: CertifiedRecipe[] }>("/api/setup/lifecycle/recipes"),
  setupLifecycleInstallPlan: (body: { componentId: string; action?: string; destinationRoot?: string }) =>
    req<LifecycleInstallPlan>("/api/setup/lifecycle/install-plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupLifecycleHardware: () => req<Record<string, unknown>>("/api/setup/lifecycle/hardware"),
  setupLifecycleCloudProviders: () => req<{ count: number; items: LifecycleCloudProvider[] }>("/api/setup/lifecycle/cloud-providers"),
  setupLifecycleVerify: (componentId: string) =>
    req<Record<string, unknown>>(`/api/setup/lifecycle/components/${encodeURIComponent(componentId)}/verify`, {
      method: "POST",
    }),
  setupLifecycleCalibrate: (componentId: string) =>
    req<Record<string, unknown>>(`/api/setup/lifecycle/components/${encodeURIComponent(componentId)}/calibrate`, {
      method: "POST",
    }),
  setupLifecycleCertify: (componentId: string) =>
    req<Record<string, unknown>>(`/api/setup/lifecycle/components/${encodeURIComponent(componentId)}/certify`, {
      method: "POST",
    }),
  setupLifecycleMonitor: () =>
    req<{ count: number; items: Array<{ componentId: string; statusLabel: string; findings: MonitorFinding[] }> }>("/api/setup/lifecycle/monitor"),
  setupPreparePlan: () =>
    req<StudioPreparationPlan>("/api/setup/prepare/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
  setupPrepare: () =>
    req<SetupOperation>("/api/setup/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
  setupOperation: (operationId: string) =>
    req<SetupOperation>(`/api/setup/operations/${encodeURIComponent(operationId)}`),
  setupCheckpoint: (operationId: string, answer: SetupCheckpointAnswer) =>
    req<SetupOperation>(`/api/setup/operations/${encodeURIComponent(operationId)}/checkpoint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(answer),
    }),
  setupBrowsePath: (body: {
    mode?: "directory" | "file";
    start_dir?: string;
    title?: string;
    component_id?: string;
    forced_path?: string;
  } = {}) =>
    req<{ path: string | null; cancelled: boolean; e2e_forced?: boolean }>("/api/setup/browse-path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupSuggestedPath: (componentId: string) =>
    req<{ component_id: string; suggested_path: string; path_selector?: "directory" | "file" }>(
      `/api/setup/components/${encodeURIComponent(componentId)}/suggested-path`,
    ),
  setupDiagnostics: (componentId: string) =>
    req<ComponentDiagnosticResult>(`/api/setup/components/${encodeURIComponent(componentId)}/diagnostics`, {
      method: "POST",
    }),
  setupRecommendedAction: (componentId: string) =>
    req<SetupOperation>(`/api/setup/components/${encodeURIComponent(componentId)}/recommended-action`, {
      method: "POST",
    }),
  setupRefreshSource: (componentId: string) =>
    req<{
      component_id: string;
      source_valid: boolean;
      source_host?: string | null;
      version?: string;
      error?: { code: string; message: string } | null;
    }>(`/api/setup/components/${encodeURIComponent(componentId)}/refresh-source`, {
      method: "POST",
    }),
  setupLinkExisting: (componentId: string) =>
    req<SetupOperation>(`/api/setup/components/${encodeURIComponent(componentId)}/link-existing`, {
      method: "POST",
    }),
  setupChooseInstallLocation: (componentId: string) =>
    req<SetupOperation>(
      `/api/setup/components/${encodeURIComponent(componentId)}/choose-install-location`,
      { method: "POST" },
    ),
  setupDownloadSources: () => req<DownloadSourcesResponse>("/api/setup/download-sources"),
  setupDetectDownloadSource: (provider: string) =>
    req<DownloadSourcesResponse["github"]>(
      `/api/setup/download-sources/${encodeURIComponent(provider)}/detect`,
      { method: "POST" },
    ),
  setupVerifyDownloadSource: (provider: string) =>
    req<DownloadSourcesResponse["github"]>(
      `/api/setup/download-sources/${encodeURIComponent(provider)}/verify`,
      { method: "POST" },
    ),
  setupSignInDownloadSource: (provider: string, body: { launch?: boolean } = { launch: true }) =>
    req<{
      provider: string;
      command_summary?: string;
      message?: string;
      requires_confirmation?: boolean;
      launched?: boolean;
      launch_error?: string;
      command?: string[];
    }>(`/api/setup/download-sources/${encodeURIComponent(provider)}/sign-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupInstallDownloadSourceCli: (provider: string, body: { confirm?: boolean; method?: string } = {}) =>
    req<Record<string, unknown>>(`/api/setup/download-sources/${encodeURIComponent(provider)}/install`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupVerifySourceUrl: (body: {
    url: string;
    component_id?: string;
    revision?: string;
    asset_name?: string;
    selected_files?: string[];
  }) =>
    req<SourceVerificationResult>("/api/setup/sources/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupListSourceFiles: (body: { url: string; revision?: string }) =>
    req<{ ok?: boolean; files?: SourceVerificationResult["files"] }>("/api/setup/sources/list-files", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  setupSaveSourceOverride: (
    componentId: string,
    body: { url?: string; verification?: SourceVerificationResult; revision?: string; assetName?: string },
  ) =>
    req<{ ok: boolean; override: Record<string, unknown>; verification: SourceVerificationResult }>(
      `/api/setup/components/${encodeURIComponent(componentId)}/source-override`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  setupClearSourceOverride: (componentId: string) =>
    req<{ ok: boolean }>(`/api/setup/components/${encodeURIComponent(componentId)}/source-override`, {
      method: "DELETE",
    }),
  // --- capability registry ------------------------------------------------
  // The truth source for "can this be used right now?". Read-only; `refreshCapabilities`
  // re-probes the environment and never installs or downloads anything.
  capabilities: (opts?: { projectId?: string; refresh?: boolean; signal?: AbortSignal }) => {
    const params = new URLSearchParams();
    if (opts?.projectId) params.set("projectId", opts.projectId);
    if (opts?.refresh) params.set("refresh", "true");
    const query = params.toString();
    return req<CapabilitySnapshot>(`/api/capabilities${query ? `?${query}` : ""}`, {
      signal: opts?.signal,
    });
  },
  projectCapabilities: (projectId: string, opts?: { refresh?: boolean; signal?: AbortSignal }) =>
    req<CapabilitySnapshot>(
      `/api/projects/${encodeURIComponent(projectId)}/capabilities${opts?.refresh ? "?refresh=true" : ""}`,
      { signal: opts?.signal },
    ),
  capability: (capabilityId: string, opts?: { projectId?: string }) =>
    req<Capability>(
      `/api/capabilities/${encodeURIComponent(capabilityId)}${
        opts?.projectId ? `?projectId=${encodeURIComponent(opts.projectId)}` : ""
      }`,
    ),
  refreshCapabilities: (projectId?: string) =>
    req<CapabilitySnapshot>(
      `/api/capabilities/refresh${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
      { method: "POST" },
    ),
  comfyHealth: () => req<ComfyHealth>("/api/comfy/health"),
  listWorkflows: () => req<{ workflows: WorkflowDescriptor[] }>("/api/workflows"),
  workflowReadiness: (workflowId: string) =>
    req<WorkflowReadiness>(`/api/workflows/${encodeURIComponent(workflowId)}/readiness`),
  sourceManagerOverview: () => req<SourceManagerOverview>("/api/source-manager/overview"),
  sourceManagerVoiceModels: () =>
    req<{ components: Record<string, unknown>[]; count: number }>("/api/source-manager/voice-models"),
  sourceManagerVoiceModelInstall: (
    componentId: string,
    body?: { confirm?: boolean; confirmDownloadModels?: boolean },
  ) =>
    req<{
      operation?: Record<string, unknown>;
      componentId: string;
      runtime?: Record<string, unknown>;
      confirmDownloadModels?: boolean;
      downloadDeferred?: boolean;
    }>(`/api/source-manager/voice-models/${encodeURIComponent(componentId)}/install`, {
      method: "POST",
      body: JSON.stringify({
        confirm: body?.confirm ?? true,
        confirmDownloadModels: body?.confirmDownloadModels ?? false,
      }),
    }),
  sourceManagerVoiceModelUninstall: (componentId: string) =>
    req<Record<string, unknown>>(
      `/api/source-manager/voice-models/${encodeURIComponent(componentId)}/uninstall`,
      { method: "POST" },
    ),
  sourceManagerProviders: () =>
    req<{ providers: SourceManagerOverview["providers"] }>("/api/source-manager/providers"),
  sourceManagerDeleteSource: (sourceId: string) =>
    req<{ ok: boolean }>(`/api/source-manager/sources/${encodeURIComponent(sourceId)}`, {
      method: "DELETE",
    }),
  sourceManagerVerify: (body: { url: string; componentId?: string; revision?: string }) =>
    req<Record<string, unknown>>("/api/source-manager/sources/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  sourceManagerSelectProvider: (body: {
    url?: string;
    localPath?: string;
    providerHint?: string;
    revision?: string;
    componentId?: string;
  }) =>
    req<{
      providerId: string;
      provider: SourceManagerOverview["providers"][number];
    }>("/api/source-manager/select-provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  sourceManagerAssignComponentSource: (
    componentId: string,
    body: {
      url?: string;
      sourceUrl?: string;
      verification?: SourceVerificationResult | Record<string, unknown>;
      revision?: string;
      assetName?: string;
      selectedFiles?: string[];
    },
  ) =>
    req<{
      override?: Record<string, unknown>;
      source?: Record<string, unknown>;
      assignment?: Record<string, unknown>;
    }>(`/api/source-manager/components/${encodeURIComponent(componentId)}/source`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  sourceManagerRemoveComponentSource: (componentId: string) =>
    req<{
      componentId: string;
      removedOverride?: boolean;
      removedSource?: boolean;
      sourceId?: string | null;
    }>(`/api/source-manager/components/${encodeURIComponent(componentId)}/source`, {
      method: "DELETE",
    }),
  installJobs: {
    list: async (opts?: { active?: boolean; componentId?: string; signal?: AbortSignal }) => {
      const params = new URLSearchParams();
      if (opts?.active) params.set("active", "true");
      if (opts?.componentId) params.set("componentId", opts.componentId);
      const query = params.toString();
      const data = await req<{ jobs?: InstallJob[]; items?: InstallJob[]; operations?: InstallJob[] }>(
        `/api/setup/install-jobs${query ? `?${query}` : ""}`,
        { signal: opts?.signal },
      );
      return data.jobs ?? data.items ?? data.operations ?? [];
    },
    create: (componentId: string, body: {
      projectId?: string;
      destinationRoot?: string;
      confirm?: boolean;
      confirmDownloadModels?: boolean;
      sourceId?: string;
      sourceUrl?: string;
      revision?: string;
      providerHint?: string;
      action?: "install" | "repair" | "verify" | string;
    }) =>
      req<{ job: InstallJob; created?: boolean; existing?: boolean }>("/api/setup/install-jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          componentId,
          ...body,
        }),
      }),
    get: async (jobId: string) => {
      const data = await req<{ job?: InstallJob; operation?: InstallJob }>(
        `/api/setup/install-jobs/${encodeURIComponent(jobId)}`,
      );
      return data.job ?? data.operation;
    },
    pause: (jobId: string) =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/pause`, {
        method: "POST",
      }),
    resume: (jobId: string) =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/resume`, {
        method: "POST",
      }),
    cancel: (jobId: string) =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
      }),
    retry: (jobId: string) =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/retry`, {
        method: "POST",
      }),
    repair: (jobId: string, action = "retry_download") =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/repair`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }),
    verify: (jobId: string) =>
      req<{ job: InstallJob }>(`/api/setup/install-jobs/${encodeURIComponent(jobId)}/verify`, {
        method: "POST",
      }),
    requiredComponents: (capabilityId: string) =>
      req<Record<string, unknown>>(
        `/api/source-manager/capabilities/${encodeURIComponent(capabilityId)}/required-components`
      ),
    componentRequirements: (componentId: string) =>
      req<Record<string, unknown>>(
        `/api/source-manager/components/${encodeURIComponent(componentId)}/requirements`
      ),
    validateSource: (
      componentId: string,
      body: { url: string; revision?: string | null }
    ) =>
      req<Record<string, unknown>>(
        `/api/source-manager/components/${encodeURIComponent(componentId)}/sources/validate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    saveSource: (
      componentId: string,
      body: {
        url?: string | null;
        revision?: string | null;
        confirm?: boolean;
        verification?: Record<string, unknown> | null;
      }
    ) =>
      req<Record<string, unknown>>(
        `/api/source-manager/components/${encodeURIComponent(componentId)}/sources`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
  },
  listDownloads: (opts?: { active?: boolean; componentId?: string; signal?: AbortSignal }) => {
    const params = new URLSearchParams();
    if (opts?.active) params.set("active", "true");
    if (opts?.componentId) params.set("componentId", opts.componentId);
    const q = params.toString();
    return req<{ operations: DownloadOperation[] }>(`/api/downloads${q ? `?${q}` : ""}`, {
      signal: opts?.signal,
    });
  },
  enqueueDownload: (body: Record<string, unknown>) =>
    req<{ operation: DownloadOperation }>("/api/downloads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getDownload: (operationId: string) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}`),
  cancelDownload: (operationId: string) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}/cancel`, {
      method: "POST",
    }),
  pauseDownload: (operationId: string) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}/pause`, {
      method: "POST",
    }),
  resumeDownload: (operationId: string) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}/resume`, {
      method: "POST",
    }),
  retryDownload: (operationId: string) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}/retry`, {
      method: "POST",
    }),
  setDownloadPriority: (operationId: string, priority: number) =>
    req<{ operation: DownloadOperation }>(`/api/downloads/${encodeURIComponent(operationId)}/priority`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ priority }),
    }),
  installHistory: () =>
    req<{ entries: InstallHistoryEntry[]; count: number }>("/api/install-history"),
  getInstallReceipt: (installId: string) =>
    req<{ receipt: InstallReceipt }>(`/api/install-history/${encodeURIComponent(installId)}`),
  setupUpdateLater: (componentId: string) =>
    req<SetupUpdateDismissal>(`/api/setup/components/${encodeURIComponent(componentId)}/update/later`, {
      method: "POST",
    }),
  setupAction: (componentId: string, action: string, path: string, approved: boolean) => {
    const fd = new FormData();
    fd.append("action", action);
    fd.append("path", path);
    fd.append("approved", approved ? "true" : "false");
    return req<SetupLegacyActionResult>(`/api/setup/components/${encodeURIComponent(componentId)}/action`, {
      method: "POST",
      body: fd,
    });
  },
  listProfiles: (kind?: string) =>
    req<any[]>(`/api/profiles${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  createProfile: (kind: string, body: Record<string, unknown>) =>
    req<any>(`/api/profiles/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteProfile: (id: string) => req(`/api/profiles/item/${id}`, { method: "DELETE" }),
  uploadProfile: async (
    kind: string,
    file: File,
    meta: { name?: string; tag?: string; category?: string; description?: string }
  ) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", meta.name || "");
    fd.append("tag", meta.tag || "");
    fd.append("category", meta.category || "");
    fd.append("description", meta.description || "");
    return req(`/api/profiles/${kind}/upload`, { method: "POST", body: fd });
  },
  validateMotionTags: (text: string) =>
    req<{ resolved: any[]; undefined: string[]; warnings: string[] }>(
      "/api/profiles/motions/validate-tags",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }
    ),
  getLearning: (projectId: string) => req<any>(`/api/projects/${projectId}/learning`),
  putLearning: (projectId: string, body: any) =>
    req<any>(`/api/projects/${projectId}/learning`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  resetLearning: (projectId: string) =>
    req<any>(`/api/projects/${projectId}/learning/reset`, { method: "POST" }),
  exportLearning: (projectId: string) => req<any>(`/api/projects/${projectId}/learning/export`),
  importLearning: (projectId: string, body: any) =>
    req<any>(`/api/projects/${projectId}/learning/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  continuitySuggestions: (projectId: string) =>
    req<{ suggestions: any[] }>(`/api/projects/${projectId}/continuity-suggestions`),
  dismissContinuity: (projectId: string, suggestionId: string) =>
    req(`/api/projects/${projectId}/continuity-suggestions/${encodeURIComponent(suggestionId)}/dismiss`, {
      method: "POST",
    }),
  getJobPreview: (jobId: string) => req<any>(`/api/jobs/${jobId}/preview`),
  savePreviewFrame: (jobId: string, projectId: string, tag: string) => {
    const fd = new FormData();
    fd.append("project_id", projectId);
    fd.append("tag", tag);
    return req(`/api/jobs/${jobId}/preview/save-frame`, { method: "POST", body: fd });
  },
  executionPlan: (projectId: string, sceneId?: string) =>
    req<any>(
      `/api/projects/${projectId}/execution-plan${sceneId ? `?scene_id=${encodeURIComponent(sceneId)}` : ""}`
    ),
  projectDashboard: (projectId: string, init?: RequestInit) =>
    req<any>(`/api/projects/${projectId}/dashboard`, init),
  duplicateProject: (projectId: string, body?: Record<string, unknown>) =>
    req<{ ok: boolean; id: string; name: string }>(`/api/projects/${projectId}/duplicate`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  archiveProject: (projectId: string, archived = true) =>
    req<{ ok: boolean; archived: number }>(
      `/api/projects/${projectId}/archive?archived=${archived ? "true" : "false"}`,
      { method: "POST" }
    ),
  exportProject: (projectId: string, body?: Record<string, unknown>) =>
    req<Job>(`/api/projects/${projectId}/export`, {
      method: "POST",
      body: JSON.stringify(body || { exportMode: "without_password" }),
    }),
  getProjectSecurity: (projectId: string) =>
    req<{
      projectId: string;
      passwordProtected: boolean;
      unlocked: boolean;
      passwordHint?: string | null;
      passwordVersion: number;
      mock: boolean;
    }>(`/api/projects/${encodeURIComponent(projectId)}/security`),
  setProjectPassword: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/security/password`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  unlockProject: (projectId: string, body: Record<string, unknown>) =>
    req<{ ok: boolean; projectId: string; unlockToken: string; expiresAt: string; mock: boolean }>(
      `/api/projects/${encodeURIComponent(projectId)}/security/unlock`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  lockProjectNow: (projectId: string) =>
    req<{ ok: boolean }>(`/api/projects/${encodeURIComponent(projectId)}/security/lock`, {
      method: "POST",
      body: "{}",
    }),
  changeProjectPassword: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/security/password`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  disableProjectPassword: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/security/password`, {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  resetProjectPassword: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/security/reset`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  projectPasswordProtectionGate: () =>
    req<{ projectPasswordProtectionGo: boolean; flags: Record<string, boolean>; binaryOnly: boolean }>(
      "/api/project-security/gate/password-protection",
    ),
  getMasterSheet: (projectId: string, sceneId: string) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/master-sheet`),
  putMasterSheet: (projectId: string, sceneId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/master-sheet`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listMasterSheets: (projectId: string) =>
    req<any[]>(`/api/projects/${projectId}/master-sheets`),
  validateMasterSheet: (projectId: string, sceneId: string) =>
    req<{ ok: boolean; issues: { level: string; text: string }[] }>(
      `/api/projects/${projectId}/scenes/${sceneId}/master-sheet/validate`,
      { method: "POST" }
    ),
  setMasterSheetAuthority: (projectId: string, sceneId: string, approved = true) =>
    req<any>(`/api/projects/${projectId}/scenes/${sceneId}/master-sheet/authority`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_authority: approved }),
    }),
  listAvatarSessions: (projectId: string) => req<any[]>(`/api/projects/${projectId}/avatar-sessions`),
  createAvatarSession: (
    projectId: string,
    body?: {
      name?: string;
      character_profile_id?: string;
      character_name?: string;
      mode?: string;
      bootstrap?: Record<string, unknown>;
    }
  ) =>
    req<any>(`/api/projects/${projectId}/avatar-sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  getAvatarSession: (projectId: string, sessionId: string) =>
    req<any>(`/api/projects/${projectId}/avatar-sessions/${sessionId}`),
  patchAvatarSession: (projectId: string, sessionId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/avatar-sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteAvatarSession: (projectId: string, sessionId: string) =>
    req(`/api/projects/${projectId}/avatar-sessions/${sessionId}`, { method: "DELETE" }),
  validateAvatarSession: (projectId: string, sessionId: string) =>
    req<{ ok: boolean; issues: { level: string; text: string }[] }>(
      `/api/projects/${projectId}/avatar-sessions/${sessionId}/validate`,
      { method: "POST" }
    ),
  addAvatarTake: (
    projectId: string,
    sessionId: string,
    body: {
      asset_id?: string;
      scene_id?: string;
      label?: string;
      status?: string;
      performance_note?: string;
      favorite?: boolean;
      approved?: boolean;
    }
  ) =>
    req<any>(`/api/projects/${projectId}/avatar-sessions/${sessionId}/takes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listAvatarJobs: (projectId: string, sessionId: string) =>
    req<AvatarProjectJob[]>(`/api/projects/${projectId}/avatar-sessions/${sessionId}/jobs`),
  createAvatarJob: (
    projectId: string,
    sessionId: string,
    body?: {
      providerId?: string;
      scriptSourceId?: string;
      startImmediately?: boolean;
      overlapMs?: number;
      targetSectionDurationMs?: number;
    },
  ) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-sessions/${sessionId}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  getAvatarJob: (projectId: string, jobId: string) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}`),
  pauseAvatarJob: (projectId: string, jobId: string) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}/pause`, { method: "POST" }),
  resumeAvatarJob: (projectId: string, jobId: string) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}/resume`, { method: "POST" }),
  cancelAvatarJob: (projectId: string, jobId: string) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}/cancel`, { method: "POST" }),
  validateAvatarTransitions: (
    projectId: string,
    jobId: string,
    body?: { validated?: boolean; notes?: string },
  ) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}/transition-validation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  retryAvatarSection: (projectId: string, jobId: string, sectionId: string) =>
    req<AvatarProjectJob>(
      `/api/projects/${projectId}/avatar-jobs/${jobId}/sections/${sectionId}/retry`,
      { method: "POST" },
    ),
  requestAvatarSectionRetake: (
    projectId: string,
    jobId: string,
    sectionId: string,
    body?: { note?: string },
  ) =>
    req<AvatarProjectJob>(
      `/api/projects/${projectId}/avatar-jobs/${jobId}/sections/${sectionId}/retake`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      },
    ),
  approveAvatarSection: (projectId: string, jobId: string, sectionId: string) =>
    req<AvatarProjectJob>(
      `/api/projects/${projectId}/avatar-jobs/${jobId}/sections/${sectionId}/approve`,
      { method: "POST" },
    ),
  assembleAvatarJob: (projectId: string, jobId: string) =>
    req<AvatarProjectJob>(`/api/projects/${projectId}/avatar-jobs/${jobId}/assemble`, {
      method: "POST",
    }),
  prepareAvatarTimeline: (
    projectId: string,
    jobId: string,
    body?: {
      placementMode?: string;
      sectionId?: string;
      replaceSectionId?: string;
      trackId?: string;
      startMs?: number;
      confirmReplace?: boolean;
    },
  ) =>
    req<{
      ok: boolean;
      job: AvatarProjectJob;
      timelineProposal: Record<string, unknown>;
      timelineWritten: boolean;
    }>(`/api/projects/${projectId}/avatar-jobs/${jobId}/timeline/prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  listDirectorSequences: (projectId: string, status?: string) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return req<any[]>(`/api/projects/${projectId}/director-sequences${qs}`);
  },
  createDirectorSequence: (
    projectId: string,
    body?: {
      name?: string;
      scene_id?: string;
      status?: string;
      asset_id?: string;
      bootstrap?: Record<string, unknown>;
    }
  ) =>
    req<any>(`/api/projects/${projectId}/director-sequences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  directorSequenceFromScene: (
    projectId: string,
    body: {
      scene_id: string;
      name?: string;
      status?: string;
      include_audio?: boolean;
      proxy?: boolean;
      segment_ids?: string[];
    }
  ) =>
    req<any>(`/api/projects/${projectId}/director-sequences/from-scene`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getDirectorSequence: (projectId: string, seqId: string) =>
    req<any>(`/api/projects/${projectId}/director-sequences/${seqId}`),
  patchDirectorSequence: (
    projectId: string,
    seqId: string,
    body: {
      name?: string;
      status?: string;
      approve?: boolean;
      bump_version?: boolean;
      asset_id?: string;
      patch?: Record<string, unknown>;
    }
  ) =>
    req<any>(`/api/projects/${projectId}/director-sequences/${seqId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  sendDirectorToEditor: (
    projectId: string,
    seqId: string,
    body?: {
      track?: string;
      label?: string;
      include_audio?: boolean;
      proxy?: boolean;
      start?: number;
      length?: number;
    }
  ) =>
    req<{ sequence: any; editor: any; clip: any }>(
      `/api/projects/${projectId}/director-sequences/${seqId}/send-to-editor`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }
    ),
  getEditor: (projectId: string) => req<any>(`/api/projects/${projectId}/editor`),
  putEditor: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/editor`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  audioStudioGateW45: () => req<Record<string, unknown>>("/api/audio-studio/gate/w45"),
  audioStudioWorkspace: (projectId: string) =>
    req<Record<string, unknown>>(`/api/audio-studio/projects/${encodeURIComponent(projectId)}/workspace`),
  audioStudioGenerate: (
    projectId: string,
    body: {
      kind: "music" | "sfx" | "ambience" | string;
      prompt?: string;
      durationSeconds?: number;
      durationSec?: number;
      mood?: string | string[];
      genre?: string;
      energy?: string;
      instrumentation?: string | string[];
      category?: string;
      intensity?: string;
      loopRequired?: boolean;
      loop?: boolean;
      candidateCount?: number;
      preferredProvider?: string;
      allowProviderSwitch?: boolean;
      brief?: Record<string, unknown>;
      asyncMode?: boolean;
    }
  ) => {
    const mood = Array.isArray(body.mood) ? body.mood : body.mood ? [body.mood] : undefined;
    const instrumentation = Array.isArray(body.instrumentation)
      ? body.instrumentation
      : body.instrumentation
        ? [body.instrumentation]
        : undefined;
    return req<Record<string, unknown>>(`/api/audio-studio/projects/${encodeURIComponent(projectId)}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: body.kind,
        prompt: body.prompt,
        durationSeconds: body.durationSeconds ?? body.durationSec,
        mood,
        genre: body.genre,
        energy: body.energy,
        instrumentation,
        category: body.category,
        intensity: body.intensity,
        loopRequired: body.loopRequired ?? body.loop,
        candidateCount: body.candidateCount ?? 3,
        preferredProvider: body.preferredProvider,
        allowProviderSwitch: body.allowProviderSwitch ?? false,
        brief: body.brief,
        asyncMode: body.asyncMode ?? true,
      }),
    });
  },
  audioStudioGetBatch: (projectId: string, batchId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/batches/${encodeURIComponent(batchId)}`
    ),
  audioStudioCancelBatch: (projectId: string, batchId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/batches/${encodeURIComponent(batchId)}/cancel`,
      { method: "POST" }
    ),
  audioStudioCancelGenerations: (projectId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/cancel-generations`,
      { method: "POST" }
    ),
  audioStudioSelectCandidate: (projectId: string, batchId: string, candidateId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/batches/${encodeURIComponent(batchId)}/candidates/${encodeURIComponent(candidateId)}/select`,
      { method: "POST" }
    ),
  audioStudioApproveCandidate: (projectId: string, batchId: string, candidateId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/batches/${encodeURIComponent(batchId)}/candidates/${encodeURIComponent(candidateId)}/approve`,
      { method: "POST" }
    ),
  audioStudioRetryCandidate: (projectId: string, batchId: string, candidateId: string) =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/batches/${encodeURIComponent(batchId)}/candidates/${encodeURIComponent(candidateId)}/retry`,
      { method: "POST" }
    ),
  audioStudioPlace: (
    projectId: string,
    body: { assetId: string; category?: string; startMs?: number; loop?: boolean; sceneId?: string }
  ) =>
    req<Record<string, unknown>>(`/api/audio-studio/projects/${encodeURIComponent(projectId)}/place`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  audioStudioProviders: (projectId: string, kind: string = "music") =>
    req<Record<string, unknown>>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/providers?kind=${encodeURIComponent(kind)}`
    ),
  audioStudioGetMix: (projectId: string) =>
    req<{ ok: boolean; mix: Record<string, unknown>; mock: boolean }>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/mix`
    ),
  audioStudioUpdateMix: (
    projectId: string,
    body: {
      master?: Record<string, unknown>;
      clips?: Record<string, Record<string, unknown>>;
      clip?: Record<string, unknown>;
    }
  ) =>
    req<{ ok: boolean; mix: Record<string, unknown>; mock: boolean }>(
      `/api/audio-studio/projects/${encodeURIComponent(projectId)}/mix`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),
  directorTimelineGate: () =>
    req<{
      ok: boolean;
      directorTimelineGo: boolean;
      verdict: string;
      flags: Record<string, boolean>;
      mock: boolean;
    }>("/api/director-timeline/gate"),
  directorTimelineCameraCatalog: () =>
    req<DirectorTimelineCameraCatalog>("/api/director-timeline/camera-catalog"),
  directorTimelineGenerators: () => req<Record<string, unknown>>("/api/director-timeline/generators"),
  directorTimelineMaster: (projectId: string, sceneId: string) =>
    req<{ ok: boolean; master: import("./timelineMaster/contracts").SceneTimelineMaster; mock: boolean }>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/master`,
    ),
  directorTimelineDismissFailure: (projectId: string, sceneId: string, jobId: string) =>
    req<{ ok: boolean; master: import("./timelineMaster/contracts").SceneTimelineMaster; mock: boolean }>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/dismiss-failure`,
      { method: "POST", body: JSON.stringify({ jobId }) },
    ),
  directorTimelineSetMode: (
    projectId: string,
    sceneId: string,
    mode: import("./timelineMaster/contracts").ModalityMode,
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/mode`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      },
    ),
  directorTimelineAddBatch: (
    projectId: string,
    sceneId: string,
    body?: { label?: string; plannedDuration?: number; generatorId?: string },
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      },
    ),
  directorTimelineDuplicateBatch: (projectId: string, sceneId: string, batchId: string) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}/duplicate`,
      { method: "POST" },
    ),
  directorTimelineDeleteBatch: (projectId: string, sceneId: string, batchId: string) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}`,
      { method: "DELETE" },
    ),
  directorTimelinePatchBatch: (
    projectId: string,
    sceneId: string,
    batchId: string,
    body: Record<string, unknown>,
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  directorTimelineGenerateBatch: (projectId: string, sceneId: string, batchId: string) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}/generate`,
      { method: "POST" },
    ),
  directorTimelineAddClipToBatch: (
    projectId: string,
    sceneId: string,
    batchId: string,
    body: {
      kind: "image" | "video" | "audio" | "sfx" | "camera";
      assetId?: string | null;
      start?: number;
      length?: number;
      trimStart?: number;
      label?: string;
      role?: string | null;
      volume?: number;
      fade_in?: number;
      fade_out?: number;
      motion_type?: string | null;
      rig?: string | null;
    },
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}/clips`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  directorTimelineGenerateScene: (
    projectId: string,
    sceneId: string,
    body?: { scope?: string; batchBlockIds?: string[] },
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || { scope: "full" }),
      },
    ),
  directorTimelineCancel: (
    projectId: string,
    sceneId: string,
    body: { action: import("./timelineMaster/contracts").CancelAction; batchBlockIds?: string[] },
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/cancel`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  directorTimelineAddRepair: (
    projectId: string,
    sceneId: string,
    batchId: string,
    body: { start: number; length: number; label?: string; policy?: string; inPaintStrategy?: string },
  ) =>
    req<Record<string, unknown>>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/batches/${encodeURIComponent(batchId)}/repair-ranges`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  directorTimelinePreflight: (projectId: string, sceneId: string) =>
    req<{ ok: boolean; findings: Array<{ severity: string; message: string; code?: string }> }>(
      `/api/director-timeline/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/preflight`,
    ),
  knowledgebaseModels: () => req<any[]>("/api/knowledgebase/generation/models"),
  knowledgebaseModel: (id: string) => req<any>(`/api/knowledgebase/generation/models/${id}`),
  knowledgebaseDoc: (path: string) =>
    req<{ path: string; content: string }>(
      `/api/knowledgebase/generation/doc?path=${encodeURIComponent(path)}`
    ),
  compilePrompt: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/compile-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  promptIntelligence: {
    enhance: (body: Record<string, unknown>) =>
      req<{
        ok: boolean;
        record: Record<string, unknown>;
        profileRecommendation?: string | null;
        error?: Record<string, unknown> | null;
      }>("/api/codirector/prompt-intelligence/enhance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    analyze: (body: Record<string, unknown>) =>
      req<{
        ok: boolean;
        qualityReport: {
          overall: number;
          dimensions: Record<string, number>;
          recommendations: Array<{ code: string; message: string; suggestedModule?: string; severity: string }>;
        };
        profileRecommendation?: string | null;
        profile?: Record<string, unknown>;
      }>("/api/codirector/prompt-intelligence/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    profiles: (query?: { providerId?: string; modelId?: string; engineId?: string; domain?: string }) => {
      const params = new URLSearchParams();
      if (query?.providerId) params.set("providerId", query.providerId);
      if (query?.modelId) params.set("modelId", query.modelId);
      if (query?.engineId) params.set("engineId", query.engineId);
      if (query?.domain) params.set("domain", query.domain);
      const q = params.toString();
      return req<{
        resolved: Record<string, unknown>;
        recommendation?: string | null;
        profiles: Record<string, unknown>[];
        languageModules: Array<{ languageId: string; status: string }>;
      }>(`/api/codirector/prompt-intelligence/profiles${q ? `?${q}` : ""}`);
    },
    validate: (body: Record<string, unknown>) =>
      req<{ ok: boolean; errors: string[]; length: number }>("/api/codirector/prompt-intelligence/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    v2: {
      suites: () => req<{ ok: boolean; suites: Record<string, unknown>[] }>("/api/codirector/prompt-intelligence/v2/suites"),
      plan: (body: Record<string, unknown>) =>
        req<{ ok: boolean; plan: Record<string, unknown> }>("/api/codirector/prompt-intelligence/v2/plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      startRun: (body: Record<string, unknown>) =>
        req<{ ok: boolean; suiteRun: Record<string, unknown> }>("/api/codirector/prompt-intelligence/v2/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      runs: (suiteRunId?: string) =>
        req<Record<string, unknown>>(
          suiteRunId
            ? `/api/codirector/prompt-intelligence/v2/runs?suiteRunId=${encodeURIComponent(suiteRunId)}`
            : "/api/codirector/prompt-intelligence/v2/runs",
        ),
      pause: (suiteRunId: string) =>
        req<{ ok: boolean }>(`/api/codirector/prompt-intelligence/v2/runs/${encodeURIComponent(suiteRunId)}/pause`, {
          method: "POST",
        }),
      resume: (suiteRunId: string) =>
        req<{ ok: boolean }>(`/api/codirector/prompt-intelligence/v2/runs/${encodeURIComponent(suiteRunId)}/resume`, {
          method: "POST",
        }),
      cancel: (suiteRunId: string) =>
        req<{ ok: boolean }>(`/api/codirector/prompt-intelligence/v2/runs/${encodeURIComponent(suiteRunId)}/cancel`, {
          method: "POST",
        }),
      reviews: () => req<{ ok: boolean; reviews: Record<string, unknown>[] }>("/api/codirector/prompt-intelligence/v2/reviews"),
      review: (comparisonId: string) =>
        req<{ ok: boolean; review: Record<string, unknown> }>(
          `/api/codirector/prompt-intelligence/v2/reviews/${encodeURIComponent(comparisonId)}`,
        ),
      submitReview: (body: Record<string, unknown>) =>
        req<{ ok: boolean; review: Record<string, unknown> }>("/api/codirector/prompt-intelligence/v2/reviews/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      evaluate: (body: Record<string, unknown>) =>
        req<{ ok: boolean; evidence: Record<string, unknown> }>("/api/codirector/prompt-intelligence/v2/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      promote: (body: Record<string, unknown>) =>
        req<{ ok: boolean; evidence?: Record<string, unknown>; detail?: Record<string, unknown> }>(
          "/api/codirector/prompt-intelligence/v2/promote",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        ),
      rollback: (body: Record<string, unknown>) =>
        req<{ ok: boolean }>("/api/codirector/prompt-intelligence/v2/rollback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      recommend: (body: Record<string, unknown>) =>
        req<{ ok: boolean; strategyRecommendation: Record<string, unknown> }>(
          "/api/codirector/prompt-intelligence/v2/recommend",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        ),
      analyze: (body: Record<string, unknown>) =>
        req<{ ok: boolean; axes: Record<string, unknown>; strategyRecommendation: Record<string, unknown> }>(
          "/api/codirector/prompt-intelligence/v2/analyze",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
        ),
      evidence: () =>
        req<{ ok: boolean; evidence: Record<string, unknown>[] }>("/api/codirector/prompt-intelligence/v2/evidence"),
      liveProviders: () =>
        req<{ ok: boolean; video: Record<string, unknown> }>("/api/codirector/prompt-intelligence/v2/providers/live"),
    },

  },
  txt2vid: (projectId: string, body: Record<string, unknown>) =>
    req<Job>(`/api/projects/${projectId}/txt2vid`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imagegen: (projectId: string, body: Record<string, unknown>) =>
    req<Job>(`/api/projects/${projectId}/imagegen`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imagegenModels: () => req<{ id: string; label: string; group: string }[]>("/api/imagegen/models"),
  imageProduct: {
    generate: (projectId: string, body: Record<string, unknown>) =>
      req<ImageProductGenerateResult>(`/api/image-product/projects/${projectId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    recommend: (body: Record<string, unknown>) =>
      req<ImageProductRecommendation>("/api/image-product/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    expandPrompt: (body: Record<string, unknown>) =>
      req<Record<string, unknown>>("/api/image-product/expand-prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    families: () => req<{ families: ImageProductFamily[] }>("/api/image-product/families"),
    gate: () => req<Record<string, unknown>>("/api/image-product/gate"),
    listPresets: (projectId: string) =>
      req<{ presets: ImageProductPreset[] }>(`/api/image-product/projects/${projectId}/presets`),
    createPreset: (projectId: string, body: Record<string, unknown>) =>
      req<ImageProductPreset>(`/api/image-product/projects/${projectId}/presets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    patchPreset: (projectId: string, presetId: string, body: Record<string, unknown>) =>
      req<ImageProductPreset>(`/api/image-product/projects/${projectId}/presets/${presetId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    deletePreset: (projectId: string, presetId: string) =>
      req<{ ok: boolean; deleted: string }>(`/api/image-product/projects/${projectId}/presets/${presetId}`, {
        method: "DELETE",
      }),
    listCollections: (projectId: string) =>
      req<{ collections: Record<string, unknown>[] }>(`/api/image-product/projects/${projectId}/collections`),
    createCollection: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/image-product/projects/${projectId}/collections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    patchCollection: (projectId: string, collectionId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/image-product/projects/${projectId}/collections/${collectionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    deleteCollection: (projectId: string, collectionId: string) =>
      req<{ ok: boolean; deleted: string }>(
        `/api/image-product/projects/${projectId}/collections/${collectionId}`,
        { method: "DELETE" }
      ),
    addCollectionAssets: (projectId: string, collectionId: string, assetIds: string[]) =>
      req<Record<string, unknown>>(
        `/api/image-product/projects/${projectId}/collections/${collectionId}/assets`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ assetIds }),
        }
      ),
    listReferences: (projectId: string, type?: string) => {
      const qs = type ? `?type=${encodeURIComponent(type)}` : "";
      return req<{ references: Record<string, unknown>[] }>(
        `/api/image-product/projects/${projectId}/references${qs}`
      );
    },
    createReference: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/image-product/projects/${projectId}/references`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    bridgeReference: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/image-product/projects/${projectId}/references/bridge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    history: (projectId: string, limit = 50) =>
      req<{ entries: Record<string, unknown>[]; prompts: string[] }>(
        `/api/image-product/projects/${projectId}/history?limit=${limit}`
      ),
    promptHistory: (projectId: string) =>
      req<{ prompts: string[] }>(`/api/image-product/projects/${projectId}/prompt-history`),
    gateWave4: () => req<Record<string, unknown>>("/api/image-product/gate/wave4"),
    editRecommend: (body: Record<string, unknown>) =>
      req<ImageProductEditRecommendation>("/api/image-product/edit/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    editCompile: (body: Record<string, unknown>) =>
      req<Record<string, unknown>>("/api/image-product/edit/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    editEnqueue: (body: Record<string, unknown>) =>
      req<ImageProductEditEnqueueResult>("/api/image-product/edit/enqueue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    editBatch: (body: Record<string, unknown>) =>
      req<ImageProductEditEnqueueResult>("/api/image-product/edit/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    listRecipes: (projectId: string) =>
      req<{ recipes: ImageProductRecipe[] }>(`/api/image-product/projects/${projectId}/recipes`),
    createRecipe: (projectId: string, body: Record<string, unknown>) =>
      req<ImageProductRecipe>(`/api/image-product/projects/${projectId}/recipes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    patchRecipe: (projectId: string, recipeId: string, body: Record<string, unknown>) =>
      req<ImageProductRecipe>(`/api/image-product/projects/${projectId}/recipes/${recipeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    deleteRecipe: (projectId: string, recipeId: string) =>
      req<{ ok: boolean; deleted: string }>(
        `/api/image-product/projects/${projectId}/recipes/${recipeId}`,
        { method: "DELETE" }
      ),
    saveMask: (projectId: string, body: Record<string, unknown>) =>
      req<ImageProductMask>(`/api/image-product/projects/${projectId}/masks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    listMasks: (projectId: string, sourceAssetId?: string) => {
      const qs = sourceAssetId ? `?sourceAssetId=${encodeURIComponent(sourceAssetId)}` : "";
      return req<{ masks: ImageProductMask[] }>(`/api/image-product/projects/${projectId}/masks${qs}`);
    },
    getMask: (projectId: string, maskId: string) =>
      req<ImageProductMask>(`/api/image-product/projects/${projectId}/masks/${maskId}`),
    deleteMask: (projectId: string, maskId: string) =>
      req<{ ok: boolean; deleted: string }>(
        `/api/image-product/projects/${projectId}/masks/${maskId}`,
        { method: "DELETE" }
      ),
    listVersions: (projectId: string) =>
      req<{ projectId: string; roots: ImageProductVersion[]; versions: ImageProductVersion[]; versionCount: number }>(
        `/api/image-product/projects/${projectId}/versions`
      ),
    createVersion: (projectId: string, body: Record<string, unknown>) =>
      req<ImageProductVersion>(`/api/image-product/projects/${projectId}/versions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    patchVersion: (projectId: string, versionId: string, body: Record<string, unknown>) =>
      req<ImageProductVersion>(`/api/image-product/projects/${projectId}/versions/${versionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    kontextCreateSession: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/image-product/projects/${projectId}/kontext/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    kontextAddTurn: (projectId: string, sessionId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/image-product/projects/${projectId}/kontext/session/${sessionId}/turn`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
  },
  imagePipeline: {
    preparePlan: (body: import("./contracts/imagePipeline").ProductionImageRequest, projectPolicy = "Ask") =>
      req<{
        planId: string;
        creatorPreview: string;
        plan: import("./contracts/imagePipeline").ImageGenerationPlan;
        readiness: Record<string, unknown>;
      }>(`/api/image-pipeline/prepare-plan?projectPolicy=${encodeURIComponent(projectPolicy)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    getPlan: (projectId: string, planId: string) =>
      req<{ plan: import("./contracts/imagePipeline").ImageGenerationPlan }>(
        `/api/image-pipeline/plans/${projectId}/${planId}`
      ),
    generateCandidates: (projectId: string, planId: string, body?: { candidateCount?: number }) =>
      req<{
        readiness: string;
        group: import("./contracts/imagePipeline").ImagePipelineCandidateGroup;
        message: string;
      }>(`/api/image-pipeline/plans/${projectId}/${planId}/candidates/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }),
    recommendCandidate: (projectId: string, planId: string, groupId: string) =>
      req<{
        recommendedCandidateId?: string | null;
        explanation: string;
        group: import("./contracts/imagePipeline").ImagePipelineCandidateGroup;
      }>(`/api/image-pipeline/plans/${projectId}/${planId}/candidates/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ groupId }),
      }),
    selectCandidate: (projectId: string, planId: string, groupId: string, candidateId: string) =>
      req<{ group: import("./contracts/imagePipeline").ImagePipelineCandidateGroup }>(
        `/api/image-pipeline/plans/${projectId}/${planId}/candidates/select`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ groupId, candidateId }),
        }
      ),
    approvePlan: (projectId: string, planId: string, body?: { kind?: string; approvedBy?: string }) =>
      req<{ plan: import("./contracts/imagePipeline").ImageGenerationPlan }>(
        `/api/image-pipeline/plans/${projectId}/${planId}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body || {}),
        }
      ),
  },
  environmentReferenceSheet: {
    listSheets: (projectId: string) =>
      req<{ sheets: import("./contracts/environmentReferenceSheet").EnvironmentReferenceSheetSummary[] }>(
        `/api/environment-reference-sheets/projects/${encodeURIComponent(projectId)}`,
        { cache: "no-store" }
      ),
    getSheet: (projectId: string, sheetId: string) =>
      req<{
        sheet: import("./contracts/environmentReferenceSheet").EnvironmentReferenceSheet;
        summary: import("./contracts/environmentReferenceSheet").EnvironmentReferenceSheetSummary;
      }>(`/api/environment-reference-sheets/projects/${encodeURIComponent(projectId)}/${encodeURIComponent(sheetId)}`, {
        cache: "no-store",
      }),
  },
  minimaxH3: {
    capability: (territory = resolveMiniMaxH3Territory()) =>
      req<Record<string, unknown>>(`/api/minimax-h3/capability?territory=${encodeURIComponent(territory)}`),
    readiness: () =>
      req<{
        ok: boolean;
        ready: boolean;
        privateLocalEnabled: boolean;
        ownerOnly: boolean;
        creatorStatus?: string;
        profile?: {
          label: string;
          width: number;
          height: number;
          length: number;
          steps: number;
          nativeAudio: boolean;
        } | null;
        missingFiles?: string[];
        missingNodes?: string[];
        access?: Record<string, unknown>;
      }>("/api/minimax-h3/readiness"),
    access: () =>
      req<{
        privateLocalEnabled: boolean;
        ownerOnly: boolean;
        publicCreatorEnabled: boolean;
        bestMatchEnabled: boolean;
        generalRoutingEnabled: boolean;
        runtimeUrl: string;
        modelRoot: string;
        runtimeIsIsolatedRouteA: boolean;
        ownerAccessActive: boolean;
      }>("/api/minimax-h3/access"),
    preparePlan: (body: import("./contracts/minimaxH3").AdeptMiniMaxH3Request) =>
      req<{
        ok: boolean;
        planId: string;
        creatorPreview: string;
        plan: import("./contracts/minimaxH3").H3Plan;
        preflight?: import("./contracts/minimaxH3").H3PreflightResult | null;
      }>("/api/minimax-h3/prepare-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    preflight: (body: import("./contracts/minimaxH3").AdeptMiniMaxH3Request) =>
      req<{
        ok: boolean;
        preflight: import("./contracts/minimaxH3").H3PreflightResult;
        plan: import("./contracts/minimaxH3").H3Plan;
      }>("/api/minimax-h3/preflight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    threeFramePlan: (body: import("./contracts/minimaxH3").AdeptMiniMaxH3Request) =>
      req<{ ok: boolean; threeFramePlan: Record<string, unknown> }>("/api/minimax-h3/three-frame/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    createJob: (projectId: string, planId: string, approvalId?: string | null) =>
      req<{
        ok: boolean;
        status: string;
        planId: string;
        jobId?: string;
        stage?: string;
        errorCode?: string;
        message?: string;
        provenance?: Record<string, unknown>;
      }>("/api/minimax-h3/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId, planId, approvalId: approvalId ?? null }),
      }),
    getJob: (projectId: string, jobId: string) =>
      req<{
        ok: boolean;
        job?: {
          jobId: string;
          projectId: string;
          planId: string;
          status: string;
          stage: string;
          errorCode?: string | null;
          errorMessage?: string | null;
          outputPath?: string | null;
          media?: Record<string, unknown>;
          provenance?: Record<string, unknown>;
          cancelled?: boolean;
        };
      }>(`/api/minimax-h3/jobs/${encodeURIComponent(projectId)}/${encodeURIComponent(jobId)}`),
    cancelJob: (projectId: string, planId: string, jobId?: string | null, reason?: string | null) =>
      req<{
        ok: boolean;
        plan: import("./contracts/minimaxH3").H3Plan;
        job?: Record<string, unknown> | null;
        message: string;
      }>("/api/minimax-h3/jobs/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          projectId,
          planId,
          jobId: jobId ?? null,
          reason: reason ?? null,
        }),
      }),
    acceptLtxFallback: (projectId: string, planId: string) =>
      req<{
        ok: boolean;
        message: string;
        plan: import("./contracts/minimaxH3").H3Plan;
      }>("/api/minimax-h3/fallback/ltx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId, planId, acceptedBy: "creator" }),
      }),
  },
  timelineRetakes: {
    getShot: (projectId: string, shotId: string) =>
      req<any>(`/api/timeline-retakes/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(shotId)}`),
    list: (projectId: string) =>
      req<any>(`/api/timeline-retakes/projects/${encodeURIComponent(projectId)}`),
    ensureBaseline: (
      projectId: string,
      body: {
        shotId: string;
        sceneId?: string | null;
        assetId?: string | null;
        jobId?: string | null;
        prompt: string;
        durationSec?: number;
        provenance?: Record<string, unknown>;
      },
    ) =>
      req<any>(`/api/timeline-retakes/projects/${encodeURIComponent(projectId)}/baseline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    addAlternate: (
      projectId: string,
      body: {
        shotId: string;
        sourceTakeId: string;
        assetId?: string | null;
        jobId?: string | null;
        prompt: string;
        deltaInstruction: string;
        durationSec?: number;
        provenance?: Record<string, unknown>;
        activate?: boolean;
      },
    ) =>
      req<any>(`/api/timeline-retakes/projects/${encodeURIComponent(projectId)}/alternate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    setActive: (projectId: string, shotId: string, takeId: string) =>
      req<any>(
        `/api/timeline-retakes/projects/${encodeURIComponent(projectId)}/shots/${encodeURIComponent(shotId)}/active`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ takeId }),
        },
      ),
  },
  /** M4.8 Cinematic Image Studio + Visual Continuity Sessions */
  imageStudio: {
    listProviders: (includeUnready = true) =>
      req<{
        providers: import("./contracts/cinematicImageStudio").ImageProviderDescriptor[];
        families: Array<Record<string, unknown>>;
      }>(`/api/image-studio/providers?includeUnready=${includeUnready ? "true" : "false"}`),
    providersForMode: (body: {
      mode: import("./contracts/cinematicImageStudio").GenerationMode;
      prompt?: string;
      purpose?: string;
      preferredFamily?: string;
    }) =>
      req<{
        mode: string;
        recommendation: Record<string, unknown>;
        bestMatch: import("./contracts/cinematicImageStudio").ImageProviderDescriptor | null;
        providers: import("./contracts/cinematicImageStudio").ImageProviderDescriptor[];
        readyCount: number;
        paidProvidersRequireConfirmation: string[];
        costPreflight: Record<string, unknown>;
      }>("/api/image-studio/providers/for-mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    families: () =>
      req<{ families: Array<Record<string, unknown>> }>("/api/image-studio/families"),
    listContinuitySessions: (projectId: string) =>
      req<{ sessions: import("./contracts/visualContinuity").VisualContinuitySession[] }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions`
      ),
    createContinuitySession: (projectId: string, body: Record<string, unknown>) =>
      req<{ session: import("./contracts/visualContinuity").VisualContinuitySession }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    inheritContinuityFromScene: (projectId: string, sceneId: string) =>
      req<{ session: import("./contracts/visualContinuity").VisualContinuitySession }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions/inherit-from-scene`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneId }),
        }
      ),
    getContinuitySession: (projectId: string, sessionId: string) =>
      req<{ session: import("./contracts/visualContinuity").VisualContinuitySession }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions/${sessionId}`
      ),
    patchContinuitySession: (projectId: string, sessionId: string, body: Record<string, unknown>) =>
      req<{ session: import("./contracts/visualContinuity").VisualContinuitySession }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions/${sessionId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    approveContinuityImage: (projectId: string, sessionId: string, assetId: string) =>
      req<{ session: import("./contracts/visualContinuity").VisualContinuitySession }>(
        `/api/image-studio/projects/${projectId}/continuity-sessions/${sessionId}/approve-image`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ assetId }),
        }
      ),
    compilePreview: (projectId: string, body: Record<string, unknown>) =>
      req<{ imageProductBody: Record<string, unknown>; continuitySessionId?: string }>(
        `/api/image-studio/projects/${projectId}/cinematic/compile-preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    reopenAsset: (projectId: string, assetId: string) =>
      req<{
        reopen: {
          assetId: string;
          prompt: string;
          negativePrompt?: string;
          referenceAssetIds: string[];
          continuitySessionId?: string;
          sceneId?: string;
          spatialMapId?: string;
          spatialMapVersion?: string;
          spatialCameraId?: string;
          modelFamilyPreference?: string;
          controls: Record<string, unknown>;
          panelId?: string;
          provenance?: Record<string, unknown>;
        };
      }>(`/api/image-studio/projects/${projectId}/assets/${assetId}/reopen`),
  },
  /** M4.9 Storyboard Studio pages / timeline prep */
  storyboardStudio: {
    listDocuments: (projectId: string) =>
      req<{ documents: import("./contracts/storyboardStudio").StoryboardDocument[] }>(
        `/api/storyboard-studio/projects/${projectId}/documents`
      ),
    ensureDocument: (projectId: string, pageSize: 6 | 9 | 12 = 9) =>
      req<{ document: import("./contracts/storyboardStudio").StoryboardDocument }>(
        `/api/storyboard-studio/projects/${projectId}/documents/ensure`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pageSize }),
        }
      ),
    workspace: (projectId: string, documentId?: string) => {
      const qs = documentId ? `?documentId=${encodeURIComponent(documentId)}` : "";
      return req<import("./contracts/storyboardStudio").StoryboardWorkspacePayload>(
        `/api/storyboard-studio/projects/${projectId}/workspace${qs}`
      );
    },
    setPageSize: (projectId: string, documentId: string, pageSize: 6 | 9 | 12) =>
      req<{ document: import("./contracts/storyboardStudio").StoryboardDocument }>(
        `/api/storyboard-studio/projects/${projectId}/documents/${documentId}/page-size`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pageSize }),
        }
      ),
    reorder: (projectId: string, documentId: string, panelOrder: string[]) =>
      req<{ document: import("./contracts/storyboardStudio").StoryboardDocument }>(
        `/api/storyboard-studio/projects/${projectId}/documents/${documentId}/reorder`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ panelOrder }),
        }
      ),
    appendPanel: (projectId: string, documentId: string, panelId: string) =>
      req<{
        document: import("./contracts/storyboardStudio").StoryboardDocument;
        slot: { documentId: string; pageIndex: number; slotIndex: number; nextPanelOrdinal: number };
      }>(`/api/storyboard-studio/projects/${projectId}/documents/${documentId}/append-panel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ panelId }),
      }),
    nextFreeSlot: (projectId: string, documentId?: string) => {
      const qs = documentId ? `?documentId=${encodeURIComponent(documentId)}` : "";
      return req<{
        documentId: string;
        pageIndex: number;
        slotIndex: number;
        nextPanelOrdinal: number;
      }>(`/api/storyboard-studio/projects/${projectId}/next-free-slot${qs}`);
    },
    prepareTimeline: (
      projectId: string,
      body?: { documentId?: string; panelIds?: string[]; approvedOnly?: boolean }
    ) =>
      req<{ proposal: import("./contracts/storyboardStudio").TimelinePrepProposal }>(
        `/api/storyboard-studio/projects/${projectId}/prepare-timeline`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body || {}),
        }
      ),
    confirmTimelineProposal: (
      projectId: string,
      proposalId: string,
      body?: { panelIds?: string[] }
    ) =>
      req<{
        ok: boolean;
        proposal: Record<string, unknown>;
        timelinePayload: Array<Record<string, unknown>>;
        createdSceneIds: string[];
        note: string;
      }>(`/api/storyboard-studio/projects/${projectId}/timeline-proposals/${proposalId}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }),
    addImage: (
      projectId: string,
      body: {
        assetId: string;
        prompt?: string;
        label?: string;
        lens?: string;
        shotSize?: string;
        continuitySessionId?: string;
        sceneId?: string;
        spatialMapId?: string;
        spatialMapVersion?: string;
        documentId?: string;
        scriptwriterSceneId?: string;
      }
    ) =>
      req<{
        panelId: string;
        documentId: string;
        slot: { pageIndex: number; slotIndex: number; nextPanelOrdinal: number };
        assetId: string;
        scriptwriterSceneId?: string;
        undo: { clearAsset: boolean; panelId: string };
      }>(`/api/storyboard-studio/projects/${projectId}/add-image`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    replacePanel: (
      projectId: string,
      body: {
        panelId: string;
        assetId: string;
        prompt?: string;
        label?: string;
        lens?: string;
        shotSize?: string;
        continuitySessionId?: string;
        sceneId?: string;
        spatialMapId?: string;
        spatialMapVersion?: string;
        scriptwriterSceneId?: string;
      }
    ) =>
      req<{
        ok: boolean;
        panelId: string;
        assetId: string;
        scriptwriterSceneId?: string;
        undo: { restorePrevious: boolean; panelId: string; previous: Record<string, unknown> };
      }>(`/api/storyboard-studio/projects/${projectId}/replace-panel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    undoAddImage: (projectId: string, panelId: string) =>
      req<{ ok: boolean; panelId: string }>(
        `/api/storyboard-studio/projects/${projectId}/undo-add-image`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ panelId }),
        }
      ),
    undoReplacePanel: (projectId: string, panelId: string) =>
      req<{ ok: boolean; panelId: string; mode?: string; assetId?: string }>(
        `/api/storyboard-studio/projects/${projectId}/undo-replace-panel`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ panelId }),
        }
      ),
    exportPdfUrl: (projectId: string, documentId?: string) => {
      const qs = documentId ? `?documentId=${encodeURIComponent(documentId)}` : "";
      return `/api/storyboard-studio/projects/${projectId}/export.pdf${qs}`;
    },
  },
  sceneReferences: {
    list: (
      projectId: string,
      opts?: {
        scopeType?: string;
        scopeId?: string;
        includeInherited?: boolean;
        sequenceId?: string;
        sceneId?: string;
        shotId?: string;
      }
    ) => {
      const q = new URLSearchParams();
      if (opts?.scopeType) q.set("scope_type", opts.scopeType);
      if (opts?.scopeId) q.set("scope_id", opts.scopeId);
      if (opts?.includeInherited) q.set("include_inherited", "true");
      if (opts?.sequenceId) q.set("sequence_id", opts.sequenceId);
      if (opts?.sceneId) q.set("scene_id", opts.sceneId);
      if (opts?.shotId) q.set("shot_id", opts.shotId);
      const qs = q.toString();
      return req<{ items: any[]; count: number }>(
        `/api/projects/${projectId}/references${qs ? `?${qs}` : ""}`
      );
    },
    attach: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/projects/${projectId}/references`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    update: (projectId: string, bindingId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/projects/${projectId}/references/${bindingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    remove: (projectId: string, bindingId: string) =>
      req<{ ok: boolean }>(`/api/projects/${projectId}/references/${bindingId}`, { method: "DELETE" }),
    reorder: (projectId: string, bindingIds: string[]) =>
      req<{ items: any[] }>(`/api/projects/${projectId}/references/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ binding_ids: bindingIds }),
      }),
    copy: (projectId: string, body: Record<string, unknown>) =>
      req<{ items: any[]; count: number }>(`/api/projects/${projectId}/references/copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    apply: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/projects/${projectId}/references/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    readiness: (projectId: string, scopeType: string, scopeId: string, workflowKey: string) =>
      req<Record<string, unknown>>(
        `/api/projects/${projectId}/references/readiness?scope_type=${encodeURIComponent(scopeType)}&scope_id=${encodeURIComponent(scopeId)}&workflow_key=${encodeURIComponent(workflowKey)}`
      ),
    preflight: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/projects/${projectId}/references/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    assetUsage: (projectId: string, assetId: string) =>
      req<Record<string, unknown>>(`/api/projects/${projectId}/references/assets/${assetId}/usage`),
    capabilities: () => req<{ items: any[] }>("/api/scene-references/capabilities"),
    gate: () => req<Record<string, unknown>>("/api/m42-product/gate/wave6p/scene-references"),
  },
  wave6p: {
    gate: () => req<Record<string, unknown>>("/api/m42-product/gate/wave6p"),
  },
  continuity: {
    gateWave5: () => req<Record<string, unknown>>("/api/continuity/gate/wave5"),
    policy: (projectId: string) =>
      req<Record<string, unknown>>(`/api/continuity/projects/${projectId}/policy`),
    updatePolicy: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/continuity/projects/${projectId}/policy`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    summary: (projectId: string) =>
      req<Record<string, unknown>>(`/api/continuity/projects/${projectId}/summary`),
    issues: (projectId: string) =>
      req<{ items: any[] }>(`/api/continuity/projects/${projectId}/issues`),
    listIdentities: (projectId: string) =>
      req<{ items: any[] }>(`/api/continuity/identities?projectId=${encodeURIComponent(projectId)}`),
    createIdentity: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/continuity/identities?projectId=${encodeURIComponent(projectId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    getIdentity: (projectId: string, identityId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/identities/${identityId}?projectId=${encodeURIComponent(projectId)}`
      ),
    readiness: (projectId: string, identityId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/identities/${identityId}/readiness?projectId=${encodeURIComponent(projectId)}`
      ),
    listVersions: (projectId: string, identityId: string) =>
      req<{ items: any[] }>(
        `/api/continuity/identities/${identityId}/versions?projectId=${encodeURIComponent(projectId)}`
      ),
    createVersion: (projectId: string, identityId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/continuity/identities/${identityId}/versions?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      ),
    patchVersion: (projectId: string, versionId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/continuity/versions/${versionId}?projectId=${encodeURIComponent(projectId)}`,
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      ),
    approveVersion: (projectId: string, versionId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/versions/${versionId}/approve?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST" }
      ),
    createVariant: (projectId: string, versionId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/continuity/versions/${versionId}/variants?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      ),
    listReferences: (projectId: string, identityId?: string) => {
      const q = new URLSearchParams({ projectId });
      if (identityId) q.set("identityId", identityId);
      return req<{ items: any[] }>(`/api/continuity/references?${q}`);
    },
    createReference: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/continuity/references?projectId=${encodeURIComponent(projectId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    approveReference: (projectId: string, referenceId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/references/${referenceId}/approve?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST" }
      ),
    rejectReference: (projectId: string, referenceId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/references/${referenceId}/reject?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST" }
      ),
    revokeReference: (projectId: string, referenceId: string, reason = "") =>
      req<Record<string, unknown>>(
        `/api/continuity/references/${referenceId}/revoke?projectId=${encodeURIComponent(projectId)}&reason=${encodeURIComponent(reason)}`,
        { method: "POST" }
      ),
    preflight: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/continuity/preflight?projectId=${encodeURIComponent(projectId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    getPacket: (projectId: string, packetId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/packets/${packetId}?projectId=${encodeURIComponent(projectId)}`
      ),
    evaluate: (projectId: string, body: { assetId: string; packetId: string }) =>
      req<Record<string, unknown>>(`/api/continuity/evaluate?projectId=${encodeURIComponent(projectId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    getEvaluation: (projectId: string, evaluationId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/evaluations/${evaluationId}?projectId=${encodeURIComponent(projectId)}`
      ),
    review: (projectId: string, evaluationId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/continuity/evaluations/${evaluationId}/review?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      ),
    proposeCorrection: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(
        `/api/continuity/corrections/propose?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      ),
    enqueueCorrection: (projectId: string, correctionId: string) =>
      req<Record<string, unknown>>(
        `/api/continuity/corrections/${correctionId}/enqueue?projectId=${encodeURIComponent(projectId)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approvedBy: "user" }) }
      ),
  },
  magi: {
    readiness: () => req<Record<string, unknown>>("/api/magi/readiness"),
    gateWave4b: () => req<Record<string, unknown>>("/api/magi/gate/wave4b"),
    gateWave5MayBegin: () => req<Record<string, unknown>>("/api/magi/gate/wave5-may-begin"),
    refuseDeferred: (surfaceId: string) =>
      req<Record<string, unknown>>(`/api/magi/deferred/${encodeURIComponent(surfaceId)}/execute`, {
        method: "POST",
      }),
    fonts: () => req<Record<string, unknown>>("/api/magi/fonts"),
    listOverlays: (projectId: string) =>
      req<{ items: any[] }>(`/api/magi/projects/${projectId}/overlays`),
    getOverlayForAsset: (projectId: string, assetId: string) =>
      req<Record<string, unknown>>(
        `/api/magi/projects/${projectId}/overlays/by-asset/${encodeURIComponent(assetId)}`
      ),
    saveOverlay: (projectId: string, compositionId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/magi/projects/${projectId}/overlays/${compositionId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    validateOverlay: (projectId: string, body: Record<string, unknown>) =>
      req<{ ok: boolean; errors?: string[] }>(`/api/magi/projects/${projectId}/overlays/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    renderOverlay: (projectId: string, body: Record<string, unknown>) =>
      req<Record<string, unknown>>(`/api/magi/projects/${projectId}/overlays/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    importTimelineAsset: (projectId: string, body: Record<string, unknown>) =>
      req<{ ok: boolean; clip?: Record<string, unknown>; message?: string }>(
        `/api/magi/projects/${projectId}/timeline/import`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    exportToTimeline: (
      projectId: string,
      sceneId: string,
      body: Record<string, unknown>
    ) =>
      req<{ ok: boolean; batchBlockId: string; clips: Array<{ ok: boolean }>; mock: boolean }>(
        `/api/magi/projects/${projectId}/scenes/${encodeURIComponent(sceneId)}/timeline/export`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
  },
  library: (projectId: string, opts?: { q?: string; scope?: string; folder?: string; system_key?: string }) => {
    const q = new URLSearchParams();
    if (opts?.q) q.set("q", opts.q);
    if (opts?.scope) q.set("scope", opts.scope);
    if (opts?.folder) q.set("folder", opts.folder);
    if (opts?.system_key) q.set("system_key", opts.system_key);
    const qs = q.toString();
    return req<{
      items: any[];
      tree: {
        projectId: string;
        librarySchemaVersion: number;
        folders: any[];
        entityFolderCount: number;
        systemFolderCount: number;
      };
      librarySchemaVersion: number;
      folderMap: Record<string, { folderId: string; displayName: string; displayPath: string; systemKey?: string }>;
    }>(`/api/projects/${projectId}/library${qs ? `?${qs}` : ""}`);
  },
  libraryMigrate: (projectId: string) =>
    req(`/api/projects/${projectId}/library/migrate`, { method: "POST" }),
  libraryRepair: (projectId: string) =>
    req(`/api/projects/${projectId}/library/repair`, { method: "POST" }),
  libraryResolvePath: (projectId: string, body: { folderId?: string; systemKey?: string }) =>
    req<{ libraryPath: string }>(`/api/projects/${projectId}/library/resolve-path`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  libraryResolve: (projectId: string, body: { path?: string; systemKey?: string; query?: string }) =>
    req<any>(`/api/projects/${projectId}/library/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  libraryCodirectorContext: (projectId: string, limit = 8) =>
    req<any>(`/api/projects/${projectId}/library/codirector-context?limit=${limit}`),
  libraryPreflight: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/library/preflight`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchAssetLibrary: (assetId: string, body: Record<string, unknown>) =>
    req(`/api/assets/${assetId}/library`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchAssetMeta: (assetId: string, body: Record<string, unknown>) =>
    req(`/api/assets/${assetId}/meta`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  promoteGlobal: (assetId: string) => req(`/api/assets/${assetId}/promote-global`, { method: "POST" }),
  assetGraph: (assetId: string) => req<any>(`/api/assets/${assetId}/graph`),
  createAssetEdge: (body: { from_id: string; to_id: string; relation?: string; meta?: any }) =>
    req(`/api/assets/edges`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  marketplace: (opts?: { category?: string; base_model?: string; q?: string }) => {
    const q = new URLSearchParams();
    if (opts?.category) q.set("category", opts.category);
    if (opts?.base_model) q.set("base_model", opts.base_model);
    if (opts?.q) q.set("q", opts.q);
    const qs = q.toString();
    return req<any[]>(`/api/marketplace${qs ? `?${qs}` : ""}`);
  },
  marketplaceInstall: (itemId: string, path: string, approved: boolean) => {
    const fd = new FormData();
    fd.append("path", path);
    fd.append("approved", approved ? "true" : "false");
    return req<any>(`/api/marketplace/${itemId}/install`, { method: "POST", body: fd });
  },
  loraStack: (scope = "global") => req<{ scope: string; stack: any[] }>(`/api/lora/stack?scope=${encodeURIComponent(scope)}`),
  putLoraStack: (scope: string, stack: any[]) =>
    req(`/api/lora/stack`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, stack }),
    }),
  promote: (projectId: string, body: Record<string, unknown>) =>
    req<{ ok: boolean; applied: string[] }>(`/api/projects/${projectId}/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  spatialMap: {
    listMaps: (projectId: string) =>
      req<SpatialMapListResponse>(`/api/spatial-map/projects/${projectId}/maps`),
    createMap: (projectId: string, body: SpatialMapCreateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    getMap: (projectId: string, documentId: string) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}`),
    updateMap: (projectId: string, documentId: string, body: SpatialMapUpdateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    placeCharacter: (projectId: string, documentId: string, body: SpatialCharacterPlacementBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/characters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    placeProp: (projectId: string, documentId: string, body: SpatialPropPlacementBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/props`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    createCamera: (projectId: string, documentId: string, body: SpatialCameraCreateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/cameras`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    createPath: (projectId: string, documentId: string, body: SpatialMovementPathCreateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/paths`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    assignScene: (projectId: string, documentId: string, body: SpatialAssignSceneBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/assign-scene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    createVariant: (projectId: string, documentId: string, body: SpatialVariantCreateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/variants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    referenceBundle: (projectId: string, documentId: string, target: "image" | "video", cameraId?: string) => {
      const query = new URLSearchParams({ target });
      if (cameraId) query.set("cameraId", cameraId);
      return req<SpatialReferenceBundleResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/reference-bundle?${query.toString()}`
      );
    },
    createCollage: (projectId: string, documentId: string, body: SpatialCollageCreateBody) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/collage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    upsertCollageView: (
      projectId: string,
      documentId: string,
      direction: string,
      body: Spatial360ViewUpsertBody
    ) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/collage/views/${direction}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    capturePlan: (projectId: string, documentId: string, body: SpatialCapturePlanBody) =>
      req<SpatialCapturePlanResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/capture-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    moveCharacter: (
      projectId: string,
      documentId: string,
      placementId: string,
      body: SpatialCharacterPlacementUpdateBody
    ) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/characters/${placementId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    moveProp: (projectId: string, documentId: string, placementId: string, body: SpatialPropPlacementUpdateBody) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/props/${placementId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    updateCamera: (projectId: string, documentId: string, cameraId: string, body: SpatialCameraUpdateBody) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/cameras/${cameraId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      ),
    removeCharacter: (projectId: string, documentId: string, placementId: string) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/characters/${placementId}`,
        { method: "DELETE" }
      ),
    removeProp: (projectId: string, documentId: string, placementId: string) =>
      req<SpatialMapDocumentResponse>(`/api/spatial-map/projects/${projectId}/maps/${documentId}/props/${placementId}`, {
        method: "DELETE",
      }),
    removeCamera: (projectId: string, documentId: string, cameraId: string) =>
      req<SpatialMapDocumentResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/cameras/${cameraId}`,
        { method: "DELETE" }
      ),
    consistencyCheck: (projectId: string, documentId: string) =>
      req<SpatialConsistencyCheckResponse>(
        `/api/spatial-map/projects/${projectId}/maps/${documentId}/consistency-check`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        }
      ),
  },
  getSceneSpatial: (projectId: string, sceneId: string) =>
    req<{ id: string; project_id: string; scene_id: string; guidance: string; doc: any }>(
      `/api/projects/${projectId}/scenes/${sceneId}/spatial`
    ),
  putSceneSpatial: (projectId: string, sceneId: string, body: { doc: any; guidance?: string }) =>
    req(`/api/projects/${projectId}/scenes/${sceneId}/spatial`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  spatialPrompt: (projectId: string, sceneId: string, body?: Record<string, unknown>) =>
    req<{ layers: Record<string, string>; positive: string; negative: string; guidance: string; guidance_hint: string }>(
      `/api/projects/${projectId}/scenes/${sceneId}/spatial/prompt`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }
    ),
  spatialGenerate: (projectId: string, sceneId: string, body?: Record<string, unknown>) =>
    req<{ id: string; status: string; params: any }>(`/api/projects/${projectId}/scenes/${sceneId}/spatial/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  spatialSendDirector: (projectId: string, sceneId: string, body?: Record<string, unknown>) =>
    req<{ ok: boolean; applied: string[]; scene_id: string }>(
      `/api/projects/${projectId}/scenes/${sceneId}/spatial/send-director`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }
    ),
  spatialCommands: (projectId: string, sceneId: string, body: { command: string; approved?: boolean }) =>
    req<{ proposed_mutations: any[]; applied: boolean; message: string; doc?: any }>(
      `/api/projects/${projectId}/scenes/${sceneId}/spatial/commands`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    ),
  scriptwriter: {
    studio: (projectId: string) =>
      req<{
        ok: boolean;
        document: Record<string, unknown>;
        stats: Record<string, unknown>;
        navigator: Array<Record<string, unknown>>;
        continuity: Array<Record<string, unknown>>;
        bibleCandidates: Array<Record<string, unknown>>;
        revisions: Array<Record<string, unknown>>;
        transactions: Array<Record<string, unknown>>;
        recovery?: Record<string, unknown> | null;
        paginationMode?: string;
      }>(`/api/projects/${projectId}/scriptwriter`),
    documents: (projectId: string) =>
      req<{ ok: boolean; documents: Array<Record<string, unknown>> }>(
        `/api/projects/${projectId}/scriptwriter/documents`,
      ),
    document: (projectId: string, documentId: string) =>
      req<{
        ok: boolean;
        document: Record<string, unknown>;
        stats: Record<string, unknown>;
        navigator: Array<Record<string, unknown>>;
        continuity: Array<Record<string, unknown>>;
        bibleCandidates: Array<Record<string, unknown>>;
        revisions: Array<Record<string, unknown>>;
        transactions: Array<Record<string, unknown>>;
        recovery?: Record<string, unknown> | null;
        paginationMode?: string;
      }>(`/api/projects/${projectId}/scriptwriter/documents/${documentId}`),
    autosave: (projectId: string, documentId: string, body: { elements: unknown[]; expectedRevision?: number }) =>
      req<{ ok: boolean; document: Record<string, unknown>; saveState?: string }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/autosave`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
      ),
    insertScene: (projectId: string, documentId: string, body?: { afterOrder?: number; heading?: string }) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/scenes/insert`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) },
      ),
    deleteScene: (projectId: string, documentId: string, sceneHeadingId: string) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/scenes/delete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId }),
        },
      ),
    moveScene: (projectId: string, documentId: string, sceneHeadingId: string, toIndex: number) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/scenes/move`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId, toIndex }),
        },
      ),
    createRevision: (projectId: string, documentId: string, body: { name: string; color?: string; note?: string }) =>
      req<{ ok: boolean; revision: Record<string, unknown>; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/revisions`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
      ),
    compareRevisions: (projectId: string, documentId: string, revisionA: string, revisionB: string) =>
      req<{ ok: boolean; changed: unknown[] }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/revisions/compare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ revisionA, revisionB }),
        },
      ),
    restoreRevision: (projectId: string, documentId: string, revisionId: string) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/revisions/restore`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ revisionId }),
        },
      ),
    importText: (projectId: string, documentId: string, text: string, format = "fountain") =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/import`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, format }),
        },
      ),
    exportFountain: (projectId: string, documentId: string) =>
      req<{ ok: boolean; fountain: string; title: string }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/export/fountain`,
      ),
    exportPdf: (projectId: string, documentId: string) =>
      req<{ ok: boolean; path?: string; error?: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/export/pdf`,
        { method: "POST" },
      ),
    applyProposal: (projectId: string, documentId: string, proposal: Record<string, unknown>) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/proposals/apply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ proposal }),
        },
      ),
    convertOutline: (projectId: string, documentId: string, beats: Array<Record<string, unknown>>) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/outline/convert`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ beats }),
        },
      ),
    linkScene: (projectId: string, documentId: string, sceneHeadingId: string, projectSceneId: string) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/scenes/link`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId, projectSceneId }),
        },
      ),
    prepareTimeline: (projectId: string, documentId: string, sceneHeadingId: string) =>
      req<{ ok: boolean; proposal: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/timeline/prepare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId }),
        },
      ),
    applyTimelineMetadata: (
      projectId: string,
      documentId: string,
      sceneHeadingId: string,
      metadata: Record<string, unknown>,
    ) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/timeline/apply-metadata`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId, metadata }),
        },
      ),
    analyzeScene: (projectId: string, documentId: string, sceneHeadingId: string) =>
      req<{ ok: boolean; analysis: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/analyze/scene`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sceneHeadingId }),
        },
      ),
    undo: (projectId: string, documentId: string) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/undo`,
        { method: "POST" },
      ),
    productionLock: (projectId: string, documentId: string, locked: boolean) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/production-lock`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ locked }),
        },
      ),
    searchReplace: (
      projectId: string,
      documentId: string,
      body: { find: string; replace?: string; elementTypes?: string[] },
    ) =>
      req<{ ok: boolean; document: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/search-replace`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      ),
    proposeBible: (projectId: string, documentId: string) =>
      req<{ ok: boolean; proposals: Array<Record<string, unknown>> }>(
        `/api/projects/${projectId}/scriptwriter/documents/${documentId}/bible/propose`,
        { method: "POST" },
      ),
    migrationPreview: (projectId: string) =>
      req<{ ok?: boolean; segmentCount?: number; preview?: unknown }>(
        `/api/projects/${projectId}/scriptwriter/migration/preview`,
      ),
    migrationRun: (projectId: string) =>
      req<{ ok?: boolean; document?: Record<string, unknown> }>(
        `/api/projects/${projectId}/scriptwriter/migration/run`,
        { method: "POST" },
      ),
  },
  getScript: (projectId: string) =>
    req<{ doc: any; segments: any[]; panels: any[] }>(`/api/projects/${projectId}/script`),
  importScript: (projectId: string, text: string) =>
    req<{ ok: boolean; count: number; segments: any[] }>(`/api/projects/${projectId}/script/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),
  createSegment: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/script/segments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchSegment: (projectId: string, segmentId: string, body: Record<string, unknown>) =>
    req<{ segment: any; visual_change: boolean }>(`/api/projects/${projectId}/script/segments/${segmentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  createPanel: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/storyboard/panels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchPanel: (projectId: string, panelId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/storyboard/panels/${panelId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  storyboardGenerate: (projectId: string, body: Record<string, unknown>) =>
    req<{ job_id: string; panel_id: string; status: string }>(`/api/projects/${projectId}/storyboard/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  storyboardSendDirector: (projectId: string, body: Record<string, unknown>) =>
    req<{ ok: boolean; created_scene_ids: string[] }>(`/api/projects/${projectId}/storyboard/send-director`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  // --------------------------------------------------------------------
  // M2.1: Production Bible + durable proposals/approvals/execution.
  // --------------------------------------------------------------------
  getBible: (projectId: string) =>
    req<CoDirectorBible>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible`),
  listBibleVersions: (projectId: string) =>
    req<{ projectId: string; versions: CoDirectorBibleVersion[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/versions`,
    ),
  getBibleVersion: (projectId: string, versionNumber: number) =>
    req<CoDirectorBibleVersion>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/versions/${versionNumber}`,
    ),
  previewBibleImport: (projectId: string, body: { includeScenes?: boolean; includeAssetsAsProps?: boolean } = {}) =>
    req<CoDirectorBibleImportPreview>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/import/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  confirmBibleImport: (
    projectId: string,
    body: { entities: CoDirectorBibleEntity[]; facts: CoDirectorBibleFact[]; summary?: string; changeReason?: string },
  ) =>
    req<CoDirectorBible>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/import/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  createBibleVersion: (
    projectId: string,
    body: { mutations: CoDirectorBibleMutationSet; createdBy?: string },
  ) =>
    req<CoDirectorBibleVersion>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  // M2.3: Production Bible domain APIs
  getBibleSummary: (projectId: string) =>
    req<BibleDomainSummary>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/summary`),
  getBibleHealth: (projectId: string) =>
    req<BibleDomainSummary>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/health`),
  exportBible: (projectId: string) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/export`),
  listBibleAudit: (projectId: string, limit = 100) =>
    req<{ projectId: string; events: BibleAuditEvent[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/audit?limit=${limit}`,
    ),
  listBibleCharacters: (projectId: string) =>
    req<{ projectId: string; characters: CoDirectorBibleEntity[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/characters`,
    ),
  createBibleCharacter: (
    projectId: string,
    body: { entityKey: string; displayName?: string; data?: Record<string, unknown> },
  ) =>
    req<CoDirectorBibleEntity>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/characters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  patchBibleCharacter: (
    projectId: string,
    stableId: string,
    body: { displayName?: string; data?: Record<string, unknown>; contentRevision?: number },
  ) =>
    req<CoDirectorBibleEntity>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/characters/${encodeURIComponent(stableId)}`,
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  approveBibleCharacter: (projectId: string, stableId: string) =>
    req<CoDirectorBibleEntity>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/characters/${encodeURIComponent(stableId)}/approve`,
      { method: "POST" },
    ),
  lockBibleCharacter: (projectId: string, stableId: string) =>
    req<CoDirectorBibleEntity>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/characters/${encodeURIComponent(stableId)}/lock`,
      { method: "POST" },
    ),
  listBibleLocations: (projectId: string) =>
    req<{ projectId: string; locations: CoDirectorBibleEntity[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/locations`,
    ),
  listBibleRelationships: (projectId: string) =>
    req<{ projectId: string; relationships: CoDirectorBibleEntity[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/relationships`,
    ),
  listBibleConflicts: (projectId: string) =>
    req<{ projectId: string; conflicts: CoDirectorBibleEntity[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/conflicts`,
    ),
  syncBibleConflicts: (projectId: string) =>
    req<{ projectId: string; conflicts: Record<string, unknown>[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/bible/conflicts/sync`,
      { method: "POST" },
    ),
  seedDemoBible: (projectId: string) =>
    req<{ seeded: boolean }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/bible/seed-demo`, {
      method: "POST",
    }),
  listProposals: (projectId: string, status?: string) =>
    req<{ projectId: string; proposals: CoDirectorProposal[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  getProposal: (projectId: string, proposalId: string) =>
    req<CoDirectorProposal>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}`,
    ),
  previewProposal: (projectId: string, proposalId: string) =>
    req<{
      proposal: CoDirectorProposal;
      currentVersionNumber: number | null;
      wouldCreateVersionNumber: number | null;
      entityDiff: Record<string, unknown>[];
      factDiff: Record<string, unknown>[];
      isStale: boolean;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/preview`),
  approveProposal: (projectId: string, proposalId: string, body: { note?: string; decidedBy?: string } = {}) =>
    req<CoDirectorExecutionReceipt>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/approve`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  rejectProposal: (projectId: string, proposalId: string, body: { note?: string; decidedBy?: string } = {}) =>
    req<CoDirectorProposal>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/reject`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  requestProposalRevision: (projectId: string, proposalId: string, body: { note?: string; decidedBy?: string } = {}) =>
    req<CoDirectorProposal>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/request-revision`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  cancelProposal: (projectId: string, proposalId: string, body: { note?: string; decidedBy?: string } = {}) =>
    req<CoDirectorProposal>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/cancel`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  getProposalReceipt: (projectId: string, proposalId: string) =>
    req<CoDirectorExecutionReceipt>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposalId)}/receipt`,
    ),
  visionValidate: (body: {
    projectId: string;
    assetId?: string;
    planId?: string;
    sceneId?: string;
    referenceAssetId?: string;
    referenceSet?: {
      id: string;
      version: number;
      bindings: Array<{
        bindingId: string;
        role: string;
        influence?: string;
        assetId: string;
      }>;
    } | null;
    provider?: "mock" | "local";
    fixtureProfile?: string;
    validators?: string[];
  }) =>
    req<{ session: Record<string, unknown>; report: Record<string, unknown>; comparison: Record<string, unknown> }>(
      "/api/codirector/vision/validate",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  visionValidationReport: (reportId: string, projectId?: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/vision/report/${encodeURIComponent(reportId)}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
    ),
  visionValidationSession: (sessionId: string, projectId?: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/vision/session/${encodeURIComponent(sessionId)}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
    ),
  visionApprove: (body: {
    projectId: string;
    sessionId: string;
    reviewer?: string;
    notes?: string;
    override?: boolean;
    linkToBible?: boolean;
  }) =>
    req<Record<string, unknown>>("/api/codirector/vision/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  visionReject: (body: {
    projectId: string;
    sessionId: string;
    reviewer?: string;
    notes?: string;
    override?: boolean;
  }) =>
    req<Record<string, unknown>>("/api/codirector/vision/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  visionCorrection: (body: {
    projectId: string;
    sessionId: string;
    findingValidatorIds?: string[];
    notes?: string;
    createdBy?: string;
  }) =>
    req<Record<string, unknown>>("/api/codirector/vision/correction", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  visionValidationComparison: (comparisonId: string, projectId?: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/vision/comparison/${encodeURIComponent(comparisonId)}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
    ),
  visionValidationHistory: (projectId: string, limit: number = 50) =>
    req<{ projectId: string; sessions: Record<string, unknown>[] }>(
      `/api/codirector/vision/history?projectId=${encodeURIComponent(projectId)}&limit=${limit}`,
    ),
  // M2.7 Production Executive (flag: STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1)
  productionJobsList: (projectId: string, opts?: { status?: string; sceneId?: string; limit?: number }) => {
    const q = new URLSearchParams({ projectId });
    if (opts?.status) q.set("status", opts.status);
    if (opts?.sceneId) q.set("sceneId", opts.sceneId);
    if (opts?.limit) q.set("limit", String(opts.limit));
    return req<{ projectId: string; jobs: Record<string, unknown>[] }>(`/api/codirector/jobs?${q}`);
  },
  productionJobGet: (jobId: string, projectId?: string) =>
    req<{ job: Record<string, unknown> }>(
      `/api/codirector/jobs/${encodeURIComponent(jobId)}${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
    ),
  productionJobCreate: (body: Record<string, unknown>) =>
    req<{ job: Record<string, unknown> }>("/api/codirector/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionClosedLoop: (body: {
    projectId: string;
    sceneId: string;
    owner?: string;
    idempotencyKey?: string;
    provider?: string;
  }) =>
    req<Record<string, unknown>>("/api/codirector/jobs/closed-loop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionJobPause: (jobId: string, body: { actor?: string; reason?: string } = {}) =>
    req<{ job: Record<string, unknown> }>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionJobResume: (jobId: string, body: { actor?: string; reason?: string } = {}) =>
    req<{ job: Record<string, unknown> }>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionJobRetry: (jobId: string, body: { actor?: string; reason?: string } = {}) =>
    req<{ job: Record<string, unknown> }>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionJobCancel: (jobId: string, body: { actor?: string; reason?: string } = {}) =>
    req<{ job: Record<string, unknown> }>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  productionJobMarkApproval: (
    jobId: string,
    body: { proposalId: string; approved?: boolean; actor?: string; reason?: string },
  ) =>
    req<{ job: Record<string, unknown>; autoApproved: boolean }>(
      `/api/codirector/jobs/${encodeURIComponent(jobId)}/mark-approval`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  productionJobHistory: (jobId: string) =>
    req<Record<string, unknown>>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/history`),
  productionJobDependencies: (jobId: string) =>
    req<Record<string, unknown>>(`/api/codirector/jobs/${encodeURIComponent(jobId)}/dependencies`),
  productionEvents: (projectId: string, jobId?: string) => {
    const q = new URLSearchParams({ projectId });
    if (jobId) q.set("jobId", jobId);
    return req<{ projectId: string; events: Record<string, unknown>[] }>(`/api/codirector/jobs/events?${q}`);
  },
  productionNotifications: (projectId: string, unreadOnly = false) =>
    req<{ projectId: string; notifications: Record<string, unknown>[] }>(
      `/api/codirector/jobs/notifications?projectId=${encodeURIComponent(projectId)}&unreadOnly=${unreadOnly ? "true" : "false"}`,
    ),
  productionStatistics: (projectId: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/jobs/statistics?projectId=${encodeURIComponent(projectId)}`,
    ),
  productionSceneProgress: (projectId: string, sceneId: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/jobs/scene-progress?projectId=${encodeURIComponent(projectId)}&sceneId=${encodeURIComponent(sceneId)}`,
    ),
  productionWorkerDrain: (maxSteps = 50) =>
    req<{ steps: number; workerRunning: boolean }>("/api/codirector/jobs/worker/drain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ maxSteps }),
    }),
  // M2.2 tools. There is no "execute tool" call by design: read tools run through
  // `runCoDirectorReadTool`, and mutating tools go through the proposal endpoints above.
  listCoDirectorTools: () =>
    req<{ toolSchemaVersion: number; tools: CoDirectorToolDefinition[] }>("/api/codirector/tools"),
  listProjectCoDirectorTools: (projectId: string) =>
    req<{
      projectId: string;
      toolSchemaVersion: number;
      tools: CoDirectorToolDefinition[];
      availability: CoDirectorToolAvailability[];
      capabilities: Record<string, unknown>;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools`),
  coDirectorToolAvailability: (projectId: string) =>
    req<{
      projectId: string;
      availability: CoDirectorToolAvailability[];
      capabilities: Record<string, unknown>;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/availability`),
  runCoDirectorReadTool: (
    projectId: string,
    body: {
      toolId: string;
      arguments?: Record<string, unknown>;
      sceneId?: string;
      requestId?: string;
      toolSchemaVersion?: number;
    },
  ) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  proposeCoDirectorToolCall: (
    projectId: string,
    body: { toolId: string; arguments?: Record<string, unknown>; sceneId?: string; requestId?: string; createdBy?: string },
  ) =>
    req<CoDirectorProposal>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/proposals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  runCoDirectorAuditedTool: (
    projectId: string,
    body: {
      toolId: string;
      arguments?: Record<string, unknown>;
      sceneId?: string;
      requestId?: string;
    },
  ) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/audited`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getCoDirectorProjectWiki: (projectId: string) =>
    req<CoDirectorProjectWiki>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki`),
  getCoDirectorProjectNotes: (projectId: string) =>
    req<{ ok: boolean; notes: Array<Record<string, unknown>>; count: number }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/notes`,
    ),
  promoteCoDirectorWiki: (
    projectId: string,
    body: { text?: string; noteId?: string; destination?: string; pageHint?: string },
  ) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  compileCoDirectorWiki: (projectId: string) =>
    req<{ ok: boolean; compiled?: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/compile`,
      { method: "POST" },
    ),
  refineCoDirectorStorySummary: (projectId: string) =>
    req<{ ok: boolean; storySummary: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/story-summary/refine`,
      { method: "POST" },
    ),
  correctCoDirectorStorySummary: (projectId: string, correction: string) =>
    req<{ ok: boolean; storySummary: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/story-summary/correct`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correction }),
      },
    ),
  previewCoDirectorWikiCorrection: (
    projectId: string,
    instruction: string,
    target?: Record<string, unknown>,
  ) =>
    req<{ ok: boolean; preview: Record<string, unknown> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/correction/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction, target }),
      },
    ),
  applyCoDirectorWikiCorrection: (projectId: string, previewId: string) =>
    req<{
      ok: boolean;
      correction?: Record<string, unknown>;
      undoId?: string;
      summaryLines?: string[];
      compiledRevision?: number;
    }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/correction/apply`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ previewId }),
      },
    ),
  undoCoDirectorWikiCorrection: (projectId: string, correctionId: string) =>
    req<{ ok: boolean; restoredRevision?: number }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/correction/${encodeURIComponent(correctionId)}/undo`,
      { method: "POST" },
    ),
  getCoDirectorWikiCorrections: (projectId: string) =>
    req<{ ok: boolean; corrections: Array<Record<string, unknown>> }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/corrections`,
    ),
  getCoDirectorProductionLifecycle: (projectId: string) =>
    req<{
      ok: boolean;
      lifecycle: Record<string, unknown>;
      castingBlockedReason?: string | null;
      productionBlockedReason?: string | null;
      nextSteps?: string[];
      requiresScriptForCasting?: boolean;
      specialistsForStage?: string[];
      sceneReadinessMatrix?: Array<Record<string, unknown>>;
      handoffs?: { timelineReady?: boolean; magiReady?: boolean; generationAllowedSceneIds?: string[] };
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/production-lifecycle`),
  putCoDirectorLifecycleScript: (projectId: string, status: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/production-lifecycle/script`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    ),
  getTimelineContextPackage: (
    projectId: string,
    sceneId: string,
    actionScope: "exploration" | "production" = "exploration",
  ) =>
    req<{
      ok: boolean;
      package?: {
        projectId: string;
        sceneId: string;
        compiledAt: string;
        logline: string;
        shortSummary: string;
        longSummary: string;
        themes: string[];
        characters: Array<{
          characterId: string;
          name: string;
          castStatus: string;
          portraitAssetId?: string | null;
          voiceId?: string | null;
          wikiPageId?: string | null;
          locked: boolean;
        }>;
        references: Array<{ assetId: string; tag: string; kind: string; filename: string; role: string }>;
        locations: Array<{ locationId: string; name: string; wikiPageId?: string | null; ready: boolean }>;
        continuity: Record<string, string>;
        productionNotes: Record<string, unknown>;
        referenceAssets: Array<{ assetId: string; tag: string; kind: string; filename: string; role: string }>;
        generationConstraints: {
          engine: string;
          durationSec: number;
          aspectRatio: string;
          fps: number;
          fpsMode: string;
          negativePrompt: string;
          globalStylePrompt: string;
        };
        readiness: {
          sceneId: string;
          status: string;
          blockerSummary: string;
          castReady: boolean;
          locationReady: boolean;
          wardrobeReady: boolean;
          propsReady: boolean;
          imageReferencesReady: boolean;
          voiceReady: boolean;
          generationPlanReady: boolean;
        };
        gateLevel: "EXPLORATION" | "PRODUCTION_WARNING" | "PRODUCTION_LOCK";
        sceneStatus: string;
        sceneCraft: {
          sceneId: string;
          shots: Array<{
            shotId: string;
            sceneId: string;
            label: string;
            assetIds: string[];
            timelineClipIds: string[];
            status: string;
          }>;
        };
      };
      error?: string;
    }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/timeline-context/${encodeURIComponent(sceneId)}?action_scope=${actionScope}`,
    ),
  getTimelineSceneStatus: (projectId: string) =>
    req<{
      ok: boolean;
      projectId: string;
      counts: Record<string, number>;
      scenes: Array<{ sceneId: string; name: string; status: string }>;
      totalScenes: number;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/timeline-context/scene-status`),
  getTimelineSmartGate: (
    projectId: string,
    sceneId: string,
    actionScope: "exploration" | "production" = "production",
  ) =>
    req<{
      ok: boolean;
      level: "EXPLORATION" | "PRODUCTION_WARNING" | "PRODUCTION_LOCK";
      decision: "ALLOW" | "ALLOW_WITH_WARNING" | "BLOCK";
      reason: string;
      readiness?: Record<string, unknown> | null;
      package?: Record<string, unknown> | null;
    }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/timeline-context/${encodeURIComponent(sceneId)}/gate?action_scope=${actionScope}`,
    ),
  postCoDirectorLifecycleCasting: (
    projectId: string,
    body: { characterName: string; status: string; exploratory?: boolean; wikiPageId?: string },
  ) =>
    req<Record<string, unknown>>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/production-lifecycle/casting`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  rebuildCoDirectorProjectWiki: (projectId: string) =>
    req<{
      ok: boolean;
      requestId?: string;
      projectId?: string;
      extractedCandidates?: number;
      wikiHasContent?: boolean;
      toc?: { key: string; label: string; count: number }[];
      verification?: Record<string, unknown>;
      error?: string;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/rebuild`, {
      method: "POST",
    }),
  diagnoseCoDirectorProjectWiki: (projectId: string) =>
    req<{
      ok: boolean;
      projectId?: string;
      projectName?: string;
      userMessageCount?: number;
      knowledgeEntryCount?: number;
      wikiHasContent?: boolean;
      wikiSectionCounts?: Record<string, number>;
      sourceOfTruth?: string;
      error?: string;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/diagnostic`),
  remediateCoDirectorReasoningLeaks: (projectId: string) =>
    req<{
      ok: boolean;
      projectId?: string;
      scanned?: number;
      remediated?: number;
      quarantinedFull?: number;
      gate?: string;
      pass?: boolean;
      error?: string;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/conversation/remediate-reasoning`, {
      method: "POST",
    }),
  reorganizeCoDirectorProjectWiki: (
    projectId: string,
    body?: {
      domains?: string[];
      useSpecialists?: boolean;
      preserveLockedCanon?: boolean;
      createUndoSnapshot?: boolean;
    },
  ) =>
    req<{
      ok: boolean;
      job?: {
        id: string;
        status: string;
        stage?: string | null;
        summaryLines?: string[];
        recordsReviewed?: number;
        recordsMerged?: number;
        recordsReclassified?: number;
        recordsRejected?: number;
        conflictsFound?: number;
        tocRebuilt?: boolean;
        readBackVerified?: boolean;
        specialistAssignments?: { selectedSpecialists?: string[] }[];
        changes?: unknown[];
        revisionId?: string | null;
        error?: string | null;
      };
      stages?: string[];
      specialistsActivated?: string[];
      error?: string;
    }>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/reorganize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  getCoDirectorWikiReorganizeJob: (projectId: string, jobId: string) =>
    req<Record<string, unknown>>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/reorganize/${encodeURIComponent(jobId)}`,
    ),
  undoCoDirectorWikiReorganize: (projectId: string, jobId: string) =>
    req<{ ok: boolean; error?: string; wiki?: CoDirectorProjectWiki }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/reorganize/${encodeURIComponent(jobId)}/undo`,
      { method: "POST" },
    ),
  getCoDirectorWikiHealth: (projectId: string) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/health`),
  runCoDirectorWikiMaintenance: (projectId: string, body?: { applyLightCleanup?: boolean }) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/maintenance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  getCoDirectorWikiToolContext: (projectId: string) =>
    req<Record<string, unknown>>(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/tool-context`),
  exportCoDirectorProjectWikiPdf: (
    projectId: string,
    body: {
      exportTitle?: string;
      includeCover?: boolean;
      includeToc?: boolean;
      includeOpenQuestions?: boolean;
      includeUnresolved?: boolean;
      includeImages?: boolean;
      includeAudioVideo?: boolean;
      includeProductionMetadata?: boolean;
      sectionsMode?: string;
      selectedSections?: string[];
      sizeMode?: string;
    },
  ) =>
    reqBlob(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/export/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  exportCoDirectorProjectWikiHtml: (
    projectId: string,
    body: {
      exportTitle?: string;
      includeCover?: boolean;
      includeToc?: boolean;
      includeOpenQuestions?: boolean;
      includeUnresolved?: boolean;
      includeImages?: boolean;
      includeAudioVideo?: boolean;
      includeProductionMetadata?: boolean;
      sectionsMode?: string;
      selectedSections?: string[];
      sizeMode?: string;
    },
  ) =>
    reqBlob(`/api/codirector/projects/${encodeURIComponent(projectId)}/wiki/export/html`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getCoDirectorActivePlan: (projectId: string) =>
    req<CoDirectorProjectPlanLookup>(`/api/codirector/projects/${encodeURIComponent(projectId)}/plans/active`),
  getCoDirectorProjectPlanById: (projectId: string, planId: string) =>
    req<CoDirectorProjectPlanLookup>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/plans/${encodeURIComponent(planId)}`,
    ),
  getProductionPlan: (projectId: string, planId: string) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId: "production_plan.get",
        arguments: { planId },
        requestId: `plan-get-${planId}-${Date.now()}`,
      }),
    }),
  listProductionPlans: (projectId: string, limit = 25) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId: "production_plan.list",
        arguments: { limit },
        requestId: `plan-list-${Date.now()}`,
      }),
    }),
  getProductionPlanReadiness: (projectId: string, planId: string) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId: "production_plan.get_readiness",
        arguments: { planId },
        requestId: `plan-ready-${planId}-${Date.now()}`,
      }),
    }),
  listProductionPlanEvents: (projectId: string, planId: string) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId: "production_plan.list_events",
        arguments: { planId, limit: 100 },
        requestId: `plan-events-${planId}-${Date.now()}`,
      }),
    }),
  listProductionPlanVersions: (projectId: string, planId: string) =>
    req<CoDirectorToolInvocation>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId: "production_plan.list_versions",
        arguments: { planId },
        requestId: `plan-versions-${planId}-${Date.now()}`,
      }),
    }),
  proposeProductionPlanCommand: (
    projectId: string,
    toolId: string,
    arguments_: Record<string, unknown>,
    requestId?: string,
  ) =>
    req<CoDirectorProposal>(`/api/codirector/projects/${encodeURIComponent(projectId)}/tools/proposals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        toolId,
        arguments: arguments_,
        requestId: requestId || `plan-cmd-${toolId}-${Date.now()}`,
        createdBy: "user",
      }),
    }),
  listCoDirectorToolInvocations: (projectId: string, opts: { toolId?: string; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (opts.toolId) params.set("tool_id", opts.toolId);
    if (opts.limit) params.set("limit", String(opts.limit));
    const query = params.toString();
    return req<{ projectId: string; invocations: CoDirectorToolInvocation[] }>(
      `/api/codirector/projects/${encodeURIComponent(projectId)}/tool-invocations${query ? `?${query}` : ""}`,
    );
  },
  mediaUrl: (absPath?: string | null) => {
    if (!absPath) return "";
    const normalized = absPath.replace(/\//g, "\\").toLowerCase();
    const marker = "\\data\\";
    const idx = normalized.lastIndexOf(marker);
    if (idx >= 0) {
      const rel = absPath.slice(idx + marker.length).replace(/\\/g, "/");
      return `/media/${rel}`;
    }
    return `/api/file?path=${encodeURIComponent(absPath)}`;
  },
  assetUrl: (assetId: string) => `/api/assets/${assetId}/file`,
  m28Status: () => req<Record<string, boolean>>("/api/codirector/m28/status"),
  m28RadarDiscover: (source: "huggingface" | "github") =>
    req<any>("/api/codirector/m28/radar/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    }),
  m28RadarRegistry: () =>
    req<{ entries: any[] }>("/api/codirector/m28/radar/registry"),
  m28WatchlistAdd: (entryId: string, projectId?: string) =>
    req<any>("/api/codirector/m28/radar/watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entryId, projectId }),
    }),
  m28CompatEvaluate: (entryId: string, env?: Record<string, unknown>) =>
    req<any>("/api/codirector/m28/compat/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entryId, env }),
    }),
  m28SandboxCreate: (name: string) =>
    req<any>("/api/codirector/m28/sandbox", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  m28SandboxPlan: (sandboxId: string, entryId: string) =>
    req<any>("/api/codirector/m28/sandbox/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sandboxId, entryId }),
    }),
  m28SandboxPlanReject: (planId: string) =>
    req<any>(`/api/codirector/m28/sandbox/plan/${encodeURIComponent(planId)}/reject`, {
      method: "POST",
    }),
  m28SandboxPlanApprove: (planId: string, projectId: string) =>
    req<any>(`/api/codirector/m28/sandbox/plan/${encodeURIComponent(planId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId }),
    }),
  m28SandboxStart: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/start`, { method: "POST" }),
  m28SandboxStop: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/stop`, { method: "POST" }),
  m28SandboxRestart: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/restart`, { method: "POST" }),
  m28SandboxHealth: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/health`),
  m28SandboxDetect: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/detect`, { method: "POST" }),
  m28SandboxValidate: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/validate`, { method: "POST" }),
  m28SandboxRemove: (sandboxId: string) =>
    req<any>(`/api/codirector/m28/sandbox/${encodeURIComponent(sandboxId)}/remove`, { method: "POST" }),
  m28PromoteCreate: (sandboxId: string) =>
    req<any>("/api/codirector/m28/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sandboxId }),
    }),
  m28PromoteReject: (manifestId: string) =>
    req<any>(`/api/codirector/m28/promote/${encodeURIComponent(manifestId)}/reject`, { method: "POST" }),
  m28PromoteApprove: (manifestId: string, projectId: string) =>
    req<any>(`/api/codirector/m28/promote/${encodeURIComponent(manifestId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId }),
    }),
  m28RoutingRecommend: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m28/routing/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m28RecipeCreate: (projectId: string, name: string) =>
    req<any>("/api/codirector/m28/recipes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, name }),
    }),
  m28RecipeRun: (recipeId: string, simulateFailureAt?: number) =>
    req<any>(`/api/codirector/m28/recipes/${encodeURIComponent(recipeId)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ simulateFailureAt }),
    }),
  m28ShotProfileCreate: (projectId: string, name: string) =>
    req<any>("/api/codirector/m28/shot-profiles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, name }),
    }),
  m28ShotProfileSave: (profileId: string, payload: Record<string, unknown>, mode?: string) =>
    req<any>(`/api/codirector/m28/shot-profiles/${encodeURIComponent(profileId)}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, mode }),
    }),
  m28ShotProfileDepth: (profileId: string, suggestions: any[], acceptIds: string[]) =>
    req<any>(`/api/codirector/m28/shot-profiles/${encodeURIComponent(profileId)}/cinematic-depth`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestions, acceptIds }),
    }),
  m28ShotProfileAssociate: (profileId: string, storyboardShotId?: string, timelineItemId?: string) =>
    req<any>(`/api/codirector/m28/shot-profiles/${encodeURIComponent(profileId)}/associate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ storyboardShotId, timelineItemId }),
    }),
  m28VirtualStageCreate: (projectId: string, sceneId?: string, name?: string) =>
    req<any>("/api/codirector/m28/virtual-stage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, sceneId, name }),
    }),
  m28VirtualStageGet: (stageId: string) =>
    req<any>(`/api/codirector/m28/virtual-stage/${encodeURIComponent(stageId)}`),
  m28VirtualStageCamera: (stageId: string, camera: Record<string, unknown>) =>
    req<any>(`/api/codirector/m28/virtual-stage/${encodeURIComponent(stageId)}/camera`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera }),
    }),
  m28LocationSpinPlan: (projectId: string, locationName?: string) =>
    req<any>("/api/codirector/m28/location-spin/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId, locationName }),
    }),
  m28LocationSpinCamera: (spinId: string, angles?: number[]) =>
    req<any>(`/api/codirector/m28/location-spin/${encodeURIComponent(spinId)}/spin-camera`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ angles }),
    }),

  m29Status: () => req<Record<string, boolean>>("/api/codirector/m29/status"),
  m29ImageGenerate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/image/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29ImageApprove: (versionId: string, actor = "user", projectId?: string, sceneId?: string) =>
    req<any>(`/api/codirector/m29/image/${encodeURIComponent(versionId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor,
        ...(projectId ? { projectId } : {}),
        ...(sceneId ? { sceneId } : {}),
      }),
    }),
  m29ImageReject: (versionId: string, actor = "user", projectId?: string, sceneId?: string) =>
    req<any>(`/api/codirector/m29/image/${encodeURIComponent(versionId)}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor,
        ...(projectId ? { projectId } : {}),
        ...(sceneId ? { sceneId } : {}),
      }),
    }),
  m29ImagePublishReference: (versionId: string, actor = "user", projectId?: string, sceneId?: string) =>
    req<any>(
      `/api/codirector/m29/image/${encodeURIComponent(versionId)}/publish-reference`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actor,
          ...(projectId ? { projectId } : {}),
          ...(sceneId ? { sceneId } : {}),
        }),
      },
    ),
  m29FramesGenerate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/frames/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29FramesList: (projectId: string, shotId?: string) =>
    req<{ frames: any[] }>(
      `/api/codirector/m29/frames?projectId=${encodeURIComponent(projectId)}${
        shotId ? `&shotId=${encodeURIComponent(shotId)}` : ""
      }`,
    ),
  m29FramesBind: (frameId: string, shotId: string, projectId?: string) =>
    req<any>(`/api/codirector/m29/frames/${encodeURIComponent(frameId)}/bind`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shotId, ...(projectId ? { projectId } : {}) }),
    }),
  m29VideoGenerate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/video/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29AudioGenerate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/audio/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  generationToolsCatalog: () => req<any>("/api/generation-tools/catalog"),
  generationToolStatus: (toolId: string) =>
    req<any>(`/api/generation-tools/${encodeURIComponent(toolId)}/status`),
  projectGenerationToolsStatus: (projectId: string) =>
    req<any>(`/api/projects/${projectId}/generation-tools/status`),
  runGenerationTool: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${projectId}/generation-tools/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29AudioProcess: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/audio/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29LipsyncGenerate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/lipsync/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29MouthTrack: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/lipsync/mouth-track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29MouthRectangle: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/lipsync/mouth-rectangle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29TimelinePropose: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/timeline/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29TimelineApprove: (proposalId: string, actor = "user", projectId?: string) =>
    req<any>(`/api/codirector/m29/timeline/${encodeURIComponent(proposalId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor, ...(projectId ? { projectId } : {}) }),
    }),
  m29TimelineReject: (proposalId: string, actor = "user", projectId?: string) =>
    req<any>(`/api/codirector/m29/timeline/${encodeURIComponent(proposalId)}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor, ...(projectId ? { projectId } : {}) }),
    }),
  m29TimelineApply: (proposalId: string, actor = "user", projectId?: string) =>
    req<any>(`/api/codirector/m29/timeline/${encodeURIComponent(proposalId)}/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor, ...(projectId ? { projectId } : {}) }),
    }),
  m29EditingPropose: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/editing/propose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29EditingApply: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/editing/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29Render: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29RenderGet: (manifestId: string, projectId?: string) =>
    req<any>(
      `/api/codirector/m29/render/${encodeURIComponent(manifestId)}${
        projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""
      }`,
    ),
  m29ControlDecompose: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m29/control/decompose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m29ControlGet: (planId: string, projectId?: string) =>
    req<any>(
      `/api/codirector/m29/control/${encodeURIComponent(planId)}${
        projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""
      }`,
    ),
  m29ControlResume: (planId: string, opts?: { actor?: string; projectId?: string }) =>
    req<any>(`/api/codirector/m29/control/plans/${encodeURIComponent(planId)}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: opts?.actor ?? "user",
        ...(opts?.projectId ? { projectId: opts.projectId } : {}),
      }),
    }),
  m211Status: () => req<Record<string, unknown>>("/api/codirector/m211/status"),
  m211Dashboard: (projectId: string) =>
    req<any>(`/api/codirector/m211/dashboard?projectId=${encodeURIComponent(projectId)}`),
  m211Orchestrate: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m211/orchestrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m211MemoryList: (projectId: string, sceneId?: string) =>
    req<{ items: any[]; count: number }>(
      `/api/codirector/m211/memory?projectId=${encodeURIComponent(projectId)}` +
      (sceneId ? `&sceneId=${encodeURIComponent(sceneId)}` : ""),
    ),
  m211Traces: (projectId: string, limit = 50) =>
    req<{ traces: any[]; count: number }>(
      `/api/codirector/m211/traces?projectId=${encodeURIComponent(projectId)}&limit=${limit}`,
    ),
  m211Specialists: () => req<{ count: number; specialists: any[] }>("/api/codirector/m211/specialists"),

  m212Status: () => req<Record<string, unknown>>("/api/codirector/m212/status"),
  m212Dashboard: (projectId: string) =>
    req<any>(`/api/codirector/m212/dashboard?projectId=${encodeURIComponent(projectId)}`),
  m212ListLessons: (projectId: string, status?: string) =>
    req<any>(
      `/api/codirector/m212/lessons?projectId=${encodeURIComponent(projectId)}` +
        (status ? `&status=${encodeURIComponent(status)}` : "")
    ),
  m212RunRegression: (lessonId: string) =>
    req<any>(`/api/codirector/m212/lessons/${encodeURIComponent(lessonId)}/regression`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  m212PromoteLesson: (lessonId: string, body: Record<string, unknown>) =>
    req<any>(`/api/codirector/m212/lessons/${encodeURIComponent(lessonId)}/promote`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  m212RollbackLesson: (lessonId: string, body: Record<string, unknown>) =>
    req<any>(`/api/codirector/m212/lessons/${encodeURIComponent(lessonId)}/rollback`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  m212Critique: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m212/critique", { method: "POST", body: JSON.stringify(body) }),
  m212Retrospective: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m212/retrospectives", { method: "POST", body: JSON.stringify(body) }),
  m213Status: () => req<Record<string, unknown>>("/api/codirector/m213/status"),
  m214Status: () => req<Record<string, unknown>>("/api/codirector/m214/status"),
  m214Idea: (body: { projectId: string; idea: string; preferredFormat?: string }) =>
    req<Record<string, any>>("/api/codirector/m214/idea", { method: "POST", body: JSON.stringify(body) }),
  m214Stage: (body: { projectId: string; stage: string }) =>
    req<Record<string, any>>("/api/codirector/m214/stage", { method: "POST", body: JSON.stringify(body) }),
  m214Media: (projectId: string) =>
    req<{ items: any[]; groups: Record<string, any[]> }>(`/api/codirector/m214/media/${projectId}`),
  m214HitchhikerSmoke: (body: { projectId: string }) =>
    req<{ cards: any[] }>("/api/codirector/m214/hitchhiker/smoke", { method: "POST", body: JSON.stringify(body) }),
  m214Approvals: (body: { projectId: string; pending?: Record<string, unknown> }) =>
    req<Record<string, any>>("/api/codirector/m214/approvals", { method: "POST", body: JSON.stringify(body) }),
  m214Plan: (projectId: string) => req<Record<string, any>>(`/api/codirector/m214/plan/${projectId}`),
  m214Session: (projectId: string) => req<Record<string, any>>(`/api/codirector/m214/session/${projectId}`),
  m214StorytellerApprove: (handoffId: string, projectId?: string) =>
    req<any>(`/api/codirector/m214/storyteller/handoff/${encodeURIComponent(handoffId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectId ? { projectId } : {}),
    }),
  m214SonicApprove: (conceptId: string, projectId?: string) =>
    req<any>(`/api/codirector/m214/sound/concept/${encodeURIComponent(conceptId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectId ? { projectId } : {}),
    }),
  m214AttachmentConfirm: (
    interpretationId: string,
    body: { decision: string; correctedKind?: string; note?: string; projectId?: string },
  ) =>
    req<any>(`/api/codirector/m214/attachments/${encodeURIComponent(interpretationId)}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  m213Import: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/import", { method: "POST", body: JSON.stringify(body) }),
  m213CameraSpin: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/camera-spin", { method: "POST", body: JSON.stringify(body) }),
  m213Reconstruct: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/reconstruction", { method: "POST", body: JSON.stringify(body) }),
  m213ApproveEnv: (environmentId: string, body: Record<string, unknown> = {}) =>
    req<any>(`/api/codirector/m213/environments/${encodeURIComponent(environmentId)}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  m213ThemesRecommend: (style = "") =>
    req<any>(`/api/codirector/m213/themes/recommend?style=${encodeURIComponent(style)}`),
  m213CreateTheme: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/themes", { method: "POST", body: JSON.stringify(body) }),
  m213SaveBlocking: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/blocking", { method: "POST", body: JSON.stringify(body) }),
  m213SaveSceneState: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/scene-state", { method: "POST", body: JSON.stringify(body) }),
  m213CreatePlan: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/plans", { method: "POST", body: JSON.stringify(body) }),
  m213PlanDashboard: (planId: string) =>
    req<any>(`/api/codirector/m213/plans/${encodeURIComponent(planId)}/dashboard`),
  m213AdvancePlan: (planId: string, body: Record<string, unknown>) =>
    req<any>(`/api/codirector/m213/plans/${encodeURIComponent(planId)}/advance`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  m213GenerateConcept: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/concepts", { method: "POST", body: JSON.stringify(body) }),
  m213PublishTimeline: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/timeline/publish", { method: "POST", body: JSON.stringify(body) }),
  m213E2EGuided: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/m213/e2e/guided", { method: "POST", body: JSON.stringify(body) }),

  /** M3.0e Model Intelligence Layer */
  milPacks: () => req<{ packs: any[]; validation: any }>("/api/codirector/model-intelligence/packs"),
  milFilmmakerSummary: (userPrompt: string, modelId?: string) => {
    const q = new URLSearchParams({ userPrompt });
    if (modelId) q.set("modelId", modelId);
    return req<{
      recommendedModel: string;
      why: string;
      confidence: number;
      audioPlan: string;
      knownLimitations: string[];
      preflight: string;
      warnings: string[];
      advanced: Record<string, unknown>;
    }>(`/api/codirector/model-intelligence/filmmaker-summary?${q.toString()}`);
  },
  milCompile: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/model-intelligence/compile", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  milPreflight: (body: Record<string, unknown>, paidPath = false) =>
    req<any>(`/api/codirector/model-intelligence/preflight?paidPath=${paidPath ? "true" : "false"}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  milRecommend: (body: Record<string, unknown>) =>
    req<any>("/api/codirector/model-intelligence/recommend", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** M3.3 Character Identity */
  listCharacterProfiles: (projectId: string) =>
    req<{ items: any[] }>(`/api/projects/${encodeURIComponent(projectId)}/characters`),
  createCharacterProfile: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/characters`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCharacterProfile: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}`,
    ),
  patchCharacterProfile: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}`,
      { method: "PATCH", body: JSON.stringify(body) },
    ),
  listCharacterVersions: (projectId: string, characterId: string) =>
    req<{ items: any[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/versions`,
    ),
  approveCharacterVersion: (projectId: string, characterId: string, versionId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/versions/${encodeURIComponent(versionId)}/approve`,
      { method: "POST", body: "{}" },
    ),
  lockCharacterVersion: (projectId: string, characterId: string, versionId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/versions/${encodeURIComponent(versionId)}/lock`,
      { method: "POST", body: "{}" },
    ),
  listCharacterReferences: (projectId: string, characterId: string) =>
    req<{ items: any[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/references`,
    ),
  attachCharacterReference: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/references`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  getCharacterCoverage: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/coverage`,
    ),
  listCharacterWardrobes: (projectId: string, characterId: string) =>
    req<{ items: any[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/wardrobes`,
    ),
  createCharacterWardrobe: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/wardrobes`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listCharacterProps: (projectId: string, characterId: string) =>
    req<{ items: any[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/props`,
    ),
  createCharacterProp: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/props`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listCharacterVoiceProfiles: (projectId: string, characterId: string) =>
    req<{ items: any[] }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles`,
    ),
  createCharacterVoiceProfile: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  recordCharacterVoiceConsent: (
    projectId: string,
    characterId: string,
    voiceId: string,
    body: Record<string, unknown>,
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/${encodeURIComponent(voiceId)}/consent`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  approveCharacterVoiceProfile: (projectId: string, characterId: string, voiceId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/${encodeURIComponent(voiceId)}/approve`,
      { method: "POST", body: "{}" },
    ),
  validateCharacterVoiceReference: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/validate-reference`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  designCharacterVoice: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/design`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  cloneCharacterVoice: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/clone`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  generateCharacterDialogue: (
    projectId: string,
    characterId: string,
    voiceId: string,
    body: Record<string, unknown>,
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice-profiles/${encodeURIComponent(voiceId)}/generate-dialogue`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  characterVoiceProviders: () => req<any>("/api/character-voice/providers"),
  getCharacterVoiceWorkspace: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice`,
    ),
  previewCharacterVoiceDesign: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/design/preview`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  generateCharacterVoiceCandidates: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/design/generate`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  saveVoiceStudioDraft: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/studio-draft`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  selectVoiceForTesting: (projectId: string, characterId: string, body: { voiceId: string; candidateId: string }) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/select-testing`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  retryCharacterVoiceCandidate: (
    projectId: string,
    characterId: string,
    candidateId: string,
    body: { voiceId: string; testLine?: string },
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/candidates/${encodeURIComponent(candidateId)}/retry`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  registerCharacterVoiceUpload: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/upload/register`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listCharacterVoiceCandidates: (projectId: string, characterId: string, voiceId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/candidates?voiceId=${encodeURIComponent(voiceId)}`,
    ),
  characterVoiceCandidateAction: (
    projectId: string,
    characterId: string,
    voiceId: string,
    candidateId: string,
    action: "shortlist" | "reject" | "refine" | "approve",
    body?: Record<string, unknown>,
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/candidates/${encodeURIComponent(candidateId)}/${encodeURIComponent(action)}?voiceId=${encodeURIComponent(voiceId)}`,
      { method: "POST", body: JSON.stringify(body || {}) },
    ),
  approveCharacterVoiceCandidate: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/approve`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  auditionCharacterVoiceLine: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/audition`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  upsertCharacterVoicePronunciations: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/pronunciations`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  testCharacterVoicePronunciation: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/pronunciations/test`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  generateCharacterVoiceReactions: (projectId: string, characterId: string, voiceId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/reactions/generate`,
      { method: "POST", body: JSON.stringify({ voiceId }) },
    ),
  getCharacterVoiceVersions: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/versions`,
    ),
  getCharacterVoiceProvenance: (projectId: string, characterId: string, voiceId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/provenance?voiceId=${encodeURIComponent(voiceId)}`,
    ),
  cloneCharacterVoiceWorkspace: (projectId: string, characterId: string, body: Record<string, unknown>) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/voice/clone/generate`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  voicePerformanceGate: () => req<any>("/api/voice-performance/gate/wave44"),
  voicePerformanceTags: () => req<any>("/api/voice-performance/tags"),
  voicePerformanceProviders: () => req<any>("/api/voice-performance/providers"),
  voicePerformanceReadiness: (characterId: string, projectId: string) =>
    req<any>(
      `/api/voice-performance/characters/${encodeURIComponent(characterId)}/readiness?projectId=${encodeURIComponent(projectId)}`,
    ),
  voicePerformanceParse: (body: Record<string, unknown>) =>
    req<any>("/api/voice-performance/parse", { method: "POST", body: JSON.stringify(body) }),
  voicePerformanceCreatePlan: (body: Record<string, unknown>) =>
    req<any>("/api/voice-performance/plans", { method: "POST", body: JSON.stringify(body) }),
  voicePerformanceGetPlan: (planId: string) =>
    req<any>(`/api/voice-performance/plans/${encodeURIComponent(planId)}`),
  voicePerformanceCompilePlan: (planId: string) =>
    req<any>(`/api/voice-performance/plans/${encodeURIComponent(planId)}/compile`, {
      method: "POST",
      body: "{}",
    }),
  voicePerformanceProviderTranslation: (planId: string, provider?: string) =>
    req<any>(
      `/api/voice-performance/plans/${encodeURIComponent(planId)}/provider-translation${
        provider ? `?provider=${encodeURIComponent(provider)}` : ""
      }`,
    ),
  voicePerformanceGenerate: (
    planId: string,
    body?: { allowKokoroFallback?: boolean; allowTestingVoice?: boolean },
  ) =>
    req<any>(`/api/voice-performance/plans/${encodeURIComponent(planId)}/generate`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  voicePerformanceRetrySegment: (segmentId: string, body?: { allowKokoroFallback?: boolean }) =>
    req<any>(`/api/voice-performance/segments/${encodeURIComponent(segmentId)}/retry`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  voicePerformanceApproveSegment: (segmentId: string) =>
    req<any>(`/api/voice-performance/segments/${encodeURIComponent(segmentId)}/approve`, {
      method: "POST",
      body: "{}",
    }),
  voicePerformanceRejectSegment: (segmentId: string) =>
    req<any>(`/api/voice-performance/segments/${encodeURIComponent(segmentId)}/reject`, {
      method: "POST",
      body: "{}",
    }),
  voicePerformanceAssemble: (planId: string) =>
    req<any>(`/api/voice-performance/plans/${encodeURIComponent(planId)}/assemble`, {
      method: "POST",
      body: "{}",
    }),
  voicePerformancePlaceOnTimeline: (assemblyId: string, body?: { timelineId?: string; startMs?: number }) =>
    req<any>(`/api/voice-performance/assemblies/${encodeURIComponent(assemblyId)}/place-on-timeline`, {
      method: "POST",
      body: JSON.stringify(body || {}),
    }),
  voicePerformanceM410: {
    runtimeStatus: () => req<VoicePerformanceRuntimeStatus>("/api/voice-performance/m410/runtime/status"),
    installRuntime: (body: { confirm: boolean; confirmDownloadModels?: boolean }) =>
      req<Record<string, unknown>>("/api/voice-performance/m410/runtime/install", {
        method: "POST",
        body: JSON.stringify({
          confirm: body.confirm,
          confirm_download_models: body.confirmDownloadModels ?? false,
        }),
      }),
    verifyRuntime: () => req<Record<string, unknown>>("/api/voice-performance/m410/runtime/verify", { method: "POST" }),
    capabilities: () => req<VoicePerformanceCapabilities>("/api/voice-performance/m410/capabilities"),
    emotionPresets: () =>
      req<{ ok: boolean; presets: VoicePerformanceEmotionPreset[]; mock?: boolean }>(
        "/api/voice-performance/m410/emotion-presets",
      ),
    createRecord: (body: Record<string, unknown>) =>
      req<VoicePerformanceRecord>("/api/voice-performance/m410/records", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    getRecord: (recordId: string) =>
      req<VoicePerformanceRecord>(`/api/voice-performance/m410/records/${encodeURIComponent(recordId)}`),
    listProjectRecords: (projectId: string) =>
      req<VoicePerformanceRecordList>(
        `/api/voice-performance/m410/projects/${encodeURIComponent(projectId)}/records`,
      ),
    generatePerformancePlan: (recordId: string, body?: { context?: Record<string, unknown> }) =>
      req<VoicePerformanceRecord>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/performance-plan`,
        {
          method: "POST",
          body: JSON.stringify(body || {}),
        },
      ),
    patchPerformancePlan: (
      recordId: string,
      body: {
        performancePlan: Record<string, unknown>;
        mode?: "codirector" | "manual";
        emotionSource?: string;
        emotionVector?: Record<string, number>;
      },
    ) =>
      req<VoicePerformanceRecord>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/performance-plan`,
        {
          method: "PATCH",
          body: JSON.stringify(body),
        },
      ),
    setDirectionMode: (
      recordId: string,
      body: { directionMode: "codirector" | "manual"; performancePlan?: Record<string, unknown> },
    ) =>
      req<VoicePerformanceRecord>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/direction-mode`,
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      ),
    generateTakes: (recordId: string, body?: { count?: number; labels?: string[] }) =>
      req<{
        ok: boolean;
        recordId: string;
        providerId: string;
        providerVersion?: string | null;
        modelRevision?: string | null;
        takes: VoicePerformanceRecord["takes"];
        mock?: boolean;
      }>(`/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/generate-takes`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      }),
    listTakes: (recordId: string) =>
      req<VoicePerformanceTakeList>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/takes`,
      ),
    approveTake: (recordId: string, takeId: string, body?: { approvedBy?: string }) =>
      req<{
        ok: boolean;
        recordId: string;
        takeId: string;
        approvedBy: string;
        approvedTakeId: string;
        takes: VoicePerformanceRecord["takes"];
        mock?: boolean;
      }>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/takes/${encodeURIComponent(
          takeId,
        )}/approve`,
        {
          method: "POST",
          body: JSON.stringify(body || {}),
        },
      ),
    compare: (recordId: string, body?: { takeIds?: string[] }) =>
      req<VoicePerformanceComparison>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/compare`,
        {
          method: "POST",
          body: JSON.stringify(body || {}),
        },
      ),
    sendToTimeline: (
      recordId: string,
      body?: { trackId?: string; startMs?: number; confirmReplace?: boolean },
    ) =>
      req<VoicePerformanceTimelinePlacement>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/timeline`,
        {
          method: "POST",
          body: JSON.stringify(body || {}),
        },
      ),
    prepareLipsync: (
      recordId: string,
      body?: { confirm?: boolean; setSceneAudioAsset?: boolean },
    ) =>
      req<VoicePerformanceLipsyncResult>(
        `/api/voice-performance/m410/records/${encodeURIComponent(recordId)}/lipsync`,
        {
          method: "POST",
          body: JSON.stringify(body || {}),
        },
      ),
    createSceneBatch: (body: Record<string, unknown>) =>
      req<{ ok: boolean; projectId: string; records: VoicePerformanceRecord[]; mock?: boolean }>(
        "/api/voice-performance/m410/scene-batch",
        {
          method: "POST",
          body: JSON.stringify(body),
        },
      ),
  },
  voiceEnvironment: {
    runtimeStatus: () => req<{ ok: boolean; status: string }>("/api/voice-environment/runtime/status"),
    listProfiles: (projectId: string, characterId?: string) =>
      req<any[]>(
        `/api/voice-environment/projects/${encodeURIComponent(projectId)}/profiles` +
          (characterId ? `?characterId=${encodeURIComponent(characterId)}` : ""),
      ),
    createProfile: (body: Record<string, unknown>) =>
      req<any>("/api/voice-environment/profiles", { method: "POST", body: JSON.stringify(body) }),
    updateProfile: (profileId: string, body: Record<string, unknown>) =>
      req<any>(`/api/voice-environment/profiles/${encodeURIComponent(profileId)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    recommend: (body: Record<string, unknown>) =>
      req<any>("/api/voice-environment/recommend", { method: "POST", body: JSON.stringify(body) }),
    preview: (body: Record<string, unknown>) =>
      req<any>("/api/voice-environment/preview", { method: "POST", body: JSON.stringify(body) }),
    render: (body: Record<string, unknown>) =>
      req<any>("/api/voice-environment/render", { method: "POST", body: JSON.stringify(body) }),
    listRenders: (projectId: string, opts?: { characterId?: string; performanceTakeId?: string }) => {
      const q = new URLSearchParams();
      if (opts?.characterId) q.set("characterId", opts.characterId);
      if (opts?.performanceTakeId) q.set("performanceTakeId", opts.performanceTakeId);
      const qs = q.toString();
      return req<any[]>(
        `/api/voice-environment/projects/${encodeURIComponent(projectId)}/renders` + (qs ? `?${qs}` : ""),
      );
    },
    approve: (renderId: string, approved = true) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/approve`, {
        method: "POST",
        body: JSON.stringify({ approved }),
      }),
    applyToScene: (renderId: string, sceneId: string) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/apply-to-scene`, {
        method: "POST",
        body: JSON.stringify({ sceneId }),
      }),
    prepareTimeline: (renderId: string, body?: Record<string, unknown>) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/timeline/prepare`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      }),
    placeTimeline: (renderId: string, body?: Record<string, unknown>) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/timeline`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      }),
    prepareLipsync: (renderId: string, body?: Record<string, unknown>) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/lipsync`, {
        method: "POST",
        body: JSON.stringify(body || {}),
      }),
    openAudioStudio: (renderId: string) =>
      req<any>(`/api/voice-environment/renders/${encodeURIComponent(renderId)}/audio-studio`, {
        method: "POST",
        body: "{}",
      }),
  },
  startCharacterVisualSheet: (
    projectId: string,
    characterId: string,
    body?: { includeDetails?: boolean; includePerformance?: boolean; heroAssetId?: string },
  ) =>
    req<{ ok: boolean; pack: any }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-sheet/generate`,
      { method: "POST", body: JSON.stringify(body || {}) },
    ),
  advanceCharacterVisualSheet: (projectId: string, characterId: string) =>
    req<{ ok: boolean; pack: any }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-sheet/advance`,
      { method: "POST", body: "{}" },
    ),
  getCharacterVisualSheet: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-sheet`,
    ),
  ownerApproveCharacterVisualSheet: (
    projectId: string,
    characterId: string,
    approvedBy = "owner",
    selectDirectionId = "wild_sun_sprite",
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-sheet/owner-approve`,
      {
        method: "POST",
        body: JSON.stringify({ approvedBy, selectDirectionId }),
      },
    ),
  seedKorriCanon: (projectId: string) =>
    req<any>(`/api/projects/${encodeURIComponent(projectId)}/characters/seed-korri`, {
      method: "POST",
      body: "{}",
    }),
  promoteCharacterIdentity: (projectId: string, characterId: string, approvedBy = "owner") =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/promote`,
      { method: "POST", body: JSON.stringify({ approvedBy }) },
    ),
  getCharacterPromptPackage: (projectId: string, characterId: string) =>
    req<{ characterId: string; promptPackage: Record<string, unknown> }>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/prompt-package`,
    ),
  getKorriCanon: (projectId: string) =>
    req<Record<string, unknown>>(`/api/projects/${encodeURIComponent(projectId)}/characters/canon/korri`),
  listVisualGates: (projectId: string, characterId: string) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-gates`,
    ),
  proposeVisualDirections: (projectId: string, characterId: string, directions?: unknown[]) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-gates/concept/propose`,
      { method: "POST", body: JSON.stringify({ directions: directions || null }) },
    ),
  selectVisualConcept: (
    projectId: string,
    characterId: string,
    directionId: string,
    approvedBy = "owner",
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-gates/concept/select`,
      { method: "POST", body: JSON.stringify({ directionId, approvedBy }) },
    ),
  updateVisualGate: (
    projectId: string,
    characterId: string,
    gate: string,
    body: Record<string, unknown>,
  ) =>
    req<any>(
      `/api/projects/${encodeURIComponent(projectId)}/characters/${encodeURIComponent(characterId)}/visual-gates/${encodeURIComponent(gate)}`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  characterCreatorGate: () => req<Record<string, unknown>>("/api/m42-product/gate/wave43"),

  /** M42 Wave 3 Image Product — generate, presets, collections, references, history */
  imageProductGate: () => req<Record<string, unknown>>("/api/image-product/gate"),
  imageProductRecommend: (body: Record<string, unknown>) =>
    req<any>("/api/image-product/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductExpandPrompt: (body: Record<string, unknown>) =>
    req<any>("/api/image-product/expand-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductCompile: (body: Record<string, unknown>) =>
    req<any>("/api/image-product/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductGenerate: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/image-product/projects/${encodeURIComponent(projectId)}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductFamilies: () => req<{ families: any[] }>("/api/image-product/families"),
  imageProductPresets: (projectId: string) =>
    req<{ presets: any[] }>(`/api/image-product/projects/${encodeURIComponent(projectId)}/presets`),
  imageProductCreatePreset: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/api/image-product/projects/${encodeURIComponent(projectId)}/presets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductCollections: (projectId: string) =>
    req<{ collections: any[] }>(`/api/image-product/projects/${encodeURIComponent(projectId)}/collections`),
  imageProductCreateCollection: (projectId: string, body: { name: string; assetIds?: string[] }) =>
    req<any>(`/api/image-product/projects/${encodeURIComponent(projectId)}/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductUpdateCollection: (
    projectId: string,
    collectionId: string,
    body: Record<string, unknown>,
  ) =>
    req<any>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/collections/${encodeURIComponent(collectionId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    ),
  imageProductDeleteCollection: (projectId: string, collectionId: string) =>
    req<any>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/collections/${encodeURIComponent(collectionId)}`,
      { method: "DELETE" },
    ),
  imageProductAddCollectionAssets: (projectId: string, collectionId: string, assetIds: string[]) =>
    req<any>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/collections/${encodeURIComponent(collectionId)}/assets`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assetIds }),
      },
    ),
  imageProductReferences: (projectId: string, type?: string) => {
    const qs = type ? `?type=${encodeURIComponent(type)}` : "";
    return req<{ references: any[] }>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/references${qs}`,
    );
  },
  imageProductBridgeReference: (
    projectId: string,
    body: {
      assetId: string;
      role?: string;
      displayName?: string;
      identityRegistryRef?: string;
    },
  ) =>
    req<any>(`/api/image-product/projects/${encodeURIComponent(projectId)}/references/bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  imageProductHistory: (projectId: string, limit = 50) =>
    req<{ entries: any[]; prompts: string[] }>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/history?limit=${limit}`,
    ),
  imageProductPromptHistory: (projectId: string) =>
    req<{ prompts: string[] }>(
      `/api/image-product/projects/${encodeURIComponent(projectId)}/prompt-history`,
    ),

  /** M41 4.1A/4.1B Video Runtime + Certified Workflow Library */
  videoRuntimeDiagnostics: () => req<Record<string, unknown>>("/api/video-runtime/diagnostics"),
  videoRuntimeCompatibility: () =>
    req<{ entries: Record<string, unknown>[] }>("/api/video-runtime/compatibility"),
  videoRuntimeCertifiedRegistry: () =>
    req<{ entries: Record<string, unknown>[]; productionReadyKeys: string[] }>(
      "/api/video-runtime/certified-registry",
    ),
  videoRuntimeResolve: (body: {
    intent: string;
    engine?: string;
    presentInputs?: Record<string, unknown>;
    paidFalApproved?: boolean;
    wantsIngredients?: boolean;
  }) =>
    req<Record<string, unknown>>("/api/video-runtime/resolve", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  videoRuntimePreflight: (body: {
    workflowKey: string;
    width?: number;
    height?: number;
    frames?: number;
    presentInputs?: string[];
    applySafeConfig?: boolean;
    engine?: string;
  }) =>
    req<Record<string, unknown>>("/api/video-runtime/preflight", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  videoRuntimeGate: () =>
    req<{
      wave6MediaExecutionUnlocked: boolean;
      wave6ProductionActivationUnlocked?: boolean;
      certifiedWorkflowCount?: number;
      phase41bGo?: boolean;
      message: string;
    }>("/api/video-runtime/gate"),
  hunyuanLibrary: () =>
    req<{
      ok: boolean;
      defaultProviderId: string;
      providers: Array<Record<string, unknown>>;
    }>("/api/video-runtime/hunyuan/library"),
  hunyuanProviders: () =>
    req<{ ok: boolean; providers: Array<Record<string, unknown>> }>("/api/video-runtime/hunyuan/providers"),
  hunyuanPreflight: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/preflight`,
    ),
  hunyuanHealth: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/health`,
    ),
  hunyuanInstall: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/install`,
      { method: "POST" },
    ),
  hunyuanRemove: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/remove`,
      { method: "POST" },
    ),
  hunyuanRepair: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/repair`,
      { method: "POST" },
    ),
  hunyuanBenchmark: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/benchmark`,
      { method: "POST" },
    ),
  hunyuanBenchmarkLatest: (providerId: string) =>
    req<Record<string, unknown>>(
      `/api/video-runtime/hunyuan/providers/${encodeURIComponent(providerId)}/benchmark`,
    ),

  /** M42 Production Control Dock */
  productionControlStatus: (projectId?: string) =>
    req<import("./modelRegistry/contracts").ProductionControlStatus>(
      projectId
        ? `/api/production-control/status?projectId=${encodeURIComponent(projectId)}`
        : "/api/production-control/status",
    ),
  productionControlGate: () =>
    req<import("./modelRegistry/contracts").ProductionControlGate>("/api/production-control/gate"),
  productionControlGetPreferences: async () => {
    const raw = await req<{ preferences?: import("./modelRegistry/contracts").UserGlobalPreferences } & import("./modelRegistry/contracts").UserGlobalPreferences>(
      "/api/production-control/preferences",
    );
    return (raw.preferences ?? raw) as import("./modelRegistry/contracts").UserGlobalPreferences;
  },
  productionControlPutPreferences: async (body: Partial<import("./modelRegistry/contracts").UserGlobalPreferences>) => {
    const raw = await req<{ preferences?: import("./modelRegistry/contracts").UserGlobalPreferences } & import("./modelRegistry/contracts").UserGlobalPreferences>(
      "/api/production-control/preferences",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    return (raw.preferences ?? raw) as import("./modelRegistry/contracts").UserGlobalPreferences;
  },
  productionControlGetProjectPreferences: async (projectId: string) => {
    const raw = await req<{ preferences?: import("./modelRegistry/contracts").ProjectPreferences } & import("./modelRegistry/contracts").ProjectPreferences>(
      `/api/production-control/projects/${encodeURIComponent(projectId)}/preferences`,
    );
    return (raw.preferences ?? raw) as import("./modelRegistry/contracts").ProjectPreferences;
  },
  productionControlPutProjectPreferences: async (
    projectId: string,
    body: Partial<import("./modelRegistry/contracts").ProjectPreferences>,
  ) => {
    const raw = await req<{ preferences?: import("./modelRegistry/contracts").ProjectPreferences } & import("./modelRegistry/contracts").ProjectPreferences>(
      `/api/production-control/projects/${encodeURIComponent(projectId)}/preferences`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    return (raw.preferences ?? raw) as import("./modelRegistry/contracts").ProjectPreferences;
  },
  productionControlResolve: async (body: {
    modality: import("./modelRegistry/contracts").Modality;
    projectId?: string;
  }) => {
    const qs = new URLSearchParams({ modality: body.modality });
    if (body.projectId) qs.set("projectId", body.projectId);
    else qs.set("projectId", "_global");
    const raw = await req<{ selection?: import("./modelRegistry/contracts").ResolvedSelection } & import("./modelRegistry/contracts").ResolvedSelection>(
      `/api/production-control/resolve?${qs.toString()}`,
    );
    return (raw.selection ?? raw) as import("./modelRegistry/contracts").ResolvedSelection;
  },
  // Batch resolve all 4 modalities in a single request (replaces 4 parallel /resolve calls)
  productionControlResolved: (projectId?: string) => {
    const qs = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "?projectId=_global";
    return req<{ resolved: Record<string, { ok: boolean; selection: import("./modelRegistry/contracts").ResolvedSelection }> }>(
      `/api/production-control/resolved${qs}`,
    );
  },
  productionControlModels: (modality: import("./modelRegistry/contracts").Modality) =>
    req<{
      models: import("./modelRegistry/contracts").ModelDescriptor[];
      sections?: {
        local?: import("./modelRegistry/contracts").ModelDescriptor[];
        api?: import("./modelRegistry/contracts").DiscoveredApiModel[];
      };
      api?: import("./modelRegistry/contracts").ApiModelsSectionMeta;
    }>(`/api/production-control/models?modality=${encodeURIComponent(modality)}`),
  productionControlQueue: async (projectId?: string) => {
    const raw = await req<{ queue?: import("./modelRegistry/contracts").ProductionQueueSnapshot } & import("./modelRegistry/contracts").ProductionQueueSnapshot>(
      projectId
        ? `/api/production-control/queue?projectId=${encodeURIComponent(projectId)}`
        : "/api/production-control/queue",
    );
    return (raw.queue ?? raw) as import("./modelRegistry/contracts").ProductionQueueSnapshot;
  },
  productionControlMigrate: () =>
    req<{ ok: boolean; report?: Record<string, unknown> }>("/api/production-control/migrate", {
      method: "POST",
    }),
  productionControlProviderSwitch: (body: { toProviderId?: string; providerId?: string; projectId?: string }) =>
    req<import("./modelRegistry/contracts").ProviderSwitchPreview & { token?: string; providerId?: string }>(
      "/api/production-control/providers/switch",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ providerId: body.providerId || body.toProviderId }),
      },
    ),
  productionControlProviderSwitchConfirm: (
    body: import("./modelRegistry/contracts").ProviderSwitchConfirmBody & { providerId?: string; toProviderId?: string },
  ) =>
    req<{ ok: boolean }>("/api/production-control/providers/switch/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        providerId: body.providerId || body.toProviderId,
        confirmed: body.confirmed ?? true,
      }),
    }),

  // Knowledge Card operations (ephemeral conversation-to-project bridge)
  addKnowledgeCard: (projectId: string, cardId: string) =>
    req<{ ok: boolean; status: string; error?: string }>(
      `${BASE}/api/knowledge-cards/${encodeURIComponent(cardId)}/add?project_id=${encodeURIComponent(projectId)}`,
      { method: "POST" },
    ),
  dismissKnowledgeCard: (cardId: string) =>
    req<{ ok: boolean; status: string }>(
      `${BASE}/api/knowledge-cards/${encodeURIComponent(cardId)}/dismiss`,
      { method: "POST" },
    ),
  editKnowledgeCard: (cardId: string, body: { title?: string; fields?: Record<string, unknown>; summary?: string }) =>
    req<{ ok: boolean; status: string }>(
      `${BASE}/api/knowledge-cards/${encodeURIComponent(cardId)}/edit`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  listKnowledgeCards: (projectId: string) =>
    req<Array<{ cardId: string; cardType: string; title: string; fields: Record<string, unknown>; summary?: string; status: string }>>(
      `${BASE}/api/knowledge-cards/project/${encodeURIComponent(projectId)}`,
    ),

  // M42 W47 — Docker Runtime Extensions (all Docker ops via backend only)
  dockerRuntime: {
    platform: async () => {
      const raw = await req<{ ok: boolean; platform: import("./dockerRuntime/contracts").PlatformStatus }>(
        "/api/docker-runtime/platform",
      );
      return raw.platform ?? (raw as unknown as import("./dockerRuntime/contracts").PlatformStatus);
    },
    list: () =>
      req<{ ok: boolean; runtimes: import("./dockerRuntime/contracts").DockerRuntimeDescriptor[] }>(
        "/api/docker-runtime/runtimes",
      ),
    get: (runtimeId: string) =>
      req<Record<string, unknown>>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}`),
    installPreview: (manifest: Record<string, unknown>) =>
      req<{ ok: boolean; plan: import("./dockerRuntime/contracts").RuntimeInstallationPlan }>(
        "/api/docker-runtime/install/preview",
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(manifest) },
      ),
    install: (manifest: Record<string, unknown>) =>
      req<{ ok: boolean; result?: { runtime?: import("./dockerRuntime/contracts").DockerRuntimeDescriptor }; error?: string }>(
        "/api/docker-runtime/install",
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(manifest) },
      ),
    start: (runtimeId: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/start`, { method: "POST" }),
    stop: (runtimeId: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/stop`, { method: "POST" }),
    restart: (runtimeId: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/restart`, {
        method: "POST",
      }),
    test: (runtimeId: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/test`, { method: "POST" }),
    diagnostics: (runtimeId: string) =>
      req<{ ok: boolean; report: Record<string, unknown> }>(
        `/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/diagnostics`,
      ),
    repair: (runtimeId: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/repair`, { method: "POST" }),
    update: (runtimeId: string, image: string) =>
      req<{ ok: boolean }>(`/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image }),
      }),
    uninstallPreview: (runtimeId: string, option: import("./dockerRuntime/contracts").UninstallOption) =>
      req<{ ok: boolean; plan: import("./dockerRuntime/contracts").RuntimeUninstallPlan }>(
        `/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/uninstall/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ option }),
        },
      ),
    uninstall: (runtimeId: string, option: import("./dockerRuntime/contracts").UninstallOption) =>
      req<{ ok: boolean; result?: Record<string, unknown> }>(
        `/api/docker-runtime/runtimes/${encodeURIComponent(runtimeId)}/uninstall`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ option }),
        },
      ),
    workflowInspect: (workflow: Record<string, unknown>) =>
      req<Record<string, unknown>>("/api/docker-runtime/workflow/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow }),
      }),
    dockModels: () => req<{ models: Record<string, unknown>[] }>("/api/docker-runtime/dock-models"),
    gate: () => req<{ dockerRuntimeExtensionsGo: boolean; checks?: Record<string, unknown> }>("/api/docker-runtime/gate"),
  },
  // Phase CK — Available video generators for project preferences
  videoGenerators: () => req<Array<{ id: string; label: string; available: boolean }>>(`${BASE}/api/knowledge-cards/video-generators`),
};
