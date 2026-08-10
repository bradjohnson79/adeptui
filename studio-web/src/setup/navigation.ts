export type SetupEntrySource =
  | "production_dock"
  | "status_center"
  | "workspace_launch"
  | "co_director"
  | "setup_wizard"
  | "source_manager"
  | "avatar_studio"
  | "voice_studio"
  | "image_studio"
  | "video_studio";

type BuildAiGuidedSetupPathArgs = {
  projectId?: string | null;
  componentId?: string | null;
  source?: SetupEntrySource | string | null;
};

export function buildAiGuidedSetupPath({
  projectId,
  componentId,
  source,
}: BuildAiGuidedSetupPathArgs): string {
  const params = new URLSearchParams();
  params.set("setupMode", "ai_guided");
  if (componentId) params.set("setupComponent", componentId);
  if (source) params.set("setupSource", source);
  const hash = "#ai-guided-setup-heading";
  if (projectId) {
    params.set("workspace", "setup");
    return `/project/${encodeURIComponent(projectId)}?${params.toString()}${hash}`;
  }
  return `/?${params.toString()}${hash}`;
}
