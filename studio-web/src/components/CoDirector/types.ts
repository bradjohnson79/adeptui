import type { SceneSetup } from "../../types";
import type { ActionPlan } from "../../codirector/types";

export type CoDirectorDisplayMode = "popup" | "fullscreen";

export type ChatMode = "chat" | "prompt" | "guide" | "setup";

export type PromptMode = "creative" | "structured" | "model" | "advanced";

export type OverflowPanel =
  | "none"
  | "options"
  | "knowledge"
  | "access"
  | "audit"
  | "status"
  | "provider"
  | "promptBench"
  | "plan";

export interface CoDirectorUIContext {
  projectId?: string;
  projectName?: string;
  /** M3.1a primary project type slug (e.g. educational_explainer). */
  primaryProjectType?: string;
  workspaceId?: string;
  sceneId?: string;
  sceneName?: string;
  selectedAssetIds?: string[];
  selectedCharacterIds?: string[];
  selectedStoryboardPanelIds?: string[];
  activeGenerationId?: string;
  /** Active script/document id when known (session-context contract). */
  activeDocumentId?: string;
  /** Active Co-Director Project Content tab (wiki|notes|casting|library|...|scriptwriter). */
  activeContentTab?: string | null;
  /** Navigate to a project workspace tab. */
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
}

/** M41 Wave 1 canonical session-context contract (composed; not a second store). */
export interface CoDirectorSessionContext {
  projectId?: string | null;
  projectName?: string | null;
  activeDocumentId?: string | null;
  activeSceneId?: string | null;
  activeWorkspace?: string | null;
  /** Active Co-Director Project Content tab — lightweight pillar hint. */
  activeContentTab?: string | null;
  selectedAssets: string[];
  provider?: string | null;
  model?: string | null;
  activeProductionPlan?: Record<string, unknown> | null;
  sessionStatus: string;
  lastSuccessfulToolAction?: string | null;
  unresolvedBlockers: string[];
}

export type LastBoundProjectSuggestion = {
  projectId: string;
  projectName?: string;
};

export type CoDirectorMessageStatus = "streaming" | "cancelled" | "interrupted";

/** M2.4 assistant message kinds — user-safe labels, not internal agent names. */
export type CoDirectorAssistantMessageType =
  | "answer"
  | "recommendation"
  | "clarification"
  | "warning"
  | "proposal"
  | "plan"
  | "execution_status"
  | "completion"
  | "error";

export type CoDirectorExpertiseMode = "guided" | "standard" | "expert";

/** Creator collaboration stance (Phase 4). Inferred conservatively; creator can override. */
export type CollaborationMode =
  | "explore"
  | "critique"
  | "compare"
  | "refine"
  | "decide"
  | "review"
  | "execute"
  | "teach";

export type CoDirectorActivityPreference = "always" | "longer_tasks" | "hidden";

export type CoDirectorActivityEventType =
  | "request_received"
  | "context_review"
  | "wiki_review"
  | "media_review"
  | "plan_review"
  | "tool_started"
  | "tool_completed"
  | "tool_failed"
  | "response_composing"
  | "persistence_started"
  | "persistence_completed";

export type CoDirectorActivityStageStatus = "pending" | "active" | "completed" | "failed";

export interface CoDirectorActivityStage {
  id: "request" | "context" | "wiki" | "media" | "plan" | "tool" | "response" | "persistence";
  eventType: CoDirectorActivityEventType;
  label: string;
  status: CoDirectorActivityStageStatus;
  detail?: string;
}

