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
  setupSection?: string | null;
  missingComponentIds?: string[] | null;
};

export function buildAiGuidedSetupPath({
  projectId,
  componentId,
  source,
  setupSection,
  missingComponentIds,
}: BuildAiGuidedSetupPathArgs): string {
  const params = new URLSearchParams();
  params.set("setupMode", "ai_guided");
  if (componentId) params.set("setupComponent", componentId);
  if (source) params.set("setupSource", source);
  if (setupSection) params.set("setupSection", setupSection);
  if (missingComponentIds?.length) params.set("setupMissing", missingComponentIds.join(","));
  const hash = "#ai-guided-setup-heading";
  if (projectId) {
    params.set("workspace", "setup");
    return `/project/${encodeURIComponent(projectId)}?${params.toString()}${hash}`;
  }
  return `/setup?${params.toString()}${hash}`;
}

/** Setup opens the existing wizard. It never attaches create=1. */
export function buildSetupWizardPath(projectId?: string | null): string {
  return buildAiGuidedSetupPath({
    projectId,
    source: "workspace_launch",
  });
}

export type HomeLaunchAction =
  | { type: "create-project" }
  | { type: "open-setup"; projectId?: string | null };

/**
 * create=1 opens Create Project only for a real project pending entry.
 * A setup deep link always opens the wizard.
 */
export function homeLaunchAction(args: {
  forcedCreate: boolean;
  pendingKind?: string | null;
  projectId?: string | null;
}): HomeLaunchAction | null {
  if (args.pendingKind === "setup") {
    return { type: "open-setup", projectId: args.projectId };
  }
  if (args.forcedCreate) return { type: "create-project" };
  return null;
}
