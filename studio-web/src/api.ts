import type { EngineName, Health, Job, Project, Scene, SceneSetup, SpatialMap } from "./types";
import type {
  ComponentDiagnosticResult,
  DownloadSourcesResponse,
  SetupCheckpointAnswer,
  SetupLegacyActionResult,
  SetupLegacyDetection,
  SetupLegacyState,
  SetupOperation,
  SetupStatusResponse,
  SetupUpdateDismissal,
  DownloadOperation,
  InstallHistoryEntry,
  InstallReceipt,
  SourceManagerOverview,
  SourceVerificationResult,
  StudioPreparationPlan,
} from "./setup/types";

const BASE = "";

export interface ApiErrorDetailShape {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
  recoverable?: boolean;
  recommendedAction?: string;
}

export class ApiError extends Error {
  status: number;
  /** Structured error code from a Co-Director-style `{code,message,...}` detail payload, if present. */
  code?: string;
  details?: Record<string, unknown>;
  recoverable?: boolean;
  recommendedAction?: string;

  constructor(
    message: string,
    status: number,
    opts?: { code?: string; details?: Record<string, unknown>; recoverable?: boolean; recommendedAction?: string },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = opts?.code;
    this.details = opts?.details;
    this.recoverable = opts?.recoverable;
    this.recommendedAction = opts?.recommendedAction;
  }
}

/** Backend-agnostic "couldn't reach the service" code used when fetch itself throws. */
export const BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE";

export interface ClassifiedError {
  code: string;
  message: string;
  recommendedAction?: string;
  recoverable: boolean;
}

/** SSE events emitted by POST /api/codirector/chat/stream. */
export type CoDirectorStreamEvent =
  | { type: "request_started"; requestId: string }
  | { type: "provider_connected"; requestId: string; providerId: string }
  | { type: "token"; requestId: string; content: string }
  | {
      type: "completed";
      requestId: string;
      content: string;
      modelId: string;
      providerId: string;
      sceneSetup?: SceneSetup | null;
      suggestedPrompt?: string | null;
    }
  | { type: "cancelled"; requestId: string }
  | { type: "error"; requestId: string; error: ApiErrorDetailShape };

/**
 * Turn any thrown value from a Co-Director request into a structured, user-safe
 * classification. Never surfaces a bare `TypeError: Failed to fetch`.
 */
export function classifyCoDirectorError(err: unknown): ClassifiedError {
  if (err instanceof ApiError) {
    return {
      code: err.code || "UNKNOWN_PROVIDER_ERROR",
      message: err.message || "The Co-Director backend returned an unexpected error.",
      recommendedAction: err.recommendedAction,
      recoverable: err.recoverable ?? true,
    };
  }
  if (err instanceof TypeError && /failed to fetch|networkerror when attempting to fetch|load failed/i.test(err.message)) {
    return {
      code: BACKEND_UNAVAILABLE,
      message: "Adept couldn't reach the backend service. Make sure the app/API is running, then retry.",
      recommendedAction: "retry_or_check_service",
      recoverable: true,
    };
  }
  return {
    code: "UNKNOWN_PROVIDER_ERROR",
    message: err instanceof Error ? err.message : String(err),
    recoverable: true,
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

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch (error) {
    // Preserve AbortError so callers can ignore expected cancellations.
    if (isAbortError(error) || init?.signal?.aborted) {
      throw error instanceof Error ? error : new DOMException("Aborted", "AbortError");
    }
    throw error;
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
      throw new ApiError(d.message || text || res.statusText, res.status, {
        code: d.code,
        details: d.details,
        recoverable: d.recoverable,
        recommendedAction: d.recommendedAction,
      });
    }
    if (typeof detail === "string" && detail.trim()) {
      throw new ApiError(detail, res.status);
    }
    throw new ApiError(text || res.statusText, res.status);
  }
  return res.json();
}

