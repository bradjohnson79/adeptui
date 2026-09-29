import { api } from "../api";
import { defaultNewSceneDurationSec } from "../components/timelineSceneDuration";
import type { SceneTimelineMaster } from "./contracts";

export function nextTimelineBatchPayload(
  master: SceneTimelineMaster | null | undefined,
  engine?: string | null,
): {
  plannedDuration: number;
  label: string;
} {
  const batches = (master?.batchBlocks || []).slice().sort((a, b) => a.order - b.order);
  const lastPlanned = Number(batches.at(-1)?.duration?.plannedDuration || 0);
  const seed = lastPlanned > 0 ? lastPlanned : defaultNewSceneDurationSec(engine || master?.sceneGeneratorId);
  return {
    plannedDuration: seed,
    label: `Batch ${batches.length + 1}`,
  };
}

export async function addTimelineBatch(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster | null | undefined,
) {
  return api.directorTimelineAddBatch(projectId, sceneId, nextTimelineBatchPayload(master));
}
