import type { Job } from "../types";
import type { SceneTimelineMaster } from "./contracts";

export type TakeJobLineage = {
  queueJobId: string;
  sceneTakeId: string;
  executionSnapshotId: string;
};

const LIVE = new Set(["queued", "running", "pending", "submitted", "cancelling"]);

export function activeTakeLineage(master: SceneTimelineMaster | null | undefined): TakeJobLineage[] {
  if (!master) return [];
  const focus = String(master.activeSceneTakeId || master.currentSceneTakeId || "");
  const rows: TakeJobLineage[] = [];
  for (const batch of master.batchBlocks || []) {
    for (const job of batch.generationJobs || []) {
      const queueJobId = String(job.queueJobId || "");
      if (!queueJobId) continue;
      const sceneTakeId = String(job.sceneTakeId || "");
      if (focus && sceneTakeId && sceneTakeId !== focus) continue;
      rows.push({
        queueJobId,
        sceneTakeId,
        executionSnapshotId: String(job.executionSnapshotId || ""),
      });
    }
  }
  return rows;
}

function byCreated(a: Job, b: Job): number {
  return String(a.created_at || "").localeCompare(String(b.created_at || ""));
}

/**
 * The Preview follows the active take's job.
 * A newer cancelled leftover from another take, or a duplicate of the same
 * snapshot, does not replace a live or completed job for the current take.
 * Newest-job ordering is only the fallback when this scene has no take linkage.
 */
export function selectActiveSceneJob(sceneJobs: Job[], lineage: TakeJobLineage[]): Job | null {
  if (!lineage.length) {
    const live = sceneJobs.find((job) => LIVE.has(String(job.status || "").toLowerCase()));
    if (live) return live;
    return sceneJobs.slice().sort((a, b) => byCreated(b, a))[0] || null;
  }
  const ids = new Set(lineage.map((row) => row.queueJobId));
  const owned = sceneJobs.filter((job) => ids.has(job.id));
  if (!owned.length) {
    const live = sceneJobs.find((job) => LIVE.has(String(job.status || "").toLowerCase()));
    if (live) return live;
    return null;
  }
  const live = owned.filter((job) => LIVE.has(String(job.status || "").toLowerCase())).sort(byCreated);
  if (live.length) return live[0];
  const finished = owned
    .filter((job) => {
      const status = String(job.status || "").toLowerCase();
      return status === "done" || status === "completed";
    })
    .sort((a, b) => byCreated(b, a));
  if (finished.length) return finished[0];
  const failed = owned
    .filter((job) => String(job.status || "").toLowerCase() === "failed")
    .sort((a, b) => byCreated(b, a));
  if (failed.length) return failed[0];
  return owned.slice().sort((a, b) => byCreated(b, a))[0] || null;
}
