import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useLanguagePrefs } from "../../i18n";
import {
  api,
  ApiError,
  classifyCoDirectorError,
  isAbortError,
  type ClassifiedError,
  type CoDirectorContextManifest,
  type CoDirectorProposal,
  type CoDirectorStreamEvent,
} from "../../api";
import {
  loadAudit,
  loadPolicies,
  savePolicies,
  type ActionCategory,
  type ActionPlan,
  type PermissionPolicy,
} from "../../codirector/types";
import type { Project, SceneSetup } from "../../types";
import {
  fetchLatestStatus,
  fetchStatusHistory,
  fetchStatusRegistry,
  runDeepDiagnostic as requestDeepDiagnostic,
  runStatusCheck as requestStatusCheck,
} from "../../codirector/status/client";
import type {
  StatusRegistryCheck,
  StatusRun,
} from "../../codirector/status/types";
import {
  deriveRuntimeState,
  isConnectedLike,
  runtimeChipText,
  type CoDirectorRuntimeState,
} from "./runtimeState";
import {
  applyToolEvent,
  createActivityState,
  summarizeActivity,
  updateStage,
  upsertStage,
} from "./activity";
import {
  consumeAbandonedStreamingFlag,
  consumeOpenPopupAfterNav,
  getTabSessionId,
  loadActivityPreference,
  loadContextPanelOpen,
  loadDisplayMode,
  loadExpertiseMode,
  loadLastBoundProjectSuggestion,
  loadPersistedDraft,
  loadPersistedMessages,
  markStreamingEnd,
  markStreamingStart,
  newAttachmentId,
  newMessageId,
  persistContextPanelOpen,
  persistDisplayMode,
  persistDraft,
  persistExpertiseMode,
  persistActivityPreference,
  persistLastBoundProjectSuggestion,
  persistMessages,
  WELCOME_ASSISTANT,
  type CoDirectorActivityPreference,
  type CoDirectorActivityState,
  type ChatMode,
  type CoDirectorAssistantMessageType,
  type CoDirectorAttachment,
  type CoDirectorDisplayMode,
  type CoDirectorExpertiseMode,
  type CoDirectorIntelligenceProgress,
  type CoDirectorMessageAttachment,
  type CoDirectorMessage,
  type CoDirectorMessageExecution,
  type CoDirectorProductionAnalysis,
  type CoDirectorSessionContext,
  type CoDirectorToolActivity,
  type CoDirectorUIContext,
  type CoDirectorWorkspaceBindings,
  type LastBoundProjectSuggestion,
  type OverflowPanel,
  type PromptMode,
  type WelcomeSuggestion,
} from "./types";
import type { WorkSurfaceState } from "./AgentWorkSurface/types";

const PROMPT_VERSIONS_KEY = "adept_prompt_versions";

type ProviderHealth = Awaited<ReturnType<typeof api.codirectorHealth>>;

type SessionValue = {
  open: boolean;
  displayMode: CoDirectorDisplayMode;
  draft: string;
  messages: CoDirectorMessage[];
  attachments: CoDirectorAttachment[];
  busy: boolean;
  applying: boolean;
  providerStatus: string;
  providerModel: string | null;
  providerHealth: ProviderHealth | null;
  selectedModelId: string | null;
  sendError: ClassifiedError | null;
  suggestedPrompt: string | null;
  setup: SceneSetup | null;
  applyNote: string | null;
  proposals: CoDirectorProposal[];
  proposalActingId: string | null;
  toolActivity: CoDirectorToolActivity | null;
  activity: CoDirectorActivityState | null;
  activityPreference: CoDirectorActivityPreference;
  setActivityPreference: (mode: CoDirectorActivityPreference) => void;
  retryActivityPersistence: () => Promise<void>;
  intelligenceProgress: CoDirectorIntelligenceProgress | null;
  productionAnalysis: CoDirectorProductionAnalysis | null;
  productionAnalysisExpanded: boolean;
  expertiseMode: CoDirectorExpertiseMode;
  setExpertiseMode: (mode: CoDirectorExpertiseMode) => void;
  toggleProductionAnalysis: () => void;
  approveProposal: (proposalId: string) => Promise<void>;
  rejectProposal: (proposalId: string, note?: string) => Promise<void>;
  requestProposalRevision: (proposalId: string, note?: string) => Promise<void>;
  cancelProposal: (proposalId: string) => Promise<void>;
  refreshProposals: () => Promise<void>;
  plan: ActionPlan | null;
  promptMode: PromptMode;
  includeProjectKnowledge: boolean;
  compileExplain: string[];
  overflowPanel: OverflowPanel;
  contextPanelOpen: boolean;
  assetPickerOpen: boolean;
  uiContext: CoDirectorUIContext;
  activeExecution: WorkSurfaceState | null;
  setActiveExecution: (state: WorkSurfaceState | null) => void;
  conversationStarted: boolean;
  policies: Record<ActionCategory, PermissionPolicy>;
  kbModels: { id: string; label?: string }[];
  kbDoc: string;
  audit: ReturnType<typeof loadAudit>;
  welcomeSuggestions: WelcomeSuggestion[];
  setDraft: (value: string) => void;
  setOpen: (open: boolean) => void;
  openSession: (opts?: { prompt?: string; mode?: CoDirectorDisplayMode; autoSend?: boolean }) => void;
  closeSession: () => void;
  toggleOpen: () => void;
  expandToFullScreen: () => void;
  collapseToPopup: () => void;
  setDisplayMode: (mode: CoDirectorDisplayMode) => void;
  setOverflowPanel: (panel: OverflowPanel) => void;
  setContextPanelOpen: (open: boolean) => void;
  setAssetPickerOpen: (open: boolean) => void;
  setPromptMode: (mode: PromptMode) => void;
  setIncludeProjectKnowledge: (value: boolean) => void;
  clearConversation: () => void;
  bindWorkspace: (bindings: CoDirectorWorkspaceBindings) => void;
  unbindWorkspace: () => void;
  setActiveContentTab: (tab: string | null) => void;
  send: (text?: string, mode?: ChatMode) => Promise<void>;
  retryLastSend: () => void;
  cancelSend: () => void;
  dismissSendError: () => void;
  openSettings: () => void;
  visionValidationEnabled: boolean;
  productionExecutiveEnabled: boolean;
  productionIntelligenceEnabled: boolean;
  unifiedExperienceEnabled: boolean;
  refreshProviderHealth: () => Promise<void>;
  reconnect: () => Promise<void>;
  setSelectedModelId: (modelId: string | null) => void;
  applySetup: () => Promise<void>;
  dismissSetup: () => void;
  applySuggestedPrompt: () => void;
  dismissSuggestedPrompt: () => void;
  compilePrompt: () => Promise<void>;
  addFiles: (files: FileList | File[]) => void;
  addLibraryAssets: (assets: { id: string; name: string; mimeType?: string; previewUrl?: string }[]) => void;
  removeAttachment: (id: string) => void;
  appendTranscript: (text: string) => void;
  setPolicies: (next: Record<ActionCategory, PermissionPolicy>) => void;
  loadKnowledge: () => Promise<void>;
  loadKnowledgeDoc: (modelId: string) => Promise<void>;
  refreshAudit: () => void;
  runtimeState: CoDirectorRuntimeState;
  runtimeChip: string;
  sessionContext: CoDirectorSessionContext;
  productionCapable: boolean;
  lastBoundProjectSuggestion: LastBoundProjectSuggestion | null;
  resumeSuggestedProject: () => void;
  selectProject: () => void;
  createProject: () => void;
  showReconnectAction: boolean;
  statusRegistry: StatusRegistryCheck[];
  statusLatestRun: StatusRun | null;
  statusHistory: StatusRun[];
  statusChecking: boolean;
  statusError: string | null;
  loadStatus: () => Promise<void>;
  runStatusCheck: (opts?: { deep?: boolean }) => Promise<void>;
  openStatusPanel: () => void;
};

const SessionContext = createContext<SessionValue | null>(null);

function buildWelcomeSuggestions(ctx: CoDirectorUIContext): WelcomeSuggestion[] {
  const suggestions: WelcomeSuggestion[] = [];
  const projectType = (ctx.primaryProjectType || "").toLowerCase();
  const isExplainer =
    projectType === "educational_explainer" ||
    projectType === "explainer_video" ||
    projectType.includes("explainer");
  const isDocumentary = projectType === "documentary" || projectType === "docuseries";
  const isSocial =
    projectType === "social_media" ||
    projectType.includes("tiktok") ||
    projectType.includes("reel") ||
    projectType.includes("youtube_short");
  const isTrailer =
    projectType === "video_cinematic_trailer" ||
    projectType.includes("trailer") ||
    projectType === "teaser_trailer";
  const isTalkingAvatar = projectType === "talking_avatar";

  if (isExplainer) {
    suggestions.push({
      id: "explainer-outline",
      label: "Outline this explainer",
      description: "Script beats, clarity, and captions.",
      text: "Outline this educational explainer: define learning goals, clear script beats, on-screen captions, and a simple visual sequence Co-Director can produce.",
      mode: "chat",
    });
    suggestions.push({
      id: "explainer-diagram-frames",
      label: "Plan diagram frames",
      description: "Visual steps for clarity.",
      text: "Propose diagram-style storyboard frames for this explainer that prioritize clarity over cinematic drama, with caption-ready titles.",
      mode: "prompt",
    });
  }
  if (isDocumentary) {
    suggestions.push({
      id: "doc-interview-plan",
      label: "Plan interview + B-roll",
      description: "Nonfiction coverage structure.",
      text: "Plan this documentary sequence: interview questions, observational B-roll, and archive/honesty notes Co-Director should respect.",
      mode: "chat",
    });
  }
  if (isSocial) {
    suggestions.push({
      id: "social-hook",
      label: "Write a hook-first short",
      description: "Captions and CTA pacing.",
      text: "Draft a social short for this project: strong opening hook, caption-ready lines, and a clear CTA within a short duration.",
      mode: "prompt",
    });
  }
  if (isTrailer) {
    suggestions.push({
      id: "trailer-beats",
      label: "Build trailer beats",
      description: "Cold open to title card.",
      text: "Build a cinematic trailer beat sheet: cold open, escalation, hero shots, title reveal, and release information — without inventing fake assets.",
      mode: "chat",
    });
  }
  if (isTalkingAvatar) {
    suggestions.push({
      id: "avatar-presenter",
      label: "Prep talking-avatar scene",
      description: "Script, voice, lip-sync.",
      text: "Prepare a talking-avatar presenter scene: concise script, Character Profile / voice needs, lip-sync path, and caption defaults.",
      mode: "setup",
    });
  }

  if (ctx.sceneId) {
    suggestions.push({
      id: "continue-scene",
      label: "Continue the current scene",
      description: "Advance prompts, coverage, or generation for this scene.",
      text: "Continue the current scene: review what's set up and propose the next production steps.",
      mode: "chat",
    });
  }
  if (ctx.selectedStoryboardPanelIds?.length || ctx.workspaceId === "story") {
    suggestions.push({
      id: "from-storyboard",
      label: "Create prompts from this storyboard",
      description: "Turn panels into motion-ready prompts.",
      text: "Create production prompts from the current storyboard panels.",
      mode: "prompt",
    });
  }
  if (ctx.workspaceId === "script" || ctx.sceneName?.toLowerCase().includes("dialog")) {
    suggestions.push({
      id: "plan-coverage",
      label: "Plan coverage for this dialogue",
      description: "Shot list and camera coverage.",
      text: "Plan coverage for this dialogue scene with a clear shot sequence.",
      mode: "chat",
    });
  }
  if (ctx.activeGenerationId || ctx.selectedAssetIds?.length) {
    suggestions.push({
      id: "review-generation",
      label: "Review the selected generation",
      description: "Critique and next-step recommendations.",
      text: "Review the selected generation and suggest what to refine next.",
      mode: "guide",
    });
  }
  if (!ctx.sceneId && !ctx.activeGenerationId && !ctx.selectedAssetIds?.length) {
    suggestions.push({
      id: "talk-story",
      label: "Talk about the Story",
      description: "Premise, plot, conflict, theme, or what happens.",
      text: "Tell me about the story however you want — the premise, what happens, who it follows, or simply the idea you're starting from.",
      mode: "chat",
    });
    suggestions.push({
      id: "talk-character",
      label: "Talk about a Character",
      description: "Who they are, role, personality, appearance, or references.",
      text: "Tell me about them however you like — their name, role, personality, appearance, history, or what they contribute to the story. You can also attach a reference if you have one.",
      mode: "chat",
    });
    suggestions.push({
      id: "talk-vision",
      label: "Talk about your Vision",
      description: "Audience experience, creative goals, emotional intent.",
      text: "Tell me what you're trying to create and what you want the audience to feel. References, influences, things to avoid, pacing, emotional effect — any of that is useful.",
      mode: "chat",
    });
    suggestions.push({
      id: "talk-style",
      label: "Talk about the Project Style",
      description: "Visual language, tone, genre, color, lighting, references.",
      text: "Describe how you imagine it looking and feeling — animation or live action, realism, color, lighting, camera language, genre, pacing, or any visual references you have in mind.",
      mode: "chat",
    });
    return suggestions;
  }
  const defaults: WelcomeSuggestion[] = [
    {
      id: "build-scene",
      label: "Build a scene",
      description: "Engine, duration, prompts, and frames.",
      text: "Build a complete scene setup for the selected scene: choose engine, duration, write prompts, and place available @tagged images into start/middle/end slots.",
      mode: "setup",
    },
    {
      id: "write-prompt",
      label: "Write a video prompt",
      description: "Motion-aware prompt help.",
      text: "Write a strong motion prompt for the selected scene using available @tags if any.",
      mode: "prompt",
    },
    {
      id: "from-board",
      label: "Create from storyboard",
      description: "Storyboard to Director flow.",
      text: "Turn the current storyboard into Director-ready prompts and a shot sequence.",
      mode: "chat",
    },
    {
      id: "plan-shots",
      label: "Plan a shot sequence",
      description: "Coverage and timing.",
      text: "Plan a shot sequence for the current scene with clear coverage notes.",
      mode: "chat",
    },
  ];
  for (const item of defaults) {
    if (suggestions.length >= 4) break;
    if (!suggestions.some((s) => s.id === item.id)) suggestions.push(item);
  }
  return suggestions.slice(0, 4);
}

function inferAttachmentMediaKind(name: string, mimeType?: string): string {
  const lowerMime = (mimeType || "").toLowerCase();
  const lowerName = name.toLowerCase();
  if (lowerMime.startsWith("image/")) return "image";
  if (lowerMime.startsWith("audio/")) return "audio";
  if (lowerMime.startsWith("video/")) return "video";
  if (/\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(lowerName)) return "image";
  if (/\.(mp3|wav|ogg|m4a|flac)$/i.test(lowerName)) return "audio";
  if (/\.(mp4|webm|mov|mkv|m4v)$/i.test(lowerName)) return "video";
  return "document";
}

