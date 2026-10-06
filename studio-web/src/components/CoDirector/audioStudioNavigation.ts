const AUDIO_TABS = new Set(["music", "sfx", "ambience", "library"]);

export function audioStudioTabFromResult(result: Record<string, unknown> | null | undefined): string {
  const raw = String(result?.audioTab || result?.contentTab || "music").trim().toLowerCase();
  if (raw === "sound" || raw === "sound effects" || raw === "effect" || raw === "foley") return "sfx";
  if (raw === "ambient" || raw === "bed" || raw === "atmosphere") return "ambience";
  if (raw === "project audio" || raw === "shelf") return "library";
  return AUDIO_TABS.has(raw) ? raw : "music";
}

const HANDOFF_KEYS = ["uiAction", "workspaceUrl", "audioTab", "contentTab", "projectId"] as const;

export function flattenToolHandoff(
  result: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  if (!result) return {};
  const nested =
    result.data && typeof result.data === "object" && !Array.isArray(result.data)
      ? (result.data as Record<string, unknown>)
      : {};
  const out: Record<string, unknown> = { ...nested, ...result };
  for (const key of HANDOFF_KEYS) {
    if (!out[key] && nested[key]) out[key] = nested[key];
  }
  return out;
}

export function shouldOpenAudioStudio(toolId: string, result: Record<string, unknown> | null | undefined): boolean {
  const payload = flattenToolHandoff(result);
  const action = String(payload.uiAction || "");
  return (
    action === "open_audio_studio" ||
    toolId === "audio.open_studio" ||
    toolId === "voice_environment.open_audio_studio"
  );
}

export function audioStudioWorkspacePath(projectId: string, audioTab = "music"): string {
  const tab = AUDIO_TABS.has(audioTab) ? audioTab : "music";
  return `/project/${projectId}?workspace=audiostudio&audioTab=${encodeURIComponent(tab)}`;
}

export function resolveAudioStudioNavigation(
  projectId: string,
  toolId: string,
  result: Record<string, unknown> | null | undefined,
): string | null {
  const payload = flattenToolHandoff(result);
  if (!shouldOpenAudioStudio(toolId, payload)) return null;
  const explicit = String(payload.workspaceUrl || "").trim();
  if (explicit.startsWith("/project/")) return explicit;
  const id = String(payload.projectId || projectId || "").trim();
  if (!id) return null;
  return audioStudioWorkspacePath(id, audioStudioTabFromResult(payload));
}
