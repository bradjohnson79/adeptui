import type { CoDirectorContextManifest } from "../../api";
import type {
  CoDirectorActivityPreference,
  CoDirectorActivityStage,
  CoDirectorActivityState,
  CoDirectorActivityEventType,
  CoDirectorUIContext,
} from "./types";

type StageId = CoDirectorActivityStage["id"];

function stage(
  id: StageId,
  eventType: CoDirectorActivityEventType,
  label: string,
  status: CoDirectorActivityStage["status"],
  detail?: string,
): CoDirectorActivityStage {
  return { id, eventType, label, status, detail };
}

export function createActivityState(input: {
  requestId: string;
  hasProject: boolean;
  hasContext: boolean;
  attachmentsCount: number;
}): CoDirectorActivityState {
  // Honest stages come from SSE `processing_stage`. Seed only a light pending response row —
  // never a prolonged optimistic "Understanding the request" that outlives real progress.
  const stages: CoDirectorActivityStage[] = [
    stage("request", "request_received", "Receiving your message", "active"),
  ];
  if (input.hasContext) {
    stages.push(stage("context", "context_review", "Reviewing the current context", "pending"));
  }
  if (input.attachmentsCount > 0) {
    stages.push(stage("media", "media_review", "Reviewing your references", "pending"));
  }
  stages.push(stage("response", "response_composing", "Waiting for the first words…", "pending"));
  if (input.hasProject) {
    stages.push(stage("persistence", "persistence_started", "Saving this conversation", "pending"));
  }
  return {
    requestId: input.requestId,
    status: "running",
    stages,
    summaryFacts: [],
    attachmentsCount: input.attachmentsCount,
    toolLabels: [],
    startedAt: new Date().toISOString(),
    persistenceError: null,
    processingStages: ["RECEIVING"],
    nextStepOptions: [],
    wikiBackgroundStatus: null,
    wikiRefreshNonce: 0,
    wikiVerification: null,
    wikiUiMessage: null,
    coldLoadActive: false,
  };
}

export function upsertStage(
  activity: CoDirectorActivityState,
  nextStage: CoDirectorActivityStage,
): CoDirectorActivityState {
  const existingIndex = activity.stages.findIndex((item) => item.id === nextStage.id);
  if (existingIndex === -1) {
    return { ...activity, stages: [...activity.stages, nextStage] };
  }
  const stages = [...activity.stages];
  stages[existingIndex] = {
    ...stages[existingIndex],
    ...nextStage,
    detail: nextStage.detail ?? stages[existingIndex].detail,
  };
  return { ...activity, stages };
}

export function updateStage(
  activity: CoDirectorActivityState,
  id: StageId,
  patch: Partial<CoDirectorActivityStage>,
): CoDirectorActivityState {
  const existing = activity.stages.find((item) => item.id === id);
  if (!existing) return activity;
  return upsertStage(activity, { ...existing, ...patch });
}