function buildAttachmentTag(name: string): string {
  const stem = name.replace(/\.[^.]+$/, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^[._-]+|[._-]+$/g, "");
  return (stem || "co-director-reference").slice(0, 64);
}

function toMessageAttachments(attachments: CoDirectorAttachment[]): CoDirectorMessageAttachment[] {
  return attachments
    .filter((item): item is CoDirectorAttachment & { assetId: string } => Boolean(item.assetId))
    .map((item) => ({
      assetId: item.assetId,
      name: item.name,
      mimeType: item.mimeType,
      source: item.kind,
      mediaKind: item.mediaKind,
    }));
}

function revokeFilePreview(attachment: CoDirectorAttachment) {
  if (attachment.previewUrl && attachment.kind === "file") {
    URL.revokeObjectURL(attachment.previewUrl);
  }
}

function throwIfAborted(signal: AbortSignal) {
  if (signal.aborted) {
    throw new DOMException("Aborted", "AbortError");
  }
}

// Normalizes a server-side conversation message into the client CoDirectorMessage
// shape. Server messages use snake_case (created_at, attachment_ids) and may
// carry attachments as objects; the client uses camelCase fields.
type ServerConversationMessage = {
  id?: string;
  role: string;
  content: string;
  created_at?: string;
  attachmentIds?: unknown;
  attachment_ids?: unknown;
  attachments?: unknown;
};

function normalizeServerMessage(m: ServerConversationMessage): CoDirectorMessage {
  const attachmentIds = Array.isArray(m.attachmentIds)
    ? ((m.attachmentIds as string[]).filter(Boolean) as string[])
    : Array.isArray(m.attachment_ids)
      ? ((m.attachment_ids as string[]).filter(Boolean) as string[])
      : undefined;
  const attachments = Array.isArray(m.attachments)
    ? (m.attachments as Array<Record<string, unknown>>).reduce<CoDirectorMessageAttachment[]>(
        (acc, item) => {
          const assetId = String(item.assetId || item.asset_id || "").trim();
          const name = String(item.name || "").trim();
          if (!assetId || !name) return acc;
          const source = item.source === "library" ? "library" : "file";
          const mimeType =
            typeof item.mimeType === "string"
              ? item.mimeType
              : typeof item.mime_type === "string"
                ? item.mime_type
                : undefined;
          const mediaKind =
            typeof item.mediaKind === "string"
              ? item.mediaKind
              : typeof item.kind === "string"
                ? item.kind
                : undefined;
          acc.push({ assetId, name, mimeType, source, mediaKind });
          return acc;
        },
        [],
      )
    : undefined;
  return {
    id: m.id || newMessageId(),
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    attachmentIds,
    attachments,
    createdAt: m.created_at || new Date().toISOString(),
  };
}

// Merges `incoming` (client messages) onto the latest server conversation by
// id. Server messages are kept first; any incoming message whose id is not
// already on the server is appended. This is the durable guard against the
// reload persistence race: a stale React `messages` closure (e.g.
// [WELCOME, userMsg] from a send that landed before the async conversation
// load completed) can never overwrite the real persisted history — it can
// only add messages the server doesn't have yet.
function mergeOntoServer(
  serverMessages: ServerConversationMessage[] | undefined,
  incoming: CoDirectorMessage[],
): CoDirectorMessage[] {
  const normalized = (serverMessages || []).map(normalizeServerMessage);
  const serverIds = new Set(normalized.map((m) => m.id).filter(Boolean) as string[]);
  const merged = [...normalized];
  for (const m of incoming) {
    if (m.id && serverIds.has(m.id)) continue;
    merged.push(m);
  }
  return merged;
}

