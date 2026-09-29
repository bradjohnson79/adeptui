import { describe, expect, it } from "vitest";
import type { Job } from "../types";
import type { SceneTimelineMaster } from "./contracts";
import { activeTakeLineage, selectActiveSceneJob } from "./activeSceneJob";

function job(id: string, status: string, created: string): Job {
  return {
    id,
    project_id: "p",
    scene_id: "s",
    kind: "render_scene",
    status,
    progress: status === "done" ? 1 : 0.4,
    message: status,
    created_at: created,
    updated_at: created,
  };
}

function master(activeTakeId: string, jobs: Array<{ queueJobId: string; sceneTakeId: string }>): SceneTimelineMaster {
  return {
    activeSceneTakeId: activeTakeId,
    batchBlocks: [
      {
        generationJobs: jobs.map((row) => ({
          queueJobId: row.queueJobId,
          sceneTakeId: row.sceneTakeId,
          executionSnapshotId: "snap",
        })),
      },
    ],
  } as SceneTimelineMaster;
}

describe("selectActiveSceneJob", () => {
  it("follows the completed take job instead of a newer cancelled leftover", () => {
    const lineage = activeTakeLineage(
      master("take-b", [
        { queueJobId: "done-job", sceneTakeId: "take-b" },
        { queueJobId: "cancelled-leftover", sceneTakeId: "take-b" },
      ]),
    );
    const selected = selectActiveSceneJob(
      [
        job("done-job", "done", "2026-09-22T07:50:45"),
        job("cancelled-leftover", "cancelled", "2026-09-22T07:51:59"),
      ],
      lineage,
    );
    expect(selected?.id).toBe("done-job");
  });

  it("ignores a cancelled job from the previous take", () => {
    const lineage = activeTakeLineage(
      master("take-b", [
        { queueJobId: "old-cancel", sceneTakeId: "take-a" },
        { queueJobId: "live-b", sceneTakeId: "take-b" },
      ]),
    );
    const selected = selectActiveSceneJob(
      [
        job("old-cancel", "cancelled", "2026-09-22T08:01:30"),
        job("live-b", "running", "2026-09-22T08:10:00"),
      ],
      lineage,
    );
    expect(selected?.id).toBe("live-b");
  });

  it("shows an explicit cancel of the current take", () => {
    const lineage = activeTakeLineage(
      master("take-b", [{ queueJobId: "cancelled-b", sceneTakeId: "take-b" }]),
    );
    const selected = selectActiveSceneJob([job("cancelled-b", "cancelled", "2026-09-22T08:20:00")], lineage);
    expect(selected?.id).toBe("cancelled-b");
  });

  it("keeps the earliest live job when a duplicate is also queued", () => {
    const lineage = activeTakeLineage(
      master("take-b", [
        { queueJobId: "first", sceneTakeId: "take-b" },
        { queueJobId: "second", sceneTakeId: "take-b" },
      ]),
    );
    const selected = selectActiveSceneJob(
      [
        job("second", "queued", "2026-09-22T07:51:59"),
        job("first", "running", "2026-09-22T07:50:45"),
      ],
      lineage,
    );
    expect(selected?.id).toBe("first");
  });
});
