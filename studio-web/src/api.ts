import type { Health, Job, Project, Scene, SceneSetup, SpatialMap } from "./types";

const BASE = "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  health: () => req<Health>("/api/health"),
  listProjects: () => req<Project[]>("/api/projects"),
  createProject: (name: string) =>
    req<Project>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, width: 1280, height: 720, fps: 24, preset: "quality", vram_gb: 32 }),
    }),
  getProject: (id: string) => req<Project>(`/api/projects/${id}`),
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
  render: (projectId: string, kind: "scene" | "timeline", sceneId?: string) =>
    req<Job>(`/api/projects/${projectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, scene_id: sceneId ?? null, retake: kind === "scene" }),
    }),
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
    }>("/api/assistant/apply-setup", {
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