export function CoDirectorSessionProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { prefs: languagePrefs } = useLanguagePrefs();
  const bindingsRef = useRef<CoDirectorWorkspaceBindings>({});
  const activeContentTabRef = useRef<string | null>(null);
  const [open, setOpenState] = useState(false);
  const [displayMode, setDisplayModeState] = useState<CoDirectorDisplayMode>(() => loadDisplayMode());
  const [draft, setDraftState] = useState(() => loadPersistedDraft());
  const [messages, setMessages] = useState<CoDirectorMessage[]>([WELCOME_ASSISTANT]);
  const [attachments, setAttachments] = useState<CoDirectorAttachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [providerStatus, setProviderStatus] = useState("Checking Co-Director…");
  const [providerModel, setProviderModel] = useState<string | null>(null);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null);
  const [healthPending, setHealthPending] = useState(true);
  const [modelLoading, setModelLoading] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [showReconnectAction, setShowReconnectAction] = useState(false);
  const [selectedModelId, setSelectedModelIdState] = useState<string | null>(null);
  const [sendError, setSendError] = useState<ClassifiedError | null>(null);
  const [lastSuccessfulToolAction, setLastSuccessfulToolAction] = useState<string | null>(null);
  const [lastBoundProjectSuggestion, setLastBoundProjectSuggestion] = useState<LastBoundProjectSuggestion | null>(
    () => loadLastBoundProjectSuggestion(),
  );
  const reconnectAttemptsRef = useRef(0);
  const wasConnectedRef = useRef(false);
  const sendInFlightRef = useRef(false);
  // `messageId: null` means the failed attempt never got far enough to append a user
  // message (preflight failure) — retry should go through `send()` again. Once a message
  // *has* been appended, `messageId` points at it so retry resends the same transcript
  // slice instead of appending a duplicate copy of the same user message.
  const pendingRetryRef = useRef<{ text: string; mode: ChatMode; messageId: string | null } | null>(null);
  const pendingToolRetryRef = useRef<{
    kind: "read" | "mutating";
    toolId: string;
    arguments: Record<string, unknown>;
  } | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const cancelledByUserRef = useRef(false);
  const lastLoadedProjectIdRef = useRef<string | undefined>(undefined);
  // Tracks whether the conversation for the current project has been hydrated
  // from the server. The send path persists `[...messages, userMsg]` using the
  // React `messages` closure; if a send lands before the async load completes,
  // `messages` is still `[WELCOME_ASSISTANT]` and the persist would overwrite
  // the real server conversation with a 2-message stub (data loss). This guard
  // lets `persistConversation` merge against the server list when stale.
  const conversationHydratedRef = useRef(false);
  // Serializes `persistConversation` calls. A turn fires multiple persists
  // (the fire-and-forget user-turn persist, then the final transcript persist,
  // plus error/cancel paths). Without serialization two persists can race:
  // P1 GET old, P2 GET old, P1 POST merged, P2 POST merged-over-old → data loss.
  // Each persist chains onto the previous so its GET-merge-POST runs strictly
  // after the prior one settles.
  const persistChainRef = useRef<Promise<unknown> | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    // StrictMode double-invokes effects in dev (mount → cleanup → mount) — reset on each
    // mount so the first synthetic cleanup doesn't permanently "unmount" this ref.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  const [suggestedPrompt, setSuggestedPrompt] = useState<string | null>(null);
  const [setup, setSetup] = useState<SceneSetup | null>(null);
  const [activeExecution, setActiveExecution] = useState<WorkSurfaceState | null>(null);
  const [proposals, setProposals] = useState<CoDirectorProposal[]>([]);
  const [proposalActingId, setProposalActingId] = useState<string | null>(null);
  const [toolActivity, setToolActivity] = useState<CoDirectorToolActivity | null>(null);
  const [activity, setActivity] = useState<CoDirectorActivityState | null>(null);
  const [activityPreference, setActivityPreferenceState] = useState<CoDirectorActivityPreference>(() =>
    loadActivityPreference(),
  );
  const [intelligenceProgress, setIntelligenceProgress] = useState<CoDirectorIntelligenceProgress | null>(null);
  const [productionAnalysis, setProductionAnalysis] = useState<CoDirectorProductionAnalysis | null>(null);
  const [productionAnalysisExpanded, setProductionAnalysisExpanded] = useState(false);
  const [expertiseMode, setExpertiseModeState] = useState<CoDirectorExpertiseMode>(() => loadExpertiseMode());
  const [applyNote, setApplyNote] = useState<string | null>(null);
  const [plan, setPlan] = useState<ActionPlan | null>(null);
  const [promptMode, setPromptMode] = useState<PromptMode>("creative");
  const [includeProjectKnowledge, setIncludeProjectKnowledge] = useState(true);
  const [compileExplain, setCompileExplain] = useState<string[]>([]);
  const [overflowPanel, setOverflowPanel] = useState<OverflowPanel>("none");
  const [contextPanelOpen, setContextPanelOpenState] = useState(() => loadContextPanelOpen());
  const [assetPickerOpen, setAssetPickerOpen] = useState(false);
  const [policies, setPoliciesState] = useState(loadPolicies());
  const [kbModels, setKbModels] = useState<{ id: string; label?: string }[]>([]);
  const [kbDoc, setKbDoc] = useState("");
  const [audit, setAudit] = useState(() => loadAudit().slice(0, 20));
  const [uiContext, setUiContext] = useState<CoDirectorUIContext>({});
  const [statusRegistry, setStatusRegistry] = useState<StatusRegistryCheck[]>([]);
  const [statusLatestRun, setStatusLatestRun] = useState<StatusRun | null>(null);
  const [statusHistory, setStatusHistory] = useState<StatusRun[]>([]);
  const [statusChecking, setStatusChecking] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const activityPersistenceRef = useRef<{
    messages: CoDirectorMessage[];
    model?: string | null;
    providerId?: string | null;
  } | null>(null);
  const activityManifestRef = useRef<CoDirectorContextManifest | null>(null);

  const clearComposerAttachments = useCallback(() => {
    setAttachments((prev) => {
      for (const item of prev) revokeFilePreview(item);
      return [];
    });
  }, []);

  const conversationStarted = messages.some((m) => m.role === "user");

  const cancelInFlightForProjectSwitch = useCallback(() => {
    const requestId = activeRequestIdRef.current;
    cancelledByUserRef.current = true;
    sendInFlightRef.current = false;
    if (requestId) void api.codirectorCancel(requestId).catch(() => {});
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    activeRequestIdRef.current = null;
    setBusy(false);
    setToolActivity(null);
    setActivity(null);
    setIntelligenceProgress(null);
  }, []);

  const syncProjectIdentity = useCallback((projectId?: string, projectName?: string) => {
    const resolvedProjectId = (projectId || bindingsRef.current.projectId || "").trim();
    const resolvedProjectName = (projectName || "").trim();
    if (!resolvedProjectId || !resolvedProjectName) return;
    if (bindingsRef.current.projectId && bindingsRef.current.projectId !== resolvedProjectId) return;
    bindingsRef.current = { ...bindingsRef.current, projectId: resolvedProjectId, projectName: resolvedProjectName };
    setUiContext((prev) =>
      prev.projectId === resolvedProjectId && prev.projectName === resolvedProjectName
        ? prev
        : { ...prev, projectId: resolvedProjectId, projectName: resolvedProjectName },
    );
    const suggestion = { projectId: resolvedProjectId, projectName: resolvedProjectName };
    persistLastBoundProjectSuggestion(suggestion);
    setLastBoundProjectSuggestion((prev) =>
      prev?.projectId === suggestion.projectId && prev?.projectName === suggestion.projectName ? prev : suggestion,
    );
    window.dispatchEvent(new CustomEvent("adept:project-renamed", { detail: suggestion }));
  }, []);

  const syncProjectIdentityFromResult = useCallback(
    (result: Record<string, unknown>) => {
      const projectRecord =
        result.project && typeof result.project === "object" ? (result.project as Record<string, unknown>) : null;
      const projectId = String(projectRecord?.id || result.projectId || bindingsRef.current.projectId || "");
      const projectName = String(projectRecord?.name || result.projectName || "");
      syncProjectIdentity(projectId, projectName);
    },
    [syncProjectIdentity],
  );

  const refreshProviderHealth = useCallback(async (opts?: { force?: boolean }) => {
    if (!opts?.force) {
      const { shouldSuspendDependentPolling } = await import("../../runtime/studioApiConnection");
      if (shouldSuspendDependentPolling()) {
        setHealthPending(false);
        return;
      }
    }
    setHealthPending(true);
    try {
      const health = await api.codirectorHealth("active");
      setProviderHealth(health);
      setProviderModel(health.selectedModel);
      const testLabel = health.testOnly || health.honesty === "mocked" ? " (test-only)" : "";
      setProviderStatus(
        health.status === "Ready"
          ? `${health.displayName} · ${health.selectedModel}${testLabel}`
          : health.status,
      );
      setSelectedModelIdState((prev) => prev ?? health.selectedModel ?? null);
      if (health.ok && health.reachable && health.modelAvailable) {
        wasConnectedRef.current = true;
        reconnectAttemptsRef.current = 0;
        setReconnecting(false);
        setShowReconnectAction(false);
      } else if (wasConnectedRef.current && !health.reachable) {
        setReconnecting(true);
      }
    } catch {
      setProviderHealth(null);
      setProviderModel(null);
      setProviderStatus("Co-Director unavailable");
      if (wasConnectedRef.current) {
        setReconnecting(true);
      }
    } finally {
      setHealthPending(false);
      setModelLoading(false);
    }
  }, []);

  const reconnect = useCallback(async () => {
    setShowReconnectAction(false);
    setReconnecting(true);
    reconnectAttemptsRef.current = 0;
    await refreshProviderHealth({ force: true });
  }, [refreshProviderHealth]);

  useEffect(() => {
    void refreshProviderHealth();
  }, [refreshProviderHealth]);

  // Bounded auto-reconnect when previously connected and now unavailable.
  useEffect(() => {
    if (!reconnecting) return;
    if (reconnectAttemptsRef.current >= 5) {
      setShowReconnectAction(true);
      return;
    }
    const delay = Math.min(8000, 1000 * 2 ** reconnectAttemptsRef.current);
    const timer = window.setTimeout(() => {
      reconnectAttemptsRef.current += 1;
      void refreshProviderHealth();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [reconnecting, providerHealth, refreshProviderHealth]);

  // Cancel any in-flight request when the panel unmounts (app close / hard navigation away).
  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const persistConversation = useCallback(
    async (msgs: CoDirectorMessage[], model?: string | null, providerId?: string | null) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId) return { ok: false, skipped: true, message: "No project is selected." };
      // Safe message fields only — never persist tool payloads or error traces locally.
      persistMessages(msgs, projectId);

      // Serialize persists so two concurrent persists can't race (P1 GET old,
      // P2 GET old, P1 POST merged, P2 POST merged-over-old → data loss). Each
      // persist waits for the previous to settle before doing its own
      // GET-merge-POST. The chain is per-process; project switches drop stale
      // queued persists via the `lastLoadedProjectIdRef` guard below.
      const prev = persistChainRef.current ?? Promise.resolve();
      const run = prev.then(
        async (): Promise<{ ok: boolean; skipped: boolean; message: string | null }> => {
          // If the bound project switched while this persist was queued, drop it —
          // saving a stale transcript to a new project would corrupt it.
          if (lastLoadedProjectIdRef.current !== projectId) {
            return { ok: false, skipped: true, message: "Project changed before save." };
          }
          // ALWAYS merge by id onto the latest server conversation, regardless
          // of `conversationHydratedRef`. A turn fires multiple persists: the
          // fire-and-forget user-turn persist (send()), then the final
          // transcript persist (performSend completion / error / cancel paths).
          // The final persist carries a `transcriptForApi` captured from the
          // React `messages` closure at send time — which can be a stale
          // [WELCOME, userMsg] stub if the send landed before the async
          // conversation load completed. Gating the merge on
          // `!conversationHydratedRef` (the prior fix) let the second persist
          // skip the merge once the first set the flag, overwriting the real
          // server conversation with the stale stub (data loss). Merging every
          // time means the server is always the source of truth and a stale
          // stub can only ADD messages the server doesn't have, never remove
          // history.
          let messagesToSave = msgs;
          try {
            const server = await api.codirectorGetConversation(projectId);
            if (lastLoadedProjectIdRef.current !== projectId) {
              return { ok: false, skipped: true, message: "Project changed during save." };
            }
            messagesToSave = mergeOntoServer(server.messages, msgs);
            // If hydration hasn't happened yet (send before async load), adopt
            // the merged state so the UI shows the real history instead of the
            // stub. Once hydrated, leave the in-memory state alone — the
            // streaming token handler has already been appending to it.
            if (!conversationHydratedRef.current && mountedRef.current) {
              setMessages(messagesToSave);
            }
            conversationHydratedRef.current = true;
          } catch {
            // Server fetch failed — fall back to saving `msgs` as-is. Only mark
            // hydrated if we're still on the same project, so a failed fetch
            // for the old project doesn't falsely hydrate a new project.
            if (lastLoadedProjectIdRef.current === projectId) {
              conversationHydratedRef.current = true;
            }
          }
          try {
            await api.codirectorSaveConversation(projectId, {
              messages: messagesToSave.map((m) => ({
                id: m.id,
                role: m.role,
                content: m.content,
                created_at: m.createdAt,
                attachment_ids: Array.isArray(m.attachmentIds) ? m.attachmentIds : [],
                attachments: Array.isArray(m.attachments)
                  ? m.attachments.map((item) => ({
                      asset_id: item.assetId,
                      name: item.name,
                      mime_type: item.mimeType,
                      source: item.source,
                      kind: item.mediaKind,
                    }))
                  : [],
              })),
              model: model ?? null,
              provider_id: providerId ?? null,
            });
            return { ok: true, skipped: false, message: null };
          } catch (err) {
            return {
              ok: false,
              skipped: false,
              message:
                err instanceof Error
                  ? err.message
                  : "Co-Director finished the reply, but saving this conversation did not.",
            };
          }
        },
      );
      // Keep the chain alive regardless of success/failure so a failed persist
      // doesn't permanently block subsequent ones.
      persistChainRef.current = run.then(() => undefined, () => undefined);
      return run;
    },
    [],
  );

  // Tracks the server-side conversation revision for optimistic concurrency on
  // appends. Updated from GET / append responses.
  const conversationRevisionRef = useRef<number | null>(null);

  // Wave A persistent memory: the server owns durability. The client appends a
  // creator turn as a single idempotent event (keyed on client_request_id) and
  // never replaces the authoritative transcript after generation. The server
  // appends the assistant reply (+ tool call/result) itself during stream
  // completion, so after a turn the client only RECONCILES by id (GET + merge).
  const appendUserTurn = useCallback(
    async (userMsg: CoDirectorMessage, clientRequestId: string) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId) return { ok: false, skipped: true, message: "No project is selected." };
      persistMessages([...messages, userMsg], projectId); // sessionStorage cache only
      try {
        const res = await api.codirectorAppendConversationEvents(projectId, {
          events: [
            {
              role: "user",
              content: userMsg.content,
              message_id: userMsg.id,
              client_request_id: clientRequestId,
              attachments: (userMsg.attachments || []).map((a) => ({
                assetId: a.assetId,
                name: a.name,
                mimeType: a.mimeType,
                source: a.source,
                kind: a.mediaKind,
              })),
              actor: "user",
              created_at: userMsg.createdAt,
            },
          ],
        });
        // Adopt the server's revision so a subsequent append can present it.
        conversationRevisionRef.current = res.revision;
        return { ok: true, skipped: false, message: null };
      } catch (err) {
        return {
          ok: false,
          skipped: false,
          message: err instanceof Error ? err.message : "Could not save your message.",
        };
      }
    },
    [messages],
  );

  // Reconcile local state with the server's authoritative event log by id.
  // The server already appended the assistant reply (+ tool events) during
  // stream completion; this just pulls them in so the UI matches durability.
  // It NEVER POSTs the full transcript — that path is deprecated.
  const reconcileConversation = useCallback(async () => {
    const projectId = bindingsRef.current.projectId;
    if (!projectId) return { ok: false, skipped: true, message: "No project is selected." };
    try {
      const server = await api.codirectorGetConversation(projectId);
      if (lastLoadedProjectIdRef.current !== projectId) {
        return { ok: false, skipped: true, message: "Project changed during reconcile." };
      }
      if (typeof server.revision === "number") {
        conversationRevisionRef.current = server.revision;
      }
      const serverMessages = (server.messages || []).map(normalizeServerMessage);
      setMessages((prev) => {
        const localIds = new Set(prev.map((m) => m.id).filter(Boolean) as string[]);
        const merged = [...prev];
        for (const sm of serverMessages) {
          if (sm.id && localIds.has(sm.id)) continue;
          merged.push(sm);
        }
        return merged;
      });
      conversationHydratedRef.current = true;
      return { ok: true, skipped: false, message: null };
    } catch (err) {
      return {
        ok: false,
        skipped: false,
        message: err instanceof Error ? err.message : "Could not reconcile the conversation.",
      };
    }
  }, []);

  // The server is the source of truth for a project's conversation. Hydrate from it whenever
  // the bound project changes, and surface a mid-stream reload as an interrupted turn instead
  // of silently dropping the user's last message.
  useEffect(() => {
    const projectId = uiContext.projectId;
    if (!projectId) {
      if (lastLoadedProjectIdRef.current) {
        cancelInFlightForProjectSwitch();
        lastLoadedProjectIdRef.current = undefined;
        setMessages([WELCOME_ASSISTANT]);
        setPlan(null);
        setProposals([]);
        setSendError(null);
        setActivity(null);
      }
      return;
    }
    if (projectId === lastLoadedProjectIdRef.current) return;

    // Cancel previous project's in-flight work before clearing / hydrating.
    cancelInFlightForProjectSwitch();
    const previousProjectId = lastLoadedProjectIdRef.current;
    lastLoadedProjectIdRef.current = projectId;
    conversationHydratedRef.current = false;
    // Drop any queued persists for the previous project so they can't race into
    // this new project's conversation. In-flight GET/POST for the old project
    // are still guarded by the `lastLoadedProjectIdRef` check inside
    // `persistConversation` and will self-skip.
    persistChainRef.current = null;
    setMessages([WELCOME_ASSISTANT]);
    setPlan(null);
    setSendError(null);
    setToolActivity(null);
    setActivity(null);
    if (previousProjectId) markStreamingEnd(previousProjectId);

    let cancelled = false;
    (async () => {
      const abandoned = consumeAbandonedStreamingFlag(projectId);
      try {
        const convo = await api.codirectorGetConversation(projectId);
        if (cancelled || lastLoadedProjectIdRef.current !== projectId) return;
        if (convo.messages && convo.messages.length) {
          let loaded: CoDirectorMessage[] = convo.messages.map(normalizeServerMessage);
          if (abandoned && loaded[loaded.length - 1]?.role === "user") {
            loaded = [
              ...loaded,
              {
                id: newMessageId(),
                role: "assistant",
                content: "The previous response was interrupted before it finished. You can retry.",
                createdAt: new Date().toISOString(),
                status: "interrupted",
              },
            ];
          }
          // If the send path already hydrated+merged (persistConversation ran
          // during the await above), keep its merged state — do not revert to
          // the stale server snapshot we fetched before the merge saved.
          if (!conversationHydratedRef.current) {
            setMessages(loaded);
          }
          if (convo.model) setSelectedModelIdState((prev) => prev ?? convo.model);
          if (convo.providerId || convo.model) {
            /* provider/model recorded on session via conversation row */
          }
        } else {
          const local = loadPersistedMessages(projectId);
          if (!conversationHydratedRef.current) {
            setMessages(local && local.length ? local : [WELCOME_ASSISTANT]);
          }
        }
        if (!cancelled && lastLoadedProjectIdRef.current === projectId) {
          conversationHydratedRef.current = true;
        }
      } catch {
        if (cancelled || lastLoadedProjectIdRef.current !== projectId) return;
        const local = loadPersistedMessages(projectId);
        if (local && local.length) setMessages(local);
        conversationHydratedRef.current = true;
      }

      // Restore active execution overlay after refresh (spec §18). The
      // `activeExecution` state resets to null on every reload, so without
      // this the AgentWorkSurface overlay disappears even while the backend
      // still has an in-flight execution for this project. We only rehydrate
      // non-terminal executions — a terminal execution from before the
      // refresh does not need to reclaim the right pane.
      if (projectId) {
        try {
          const activeRes = await api.getActiveExecution(projectId);
          if (cancelled || lastLoadedProjectIdRef.current !== projectId) return;
          const exec = activeRes?.execution;
          if (exec && !["completed", "failed", "cancelled"].includes(exec.status)) {
            setActiveExecution({
              mode: "agent_work",
              execution_id: exec.execution_id,
              capability: exec.capability || "",
              surface_type: exec.surface_type || "",
              status: exec.status,
              progress: exec.progress || 0,
              focused_artifact_ids: exec.result_asset_ids || [],
              child_jobs: (exec.child_jobs || []).map((c: any) => ({
                job_id: c.job_id,
                label: c.label || `Item ${(c.child_index ?? 0) + 1}`,
                status: (c.status as WorkSurfaceState["child_jobs"][number]["status"]) || "queued",
                asset_id: c.asset_id ?? null,
                error: c.error ?? null,
                progress: c.progress || 0,
                stage: c.stage || "",
                child_index: c.child_index ?? 0,
                metadata: c.metadata || {},
              })),
              result_asset_ids: exec.result_asset_ids || [],
              collection_id: exec.collection_id ?? null,
              error: exec.error ?? null,
              project_id: projectId,
            });
          }
        } catch (err) {
          // Recovery is best-effort — a missing/empty active execution just
          // means there is nothing to restore; the right pane stays normal.
          console.warn("Active execution recovery failed:", err);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [uiContext.projectId, cancelInFlightForProjectSwitch]);

  // Wave C: poll server revision when tab is visible; reconcile on change.
  useEffect(() => {
    const projectId = uiContext.projectId;
    if (!projectId) return;

    let cancelled = false;
    let lastRevision = conversationRevisionRef.current;

    const tick = async () => {
      if (cancelled || document.visibilityState !== "visible") return;
      if (lastLoadedProjectIdRef.current !== projectId) return;
      const { shouldSuspendDependentPolling } = await import("../../runtime/studioApiConnection");
      if (shouldSuspendDependentPolling()) return;
      try {
        const rev = await api.codirectorGetConversationRevision(projectId);
        if (cancelled || lastLoadedProjectIdRef.current !== projectId) return;
        if (typeof rev.revision !== "number") return;
        if (lastRevision !== null && rev.revision !== lastRevision) {
          await reconcileConversation();
        }
        lastRevision = rev.revision;
        conversationRevisionRef.current = rev.revision;
      } catch {
        /* ignore transient poll failures — outage coordinator owns reconnect */
      }
    };

    void tick();
    const interval = window.setInterval(() => void tick(), 5000);
    const onVisible = () => void tick();
    document.addEventListener("visibilitychange", onVisible);
    let unsubRecover: (() => void) | undefined;
    void import("../../runtime/studioApiConnection").then((m) => {
      unsubRecover = m.onStudioApiRecovered(() => {
        void tick();
      });
    });

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      unsubRecover?.();
    };
  }, [uiContext.projectId, reconcileConversation]);

  const NON_TERMINAL_PROPOSAL_STATUSES = new Set(["pending", "revision_requested", "stale", "executing"]);

  const refreshProposals = useCallback(async () => {
    const projectId = bindingsRef.current.projectId;
    if (!projectId) {
      setProposals([]);
      return;
    }
    try {
      const res = await api.listProposals(projectId);
      setProposals(res.proposals.filter((p) => NON_TERMINAL_PROPOSAL_STATUSES.has(p.status)));
    } catch {
      /* Bible/proposals are best-effort UI — leave prior list on transient failure. */
    }
  }, []);

  useEffect(() => {
    void refreshProposals();
  }, [refreshProposals, uiContext.projectId]);

  // Track which project the in-memory draft belongs to (project-scoped persistence).
  const draftProjectRef = useRef<string | undefined>(uiContext.projectId);

  useEffect(() => {
    persistDraft(draft, draftProjectRef.current);
  }, [draft]);

  // Swap composer draft when project binding changes so drafts cannot leak across projects.
  useEffect(() => {
    const nextId = uiContext.projectId;
    const prevId = draftProjectRef.current;
    if (nextId === prevId) return;
    persistDraft(draft, prevId);
    draftProjectRef.current = nextId;
    const nextDraft = loadPersistedDraft(nextId);
    setDraftState((prev) => (prev === nextDraft ? prev : nextDraft));
    // Intentionally omit `draft` from deps — snapshot outgoing project only on bind change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiContext.projectId]);

  useEffect(() => {
    const projectId = uiContext.projectId;
    if (projectId) persistMessages(messages, projectId);
  }, [messages, uiContext.projectId]);

  const setDraft = useCallback((value: string) => setDraftState(value), []);
  const setOpen = useCallback((value: boolean) => setOpenState(value), []);
  const setDisplayMode = useCallback((mode: CoDirectorDisplayMode) => {
    setDisplayModeState(mode);
    persistDisplayMode(mode);
  }, []);
  useEffect(() => {
    if (!consumeOpenPopupAfterNav()) return;
    setDisplayMode("popup");
    setOpenState(true);
  }, [location.pathname, setDisplayMode]);
  const setContextPanelOpen = useCallback((value: boolean) => {
    setContextPanelOpenState(value);
    persistContextPanelOpen(value);
  }, []);

  const setExpertiseMode = useCallback((mode: CoDirectorExpertiseMode) => {
    setExpertiseModeState(mode);
    persistExpertiseMode(mode);
  }, []);

  const setActivityPreference = useCallback((mode: CoDirectorActivityPreference) => {
    setActivityPreferenceState(mode);
    persistActivityPreference(mode);
  }, []);

  const toggleProductionAnalysis = useCallback(() => {
    setProductionAnalysisExpanded((prev) => !prev);
  }, []);

  const bindWorkspace = useCallback((bindings: CoDirectorWorkspaceBindings) => {
    const prevProjectId = bindingsRef.current.projectId;
    if (prevProjectId && bindings.projectId && prevProjectId !== bindings.projectId) {
      cancelInFlightForProjectSwitch();
    }
    bindingsRef.current = bindings;
    setUiContext((prev) => {
      const next: CoDirectorUIContext = {
        projectId: bindings.projectId,
        projectName: bindings.projectName,
        primaryProjectType: bindings.primaryProjectType,
        sceneId: bindings.sceneId,
        sceneName: bindings.sceneName,
        workspaceId: bindings.workspaceTab,
        activeDocumentId: bindings.activeDocumentId,
        onGoTab: bindings.onGoTab,
      };
      if (
        prev.projectId === next.projectId &&
        prev.projectName === next.projectName &&
        prev.primaryProjectType === next.primaryProjectType &&
        prev.sceneId === next.sceneId &&
        prev.sceneName === next.sceneName &&
        prev.workspaceId === next.workspaceId &&
        prev.activeDocumentId === next.activeDocumentId
      ) {
        return prev;
      }
      return next;
    });
    // Suggestion-only persistence — never auto-binds or grants production permissions.
    if (bindings.projectId) {
      const suggestion = { projectId: bindings.projectId, projectName: bindings.projectName };
      persistLastBoundProjectSuggestion(suggestion);
      setLastBoundProjectSuggestion((prev) => {
        if (
          prev?.projectId === suggestion.projectId &&
          prev?.projectName === suggestion.projectName
        ) {
          return prev;
        }
        return suggestion;
      });
    }
  }, [cancelInFlightForProjectSwitch]);

  const unbindWorkspace = useCallback(() => {
    cancelInFlightForProjectSwitch();
    bindingsRef.current = {};
    setUiContext({});
  }, [cancelInFlightForProjectSwitch]);

  const setActiveContentTab = useCallback((tab: string | null) => {
    setUiContext((prev) =>
      prev.activeContentTab === tab ? prev : { ...prev, activeContentTab: tab },
    );
  }, []);

  useEffect(() => {
    activeContentTabRef.current = uiContext.activeContentTab ?? null;
  }, [uiContext.activeContentTab]);

  const selectProject = useCallback(() => {
    navigate("/#projects-library");
  }, [navigate]);

  const createProject = useCallback(() => {
    navigate("/?create=1");
  }, [navigate]);

  const resumeSuggestedProject = useCallback(() => {
    const suggestion = lastBoundProjectSuggestion || loadLastBoundProjectSuggestion();
    if (!suggestion?.projectId) return;
    // Explicit user action only — navigate so route binding becomes canonical.
    navigate(`/project/${encodeURIComponent(suggestion.projectId)}`);
  }, [lastBoundProjectSuggestion, navigate]);

  const openSession = useCallback(
    (opts?: { prompt?: string; mode?: CoDirectorDisplayMode }) => {
      if (opts?.mode) setDisplayMode(opts.mode);
      setOpenState(true);
      if (opts?.prompt) {
        setDraftState(opts.prompt);
      }
    },
    [setDisplayMode],
  );

  const closeSession = useCallback(() => {
    abortControllerRef.current?.abort();
    setOpenState(false);
    setOverflowPanel("none");
    setAssetPickerOpen(false);
    if (displayMode === "fullscreen") {
      setDisplayMode("popup");
    }
  }, [displayMode, setDisplayMode]);

  const toggleOpen = useCallback(() => {
    setOpenState((v) => !v);
  }, []);

  const expandToFullScreen = useCallback(() => {
    setDisplayMode("fullscreen");
    setOpenState(true);
    const projectId = bindingsRef.current.projectId;
    navigate(projectId ? `/co-director?projectId=${encodeURIComponent(projectId)}` : "/co-director");
  }, [navigate, setDisplayMode]);

  const collapseToPopup = useCallback(() => {
    setDisplayMode("popup");
    setOpenState(true);
    const projectId = bindingsRef.current.projectId;
    if (projectId) navigate(`/project/${projectId}`);
    else navigate("/");
  }, [navigate, setDisplayMode]);

  const clearConversation = useCallback(() => {
    abortControllerRef.current?.abort();
    setMessages([WELCOME_ASSISTANT]);
    setPlan(null);
    setSuggestedPrompt(null);
    setSetup(null);
    setApplyNote(null);
    setCompileExplain([]);
    setSendError(null);
    setActivity(null);
    pendingRetryRef.current = null;
    const projectId = bindingsRef.current.projectId;
    if (projectId) {
      markStreamingEnd(projectId);
      void api.codirectorDeleteConversation(projectId).catch(() => {});
    }
  }, []);

  const dismissSendError = useCallback(() => setSendError(null), []);

  const openSettings = useCallback(() => {
    setOverflowPanel("provider");
    void refreshProviderHealth();
  }, [refreshProviderHealth]);

  const setSelectedModelId = useCallback((modelId: string | null) => {
    setSelectedModelIdState(modelId);
    setModelLoading(true);
    void api
      .codirectorUpdateConfig({ selectedModel: modelId })
      .then(() => refreshProviderHealth())
      .catch(() => {
        setModelLoading(false);
      });
  }, [refreshProviderHealth]);

  /**
   * Talk to the gateway for an already-built transcript (`transcriptForApi` includes the
   * user's message as its last entry). Never appends a new user message itself — that's
   * `send()`'s job — so `retryLastSend()` can call this directly to resend without
   * duplicating the user's turn in the transcript.
   */
  const performSend = useCallback(
    async (transcriptForApi: CoDirectorMessage[], mode: ChatMode, requestId = newMessageId()) => {
      // Single-flight: avoid duplicate message submission / tool execution on reconnect.
      if (sendInFlightRef.current) return;
      sendInFlightRef.current = true;
      setSendError(null);
      setBusy(true);
      setSuggestedPrompt(null);
      setSetup(null);
      setToolActivity(null);
      setIntelligenceProgress(null);
      setProductionAnalysis(null);
      setApplyNote(null);
      setOverflowPanel((prev) => (prev === "provider" ? prev : "none"));

      const b = bindingsRef.current;
      activeRequestIdRef.current = requestId;
      cancelledByUserRef.current = false;
      const controller = new AbortController();
      abortControllerRef.current = controller;
      if (b.projectId) markStreamingStart(b.projectId, requestId);

      const assistantId = newMessageId();
      // Wave A persistent memory: the server assigns the assistant message id
      // (`asst-{requestId}`) when it appends the reply event. We adopt it on
      // `completed` so the local bubble and the server event share an id and
      // reconciliation by id cannot duplicate.
      let serverAssistantId: string | null = null;
      let streamedText = "";
      let sawToken = false;
      let outcome: "completed" | "cancelled" | "error" | null = null;
      let finalModel: string | undefined;
      let finalProviderId: string | undefined;
      let sceneSetupResult: SceneSetup | null = null;
      let suggestedPromptResult: string | null = null;
      let classifiedError: ClassifiedError | null = null;
      // A `proposal_created`'s malformed sibling (STRUCTURED_OUTPUT_INVALID) arrives as an
      // `error` event *after* `completed` — it's non-fatal for the turn itself (the model's
      // reply still finished), so it must not discard the already-cleaned reply the way a
      // fatal provider error (no prior `completed`) does. Tracked separately so the completed
      // reply is finalized normally and the error is shown alongside it.
      let postCompletionError: ClassifiedError | null = null;
      let executionCreated = false;

      const apiMessages = transcriptForApi.map((m) => ({ role: m.role, content: m.content }));
      const lastUser = [...transcriptForApi].reverse().find((m) => m.role === "user");
      const turnAttachmentIds = Array.isArray(lastUser?.attachmentIds)
        ? lastUser.attachmentIds.filter((value): value is string => Boolean(value))
        : [];

      let assistantMessageType: CoDirectorAssistantMessageType | undefined;
      const updateActivityForRequest = (updater: (current: CoDirectorActivityState) => CoDirectorActivityState) => {
        setActivity((prev) => {
          if (!prev || prev.requestId !== requestId) return prev;
          return updater(prev);
        });
      };
      const markResponseComposing = () => {
        updateActivityForRequest((prev) => {
          let next = updateStage(prev, "request", { status: "completed" });
          next = updateStage(next, "context", { status: "completed" });
          next = updateStage(next, "media", { status: "completed" });
          next = updateStage(next, "plan", { status: "completed" });
          return upsertStage(next, {
            id: "response",
            eventType: "response_composing",
            label: "Composing a response",
            status: "active",
          });
        });
      };

      const onEvent = (event: CoDirectorStreamEvent) => {
        if (!mountedRef.current || activeRequestIdRef.current !== requestId) return; // stale / unmounted
        if (event.type === "request_started") {
          updateActivityForRequest((prev) => {
            const next = updateStage(prev, "request", { status: "completed" });
            return prev.stages.some((stageItem) => stageItem.id === "context")
              ? updateStage(next, "context", { status: "active" })
              : prev.stages.some((stageItem) => stageItem.id === "media")
                ? updateStage(next, "media", { status: "active" })
                : upsertStage(next, {
                    id: "response",
                    eventType: "response_composing",
                    label: "Composing a response",
                    status: "active",
                  });
          });
        } else if (event.type === "context_manifest") {
          activityManifestRef.current = event.manifest;
          updateActivityForRequest((prev) => {
            let next = updateStage(prev, "context", { status: "completed" });
            next = upsertStage(next, {
              id: "wiki",
              eventType: "wiki_review",
              label: "Checking saved project notes",
              status: "completed",
            });
            return next;
          });
        } else if (event.type === "conversation_state") {
          updateActivityForRequest((prev) => ({
            ...prev,
            cognitiveMode: event.state?.mode ?? prev.cognitiveMode,
            activeGoal: event.state?.activeGoal ?? prev.activeGoal,
            workflowHold: Boolean(event.state?.workflowHold),
            creativePosture: event.state?.creativePosture ?? event.state?.companionNeed ?? prev.creativePosture,
            advisoryDecision: event.state?.advisoryDecision ?? prev.advisoryDecision,
            advisoryStrength: event.state?.advisoryStrength ?? prev.advisoryStrength,
            changeStatus: event.state?.changeStatus ?? prev.changeStatus,
            waitingForConfirmation: Boolean(event.state?.waitingForConfirmation),
            canonUpdated: Boolean(event.state?.canonUpdated),
            roleEmphasis: event.state?.roleEmphasis ?? prev.roleEmphasis,
            assistantName: event.state?.assistantName ?? prev.assistantName,
            userPreferredName: event.state?.userPreferredName ?? prev.userPreferredName,
            creativeStage: event.state?.creativeStage ?? prev.creativeStage,
            wikiCandidates: event.state?.wikiCandidates ?? prev.wikiCandidates,
            confirmedWrites: event.state?.confirmedWrites ?? prev.confirmedWrites,
            discoveryQuestionCount: event.state?.discoveryQuestions ?? prev.discoveryQuestionCount,
            researchStatus: event.state?.researchStatus ?? prev.researchStatus,
            documentationReason: event.state?.documentationReason ?? prev.documentationReason,
            whatChanged: event.state?.whatChanged ?? prev.whatChanged,
            projectPulse: event.state?.projectPulse ?? prev.projectPulse,
            processingStages: event.state?.processingStages ?? prev.processingStages,
            onboardingNeeded: Boolean(event.state?.onboardingNeeded),
            memorySummary: event.state?.workflowHold
              ? "Listening preference saved · holding production steps"
              : prev.memorySummary || "Working memory updated",
            toolsSummary: event.state?.toolsSummary || "None this turn",
          }));
        } else if (event.type === "processing_stage") {
          const stageName = String(event.stage || "");
          updateActivityForRequest((prev) => {
            const stages = [...(prev.processingStages || []), stageName].filter(Boolean);
            const next = {
              ...prev,
              processingStages: stages,
              wikiBackgroundStatus:
                stageName === "UPDATING_WIKI" ? ("running" as const) : prev.wikiBackgroundStatus,
              coldLoadActive: stageName === "LOADING_MODEL" ? true : stageName === "STREAMING_RESPONSE" ? false : prev.coldLoadActive,
            };
            // Keep ActivityPanel request row honest — complete it once SSE stages move past RECEIVING.
            if (stageName && stageName !== "RECEIVING" && stageName !== "RECEIVED") {
              return updateStage(next, "request", {
                status: "completed",
                label: "Received your message",
              });
            }
            return next;
          });
        } else if (event.type === "wiki_status") {
          const verification = (event.verification || {}) as {
            persistenceState?: string;
            presentationState?: string;
            finalState?: string;
            error?: string | null;
          };
          updateActivityForRequest((prev) => ({
            ...prev,
            wikiVerification: verification,
            wikiBackgroundStatus:
              verification.finalState === "QUEUED" || verification.persistenceState === "PERSISTED"
                ? ("processing" as const)
                : prev.wikiBackgroundStatus,
            wikiUiMessage: event.message || prev.wikiUiMessage,
            wikiRefreshNonce: (prev.wikiRefreshNonce || 0) + 1,
          }));
        } else if (event.type === "background_job") {
          if (String(event.jobType || "") === "wiki_enrichment") {
            const status = String(event.status || "").toUpperCase();
            const verification = ((event.result as { verification?: Record<string, unknown> } | undefined)
              ?.verification || {}) as {
              persistenceState?: string;
              presentationState?: string;
              finalState?: string;
              error?: string | null;
            };
            const persistenceOk =
              verification.persistenceState === "VERIFIED" || verification.persistenceState === "PERSISTED";
            updateActivityForRequest((prev) => ({
              ...prev,
              wikiVerification: Object.keys(verification).length ? verification : prev.wikiVerification,
              wikiBackgroundStatus:
                status === "COMPLETE"
                  ? ("complete" as const)
                  : persistenceOk
                    ? ("complete" as const)
                    : ("failed" as const),
              wikiUiMessage:
                status === "COMPLETE"
                  ? null
                  : persistenceOk
                    ? "The project knowledge was saved, but the Wiki panel did not refresh."
                    : "The Wiki update could not be saved.",
              // Always bump refresh so TOC/articles can catch verified writes (never blocks chat).
              wikiRefreshNonce: (prev.wikiRefreshNonce || 0) + 1,
            }));
          }
        } else if (event.type === "next_step_options") {
          const opts = Array.isArray(event.options)
            ? event.options.map((raw) => ({
                id: String(raw.id || ""),
                type: String(raw.type || "CONTINUE_STORY") as import("./types").CoDirectorNextStepType,
                label: String(raw.label || "Continue"),
                shortDescription: raw.shortDescription ?? null,
                whyNow: raw.whyNow ?? null,
                readiness: (raw.readiness as "AVAILABLE" | "PARTIAL" | "NOT_READY") || "AVAILABLE",
                ownershipRequired: Boolean(raw.ownershipRequired),
                priority: Number(raw.priority || 50),
                previewSpine: raw.previewSpine ?? null,
              }))
            : [];
          updateActivityForRequest((prev) => ({
            ...prev,
            nextStepOptions: opts.slice(0, 4),
            nextStepIntro: event.intro || "Where would you like to go next?",
          }));
        } else if (event.type === "momentum_resume") {
          updateActivityForRequest((prev) => ({
            ...prev,
            momentumResume: event.resume || prev.momentumResume,
            momentumSummary: event.resume || prev.momentumSummary,
          }));
        } else if (event.type === "creative_momentum") {
          const mom = event.momentum || {};
          updateActivityForRequest((prev) => ({
            ...prev,
            momentumSummary:
              String(mom.lastSessionSummary || prev.momentumSummary || "") || prev.momentumSummary,
          }));
        } else if (event.type === "creative_confidence") {
          updateActivityForRequest((prev) => ({
            ...prev,
            confidenceInsight: event.insight || prev.confidenceInsight,
          }));
        } else if (event.type === "conversation_timings") {
          updateActivityForRequest((prev) => ({
            ...prev,
            lastTimings: (event.timings as Record<string, unknown>) || prev.lastTimings,
          }));
        } else if (event.type === "what_changed") {
          updateActivityForRequest((prev) => ({
            ...prev,
            whatChanged: Array.isArray(event.lines) ? event.lines.map(String) : prev.whatChanged,
          }));
        } else if (event.type === "project_pulse") {
          updateActivityForRequest((prev) => ({
            ...prev,
            projectPulse: event.pulse || prev.projectPulse,
          }));
        } else if (event.type === "conversation_actions") {
          updateActivityForRequest((prev) => ({
            ...prev,
            conversationActions: Array.isArray(event.actions) ? event.actions : prev.conversationActions,
          }));
        } else if (event.type === "artifact_readiness") {
          updateActivityForRequest((prev) => ({
            ...prev,
            artifactReadiness: Array.isArray(event.assessments) ? event.assessments : prev.artifactReadiness,
          }));
        } else if (event.type === "deliverable") {
          updateActivityForRequest((prev) => ({
            ...prev,
            activeDeliverable: event.deliverable || prev.activeDeliverable,
          }));
        } else if (event.type === "vision_profile") {
          updateActivityForRequest((prev) => ({
            ...prev,
            visionProfile: event.vision || prev.visionProfile,
          }));
        } else if (event.type === "pitch_package") {
          updateActivityForRequest((prev) => ({
            ...prev,
            pitchPackage: event.pitch || prev.pitchPackage,
          }));
        } else if (event.type === "journey_state") {
          updateActivityForRequest((prev) => ({
            ...prev,
            journeyState: event.journey || prev.journeyState,
          }));
        } else if (event.type === "inference_trace") {
          updateActivityForRequest((prev) => ({
            ...prev,
            cognitiveMode: event.trace?.mode || prev.cognitiveMode,
            selectedModel: event.trace?.selected_model || prev.selectedModel,
            actualModel: event.trace?.actual_model || prev.actualModel,
            fallbackUsed: Boolean(event.trace?.fallback_used),
            toolsSummary:
              event.trace?.workflow_advance_policy === "HOLD"
                ? "None this turn"
                : prev.toolsSummary || "None this turn",
            summaryFacts: [
              ...(prev.summaryFacts || []),
              event.trace?.mode ? `Mode: ${event.trace.mode}` : "",
              event.trace?.primary_intent ? `Intent: ${event.trace.primary_intent}` : "",
              event.trace?.fallback_used
                ? "Used a safe fallback after the model reply could not be grounded."
                : "Replied with the selected model.",
            ].filter(Boolean),
          }));
        } else if (event.type === "token") {
          markResponseComposing();
          sawToken = true;
          // Contaminated stream may be replaced with a clean same-model retry.
          if (event.replace) {
            streamedText = event.content || "";
          } else {
            streamedText += event.content;
          }
          const snapshot = streamedText;
          setMessages((prev) => {
            const idx = prev.findIndex((m) => m.id === assistantId);
            if (idx === -1) {
              return [
                ...prev,
                {
                  id: assistantId,
                  role: "assistant",
                  content: snapshot,
                  createdAt: new Date().toISOString(),
                  status: "streaming",
                },
              ];
            }
            const next = [...prev];
            next[idx] = { ...next[idx], content: snapshot };
            return next;
          });
        } else if (event.type === "execution_status") {
          // Workstream H — honest execution state. Either update the streaming
          // assistant bubble in place (when the dispatch path streams) or insert
          // a dedicated execution_status message. The execution payload is
          // attached so CoDirectorMessage can render the compact progress card.
          const execPayload = (event.execution as unknown as CoDirectorMessageExecution | undefined) || undefined;
          const execMessageType = (event.messageType as CoDirectorAssistantMessageType | undefined) || "execution_status";
          const execContent = (event.content as string | undefined) || "";
          setMessages((prev) => {
            const existingIdx = prev.findIndex(
              (m) =>
                m.role === "assistant" &&
                m.id === `exec-${requestId}` &&
                (m.messageType === "execution_status" ||
                  m.messageType === "completion" ||
                  m.messageType === "error"),
            );
            const message: CoDirectorMessage = {
              id: `exec-${requestId}`,
              role: "assistant",
              content: execContent,
              createdAt: new Date().toISOString(),
              messageType: execMessageType,
              execution: execPayload,
            };
            if (existingIdx !== -1) {
              const next = [...prev];
              next[existingIdx] = { ...prev[existingIdx], ...message };
              return next;
            }
            return [...prev, message];
          });
          // Gap 3 fix — activate the Agent Work Surface in the right pane when
          // an execution_status event arrives with an execution_id. This switches
          // the right pane from normal tabs to the live work surface so the user
          // can see real execution progress (spec §18, §21, §24).
          //
          // PREVIEW guard: a `status: "preview"` event means the capability is
          // awaiting user confirmation (e.g. an APPROVAL_REQUIRED step). The
          // execution has NOT actually started — the chat surface shows the
          // confirmation question and we must NOT steal the right pane yet.
          // Once the user confirms, a new execution_status event with a
          // non-preview status (e.g. "queued") arrives and activates the
          // overlay. This also prevents a stale preview from overwriting a
          // legitimately active (non-preview) execution in `activeExecution`.
          if (execPayload?.execution_id && execPayload.status !== "preview") {
            executionCreated = true;
            const execProjectId = b.projectId || "";
            const surfaceType = (execPayload.surface_type as WorkSurfaceState["surface_type"]) || "";
            setActiveExecution({
              mode: "agent_work",
              execution_id: execPayload.execution_id,
              capability: execPayload.capability || "",
              surface_type: surfaceType,
              status: execPayload.status || "",
              progress: execPayload.progress || 0,
              focused_artifact_ids: execPayload.result_asset_ids || [],
              child_jobs: (execPayload.child_jobs || []).map((c) => ({
                job_id: c.job_id || "",
                label: c.label || `Item ${(c.child_index ?? 0) + 1}`,
                status: (c.status as WorkSurfaceState["child_jobs"][number]["status"]) || "queued",
                asset_id: c.asset_id ?? null,
                error: c.error ?? null,
                progress: c.progress || 0,
                stage: c.stage || "",
                child_index: c.child_index ?? 0,
                metadata: {},
              })),
              result_asset_ids: execPayload.result_asset_ids || [],
              collection_id: execPayload.collection_id ?? null,
              project_id: execProjectId,
            });
          }
        } else if (event.type === "completed") {
          updateActivityForRequest((prev) =>
            upsertStage(prev, {
              id: "response",
              eventType: "response_composing",
              label: "Composing a response",
              status: "completed",
            }),
          );
          outcome = "completed";
          streamedText = event.content || streamedText;
          finalModel = event.modelId;
          finalProviderId = event.providerId;
          sceneSetupResult = (event.sceneSetup as SceneSetup) || null;
          suggestedPromptResult = event.suggestedPrompt || null;
          if (event.messageId) {
            serverAssistantId = event.messageId;
          }
          if (event.responseType) {
            assistantMessageType = event.responseType as CoDirectorAssistantMessageType;
          }
        } else if (event.type === "intelligence_progress") {
          setIntelligenceProgress({ stage: event.stage, message: event.message || event.stage });
          if (event.promptVersions) {
            setProductionAnalysis((prev) => ({
              specialists: event.specialists || prev?.specialists || [],
              findingsSummaries: prev?.findingsSummaries || [],
              bibleSources: prev?.bibleSources || [],
              capabilities: prev?.capabilities || [],
              promptVersions: event.promptVersions || prev?.promptVersions || {},
              planSteps: prev?.planSteps || [],
              recommendation: prev?.recommendation,
            }));
          }
        } else if (event.type === "intelligence_result") {
          const synthesis = event.synthesis as Record<string, unknown>;
          const refs = (synthesis.productionBibleReferences as { entityType?: string; entityId?: string }[]) || [];
          const specialistIds = (synthesis.specialistIdsUsed as string[]) || [];
          setProductionAnalysis((prev) => ({
            specialists: specialistIds.length ? specialistIds : prev?.specialists || [],
            findingsSummaries: specialistIds.map((id) => ({
              specialistId: id,
              summary: String(synthesis.recommendation || "Contributed to the recommendation."),
            })),
            bibleSources: refs.map((r) => `${r.entityType || "entity"}:${r.entityId || "?"}`),
            capabilities: prev?.capabilities || [],
            promptVersions: event.promptVersions || prev?.promptVersions || {},
            planSteps: prev?.planSteps || [],
            recommendation: (synthesis.structuredRecommendation as Record<string, unknown>) || prev?.recommendation,
          }));
          if (typeof synthesis.responseType === "string") {
            assistantMessageType = synthesis.responseType as CoDirectorAssistantMessageType;
          }
        } else if (event.type === "intelligence_plan") {
          updateActivityForRequest((prev) =>
            upsertStage(prev, {
              id: "plan",
              eventType: "plan_review",
              label: "Reviewing the active plan",
              status: "completed",
            }),
          );
          const planPayload = event.plan as {
            title?: string;
            steps?: { title?: string; status?: string; id?: string }[];
            visualValidationPending?: boolean;
          };
          const steps = (planPayload.steps || []).map((step) => ({
            title: step.title || "Step",
            status: step.status || "pending",
          }));
          // CDX-088 (Phase 7): backend intelligence plans are authoritative —
          // the local plan state stays permanently null (planFromIntention /
          // RECIPE_STUBS and the runSteps executor were removed). No code path
          // may set plan to a non-null ActionPlan.
          setPlan(null);
          setProductionAnalysis((prev) =>
            prev
              ? {
                  ...prev,
                  planSteps: steps,
                  recommendation: {
                    ...(prev.recommendation || {}),
                    planTitle: planPayload.title || prev.recommendation?.planTitle,
                    visualValidationPending: Boolean(planPayload.visualValidationPending),
                  },
                }
              : {
                  specialists: [],
                  findingsSummaries: [],
                  bibleSources: [],
                  capabilities: [],
                  promptVersions: {},
                  planSteps: steps,
                  recommendation: {
                    planTitle: planPayload.title,
                    visualValidationPending: Boolean(planPayload.visualValidationPending),
                  },
                },
          );
        } else if (event.type === "intelligence_proposal") {
          setProposals((prev) => [event.proposal, ...prev.filter((p) => p.id !== event.proposal.id)]);
          setIntelligenceProgress({ stage: "creating_proposals", message: "Ready for approval" });
        } else if (event.type === "cancelled") {
          updateActivityForRequest((prev) => ({
            ...prev,
            status: "cancelled",
            completedAt: new Date().toISOString(),
          }));
          outcome = "cancelled";
        } else if (event.type === "proposal_created" || event.type === "tool_proposal_created") {
          setProposals((prev) => [event.proposal, ...prev.filter((p) => p.id !== event.proposal.id)]);
          if (event.type === "tool_proposal_created") setToolActivity(null);
        } else if (event.type === "tool_requested") {
          setToolActivity({ toolId: event.toolId, title: event.toolId, phase: "requested" });
          updateActivityForRequest((prev) => applyToolEvent(prev, event.toolId, "started"));
          if (event.kind === "read") {
            // The tokens streamed so far were the model asking for a lookup, not an answer. The
            // server withholds `completed` for that turn and re-asks with the result, so the
            // partial request text is discarded here and the status line stands in its place.
            streamedText = "";
            setMessages((prev) => prev.filter((m) => m.id !== assistantId));
          }
        } else if (event.type === "tool_started") {
          setToolActivity({ toolId: event.toolId, title: event.title, phase: "running" });
          updateActivityForRequest((prev) => applyToolEvent(prev, event.toolId, "started"));
        } else if (event.type === "tool_completed") {
          setLastSuccessfulToolAction(event.toolId);
          updateActivityForRequest((prev) => applyToolEvent(prev, event.toolId, "completed"));
          setToolActivity((prev) => ({
            toolId: event.toolId,
            title: prev?.title || event.toolId,
            phase: "completed",
            truncated: prev?.truncated || event.invocation.resultTruncated,
          }));
          const result = (event.invocation?.result || {}) as Record<string, unknown>;
          pendingToolRetryRef.current = null;
          syncProjectIdentityFromResult(result);
          const uiAction = String(result.uiAction || "");
          if (uiAction === "open_voice_performance" || uiAction === "open_voice_creator") {
            const characterId = String(result.characterId || "");
            const workspaceUrl = String(result.workspaceUrl || "");
            if (workspaceUrl) {
              navigate(workspaceUrl);
            } else {
              try {
                bindingsRef.current.onGoTab?.("characters");
              } catch {
                /* tab binding optional */
              }
              window.dispatchEvent(
                new CustomEvent("adept:open-character-voice", {
                  detail: {
                    tab: uiAction === "open_voice_performance" ? "voicePerformance" : "voice",
                    characterId,
                  },
                }),
              );
            }
          }
          if (uiAction === "open_audio_studio") {
            try {
              bindingsRef.current.onGoTab?.("audiostudio");
            } catch {
              /* tab binding optional */
            }
          }
          if (uiAction === "open_scriptwriter") {
            const workspaceUrl = String(result.workspaceUrl || "");
            if (workspaceUrl) {
              navigate(workspaceUrl);
            } else {
              try {
                bindingsRef.current.onGoTab?.("scriptwriter");
              } catch {
                /* tab binding optional */
              }
            }
          }
          const uiFocus = (result._uiFocus || result.uiFocus) as Record<string, unknown> | undefined;
          if (uiFocus && typeof uiFocus === "object" && uiFocus.target) {
            try {
              bindingsRef.current.onGoTab?.("timeline");
            } catch {
              /* tab binding optional */
            }
            window.dispatchEvent(
              new CustomEvent("adept-timeline-focus", {
                detail: uiFocus,
              }),
            );
          }
          const operator = result.operator as
            | { requestId?: string; originSessionId?: string; toolId?: string }
            | undefined;
          if (operator?.requestId) {
            const operatorRequestId = operator.requestId;
            const operatorToolId = operator.toolId || event.toolId;
            let operatorWorkspace = "";
            let operatorTarget = "";
            let operatorVerified = false;
            if (uiAction === "open_voice_performance" || uiAction === "open_voice_creator") {
              operatorWorkspace = "voicestudio";
              operatorTarget = "voice";
              operatorVerified = true;
            } else if (uiAction === "open_audio_studio") {
              operatorWorkspace = "audiostudio";
              operatorTarget = "audio";
              operatorVerified = true;
            } else if (uiFocus && typeof uiFocus === "object" && uiFocus.target) {
              operatorWorkspace = "timeline";
              operatorTarget = String(uiFocus.target);
              operatorVerified = true;
            }
            setToolActivity({ toolId: event.toolId, title: operatorToolId, phase: "operator_pending" });
            let ackSent = false;
            const ackTimer = window.setTimeout(() => {
              if (ackSent) return;
              setToolActivity((prev) => (prev ? { ...prev, phase: "operator_timeout" } : prev));
            }, 3000);
            const confirmAndAck = () => {
              if (ackSent) return;
              ackSent = true;
              window.clearTimeout(ackTimer);
              void api
                .codirectorOperatorAck(operatorRequestId, {
                  originSessionId: operator.originSessionId || getTabSessionId(),
                  workspace: operatorWorkspace,
                  target: operatorTarget || undefined,
                  verified: operatorVerified,
                })
                .catch(() => {
                  // fire-and-forget: an ack failure must never break the chat stream
                });
              setToolActivity((prev) => (prev ? { ...prev, phase: "completed", title: operatorToolId } : prev));
            };
            // The navigation above ran synchronously; defer the ack one tick so the pending badge paints.
            window.setTimeout(confirmAndAck, 0);
          }
        } else if (event.type === "tool_result_truncated") {
          setToolActivity((prev) => (prev ? { ...prev, truncated: true } : prev));
        } else if (event.type === "tool_failed" || event.type === "capability_blocked") {
          const classified = classifyCoDirectorError(
            new ApiError(event.error.message || "Co-Director could not finish that action.", 0, {
              code: event.error.code,
              details: event.error.details,
              recoverable: event.error.recoverable,
              recommendedAction: event.error.recommendedAction,
            }),
          );
          updateActivityForRequest((prev) => applyToolEvent(prev, event.toolId, "failed", classified.message));
          setToolActivity((prev) => ({
            toolId: event.toolId,
            title: prev?.title || event.toolId,
            phase: event.type === "capability_blocked" ? "blocked" : "failed",
            detail: classified.message,
          }));
          if (event.arguments && (event.kind === "read" || event.kind === "mutating")) {
            pendingToolRetryRef.current = {
              kind: event.kind,
              toolId: String(event.toolId || ""),
              arguments: event.arguments as Record<string, unknown>,
            };
            if (outcome !== "completed") {
              classifiedError = classified;
            } else {
              postCompletionError = classified;
            }
          }
        } else if (event.type === "error") {
          const classified = classifyCoDirectorError(
            new ApiError(event.error.message || "Co-Director returned an error.", 0, {
              code: event.error.code,
              details: event.error.details,
              recoverable: event.error.recoverable,
              recommendedAction: event.error.recommendedAction,
            }),
          );
          if (outcome === "completed") {
            postCompletionError = classified;
          } else {
            outcome = "error";
            classifiedError = classified;
          }
        }
      };

      const dropEmptyStreamingBubble = () => {
        setMessages((prev) => prev.filter((m) => !(m.id === assistantId && m.status === "streaming" && !m.content)));
      };

      const finalizeCompleted = async () => {
        const finalText = streamedText;
        // Wave A persistent memory: adopt the server-assigned assistant message
        // id when present so the local bubble and the server event share an id.
        const finalMessageId = serverAssistantId || assistantId;
        const finalMessage = {
          id: finalMessageId,
          role: "assistant" as const,
          content: finalText,
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => {
          // Replace the streaming bubble (assistantId) with the finalized
          // message (finalMessageId). If they differ, drop the old bubble and
          // append the finalized one so reconciliation by id stays clean.
          if (finalMessageId !== assistantId) {
            const withoutStreaming = prev.filter((m) => m.id !== assistantId);
            return [...withoutStreaming, { ...finalMessage, messageType: assistantMessageType }];
          }
          const idx = prev.findIndex((m) => m.id === assistantId);
          const finished: CoDirectorMessage = {
            ...finalMessage,
            messageType: assistantMessageType,
          };
          if (idx === -1) return [...prev, finished];
          const next = [...prev];
          next[idx] = finished;
          return next;
        });
        if (sceneSetupResult) setSetup(sceneSetupResult);
        else if (suggestedPromptResult) setSuggestedPrompt(suggestedPromptResult);
        setProviderModel(finalModel ?? null);
        pendingRetryRef.current = null;
        const transcriptWithAssistant = [...transcriptForApi, finalMessage];
        activityPersistenceRef.current = {
          messages: transcriptWithAssistant,
          model: finalModel,
          providerId: finalProviderId,
        };
        updateActivityForRequest((prev) =>
          upsertStage(prev, {
            id: "persistence",
            eventType: "persistence_started",
            label: "Saving this conversation",
            status: "active",
          }),
        );
        // The server already appended the assistant reply event during stream
        // completion. The client only RECONCILES by id (GET + merge) — it must
        // NOT POST a full replacement transcript (deprecated, can truncate).
        const persistence = await reconcileConversation();
        updateActivityForRequest((prev) => {
          const next = upsertStage(prev, {
            id: "persistence",
            eventType: persistence.ok ? "persistence_completed" : "persistence_started",
            label: "Saving this conversation",
            status: persistence.ok ? "completed" : "failed",
            detail: persistence.ok ? undefined : persistence.message || undefined,
          });
          const summaryFacts = summarizeActivity({
            uiContext,
            manifest: activityManifestRef.current,
            attachmentsCount: next.attachmentsCount,
            stages: next.stages,
          });
          return {
            ...next,
            status: persistence.ok ? "completed" : "failed",
            completedAt: new Date().toISOString(),
            persistenceError: persistence.ok ? null : persistence.message,
            summaryFacts:
              summaryFacts.length > 0
                ? summaryFacts
                : ["Co-Director responded from the current conversation without changing project records."],
          };
        });
        if (b.projectId) {
          window.dispatchEvent(
            new CustomEvent("adept:codirector-plan-workspace-refresh", {
              detail: { projectId: b.projectId, requestId },
            }),
          );
        }
      };

      try {
        await api.codirectorChatStream(
          {
            messages: apiMessages,
            project_id: b.projectId,
            scene_id: b.sceneId,
            model: selectedModelId || undefined,
            mode,
            request_id: requestId,
            origin_session_id: getTabSessionId(),
            conversationLocale: languagePrefs.conversationLocale,
            attachment_ids: turnAttachmentIds.length ? turnAttachmentIds : undefined,
            active_content_tab: activeContentTabRef.current || undefined,
          },
          { signal: controller.signal, onEvent },
        );

        if (!mountedRef.current) {
          // Component unmounted mid-stream. The server already appended the
          // assistant reply event during stream completion (Wave A persistent
          // memory), so durability is guaranteed without a client persist.
          return;
        }

        if (outcome === "completed") {
          setIntelligenceProgress(null);
          await finalizeCompleted();
          if (postCompletionError) setSendError(postCompletionError);
        } else if (outcome === "cancelled") {
          setMessages((prev) =>
            prev
              .map((m) => (m.id === assistantId ? { ...m, status: "cancelled" as const } : m))
              .filter((m) => !(m.id === assistantId && !m.content)),
          );
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "cancelled",
                  completedAt: new Date().toISOString(),
                  summaryFacts: ["Co-Director stopped before replying."],
                }
              : prev,
          );
          void reconcileConversation();
        } else if (outcome === "error" && classifiedError) {
          dropEmptyStreamingBubble();
          setSendError(classifiedError);
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "failed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: ["Co-Director could not finish the reply."],
                }
              : prev,
          );
          void reconcileConversation();
        } else if (sawToken && executionCreated) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    status: "interrupted" as const,
                    content:
                      m.content +
                      "\n\n*Co-Director's response was interrupted, but your generation is still running.*",
                  }
                : m,
            ),
          );
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "completed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: [
                    "Co-Director's message was interrupted, but your generation is still running.",
                  ],
                }
              : prev,
          );
          void reconcileConversation();
        } else if (sawToken) {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, status: "interrupted" as const } : m)));
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "failed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: ["Co-Director started a reply, but the response was interrupted."],
                }
              : prev,
          );
          void reconcileConversation();
        } else if (executionCreated) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    status: "interrupted" as const,
                    content:
                      m.content ||
                      "*Co-Director's response was interrupted, but your generation is still running.*",
                  }
                : m,
            ),
          );
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "completed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: [
                    "Co-Director's message was interrupted, but your generation is still running.",
                  ],
                }
              : prev,
          );
          void reconcileConversation();
        } else {
          dropEmptyStreamingBubble();
          setSendError(classifyCoDirectorError(new Error("The response ended unexpectedly.")));
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "failed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: ["Co-Director could not finish the reply."],
                }
              : prev,
          );
          void reconcileConversation();
        }
      } catch (err) {
        if (isAbortError(err)) {
          const wasUserCancel = cancelledByUserRef.current;
          if (!mountedRef.current) return;
          setMessages((prev) =>
            prev
              .map((m) =>
                m.id === assistantId
                  ? { ...m, status: wasUserCancel ? ("cancelled" as const) : ("interrupted" as const) }
                  : m,
              )
              .filter((m) => !(m.id === assistantId && !m.content)),
          );
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: wasUserCancel ? "cancelled" : "failed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: [
                    wasUserCancel
                      ? "Co-Director stopped before finishing the reply."
                      : "Co-Director was interrupted before finishing the reply.",
                  ],
                }
              : prev,
          );
          void reconcileConversation();
          return;
        }

        // The stream transport itself failed before completing (network error, non-2xx
        // response, or a backend that doesn't support SSE) — fall back to the non-streaming
        // endpoint once before surfacing a classified error.
        if (!mountedRef.current) return;
        dropEmptyStreamingBubble();
        try {
          const res = await api.codirectorChat(
            {
              messages: apiMessages,
              project_id: b.projectId,
              scene_id: b.sceneId,
              model: selectedModelId || undefined,
              mode,
              request_id: requestId,
              conversationLocale: languagePrefs.conversationLocale,
              attachment_ids: turnAttachmentIds.length ? turnAttachmentIds : undefined,
              active_content_tab: activeContentTabRef.current || undefined,
            },
            { signal: controller.signal },
          );
          const assistantMsg: CoDirectorMessage = {
            id: `asst-${requestId}`,
            role: "assistant",
            content: res.reply,
            createdAt: new Date().toISOString(),
          };
          setMessages((prev) => {
            // Drop the streaming bubble if present, then append the finalized
            // assistant message with the server-assigned id so reconcile by
            // id cannot duplicate.
            const withoutStreaming = prev.filter((m) => m.id !== assistantId);
            return [...withoutStreaming, assistantMsg];
          });
          if (res.sceneSetup) setSetup(res.sceneSetup as SceneSetup);
          else if (res.suggestedPrompt) setSuggestedPrompt(res.suggestedPrompt);
          pendingRetryRef.current = null;
          setProviderModel(res.model);
          const transcriptWithAssistant = [...transcriptForApi, assistantMsg];
          activityPersistenceRef.current = {
            messages: transcriptWithAssistant,
            model: res.model,
            providerId: res.providerId,
          };
          setActivity((prev) => {
            if (!prev || prev.requestId !== requestId) return prev;
            const withResponse = upsertStage(
              updateStage(prev, "request", { status: "completed" }),
              {
                id: "response",
                eventType: "response_composing",
                label: "Composing a response",
                status: "completed",
              },
            );
            return upsertStage(withResponse, {
              id: "persistence",
              eventType: "persistence_started",
              label: "Saving this conversation",
              status: "active",
            });
          });
          // Server already appended the assistant reply in chat_for_project;
          // the client only reconciles by id (no full-replace POST).
          const persistence = await reconcileConversation();
          setActivity((prev) => {
            if (!prev || prev.requestId !== requestId) return prev;
            const next = upsertStage(prev, {
              id: "persistence",
              eventType: persistence.ok ? "persistence_completed" : "persistence_started",
              label: "Saving this conversation",
              status: persistence.ok ? "completed" : "failed",
              detail: persistence.ok ? undefined : persistence.message || undefined,
            });
            const summaryFacts = summarizeActivity({
              uiContext,
              manifest: activityManifestRef.current,
              attachmentsCount: next.attachmentsCount,
              stages: next.stages,
            });
            return {
              ...next,
              status: persistence.ok ? "completed" : "failed",
              completedAt: new Date().toISOString(),
              persistenceError: persistence.ok ? null : persistence.message,
              summaryFacts:
                summaryFacts.length > 0
                  ? summaryFacts
                  : ["Co-Director responded from the current conversation without changing project records."],
            };
          });
        } catch (err2) {
          if (isAbortError(err2)) return;
          const classified = classifyCoDirectorError(err2);
          setSendError(classified);
          setActivity((prev) =>
            prev && prev.requestId === requestId
              ? {
                  ...prev,
                  status: "failed",
                  completedAt: new Date().toISOString(),
                  summaryFacts: ["Co-Director could not finish the reply."],
                }
              : prev,
          );
          void reconcileConversation();
        }
      } finally {
        sendInFlightRef.current = false;
        setBusy(false);
        if (activeRequestIdRef.current === requestId) activeRequestIdRef.current = null;
        if (abortControllerRef.current === controller) abortControllerRef.current = null;
        if (b.projectId) markStreamingEnd(b.projectId);
        cancelledByUserRef.current = false;
      }
    },
    [persistConversation, reconcileConversation, selectedModelId, uiContext, languagePrefs],
  );

  const uploadPendingAttachments = useCallback(
    async (pending: CoDirectorAttachment[], projectId: string, signal: AbortSignal): Promise<CoDirectorAttachment[]> => {
      const uploaded: CoDirectorAttachment[] = [];
      const seen = new Set<string>();
      for (const attachment of pending) {
        throwIfAborted(signal);
        if (attachment.assetId) {
          if (!seen.has(attachment.assetId)) {
            uploaded.push(attachment);
            seen.add(attachment.assetId);
          }
          continue;
        }
        if (attachment.kind !== "file" || !attachment.file) continue;
        const mediaKind = attachment.mediaKind || inferAttachmentMediaKind(attachment.name, attachment.mimeType);
        const asset = await api.uploadAsset(
          projectId,
          attachment.file,
          buildAttachmentTag(attachment.name),
          mediaKind,
          { signal },
        );
        const assetId = String(asset.id || "").trim();
        if (!assetId) {
          throw new Error("Co-Director could not keep track of the uploaded attachment.");
        }
        const resolved: CoDirectorAttachment = {
          ...attachment,
          assetId,
          mediaKind: asset.kind || mediaKind,
        };
        setAttachments((prev) =>
          prev.map((item) => (item.id === attachment.id ? { ...item, assetId, mediaKind: resolved.mediaKind } : item)),
        );
        if (!seen.has(assetId)) {
          uploaded.push(resolved);
          seen.add(assetId);
        }
      }
      return uploaded;
    },
    [],
  );

  const send = useCallback(
    async (text?: string, mode: ChatMode = "chat") => {
      const trimmed = (text ?? draft).trim();
      if ((!trimmed && !attachments.length) || busy) return;
      pendingToolRetryRef.current = null;
      setSendError(null);
      setBusy(true);

      // Preflight: never let a bare `TypeError: Failed to fetch` reach the transcript.
      // Block the send (message stays in the transcript) if the gateway or model isn't ready.
      let health: ProviderHealth;
      try {
        health = await api.codirectorHealth("active");
        setProviderHealth(health);
        setProviderModel(health.selectedModel);
        setProviderStatus(
          health.status === "Ready" ? `${health.displayName} · ${health.selectedModel}` : health.status,
        );
      } catch (err) {
        setSendError(classifyCoDirectorError(err));
        setBusy(false);
        return;
      }
      if (!health.reachable || !health.modelAvailable) {
        setSendError({
          code: health.code || (health.reachable ? "MODEL_NOT_SELECTED" : "PROVIDER_UNAVAILABLE"),
          message:
            health.message ||
            "Co-Director's local model isn't ready yet. Open Options to pick a model, then retry.",
          recommendedAction: health.recommendedAction || "select_model",
          recoverable: true,
        });
        setBusy(false);
        return;
      }

      const projectId = bindingsRef.current.projectId;
      const needsUpload = attachments.some((item) => item.kind === "file" && !item.assetId);
      if (needsUpload && !projectId) {
        setSendError({
          code: "PROJECT_REQUIRED",
          message: "Select a project before attaching local files so Co-Director can store them in the project Library.",
          recommendedAction: "select_project",
          recoverable: true,
          category: "project",
          retryable: true,
          partial_work_created: false,
        });
        setBusy(false);
        return;
      }

      const wantsPlan =
        /build|create|prepare|plan|dialogue|storyboard|lip.?sync|master sheet|coverage|generate|workflow|assemble|editor|director sequence/i.test(
          trimmed,
        ) && mode !== "setup";

      // M41 Wave 1: never invent a local offline plan as production success.
      // Backend intelligence plans are authoritative; when unavailable, fail honestly.
      const intelligenceOn = Boolean(health.intelligenceEnabled);
      if (wantsPlan && !intelligenceOn) {
        setSendError({
          code: "PLAN_UNAVAILABLE",
          message:
            "Production planning is unavailable because Co-Director intelligence is off. Enable intelligence or continue with general chat.",
          recommendedAction: "retry_or_check_service",
          recoverable: true,
          category: "runtime",
          retryable: true,
          partial_work_created: false,
        });
        setBusy(false);
        return;
      }
      if (intelligenceOn) {
        setPlan(null);
      }

      const preflightController = new AbortController();
      abortControllerRef.current = preflightController;
      cancelledByUserRef.current = false;
      let resolvedAttachments: CoDirectorAttachment[] = [];
      try {
        resolvedAttachments =
          projectId && attachments.length
            ? await uploadPendingAttachments(attachments, projectId, preflightController.signal)
            : attachments.filter((item) => item.kind === "library" && item.assetId);
        throwIfAborted(preflightController.signal);
      } catch (err) {
        if (abortControllerRef.current === preflightController) abortControllerRef.current = null;
        if (isAbortError(err)) {
          if (cancelledByUserRef.current) clearComposerAttachments();
          cancelledByUserRef.current = false;
          setBusy(false);
          return;
        }
        setSendError(classifyCoDirectorError(err));
        setBusy(false);
        return;
      }
      if (abortControllerRef.current === preflightController) abortControllerRef.current = null;

      // Append the user's message only after file uploads have real asset ids.
      const attachmentNote = resolvedAttachments.length
        ? `\n\n[Attached: ${resolvedAttachments.map((a) => a.name).join(", ")}]`
        : "";
      const content = `${trimmed}${attachmentNote}`.trim();
      const userMsg: CoDirectorMessage = {
        id: newMessageId(),
        role: "user",
        content,
        attachmentIds: resolvedAttachments.map((a) => a.assetId).filter((value): value is string => Boolean(value)),
        attachments: toMessageAttachments(resolvedAttachments),
        createdAt: new Date().toISOString(),
      };
      const next = [...messages, userMsg];
      setMessages(next);
      setDraftState("");
      clearComposerAttachments();
      const requestId = newMessageId();
      // Wave A persistent memory: append the user turn as a single idempotent
      // event (keyed on requestId) so a reload mid-flight still shows the
      // question. The server owns durability; the client never replaces the
      // authoritative transcript.
      void appendUserTurn(userMsg, requestId);
      pendingRetryRef.current = { text: trimmed, mode, messageId: userMsg.id };
      activityManifestRef.current = null;
      activityPersistenceRef.current = null;
      setActivity(
        createActivityState({
          requestId,
          hasProject: Boolean(bindingsRef.current.projectId),
          hasContext: Boolean(
            includeProjectKnowledge &&
              (bindingsRef.current.projectId || bindingsRef.current.sceneId || bindingsRef.current.workspaceTab),
          ),
          attachmentsCount: attachments.length,
        }),
      );

      await performSend(next, mode, requestId);
    },
    [
      appendUserTurn,
      attachments,
      busy,
      clearComposerAttachments,
      draft,
      messages,
      performSend,
      selectedModelId,
      uploadPendingAttachments,
    ],
  );

  const retryLastSend = useCallback(() => {
    const pendingTool = pendingToolRetryRef.current;
    const projectId = bindingsRef.current.projectId;
    if (pendingTool && projectId && !busy) {
      setSendError(null);
      setBusy(true);
      void (async () => {
        try {
          if (pendingTool.kind === "read") {
            const invocation = await api.runCoDirectorReadTool(projectId, {
              toolId: pendingTool.toolId,
              arguments: pendingTool.arguments,
              requestId: `retry-${pendingTool.toolId}-${Date.now()}`,
            });
            setToolActivity({
              toolId: pendingTool.toolId,
              title: pendingTool.toolId,
              phase: "completed",
              truncated: invocation.resultTruncated,
            });
            const result = (invocation.result || {}) as Record<string, unknown>;
            syncProjectIdentityFromResult(result);
            setMessages((prev) => [
              ...prev,
              {
                id: newMessageId(),
                role: "assistant",
                content: "I retried that lookup successfully.",
                createdAt: new Date().toISOString(),
              },
            ]);
          } else {
            const proposal = await api.proposeCoDirectorToolCall(projectId, {
              toolId: pendingTool.toolId,
              arguments: pendingTool.arguments,
              requestId: `retry-${pendingTool.toolId}-${Date.now()}`,
              createdBy: "user",
            });
            setProposals((prev) => [proposal, ...prev.filter((item) => item.id !== proposal.id)]);
            setMessages((prev) => [
              ...prev,
              {
                id: newMessageId(),
                role: "assistant",
                content: "I retried that change. It is ready for approval.",
                createdAt: new Date().toISOString(),
              },
            ]);
          }
          pendingToolRetryRef.current = null;
        } catch (err) {
          setSendError(classifyCoDirectorError(err));
        } finally {
          setBusy(false);
        }
      })();
      return;
    }
    const pending = pendingRetryRef.current;
    if (!pending || busy) return;
    setSendError(null);
    if (!pending.messageId) {
      // Never got far enough to append a user message (preflight failure) — safe to
      // go through `send()` again, which will append it.
      void send(pending.text, pending.mode);
      return;
    }
    // The user's message is already in the transcript from the failed attempt — resend the
    // same transcript slice instead of appending a second copy of it.
    const idx = messages.findIndex((m) => m.id === pending.messageId);
    const transcript = idx >= 0 ? messages.slice(0, idx + 1) : messages;
    void performSend(transcript, pending.mode);
  }, [busy, messages, performSend, send, syncProjectIdentityFromResult]);

  const cancelSend = useCallback(() => {
    const requestId = activeRequestIdRef.current;
    cancelledByUserRef.current = true;
    if (requestId) void api.codirectorCancel(requestId).catch(() => {});
    abortControllerRef.current?.abort();
  }, []);

  // Seed prompt send when openSession was called with prompt from launchers that expect auto-send.
  const seedSendRef = useRef<string | null>(null);
  const openSessionWithOptionalSend = useCallback(
    (opts?: { prompt?: string; mode?: CoDirectorDisplayMode; autoSend?: boolean }) => {
      openSession(opts);
      if (opts?.prompt && opts.autoSend) {
        seedSendRef.current = opts.prompt;
      }
    },
    [openSession],
  );

  useEffect(() => {
    if (!seedSendRef.current || busy) return;
    const prompt = seedSendRef.current;
    seedSendRef.current = null;
    void send(prompt, "chat");
  }, [busy, open, send]);

  const applySetup = useCallback(async () => {
    const b = bindingsRef.current;
    if (!setup || !b.projectId || !b.sceneId || applying) return;
    setApplying(true);
    setApplyNote(null);
    try {
      const res = await api.assistantApplySetup({
        project_id: b.projectId,
        scene_id: b.sceneId,
        setup,
      });
      const note =
        (res.applied.length ? `Applied: ${res.applied.join(", ")}` : "Nothing changed") +
        (res.warnings.length ? `\nWarnings: ${res.warnings.join("; ")}` : "");
      setApplyNote(note);
      setMessages((m) => [
        ...m,
        { id: newMessageId(), role: "assistant", content: note, createdAt: new Date().toISOString() },
      ]);
      setSetup(null);
      await b.onAppliedSetup?.();
    } catch (err) {
      setApplyNote(err instanceof Error ? err.message : String(err));
    } finally {
      setApplying(false);
    }
  }, [applying, setup]);

  const approveProposal = useCallback(
    async (proposalId: string) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId || proposalActingId) return;
      setProposalActingId(proposalId);
      const approved = proposals.find((p) => p.id === proposalId) ?? null;
      const isTool = approved?.proposalType === "tool_call";
      try {
        const receipt = await api.approveProposal(projectId, proposalId);
        const toolResult =
          receipt.toolResult && typeof receipt.toolResult === "object"
            ? (receipt.toolResult as Record<string, unknown>)
            : null;
        if (toolResult) syncProjectIdentityFromResult(toolResult);
        setMessages((m) => [
          ...m,
          {
            id: newMessageId(),
            role: "assistant",
            content:
              toolResult?.confirmation && typeof toolResult.confirmation === "string"
                ? toolResult.confirmation
                : receipt.toolId || isTool
                  ? `Approved — I applied “${approved?.title || receipt.toolId}”.`
                : "Proposal approved and applied — a new Production Bible version was created.",
            createdAt: new Date().toISOString(),
          },
        ]);
        // c5: any tool proposal that mutates native project/scene/character/timeline/voice
        // state should notify the active workspace to refresh without requiring a manual reload.
        if (projectId && isTool) {
          window.dispatchEvent(
            new CustomEvent("adept:codirector-project-mutated", {
              detail: { projectId, proposalId, toolId: receipt.toolId },
            }),
          );
          // Legacy plan-workspace refresh: keep emitting the old event name for production_plan.*
          // tools until the Plan workspace migrates to the generic event.
          if (String(receipt.toolId || "").startsWith("production_plan.")) {
            window.dispatchEvent(
              new CustomEvent("adept:codirector-plan-workspace-refresh", {
                detail: { projectId, proposalId, toolId: receipt.toolId },
              }),
            );
          }
        }
      } catch (err) {
        const classified = classifyCoDirectorError(err);
        setMessages((m) => [
          ...m,
          {
            id: newMessageId(),
            role: "assistant",
            content:
              classified.code === "PROPOSAL_STALE"
                ? isTool
                  ? "That action is out of date because the project changed since it was proposed. Cancel it and ask again."
                  : "That proposal is out of date because the Bible changed since it was created. Cancel it and ask again."
                : `Couldn't approve that proposal: ${classified.message}`,
            createdAt: new Date().toISOString(),
          },
        ]);
      } finally {
        setProposalActingId(null);
        await refreshProposals();
      }
    },
    [proposalActingId, proposals, refreshProposals, syncProjectIdentityFromResult],
  );

  const rejectProposal = useCallback(
    async (proposalId: string, note?: string) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId || proposalActingId) return;
      setProposalActingId(proposalId);
      try {
        await api.rejectProposal(projectId, proposalId, { note });
      } catch {
        /* best-effort */
      } finally {
        setProposalActingId(null);
        await refreshProposals();
      }
    },
    [proposalActingId, refreshProposals],
  );

  const requestProposalRevision = useCallback(
    async (proposalId: string, note?: string) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId || proposalActingId) return;
      setProposalActingId(proposalId);
      try {
        await api.requestProposalRevision(projectId, proposalId, { note });
      } catch {
        /* best-effort */
      } finally {
        setProposalActingId(null);
        await refreshProposals();
      }
    },
    [proposalActingId, refreshProposals],
  );

  const cancelProposal = useCallback(
    async (proposalId: string) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId || proposalActingId) return;
      setProposalActingId(proposalId);
      try {
        await api.cancelProposal(projectId, proposalId);
      } catch {
        /* best-effort */
      } finally {
        setProposalActingId(null);
        await refreshProposals();
      }
    },
    [proposalActingId, refreshProposals],
  );

  const compilePrompt = useCallback(async () => {
    setBusy(true);
    try {
      const b = bindingsRef.current;
      const pkg = await api.compilePrompt({
        intention: draft.trim() || "Compile prompt for current scene",
        model_id: "ltx_2_3",
        mode: promptMode,
        project_id: includeProjectKnowledge ? b.projectId : undefined,
        scene_id: includeProjectKnowledge ? b.sceneId : undefined,
        projectContext: {
          sourceLanguage:
            languagePrefs.promptLanguagePolicy === "project_canonical"
              ? languagePrefs.projectPrimaryLocale
              : languagePrefs.conversationLocale,
          promptLanguagePolicy: languagePrefs.promptLanguagePolicy,
          projectPrimaryLocale: languagePrefs.projectPrimaryLocale,
        },
      });
      setCompileExplain(pkg.explain || []);
      setSuggestedPrompt(pkg.prompt || null);
      try {
        const raw = localStorage.getItem(PROMPT_VERSIONS_KEY);
        const list = raw ? JSON.parse(raw) : [];
        list.unshift({ ...pkg, saved_at: new Date().toISOString() });
        localStorage.setItem(PROMPT_VERSIONS_KEY, JSON.stringify(list.slice(0, 40)));
      } catch {
        /* ignore */
      }
      setMessages((m) => [
        ...m,
        {
          id: newMessageId(),
          role: "assistant",
          content: `Compiled ${pkg.model_id} package (${pkg.knowledge_version}). Validation: ${
            pkg.validation?.ok ? "ok" : (pkg.validation?.issues || []).join("; ")
          }`,
          createdAt: new Date().toISOString(),
        },
      ]);
      setOverflowPanel("none");
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: newMessageId(),
          role: "assistant",
          content: `Compile failed: ${e instanceof Error ? e.message : String(e)}`,
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setBusy(false);
    }
  }, [draft, includeProjectKnowledge, promptMode, languagePrefs]);

  const addFiles = useCallback((files: FileList | File[]) => {
    const list = Array.from(files);
    setAttachments((prev) => [
      ...prev,
      ...list.map((file) => ({
        id: newAttachmentId(),
        kind: "file" as const,
        name: file.name,
        mimeType: file.type,
        mediaKind: inferAttachmentMediaKind(file.name, file.type),
        previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : undefined,
        file,
      })),
    ]);
  }, []);

  const addLibraryAssets = useCallback(
    (assets: { id: string; name: string; mimeType?: string; previewUrl?: string }[]) => {
      setAttachments((prev) => {
        const existing = new Set(prev.map((a) => a.assetId).filter(Boolean));
        const next = assets
          .filter((a) => !existing.has(a.id))
          .map((a) => ({
            id: newAttachmentId(),
            kind: "library" as const,
            name: a.name,
            mimeType: a.mimeType,
            mediaKind: inferAttachmentMediaKind(a.name, a.mimeType),
            previewUrl: a.previewUrl,
            assetId: a.id,
          }));
        return [...prev, ...next];
      });
      setAssetPickerOpen(false);
    },
    [],
  );

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => {
      const target = prev.find((a) => a.id === id);
      if (target) revokeFilePreview(target);
      return prev.filter((a) => a.id !== id);
    });
  }, []);

  const appendTranscript = useCallback((text: string) => {
    setDraftState((prev) => {
      const sep = prev && !prev.endsWith(" ") && !prev.endsWith("\n") ? " " : "";
      return `${prev}${sep}${text}`;
    });
  }, []);

  const setPolicies = useCallback((next: Record<ActionCategory, PermissionPolicy>) => {
    setPoliciesState(next);
    savePolicies(next);
  }, []);

  const loadKnowledge = useCallback(async () => {
    try {
      const models = await api.knowledgebaseModels();
      setKbModels(models || []);
    } catch {
      setKbModels([]);
    }
  }, []);

  const loadKnowledgeDoc = useCallback(async (modelId: string) => {
    try {
      const d = await api.knowledgebaseDoc(`video_models/${modelId}/overview.md`);
      setKbDoc(d.content.slice(0, 1200));
    } catch {
      setKbDoc("Doc missing");
    }
  }, []);

  const loadStatus = useCallback(async () => {
    try {
      const [latest, history] = await Promise.all([
        fetchLatestStatus(uiContext.projectId, uiContext.sceneId),
        fetchStatusHistory(uiContext.projectId, uiContext.sceneId, 20),
      ]);
      setStatusLatestRun(latest);
      setStatusHistory(history);
      setStatusError(null);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "Status is unavailable.");
    }
  }, [uiContext.projectId, uiContext.sceneId]);

  const runStatusCheck = useCallback(
    async (opts?: { deep?: boolean }) => {
      setStatusChecking(true);
      setStatusError(null);
      try {
        const { shouldSuspendDependentPolling, retryStudioApiConnection } = await import(
          "../../runtime/studioApiConnection"
        );
        if (shouldSuspendDependentPolling()) {
          const ok = await retryStudioApiConnection();
          if (!ok) {
            setStatusError("Cross-check unavailable because Studio API is offline.");
            return;
          }
        } else {
          // Light preflight — never fan out PA probes when /api/health is unreachable.
          try {
            await api.health();
          } catch {
            setStatusError("Cross-check unavailable because Studio API is offline.");
            return;
          }
        }
        const body = {
          projectId: uiContext.projectId,
          sceneId: uiContext.sceneId,
          workspace: uiContext.workspaceId,
        };
        const run = opts?.deep
          ? await requestDeepDiagnostic({ ...body, confirm: true })
          : await requestStatusCheck(body);
        setStatusLatestRun(run);
        setStatusHistory((prev) => [run, ...prev.filter((item) => item.runId !== run.runId)].slice(0, 20));
      } catch (err) {
        const { isStudioApiConnectivityFailure } = await import("../../runtime/studioApiConnection");
        if (isStudioApiConnectivityFailure(err)) {
          setStatusError("Cross-check unavailable because Studio API is offline.");
        } else {
          setStatusError(err instanceof Error ? err.message : "Status check failed.");
        }
      } finally {
        setStatusChecking(false);
      }
    },
    [uiContext.projectId, uiContext.sceneId, uiContext.workspaceId],
  );

  const openStatusPanel = useCallback(() => {
    setOverflowPanel("status");
    void loadStatus();
  }, [loadStatus]);

  const retryActivityPersistence = useCallback(async () => {
    const pending = activityPersistenceRef.current;
    if (!pending) return;
    setActivity((prev) =>
      prev
        ? upsertStage(prev, {
            id: "persistence",
            eventType: "persistence_started",
            label: "Saving this conversation",
            status: "active",
          })
        : prev,
    );
    const result = await reconcileConversation();
    setActivity((prev) => {
      if (!prev) return prev;
      const next = upsertStage(prev, {
        id: "persistence",
        eventType: result.ok ? "persistence_completed" : "persistence_started",
        label: "Saving this conversation",
        status: result.ok ? "completed" : "failed",
        detail: result.ok ? undefined : result.message || undefined,
      });
      return {
        ...next,
        status: result.ok ? "completed" : "failed",
        persistenceError: result.ok ? null : result.message,
      };
    });
  }, [reconcileConversation]);

  useEffect(() => {
    void fetchStatusRegistry()
      .then((checks) => setStatusRegistry(checks))
      .catch(() => {
        setStatusRegistry([]);
      });
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  // Phase BS — automatic cross-check on mount (deferred briefly so UI paints first)
  const autoCheckedRef = useRef(false);
  useEffect(() => {
    if (!uiContext.projectId || autoCheckedRef.current) return;
    autoCheckedRef.current = true;
    const timer = window.setTimeout(() => {
      void runStatusCheck();
    }, 500);
    return () => window.clearTimeout(timer);
    // Only run once per mount; project switch resets via the dependency.
  }, [uiContext.projectId, runStatusCheck]);

  const welcomeSuggestions = useMemo(() => buildWelcomeSuggestions(uiContext), [uiContext]);

  const productionCapable = Boolean(uiContext.projectId);
  const runtimeState = useMemo(
    () =>
      deriveRuntimeState({
        health: providerHealth,
        healthPending,
        reconnecting,
        modelLoading,
        projectId: uiContext.projectId,
        toolsBlocked: Boolean(toolActivity?.phase === "blocked"),
      }),
    [
      providerHealth,
      healthPending,
      reconnecting,
      modelLoading,
      uiContext.projectId,
      toolActivity?.phase,
    ],
  );
  const runtimeChip = useMemo(
    () =>
      runtimeChipText({
        state: runtimeState,
        model: selectedModelId || providerModel,
        projectName: uiContext.projectName,
        testOnly: Boolean(providerHealth?.testOnly || providerHealth?.honesty === "mocked"),
      }),
    [runtimeState, selectedModelId, providerModel, uiContext.projectName, providerHealth],
  );
  const sessionContext = useMemo<CoDirectorSessionContext>(
    () => ({
      projectId: uiContext.projectId ?? null,
      projectName: uiContext.projectName ?? null,
      activeDocumentId: uiContext.activeDocumentId ?? null,
      activeSceneId: uiContext.sceneId ?? null,
      activeWorkspace: uiContext.workspaceId ?? null,
      activeContentTab: uiContext.activeContentTab ?? null,
      selectedAssets: uiContext.selectedAssetIds || [],
      provider: providerHealth?.providerId ?? null,
      model: selectedModelId || providerModel,
      activeProductionPlan: plan ? { id: plan.id, title: plan.title } : null,
      sessionStatus: runtimeState,
      lastSuccessfulToolAction,
      unresolvedBlockers: [
        ...(uiContext.projectId ? [] : ["no_project_selected"]),
        ...(isConnectedLike(runtimeState) ? [] : [`runtime:${runtimeState}`]),
        ...(providerHealth?.testOnly ? ["test_only_provider"] : []),
      ],
    }),
    [
      uiContext,
      providerHealth,
      selectedModelId,
      providerModel,
      plan,
      runtimeState,
      lastSuccessfulToolAction,
    ],
  );

  // Expose open with autoSend for launcher compatibility
  const openSessionPublic = useCallback(
    (opts?: { prompt?: string; mode?: CoDirectorDisplayMode; autoSend?: boolean }) => {
      if (opts?.autoSend && opts.prompt) openSessionWithOptionalSend(opts);
      else openSession(opts);
    },
    [openSession, openSessionWithOptionalSend],
  );

  const value = useMemo<SessionValue>(
    () => ({
      open,
      displayMode,
      draft,
      messages,
      attachments,
      busy,
      applying,
      providerStatus,
      providerModel,
      providerHealth,
      selectedModelId,
      sendError,
      suggestedPrompt,
      setup,
      applyNote,
      proposals,
      proposalActingId,
      toolActivity,
      activity,
      activityPreference,
      setActivityPreference,
      retryActivityPersistence,
      intelligenceProgress,
      productionAnalysis,
      productionAnalysisExpanded,
      expertiseMode,
      setExpertiseMode,
      toggleProductionAnalysis,
      approveProposal,
      rejectProposal,
      requestProposalRevision,
      cancelProposal,
      refreshProposals,
      plan,
      promptMode,
      includeProjectKnowledge,
      compileExplain,
      overflowPanel,
      contextPanelOpen,
      assetPickerOpen,
      uiContext,
      activeExecution,
      setActiveExecution,
      conversationStarted,
      policies,
      kbModels,
      kbDoc,
      audit,
      welcomeSuggestions,
      setDraft,
      setOpen,
      openSession: openSessionPublic,
      closeSession,
      toggleOpen,
      expandToFullScreen,
      collapseToPopup,
      setDisplayMode,
      setOverflowPanel,
      setContextPanelOpen,
      setAssetPickerOpen,
      setPromptMode,
      setIncludeProjectKnowledge,
      clearConversation,
      bindWorkspace,
      unbindWorkspace,
      setActiveContentTab,
      send,
      retryLastSend,
      cancelSend,
      dismissSendError,
      openSettings,
      visionValidationEnabled: Boolean(providerHealth?.visionValidationEnabled),
      productionExecutiveEnabled: Boolean(providerHealth?.productionExecutiveEnabled),
      productionIntelligenceEnabled: Boolean(providerHealth?.productionIntelligenceEnabled),
      unifiedExperienceEnabled: Boolean(providerHealth?.unifiedExperienceEnabled),
      refreshProviderHealth,
      reconnect,
      setSelectedModelId,
      applySetup,
      dismissSetup: () => setSetup(null),
      applySuggestedPrompt: () => {
        if (!suggestedPrompt) return;
        bindingsRef.current.onApplyPrompt?.(suggestedPrompt);
        setSuggestedPrompt(null);
      },
      dismissSuggestedPrompt: () => setSuggestedPrompt(null),
      compilePrompt,
      addFiles,
      addLibraryAssets,
      removeAttachment,
      appendTranscript,
      setPolicies,
      loadKnowledge,
      loadKnowledgeDoc,
      refreshAudit: () => setAudit(loadAudit().slice(0, 20)),
      runtimeState,
      runtimeChip,
      sessionContext,
      productionCapable,
      lastBoundProjectSuggestion,
      resumeSuggestedProject,
      selectProject,
      createProject,
      showReconnectAction,
      statusRegistry,
      statusLatestRun,
      statusHistory,
      statusChecking,
      statusError,
      loadStatus,
      runStatusCheck,
      openStatusPanel,
    }),
    [
      open,
      displayMode,
      draft,
      messages,
      attachments,
      busy,
      applying,
      providerStatus,
      providerModel,
      providerHealth,
      selectedModelId,
      sendError,
      suggestedPrompt,
      setup,
      applyNote,
      proposals,
      proposalActingId,
      toolActivity,
      activity,
      activityPreference,
      intelligenceProgress,
      productionAnalysis,
      productionAnalysisExpanded,
      expertiseMode,
      setActivityPreference,
      retryActivityPersistence,
      approveProposal,
      rejectProposal,
      requestProposalRevision,
      cancelProposal,
      refreshProposals,
      plan,
      promptMode,
      includeProjectKnowledge,
      compileExplain,
      overflowPanel,
      contextPanelOpen,
      assetPickerOpen,
      uiContext,
      activeExecution,
      conversationStarted,
      policies,
      kbModels,
      kbDoc,
      audit,
      welcomeSuggestions,
      setDraft,
      setOpen,
      openSessionPublic,
      closeSession,
      toggleOpen,
      expandToFullScreen,
      collapseToPopup,
      setDisplayMode,
      setContextPanelOpen,
      clearConversation,
      bindWorkspace,
      unbindWorkspace,
      setActiveContentTab,
      send,
      retryLastSend,
      cancelSend,
      dismissSendError,
      openSettings,
      providerHealth,
      refreshProviderHealth,
      reconnect,
      setSelectedModelId,
      applySetup,
      compilePrompt,
      addFiles,
      addLibraryAssets,
      removeAttachment,
      appendTranscript,
      setPolicies,
      loadKnowledge,
      loadKnowledgeDoc,
      runtimeState,
      runtimeChip,
      sessionContext,
      productionCapable,
      lastBoundProjectSuggestion,
      resumeSuggestedProject,
      selectProject,
      createProject,
      showReconnectAction,
      statusRegistry,
      statusLatestRun,
      statusHistory,
      statusChecking,
      statusError,
      loadStatus,
      runStatusCheck,
      openStatusPanel,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useCoDirectorSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useCoDirectorSession must be used within CoDirectorSessionProvider");
  return value;
}

/** Compatibility helper for dashboard / chrome launchers. */
export function useOpenCoDirector() {
  const session = useCoDirectorSession();
  return useCallback(
    (prompt?: string, opts?: { fullscreen?: boolean; autoSend?: boolean }) => {
      const fullscreen = Boolean(opts?.fullscreen);
      // Prefill the composer by default — never silently send canned prompts as if the creator typed them.
      // Callers that truly want auto-send (e.g. PoseCraft handoff) must pass autoSend: true.
      session.openSession({
        prompt,
        autoSend: Boolean(opts?.autoSend && prompt),
        mode: fullscreen ? "fullscreen" : undefined,
      });
      if (fullscreen) {
        session.expandToFullScreen();
        return;
      }
      session.setDisplayMode("popup");
      session.setOpen(true);
    },
    [session],
  );
}

export function useBindCoDirectorWorkspace(bindings: CoDirectorWorkspaceBindings) {
  const { bindWorkspace, unbindWorkspace } = useCoDirectorSession();
  // Bind after paint so we never setState on CoDirectorSessionProvider during render.
  // Depend on stable binding fields — not the bindings object identity — to avoid rebinding every paint.
  useEffect(() => {
    bindWorkspace(bindings);
  }, [
    bindWorkspace,
    bindings.projectId,
    bindings.projectName,
    bindings.primaryProjectType,
    bindings.sceneId,
    bindings.sceneName,
    bindings.workspaceTab,
    bindings.activeDocumentId,
    bindings.onGoTab,
    bindings.onApplyPrompt,
    bindings.onAppliedSetup,
  ]);
  useEffect(() => () => unbindWorkspace(), [unbindWorkspace]);
}

// Satisfy unused Project import if tree-shaking complains — keep for future typing.
export type { Project };