export interface CoDirectorActivityState {
  requestId: string;
  status: "running" | "completed" | "failed" | "cancelled";
  stages: CoDirectorActivityStage[];
  summaryFacts: string[];
  attachmentsCount: number;
  toolLabels: string[];
  startedAt: string;
  completedAt?: string;
  persistenceError?: string | null;
  /** Foundational AI observability (creator-safe). */
  cognitiveMode?: string | null;
  activeGoal?: string | null;
  workflowHold?: boolean;
  toolsSummary?: string | null;
  memorySummary?: string | null;
  fallbackUsed?: boolean;
  selectedModel?: string | null;
  actualModel?: string | null;
  creativePosture?: string | null;
  advisoryDecision?: string | null;
  advisoryStrength?: string | null;
  changeStatus?: string | null;
  waitingForConfirmation?: boolean;
  canonUpdated?: boolean;
  roleEmphasis?: string | null;
  assistantName?: string | null;
  userPreferredName?: string | null;
  creativeStage?: string | null;
  wikiCandidates?: number | null;
  confirmedWrites?: number | null;
  discoveryQuestionCount?: number | null;
  researchStatus?: string | null;
  documentationReason?: string | null;
  whatChanged?: string[];
  projectPulse?: Record<string, unknown> | null;
  activeDeliverable?: Record<string, unknown> | null;
  artifactReadiness?: Record<string, unknown>[] | null;
  visionProfile?: Record<string, unknown> | null;
  pitchPackage?: Record<string, unknown> | null;
  journeyState?: Record<string, unknown> | null;
  processingStages?: string[];
  conversationActions?: { id: string; label: string }[];
  onboardingNeeded?: boolean;
  /** Soft next-step invitations for the latest assistant turn (≤4). */
  nextStepOptions?: CoDirectorNextStepOption[];
  nextStepIntro?: string | null;
  /** Background Wiki enrichment after tokens began streaming. */
  wikiBackgroundStatus?: "running" | "complete" | "failed" | "processing" | null;
  wikiVerification?: {
    persistenceState?: string;
    presentationState?: string;
    finalState?: string;
    error?: string | null;
  } | null;
  wikiRefreshNonce?: number;
  wikiUiMessage?: string | null;
  coldLoadActive?: boolean;
  momentumResume?: string | null;
  momentumSummary?: string | null;
  lastTimings?: Record<string, unknown> | null;
  confidenceInsight?: string | null;
}

export type CoDirectorNextStepType =
  | "CONTINUE_STORY"
  | "EXPLORE_CHARACTER"
  | "EXPLORE_WORLD"
  | "EXPLORE_RULES"
  | "BUILD_STORY_TEMPLATE"
  | "BUILD_TREATMENT"
  | "BUILD_OUTLINE"
  | "DEVELOP_SCENE"
  | "DEVELOP_EPISODE"
  | "CREATE_CONCEPTS"
  | "VISUAL_DEVELOPMENT"
  | "TONE_AND_ATMOSPHERE"
  | "RESEARCH_COMPARABLES"
  | "BUILD_PITCH"
  | "REVIEW_WIKI"
  | "REVIEW_OPEN_QUESTIONS"
  | "KEEP_LISTENING";

export interface CoDirectorNextStepOption {
  id: string;
  type: CoDirectorNextStepType;
  label: string;
  shortDescription?: string | null;
  whyNow?: string | null;
  readiness: "AVAILABLE" | "PARTIAL" | "NOT_READY";
  ownershipRequired: boolean;
  priority: number;
  previewSpine?: string | null;
}

export interface CoDirectorIntelligenceProgress {
  stage: string;
  message: string;
}

export interface CoDirectorProductionAnalysis {
  specialists: string[];
  findingsSummaries: { specialistId: string; summary: string }[];
  bibleSources: string[];
  capabilities: string[];
  promptVersions: Record<string, string>;
  planSteps: { title: string; status: string }[];
  recommendation?: Record<string, unknown> | null;
}

export interface CoDirectorMessageExecutionChild {
  job_id?: string;
  child_index?: number;
  label?: string;
  status?: string;
  asset_id?: string | null;
  error?: string | null;
  progress?: number;
  stage?: string;
}

export interface CoDirectorMessageExecution {
  execution_id: string;
  capability?: string;
  status?: string;
  progress?: number;
  completed?: number;
  total?: number;
  collection_id?: string | null;
  result_asset_ids?: string[];
  child_jobs?: CoDirectorMessageExecutionChild[];
}

export interface CoDirectorMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachmentIds?: string[];
  attachments?: CoDirectorMessageAttachment[];
  createdAt: string;
  /** Present while a streamed reply is in flight, or after it ended abnormally. */
  status?: CoDirectorMessageStatus;
  /** M2.4 structured assistant message kind. */
  messageType?: CoDirectorAssistantMessageType;
  /** Workstream H — execution payload for execution_status / completion messages. */
  execution?: CoDirectorMessageExecution;
}

/**
 * What Co-Director is doing with a bounded read tool this turn (M2.2).
 *
 * Read tools run server-side and finish inside a single chat turn, so this is transient status
 * for one line of UI — it is deliberately not a task list, and never a place from which the user
 * can trigger or re-run anything.
 */
export interface CoDirectorToolActivity {
  toolId: string;
  title: string;
  phase: "requested" | "running" | "completed" | "failed" | "blocked" | "operator_pending" | "operator_timeout";
  detail?: string;
  truncated?: boolean;
}

export type AttachmentKind = "file" | "library";

export interface CoDirectorMessageAttachment {
  assetId: string;
  name: string;
  mimeType?: string;
  source: AttachmentKind;
  mediaKind?: string;
}