export const api = {
  health: () => req<Health>("/api/health"),
  listProjects: (init?: RequestInit) => req<Project[]>("/api/projects", init),
  createProject: (name: string) =>
    req<Project>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, width: 1280, height: 720, fps: 24, preset: "quality", vram_gb: 32 }),
    }),
  getProject: (id: string, init?: RequestInit) => req<Project>(`/api/projects/${id}`, init),
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
        durations: number[];
        default_duration: number;
        supports_end_image: boolean;
        description: string;
      }[]
    >("/api/fal/models"),
  falKeyStatus: () =>
    req<{ configured: boolean; hint?: string | null; fingerprint?: string | null }>("/api/fal/key"),
  falKeySet: (api_key: string) =>
    req<{ configured: boolean; hint?: string | null; fingerprint?: string | null }>("/api/fal/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key }),
    }),
  falKeyClear: () =>
    req<{ configured: boolean; hint?: string | null; fingerprint?: string | null }>("/api/fal/key", {
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
  uploadAsset: async (projectId: string, file: File, tag: string, kind: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tag", tag);
    fd.append("kind", kind);
    return req(`/api/projects/${projectId}/assets`, { method: "POST", body: fd });
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
    kind: "scene" | "timeline",
    sceneId?: string,
    extras?: {
      reference_method?: string;
      sheet_id?: string;
      strength_preset?: string;
      strength?: number;
      ingredients_ic_lora?: boolean;
    },
  ) =>
    req<Job>(`/api/projects/${projectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind,
        scene_id: sceneId ?? null,
        retake: kind === "scene",
        ...(extras || {}),
      }),
    }),
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
      ok: boolean;
    }>(`/api/codirector/providers/${encodeURIComponent(providerId)}/health`),
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
        throw new ApiError(d.message || text || res.statusText, res.status, {
          code: d.code,
          details: d.details,
          recoverable: d.recoverable,
          recommendedAction: d.recommendedAction,
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
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`),
  codirectorSaveConversation: (
    projectId: string,
    body: { messages: { id?: string; role: string; content: string; created_at?: string }[]; model?: string | null; provider_id?: string | null },
  ) =>
    req<{
      projectId: string;
      messages: { id?: string; role: string; content: string; created_at?: string }[];
      model: string | null;
      providerId: string | null;
      updatedAt: string | null;
    }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  codirectorDeleteConversation: (projectId: string) =>
    req<{ ok: boolean; projectId: string }>(`/api/codirector/conversations/${encodeURIComponent(projectId)}`, {
      method: "DELETE",
    }),
  setupDetect: () => req<SetupLegacyDetection>("/api/setup/detect"),
  setupState: () => req<SetupLegacyState>("/api/setup/state"),
  setupStatus: () => req<SetupStatusResponse>("/api/setup/status"),
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
  setupSignInDownloadSource: (provider: string) =>
    req<{
      provider: string;
      command_summary?: string;
      message?: string;
      requires_confirmation?: boolean;
    }>(`/api/setup/download-sources/${encodeURIComponent(provider)}/sign-in`, { method: "POST" }),
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
  sourceManagerOverview: () => req<SourceManagerOverview>("/api/source-manager/overview"),
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
  duplicateProject: (projectId: string) =>
    req<{ ok: boolean; id: string; name: string }>(`/api/projects/${projectId}/duplicate`, { method: "POST" }),
  archiveProject: (projectId: string, archived = true) =>
    req<{ ok: boolean; archived: number }>(
      `/api/projects/${projectId}/archive?archived=${archived ? "true" : "false"}`,
      { method: "POST" }
    ),
  exportProject: (projectId: string) =>
    req<Job>(`/api/projects/${projectId}/export`, { method: "POST" }),
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
  library: (projectId: string, opts?: { q?: string; scope?: string }) => {
    const q = new URLSearchParams();
    if (opts?.q) q.set("q", opts.q);
    if (opts?.scope) q.set("scope", opts.scope);
    const qs = q.toString();
    return req<any[]>(`/api/projects/${projectId}/library${qs ? `?${qs}` : ""}`);
  },
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
};
