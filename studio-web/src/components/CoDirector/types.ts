import type { SceneSetup } from "../../types";
import type { ActionPlan } from "../../codirector/types";

export type CoDirectorDisplayMode = "popup" | "fullscreen";

export type ChatMode = "chat" | "prompt" | "guide" | "setup";

export type PromptMode = "creative" | "structured" | "model" | "advanced";

export type OverflowPanel = "none" | "options" | "knowledge" | "access" | "audit" | "provider" | "plan";

export interface CoDirectorUIContext {
  projectId?: string;
  projectName?: string;
  workspaceId?: string;
  sceneId?: string;
  sceneName?: string;
  selectedAssetIds?: string[];
  selectedCharacterIds?: string[];
  selectedStoryboardPanelIds?: string[];
  activeGenerationId?: string;
}

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

export interface CoDirectorMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachmentIds?: string[];
  createdAt: string;
  /** Present while a streamed reply is in flight, or after it ended abnormally. */
  status?: CoDirectorMessageStatus;
  /** M2.4 structured assistant message kind. */
  messageType?: CoDirectorAssistantMessageType;
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
  phase: "requested" | "running" | "completed" | "failed" | "blocked";
  detail?: string;
  truncated?: boolean;
}

export type AttachmentKind = "file" | "library";

export interface CoDirectorAttachment {
  id: string;
  kind: AttachmentKind;
  name: string;
  mimeType?: string;
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
  sceneId?: string;
  sceneName?: string;
  workspaceTab?: string;
  onGoTab?: (tab: string) => void;
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

const DRAFT_KEY = "adept_codirector_draft";
const MESSAGES_KEY = "adept_codirector_messages";
const MODE_KEY = "adept_codirector_display_mode";
const CONTEXT_PANEL_KEY = "adept_codirector_context_panel";
const EXPERTISE_MODE_KEY = "adept_codirector_expertise_mode";

export function loadPersistedDraft(): string {
  try {
    return localStorage.getItem(DRAFT_KEY) || "";
  } catch {
    return "";
  }
}

export function persistDraft(value: string) {
  try {
    localStorage.setItem(DRAFT_KEY, value);
  } catch {
    /* ignore */
  }
}

export function loadPersistedMessages(): CoDirectorMessage[] | null {
  try {
    const raw = sessionStorage.getItem(MESSAGES_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CoDirectorMessage[];
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function persistMessages(messages: CoDirectorMessage[]) {
  try {
    sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(messages.slice(-80)));
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