function normalizeWorkspaceLabel(workspaceId?: string): string | null {
  if (!workspaceId) return null;
  return workspaceId
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function labelForTool(toolId: string): string {
  if (toolId.startsWith("production_plan.")) return "the active plan";
  if (
    toolId.startsWith("asset.") ||
    toolId.startsWith("references.") ||
    toolId.startsWith("timeline.") ||
    toolId.includes("library") ||
    toolId.includes("reference")
  ) {
    return "your project media";
  }
  if (
    toolId.startsWith("production_bible.") ||
    toolId.startsWith("script.") ||
    toolId.startsWith("continuity.") ||
    toolId.includes("bible")
  ) {
    return "saved project notes";
  }
  if (toolId.startsWith("scene.") || toolId.startsWith("character.") || toolId.startsWith("project.")) {
    return "the current project context";
  }
  return "project records";
}

export function stageForTool(toolId: string): StageId {
  if (toolId.startsWith("production_plan.")) return "plan";
  if (
    toolId.startsWith("asset.") ||
    toolId.startsWith("references.") ||
    toolId.startsWith("timeline.") ||
    toolId.includes("library") ||
    toolId.includes("reference")
  ) {
    return "media";
  }
  if (
    toolId.startsWith("production_bible.") ||
    toolId.startsWith("script.") ||
    toolId.startsWith("continuity.") ||
    toolId.includes("bible")
  ) {
    return "wiki";
  }
  return "context";
}

export function applyToolEvent(
  activity: CoDirectorActivityState,
  toolId: string,
  phase: "started" | "completed" | "failed",
  detail?: string,
): CoDirectorActivityState {
  const label = labelForTool(toolId);
  const topicalStageId = stageForTool(toolId);
  const topicalEventType =
    topicalStageId === "plan"
      ? "plan_review"
      : topicalStageId === "media"
        ? "media_review"
        : topicalStageId === "wiki"
          ? "wiki_review"
          : "context_review";
  let next = upsertStage(
    activity,
    stage(
      topicalStageId,
      topicalEventType,
      topicalStageId === "plan"
        ? "Reviewing the active plan"
        : topicalStageId === "media"
          ? "Reviewing your references"
          : topicalStageId === "wiki"
            ? "Checking saved project notes"
            : "Reviewing the current context",
      phase === "failed" ? "failed" : phase === "completed" ? "completed" : "active",
      detail,
    ),
  );
  next = upsertStage(
    next,
    stage(
      "tool",
      phase === "failed" ? "tool_failed" : phase === "completed" ? "tool_completed" : "tool_started",
      phase === "failed"
        ? `Couldn't finish checking ${label}`
        : phase === "completed"
          ? `Checked ${label}`
          : `Checking ${label}`,
      phase === "failed" ? "failed" : phase === "completed" ? "completed" : "active",
      detail,
    ),
  );
  if (next.toolLabels.includes(label)) return next;
  return { ...next, toolLabels: [...next.toolLabels, label] };
}

export function summarizeActivity(input: {
  uiContext: CoDirectorUIContext;
  manifest: CoDirectorContextManifest | null;
  attachmentsCount: number;
  stages: CoDirectorActivityStage[];
}): string[] {
  const hasCompletedStage = (id: CoDirectorActivityStage["id"]) =>
    input.stages.some((stageItem) => stageItem.id === id && stageItem.status == "completed");
  const facts: string[] = ["Worked from the current conversation."];
  if (input.uiContext.projectId) facts.push("Used the current project context.");
  if (input.uiContext.sceneName) facts.push(`Focused on scene "${input.uiContext.sceneName}".`);
  const workspaceLabel = normalizeWorkspaceLabel(input.uiContext.workspaceId);
  if (workspaceLabel) facts.push(`Worked from the ${workspaceLabel} workspace.`);
  if (input.manifest?.bibleVersionId || hasCompletedStage("wiki")) {
    facts.push("Checked saved project notes.");
  }
  if (input.attachmentsCount > 0) {
    facts.push(
      `Included ${input.attachmentsCount} attached reference${input.attachmentsCount === 1 ? "" : "s"}.`,
    );
  }
  if (hasCompletedStage("plan")) {
    facts.push("Reviewed the active plan.");
  }
  if (hasCompletedStage("tool")) {
    facts.push("Checked project records before replying.");
  }
  return Array.from(new Set(facts)).slice(0, 6);
}

export function shouldShowActivity(
  activity: CoDirectorActivityState | null,
  preference: CoDirectorActivityPreference,
): boolean {
  if (!activity || preference === "hidden") return false;
  if (preference === "always") return true;
  // Always show while a turn is in flight so creators see Processing feedback.
  if (activity.status === "running") return true;
  return activity.stages.some((stageItem) =>
    ["wiki", "media", "plan", "tool"].includes(stageItem.id),
  );
}
