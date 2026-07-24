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
import { useNavigate } from "react-router-dom";
import {
  api,
  ApiError,
  classifyCoDirectorError,
  isAbortError,
  type ClassifiedError,
  type CoDirectorStreamEvent,
} from "../../api";
import {
  loadAudit,
  loadPolicies,
  planFromIntention,
  savePolicies,
  type ActionCategory,
  type ActionPlan,
  type PermissionPolicy,
  type PlannedStep,
} from "../../codirector/types";
import { executeStep, type ExecuteContext } from "../../codirector/execute";
import type { Project, SceneSetup } from "../../types";
import {
  consumeAbandonedStreamingFlag,
  loadContextPanelOpen,
  loadDisplayMode,
  loadPersistedDraft,
  loadPersistedMessages,
  markStreamingEnd,
  markStreamingStart,
  newAttachmentId,
  newMessageId,
  persistContextPanelOpen,
  persistDisplayMode,
  persistDraft,
  persistMessages,
  WELCOME_ASSISTANT,
  type ChatMode,
  type CoDirectorAttachment,
  type CoDirectorDisplayMode,
  type CoDirectorMessage,
  type CoDirectorUIContext,
  type CoDirectorWorkspaceBindings,
  type OverflowPanel,
  type PromptMode,
  type WelcomeSuggestion,
} from "./types";

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
  setSelectedStep: (stepId: string, selected: boolean) => void;
  clearConversation: () => void;
  dismissPlan: () => void;
  bindWorkspace: (bindings: CoDirectorWorkspaceBindings) => void;
  unbindWorkspace: () => void;
  send: (text?: string, mode?: ChatMode) => Promise<void>;
  retryLastSend: () => void;
  cancelSend: () => void;
  dismissSendError: () => void;
  openSettings: () => void;
  refreshProviderHealth: () => Promise<void>;
  setSelectedModelId: (modelId: string | null) => void;
  runSteps: (steps: PlannedStep[]) => Promise<void>;
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
};

const SessionContext = createContext<SessionValue | null>(null);