export interface CoDirectorAttachment {
  id: string;
  kind: AttachmentKind;
  name: string;
  mimeType?: string;
  /** Project asset kind once selected or uploaded. */
  mediaKind?: string;
  /** Object URL for local file previews; revoke on remove. */
  previewUrl?: string;
  /** Library asset id when kind === "library". */
  assetId?: string;
  /** File blob retained until send/clear. */
  file?: File;
}

export interface CoDirectorWorkspaceBindings {
  projectId?: string;
  projectName?: string;
  primaryProjectType?: string;
  sceneId?: string;
  sceneName?: string;
  workspaceTab?: string;
  /** Active ScriptDocument id when Scriptwriter Studio is open. */
  activeDocumentId?: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
  onApplyPrompt?: (prompt: string) => void;
  onAppliedSetup?: () => void | Promise<void>;
}

export interface WelcomeSuggestion {
  id: string;
  label: string;
  description?: string;
  text: string;
  mode: ChatMode;
}

export interface CoDirectorSessionSnapshot {
  open: boolean;
  displayMode: CoDirectorDisplayMode;
  draft: string;
  messages: CoDirectorMessage[];
  attachments: CoDirectorAttachment[];
  busy: boolean;
  applying: boolean;
  providerStatus: string;
  suggestedPrompt: string | null;
  setup: SceneSetup | null;
  applyNote: string | null;
  plan: ActionPlan | null;
  selectedSteps: Record<string, boolean>;
  promptMode: PromptMode;
  includeProjectKnowledge: boolean;
  compileExplain: string[];
  overflowPanel: OverflowPanel;
  contextPanelOpen: boolean;
  assetPickerOpen: boolean;
  uiContext: CoDirectorUIContext;
  conversationStarted: boolean;
}

const DRAFT_KEY_PREFIX = "adept_codirector_draft_";
/** Legacy global draft key — never written; cleared when migrating to project-scoped drafts. */
const LEGACY_DRAFT_KEY = "adept_codirector_draft";
const MESSAGES_KEY_PREFIX = "adept_codirector_messages_";
/** Legacy global key — read once for migration, never written. */
const LEGACY_MESSAGES_KEY = "adept_codirector_messages";
const MODE_KEY = "adept_codirector_display_mode";
const CONTEXT_PANEL_KEY = "adept_codirector_context_panel";
const EXPERTISE_MODE_KEY = "adept_codirector_expertise_mode";
const LAST_PROJECT_KEY = "adept_codirector_last_project_suggestion";
const ACTIVITY_PREFERENCE_KEY = "adept_codirector_activity_preference";

/** Safe message fields only — never tokens, tool payloads, or technical_evidence. */
function sanitizeMessagesForCache(messages: CoDirectorMessage[]): CoDirectorMessage[] {
  return messages.slice(-80).map((m) => {
    const sanitized: CoDirectorMessage = {
      id: m.id,
      role: m.role,
      content: typeof m.content === "string" ? m.content.slice(0, 20_000) : "",
      attachmentIds: Array.isArray(m.attachmentIds) ? m.attachmentIds.slice(0, 12) : undefined,
      attachments: Array.isArray(m.attachments)
        ? m.attachments
            .filter((item) => item && typeof item.assetId === "string" && typeof item.name === "string")
            .slice(0, 12)
            .map((item) => ({
              assetId: item.assetId,
              name: item.name.slice(0, 300),
              mimeType: typeof item.mimeType === "string" ? item.mimeType.slice(0, 120) : undefined,
              source: item.source === "library" ? "library" : "file",
              mediaKind: typeof item.mediaKind === "string" ? item.mediaKind.slice(0, 32) : undefined,
            }))
        : undefined,
      createdAt: m.createdAt,
      status: m.status,
      messageType: m.messageType,
    };
    // Workstream H — preserve execution payload for execution_status / completion
    // messages so the compact progress card survives reload. Bound child_jobs to
    // avoid unbounded payloads; never carry arbitrary nested technical_evidence.
    const exec = m.execution;
    if (exec && typeof exec === "object" && typeof exec.execution_id === "string") {
      sanitized.execution = {
        execution_id: exec.execution_id.slice(0, 120),
        capability: typeof exec.capability === "string" ? exec.capability.slice(0, 80) : undefined,
        status: typeof exec.status === "string" ? exec.status.slice(0, 40) : undefined,
        progress: typeof exec.progress === "number" ? Math.max(0, Math.min(1, exec.progress)) : undefined,
        completed: typeof exec.completed === "number" ? Math.max(0, Math.min(9999, Math.floor(exec.completed))) : undefined,
        total: typeof exec.total === "number" ? Math.max(0, Math.min(9999, Math.floor(exec.total))) : undefined,
        collection_id: typeof exec.collection_id === "string" ? exec.collection_id.slice(0, 120) : null,
        result_asset_ids: Array.isArray(exec.result_asset_ids)
          ? exec.result_asset_ids.filter((id) => typeof id === "string").slice(0, 64)
          : undefined,
        child_jobs: Array.isArray(exec.child_jobs)
          ? exec.child_jobs.slice(0, 64).map((c) => ({
              job_id: typeof c.job_id === "string" ? c.job_id.slice(0, 120) : undefined,
              child_index: typeof c.child_index === "number" ? c.child_index : undefined,
              label: typeof c.label === "string" ? c.label.slice(0, 120) : undefined,
              status: typeof c.status === "string" ? c.status.slice(0, 40) : undefined,
              asset_id: typeof c.asset_id === "string" ? c.asset_id.slice(0, 120) : null,
              error: typeof c.error === "string" ? c.error.slice(0, 240) : null,
              progress: typeof c.progress === "number" ? Math.max(0, Math.min(1, c.progress)) : undefined,
              stage: typeof c.stage === "string" ? c.stage.slice(0, 80) : undefined,
            }))
          : undefined,
      };
    }
    return sanitized;
  });
}

