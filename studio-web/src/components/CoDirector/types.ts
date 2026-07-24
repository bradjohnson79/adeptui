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

export interface CoDirectorMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  attachmentIds?: string[];
  createdAt: string;
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
