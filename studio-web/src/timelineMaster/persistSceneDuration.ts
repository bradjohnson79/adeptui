/**
 * Persist Scene.duration_sec as the creative clock, sync Timeline duration_sec,
 * then rematerialize H3/capability windows. Does not write batch plannedDuration.
 */
import { api } from "../api";
import type { TimelineBoardView } from "../components/DirectorTracks";
import { rematerializeSceneExecutionWindows } from "./rematerializeThenGenerate";
import { sanitizeSceneDurationSec } from "./sceneDurationAuthority";

export async function persistCanonicalSceneDuration(args: {
  projectId: string;
  sceneId: string;
  durationSec: number;
  generatorId?: string | null;
  mutateTimeline: (
    mutator: (timeline: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
}): Promise<Record<string, unknown>> {
  const sanitized = sanitizeSceneDurationSec(args.durationSec);
  if (!sanitized.ok) {
    return { ok: false, error: sanitized.error || "Enter how long this scene should be." };
  }
  await api.updateScene(args.projectId, args.sceneId, { duration_sec: sanitized.durationSec });
  await args.mutateTimeline((current) => ({ ...current, duration_sec: sanitized.durationSec }), {
    refresh: false,
  });
  return rematerializeSceneExecutionWindows({
    projectId: args.projectId,
    sceneId: args.sceneId,
    generatorId: args.generatorId,
    durationSeconds: sanitized.durationSec,
  });
}