function draftStorageKey(projectId?: string | null): string {
  return DRAFT_KEY_PREFIX + (projectId || "_none");
}

export function loadPersistedDraft(projectId?: string | null): string {
  try {
    try {
      localStorage.removeItem(LEGACY_DRAFT_KEY);
    } catch {
      /* ignore */
    }
    return localStorage.getItem(draftStorageKey(projectId)) || "";
  } catch {
    return "";
  }
}

export function persistDraft(value: string, projectId?: string | null) {
  try {
    // Draft text only — never persist secrets/tokens. Scoped per project to prevent leaks.
    localStorage.setItem(draftStorageKey(projectId), (value || "").slice(0, 20_000));
    localStorage.removeItem(LEGACY_DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

export function loadPersistedMessages(projectId?: string | null): CoDirectorMessage[] | null {
  if (!projectId) return null;
  try {
    const raw = sessionStorage.getItem(MESSAGES_KEY_PREFIX + projectId);
    if (!raw) {
      // Do not hydrate from the legacy global key (cross-project leak risk).
      try {
        sessionStorage.removeItem(LEGACY_MESSAGES_KEY);
      } catch {
        /* ignore */
      }
      return null;
    }
    const parsed = JSON.parse(raw) as CoDirectorMessage[];
    return Array.isArray(parsed) ? sanitizeMessagesForCache(parsed) : null;
  } catch {
    return null;
  }
}

export function persistMessages(messages: CoDirectorMessage[], projectId?: string | null) {
  if (!projectId) return;
  try {
    sessionStorage.setItem(
      MESSAGES_KEY_PREFIX + projectId,
      JSON.stringify(sanitizeMessagesForCache(messages)),
    );
  } catch {
    /* ignore */
  }
}

export function clearPersistedMessages(projectId?: string | null) {
  if (!projectId) return;
  try {
    sessionStorage.removeItem(MESSAGES_KEY_PREFIX + projectId);
  } catch {
    /* ignore */
  }
}

/** Suggestion-only — never grants production permissions by itself. */
export function loadLastBoundProjectSuggestion(): LastBoundProjectSuggestion | null {
  try {
    const raw = localStorage.getItem(LAST_PROJECT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LastBoundProjectSuggestion;
    if (!parsed?.projectId || typeof parsed.projectId !== "string") return null;
    return {
      projectId: parsed.projectId,
      projectName: typeof parsed.projectName === "string" ? parsed.projectName : undefined,
    };
  } catch {
    return null;
  }
}

export function persistLastBoundProjectSuggestion(suggestion: LastBoundProjectSuggestion | null) {
  try {
    if (!suggestion?.projectId) {
      localStorage.removeItem(LAST_PROJECT_KEY);
      return;
    }
    localStorage.setItem(
      LAST_PROJECT_KEY,
      JSON.stringify({
        projectId: suggestion.projectId,
        projectName: suggestion.projectName?.slice(0, 200),
      }),
    );
  } catch {
    /* ignore */
  }
}

export function loadDisplayMode(): CoDirectorDisplayMode {
  try {
    const value = localStorage.getItem(MODE_KEY);
    return value === "fullscreen" ? "fullscreen" : "popup";
  } catch {
    return "popup";
  }
}

export function persistDisplayMode(mode: CoDirectorDisplayMode) {
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function loadContextPanelOpen(): boolean {
  try {
    return localStorage.getItem(CONTEXT_PANEL_KEY) === "1";
  } catch {
    return false;
  }
}

export function persistContextPanelOpen(open: boolean) {
  try {
    localStorage.setItem(CONTEXT_PANEL_KEY, open ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function loadExpertiseMode(): CoDirectorExpertiseMode {
  try {
    const value = localStorage.getItem(EXPERTISE_MODE_KEY);
    if (value === "guided" || value === "expert") return value;
    return "standard";
  } catch {
    return "standard";
  }
}

export function persistExpertiseMode(mode: CoDirectorExpertiseMode) {
  try {
    localStorage.setItem(EXPERTISE_MODE_KEY, mode);
  } catch {
    /* ignore */
  }
}

export function loadActivityPreference(): CoDirectorActivityPreference {
  try {
    const value = localStorage.getItem(ACTIVITY_PREFERENCE_KEY);
    if (value === "hidden" || value === "longer_tasks") return value;
    return "always";
  } catch {
    return "always";
  }
}

export function persistActivityPreference(mode: CoDirectorActivityPreference) {
  try {
    localStorage.setItem(ACTIVITY_PREFERENCE_KEY, mode);
  } catch {
    /* ignore */
  }
}

/** User-safe labels for intelligence progress stages (not specialist names). */
export function intelligenceStageLabel(stage: string): string {
  const labels: Record<string, string> = {
    classifying_intent: "Understanding the scene",
    compiling_context: "Reviewing project context",
    selecting_specialists: "Reviewing project context",
    running_specialists: "Preparing the shot",
    synthesizing: "Preparing the shot",
    building_plan: "Checking production requirements",
    creating_proposals: "Ready for approval",
    complete: "Complete",
  };
  return labels[stage] || "Working…";
}

// Session-scoped (survives reload, not tab close) marker so a stream abandoned mid-flight
// by a hard reload/crash can be surfaced as "interrupted" instead of silently vanishing.
const STREAMING_FLAG_PREFIX = "adept_codirector_streaming_";

export function markStreamingStart(projectId: string, requestId: string) {
  try {
    sessionStorage.setItem(STREAMING_FLAG_PREFIX + projectId, requestId);
  } catch {
    /* ignore */
  }
}

export function markStreamingEnd(projectId: string) {
  try {
    sessionStorage.removeItem(STREAMING_FLAG_PREFIX + projectId);
  } catch {
    /* ignore */
  }
}

/** Returns true (and clears the flag) if the last session ended mid-stream for this project. */
export function consumeAbandonedStreamingFlag(projectId: string): boolean {
  try {
    const key = STREAMING_FLAG_PREFIX + projectId;
    const had = sessionStorage.getItem(key) != null;
    sessionStorage.removeItem(key);
    return had;
  } catch {
    return false;
  }
}

// Per-tab session token (survives reload within the tab, dies on tab close — same scope as the
// streaming flags above). Sent as `origin_session_id` on chat-stream requests so an operator ack
// is addressable to the originating tab.
const TAB_SESSION_KEY = "adept_codirector_tab_session";

export function getTabSessionId(): string {
  try {
    const existing = sessionStorage.getItem(TAB_SESSION_KEY);
    if (existing) return existing;
    const id = `tab_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem(TAB_SESSION_KEY, id);
    return id;
  } catch {
    return `tab_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
  }
}

export function newMessageId(): string {
  return `msg_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export function newAttachmentId(): string {
  return `att_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export const WELCOME_ASSISTANT: CoDirectorMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi — I'm Co-Director. Tell me what you'd like to create, and I'll help plan scenes, prompts, storyboards, and generation steps.",
  createdAt: new Date(0).toISOString(),
};

export function summarizeSetup(s: SceneSetup): string[] {
  const lines: string[] = [];
  if (s.summary) lines.push(s.summary);
  if (s.engine) lines.push(`Engine: ${s.engine}`);
  if (s.duration_sec != null) lines.push(`Duration: ${s.duration_sec}s`);
  if (s.prompt) lines.push(`Prompt: ${s.prompt.slice(0, 100)}${s.prompt.length > 100 ? "…" : ""}`);
  return lines.length ? lines : ["Scene setup ready to apply"];
}

export function getActionCost(actionId: string): string {
  const map: Record<string, string> = {
    queueImageGeneration: "render",
    queueVideoGeneration: "render",
    searchLibrary: "free",
    manualCheckpoint: "manual",
  };
  return map[actionId] || "";
}