function buildWelcomeSuggestions(ctx: CoDirectorUIContext): WelcomeSuggestion[] {
  const suggestions: WelcomeSuggestion[] = [];
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

export function CoDirectorSessionProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const bindingsRef = useRef<CoDirectorWorkspaceBindings>({});
  const [open, setOpenState] = useState(false);
  const [displayMode, setDisplayModeState] = useState<CoDirectorDisplayMode>(() => loadDisplayMode());
  const [draft, setDraftState] = useState(() => loadPersistedDraft());
  const [messages, setMessages] = useState<CoDirectorMessage[]>(
    () => loadPersistedMessages() || [WELCOME_ASSISTANT],
  );
  const [attachments, setAttachments] = useState<CoDirectorAttachment[]>([]);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [providerStatus, setProviderStatus] = useState("Checking Co-Director…");
  const [providerModel, setProviderModel] = useState<string | null>(null);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null);
  const [selectedModelId, setSelectedModelIdState] = useState<string | null>(null);
  const [sendError, setSendError] = useState<ClassifiedError | null>(null);
  // `messageId: null` means the failed attempt never got far enough to append a user
  // message (preflight failure) — retry should go through `send()` again. Once a message
  // *has* been appended, `messageId` points at it so retry resends the same transcript
  // slice instead of appending a duplicate copy of the same user message.
  const pendingRetryRef = useRef<{ text: string; mode: ChatMode; messageId: string | null } | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const cancelledByUserRef = useRef(false);
  const lastLoadedProjectIdRef = useRef<string | undefined>(undefined);
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
  const [applyNote, setApplyNote] = useState<string | null>(null);
  const [plan, setPlan] = useState<ActionPlan | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<Record<string, boolean>>({});
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

  const conversationStarted = messages.some((m) => m.role === "user");

  const refreshProviderHealth = useCallback(async () => {
    try {
      const health = await api.codirectorHealth("active");
      setProviderHealth(health);
      setProviderModel(health.selectedModel);
      setProviderStatus(
        health.status === "Ready" ? `${health.displayName} · ${health.selectedModel}` : health.status,
      );
      setSelectedModelIdState((prev) => prev ?? health.selectedModel ?? null);
    } catch {
      setProviderHealth(null);
      setProviderModel(null);
      setProviderStatus("Co-Director unavailable");
    }
  }, []);

  useEffect(() => {
    void refreshProviderHealth();
  }, [refreshProviderHealth]);

  // Cancel any in-flight request when the panel unmounts (app close / hard navigation away).
  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const persistConversation = useCallback(
    (msgs: CoDirectorMessage[], model?: string | null, providerId?: string | null) => {
      const projectId = bindingsRef.current.projectId;
      if (!projectId) return;
      void api
        .codirectorSaveConversation(projectId, {
          messages: msgs.map((m) => ({ id: m.id, role: m.role, content: m.content, created_at: m.createdAt })),
          model: model ?? null,
          provider_id: providerId ?? null,
        })
        .catch(() => {
          /* server persistence is authoritative when reachable; local draft cache still holds the turn */
        });
    },
    [],
  );

  // The server is the source of truth for a project's conversation. Hydrate from it whenever
  // the bound project changes, and surface a mid-stream reload as an interrupted turn instead
  // of silently dropping the user's last message.
  useEffect(() => {
    const projectId = uiContext.projectId;
    if (!projectId || projectId === lastLoadedProjectIdRef.current) return;
    lastLoadedProjectIdRef.current = projectId;
    let cancelled = false;
    (async () => {
      const abandoned = consumeAbandonedStreamingFlag(projectId);
      try {
        const convo = await api.codirectorGetConversation(projectId);
        if (cancelled) return;
        if (convo.messages && convo.messages.length) {
          let loaded: CoDirectorMessage[] = convo.messages.map((m) => ({
            id: m.id || newMessageId(),
            role: m.role === "user" ? "user" : "assistant",
            content: m.content,
            createdAt: m.created_at || new Date().toISOString(),
          }));
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
          setMessages(loaded);
          if (convo.model) setSelectedModelIdState((prev) => prev ?? convo.model);
        } else {
          const local = loadPersistedMessages();
          setMessages(local && local.length ? local : [WELCOME_ASSISTANT]);
        }
      } catch {
        /* server unreachable — keep whatever is currently rendered (local draft cache) */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [uiContext.projectId]);

  useEffect(() => {
    persistDraft(draft);
  }, [draft]);

  useEffect(() => {
    persistMessages(messages);
  }, [messages]);

  const setDraft = useCallback((value: string) => setDraftState(value), []);
  const setOpen = useCallback((value: boolean) => setOpenState(value), []);
  const setDisplayMode = useCallback((mode: CoDirectorDisplayMode) => {
    setDisplayModeState(mode);
    persistDisplayMode(mode);
  }, []);
  const setContextPanelOpen = useCallback((value: boolean) => {
    setContextPanelOpenState(value);
    persistContextPanelOpen(value);
  }, []);

  const bindWorkspace = useCallback((bindings: CoDirectorWorkspaceBindings) => {
    bindingsRef.current = bindings;
    setUiContext((prev) => {
      const next: CoDirectorUIContext = {
        projectId: bindings.projectId,
        projectName: bindings.projectName,
        sceneId: bindings.sceneId,
        sceneName: bindings.sceneName,
        workspaceId: bindings.workspaceTab,
      };
      if (
        prev.projectId === next.projectId &&
        prev.projectName === next.projectName &&
        prev.sceneId === next.sceneId &&
        prev.sceneName === next.sceneName &&
        prev.workspaceId === next.workspaceId
      ) {
        return prev;
      }
      return next;
    });
  }, []);

  const unbindWorkspace = useCallback(() => {
    bindingsRef.current = {};
    setUiContext({});
  }, []);

  const execCtx = useCallback((): ExecuteContext => {
    const b = bindingsRef.current;
    return {
      projectId: b.projectId,
      sceneId: b.sceneId,
      navigate: (path: string) => navigate(path),
      goTab: b.onGoTab,
      confirm: (msg) => window.confirm(msg),
      onRefresh: async () => {
        await b.onAppliedSetup?.();
      },
    };
  }, [navigate]);

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
    setSelectedSteps({});
    setSendError(null);
    pendingRetryRef.current = null;
    const projectId = bindingsRef.current.projectId;
    if (projectId) {
      markStreamingEnd(projectId);
      void api.codirectorDeleteConversation(projectId).catch(() => {});
    }
  }, []);

  const dismissPlan = useCallback(() => {
    setPlan(null);
    setSelectedSteps({});
  }, []);

  const dismissSendError = useCallback(() => setSendError(null), []);

  const openSettings = useCallback(() => {
    setOverflowPanel("provider");
    void refreshProviderHealth();
  }, [refreshProviderHealth]);

  const setSelectedModelId = useCallback((modelId: string | null) => {
    setSelectedModelIdState(modelId);
  }, []);

  /**
   * Talk to the gateway for an already-built transcript (`transcriptForApi` includes the
   * user's message as its last entry). Never appends a new user message itself — that's
   * `send()`'s job — so `retryLastSend()` can call this directly to resend without
   * duplicating the user's turn in the transcript.
   */
  const performSend = useCallback(
    async (transcriptForApi: CoDirectorMessage[], mode: ChatMode) => {
      setSendError(null);
      setBusy(true);
      setSuggestedPrompt(null);
      setSetup(null);
      setApplyNote(null);
      setOverflowPanel((prev) => (prev === "provider" ? prev : "none"));

      const b = bindingsRef.current;
      const requestId = newMessageId();
      activeRequestIdRef.current = requestId;
      cancelledByUserRef.current = false;
      const controller = new AbortController();
      abortControllerRef.current = controller;
      if (b.projectId) markStreamingStart(b.projectId, requestId);

      const assistantId = newMessageId();
      let streamedText = "";
      let sawToken = false;
      let outcome: "completed" | "cancelled" | "error" | null = null;
      let finalModel: string | undefined;
      let finalProviderId: string | undefined;
      let sceneSetupResult: SceneSetup | null = null;
      let suggestedPromptResult: string | null = null;
      let classifiedError: ClassifiedError | null = null;

      const apiMessages = transcriptForApi.map((m) => ({ role: m.role, content: m.content }));

      const onEvent = (event: CoDirectorStreamEvent) => {
        if (!mountedRef.current || activeRequestIdRef.current !== requestId) return; // stale / unmounted
        if (event.type === "token") {
          sawToken = true;
          streamedText += event.content;
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
        } else if (event.type === "completed") {
          outcome = "completed";
          streamedText = event.content || streamedText;
          finalModel = event.modelId;
          finalProviderId = event.providerId;
          sceneSetupResult = (event.sceneSetup as SceneSetup) || null;
          suggestedPromptResult = event.suggestedPrompt || null;
        } else if (event.type === "cancelled") {
          outcome = "cancelled";
        } else if (event.type === "error") {
          outcome = "error";
          classifiedError = classifyCoDirectorError(
            new ApiError(event.error.message || "Co-Director returned an error.", 0, {
              code: event.error.code,
              details: event.error.details,
              recoverable: event.error.recoverable,
              recommendedAction: event.error.recommendedAction,
            }),
          );
        }
      };

      const dropEmptyStreamingBubble = () => {
        setMessages((prev) => prev.filter((m) => !(m.id === assistantId && m.status === "streaming" && !m.content)));
      };

      const finalizeCompleted = () => {
        const finalText = streamedText;
        setMessages((prev) => {
          const idx = prev.findIndex((m) => m.id === assistantId);
          const finished: CoDirectorMessage = {
            id: assistantId,
            role: "assistant",
            content: finalText,
            createdAt: new Date().toISOString(),
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
        persistConversation(
          [...transcriptForApi, { id: assistantId, role: "assistant", content: finalText, createdAt: new Date().toISOString() }],
          finalModel,
          finalProviderId,
        );
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
          },
          { signal: controller.signal, onEvent },
        );

        if (!mountedRef.current) {
          // Component unmounted mid-stream; still persist whatever finished so it isn't lost.
          if (outcome === "completed") {
            persistConversation(
              [...transcriptForApi, { id: assistantId, role: "assistant", content: streamedText, createdAt: new Date().toISOString() }],
              finalModel,
              finalProviderId,
            );
          }
          return;
        }

        if (outcome === "completed") {
          finalizeCompleted();
        } else if (outcome === "cancelled") {
          setMessages((prev) =>
            prev
              .map((m) => (m.id === assistantId ? { ...m, status: "cancelled" as const } : m))
              .filter((m) => !(m.id === assistantId && !m.content)),
          );
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
        } else if (outcome === "error" && classifiedError) {
          dropEmptyStreamingBubble();
          setSendError(classifiedError);
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
        } else if (sawToken) {
          // Stream ended without a terminal event but tokens arrived — preserve the partial
          // reply instead of discarding it.
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, status: "interrupted" as const } : m)));
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
        } else {
          dropEmptyStreamingBubble();
          setSendError(classifyCoDirectorError(new Error("The response ended unexpectedly.")));
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
        }
      } catch (err) {
        if (isAbortError(err)) {
          const wasUserCancel = cancelledByUserRef.current;
          if (!mountedRef.current) return;
          setMessages((prev) =>
            prev
              .map((m) =>
                m.id === assistantId ? { ...m, status: (wasUserCancel ? "cancelled" : "interrupted") as const } : m,
              )
              .filter((m) => !(m.id === assistantId && !m.content)),
          );
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
          return;
        }

        // The stream transport itself failed before completing (network error, non-2xx
        // response, or a backend that doesn't support SSE) — fall back to the non-streaming
        // endpoint once before surfacing a classified error.
        if (!mountedRef.current) return;
        dropEmptyStreamingBubble();
        try {
          const res = await api.codirectorChat(
            { messages: apiMessages, project_id: b.projectId, scene_id: b.sceneId, model: selectedModelId || undefined, mode, request_id: requestId },
            { signal: controller.signal },
          );
          const assistantMsg: CoDirectorMessage = {
            id: newMessageId(),
            role: "assistant",
            content: res.reply,
            createdAt: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          if (res.sceneSetup) setSetup(res.sceneSetup as SceneSetup);
          else if (res.suggestedPrompt) setSuggestedPrompt(res.suggestedPrompt);
          pendingRetryRef.current = null;
          setProviderModel(res.model);
          persistConversation([...transcriptForApi, assistantMsg], res.model, res.providerId);
        } catch (err2) {
          if (isAbortError(err2)) return;
          const classified = classifyCoDirectorError(err2);
          setSendError(classified);
          persistConversation(transcriptForApi, selectedModelId ?? undefined, undefined);
        }
      } finally {
        setBusy(false);
        if (activeRequestIdRef.current === requestId) activeRequestIdRef.current = null;
        if (abortControllerRef.current === controller) abortControllerRef.current = null;
        if (b.projectId) markStreamingEnd(b.projectId);
        cancelledByUserRef.current = false;
      }
    },
    [persistConversation, selectedModelId],
  );

  const send = useCallback(
    async (text?: string, mode: ChatMode = "chat") => {
      const trimmed = (text ?? draft).trim();
      if ((!trimmed && !attachments.length) || busy) return;
      setSendError(null);
      setBusy(true);

      // Append the user's message immediately — it must survive any downstream failure
      // (provider down, no models, network error). Never silently drop it.
      const attachmentNote = attachments.length
        ? `\n\n[Attached: ${attachments.map((a) => a.name).join(", ")}]`
        : "";
      const content = `${trimmed}${attachmentNote}`.trim();
      const userMsg: CoDirectorMessage = {
        id: newMessageId(),
        role: "user",
        content,
        attachmentIds: attachments.map((a) => a.id),
        createdAt: new Date().toISOString(),
      };
      const next = [...messages, userMsg];
      setMessages(next);
      setDraftState("");
      // Keep library attachments listed in message; revoke file previews after send.
      setAttachments((prev) => {
        for (const item of prev) {
          if (item.previewUrl && item.kind === "file") URL.revokeObjectURL(item.previewUrl);
        }
        return [];
      });
      // Persist the user's turn immediately (before the reply arrives) so a reload mid-flight
      // still shows the question, not just silence.
      persistConversation(next, selectedModelId ?? undefined, undefined);
      pendingRetryRef.current = { text: trimmed, mode, messageId: userMsg.id };

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

      const wantsPlan =
        /build|create|prepare|plan|dialogue|storyboard|lip.?sync|master sheet|coverage|generate|workflow|assemble|editor|director sequence/i.test(
          trimmed,
        ) && mode !== "setup";

      const b = bindingsRef.current;
      if (wantsPlan) {
        const p = planFromIntention(trimmed, { projectId: b.projectId, sceneId: b.sceneId });
        setPlan(p);
        setSelectedSteps(Object.fromEntries(p.steps.map((s) => [s.id, true])));
        setMessages([
          ...next,
          {
            id: newMessageId(),
            role: "assistant",
            content: `I drafted a plan: “${p.title}” with ${p.steps.length} steps. Review the steps below, then Approve all or Run selected.`,
            createdAt: new Date().toISOString(),
          },
        ]);
        pendingRetryRef.current = null;
        setBusy(false);
        return;
      }

      await performSend(next, mode);
    },
    [attachments, busy, draft, messages, performSend, persistConversation, selectedModelId],
  );

  const retryLastSend = useCallback(() => {
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
  }, [busy, messages, performSend, send]);

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

  const runSteps = useCallback(
    async (steps: PlannedStep[]) => {
      if (!plan) return;
      let current = { ...plan, steps: [...plan.steps] };
      for (const step of steps) {
        const idx = current.steps.findIndex((s) => s.id === step.id);
        if (idx < 0) continue;
        current.steps[idx] = { ...current.steps[idx], status: "running" };
        setPlan({ ...current });
        const done = await executeStep(current.steps[idx], execCtx());
        current.steps[idx] = done;
        setPlan({ ...current });
        if (done.status === "checkpoint") {
          current.pausedAt = new Date().toISOString();
          setPlan({ ...current });
          setMessages((m) => [
            ...m,
            {
              id: newMessageId(),
              role: "assistant",
              content: `Checkpoint: ${done.checkpointMessage || "Complete the manual step, then Continue."}`,
              createdAt: new Date().toISOString(),
            },
          ]);
          break;
        }
        if (done.reuseAssets?.length) {
          setMessages((m) => [
            ...m,
            {
              id: newMessageId(),
              role: "assistant",
              content: `Asset-first: found ${done.reuseAssets!.length} library matches — consider reusing before generating.`,
              createdAt: new Date().toISOString(),
            },
          ]);
        }
      }
      setAudit(loadAudit().slice(0, 20));
    },
    [execCtx, plan],
  );

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
  }, [draft, includeProjectKnowledge, promptMode]);

  const addFiles = useCallback((files: FileList | File[]) => {
    const list = Array.from(files);
    setAttachments((prev) => [
      ...prev,
      ...list.map((file) => ({
        id: newAttachmentId(),
        kind: "file" as const,
        name: file.name,
        mimeType: file.type,
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
      if (target?.previewUrl && target.kind === "file") URL.revokeObjectURL(target.previewUrl);
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

  const welcomeSuggestions = useMemo(() => buildWelcomeSuggestions(uiContext), [uiContext]);

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
      plan,
      selectedSteps,
      promptMode,
      includeProjectKnowledge,
      compileExplain,
      overflowPanel,
      contextPanelOpen,
      assetPickerOpen,
      uiContext,
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
      setSelectedStep: (stepId, selected) =>
        setSelectedSteps((prev) => ({ ...prev, [stepId]: selected })),
      clearConversation,
      dismissPlan,
      bindWorkspace,
      unbindWorkspace,
      send,
      retryLastSend,
      cancelSend,
      dismissSendError,
      openSettings,
      refreshProviderHealth,
      setSelectedModelId,
      runSteps,
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
      plan,
      selectedSteps,
      promptMode,
      includeProjectKnowledge,
      compileExplain,
      overflowPanel,
      contextPanelOpen,
      assetPickerOpen,
      uiContext,
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
      dismissPlan,
      bindWorkspace,
      unbindWorkspace,
      send,
      retryLastSend,
      cancelSend,
      dismissSendError,
      openSettings,
      refreshProviderHealth,
      setSelectedModelId,
      runSteps,
      applySetup,
      compilePrompt,
      addFiles,
      addLibraryAssets,
      removeAttachment,
      appendTranscript,
      setPolicies,
      loadKnowledge,
      loadKnowledgeDoc,
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
    (prompt?: string) => {
      session.openSession({ prompt, autoSend: Boolean(prompt) });
      if (session.displayMode === "fullscreen") {
        /* already full screen */
      } else {
        session.setOpen(true);
      }
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
    bindings.sceneId,
    bindings.sceneName,
    bindings.workspaceTab,
    bindings.onGoTab,
    bindings.onApplyPrompt,
    bindings.onAppliedSetup,
  ]);
  useEffect(() => () => unbindWorkspace(), [unbindWorkspace]);
}

// Satisfy unused Project import if tree-shaking complains — keep for future typing.
export type { Project };
