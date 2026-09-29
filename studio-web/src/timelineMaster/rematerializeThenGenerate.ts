/**
 * Creator generate path: rematerialize execution windows from CD plan / duration,
 * then queue scene generate. No manual batchCount / Add Batch.
 * HARD LOCK: generator/topology switch requires new SceneTake before rematerialize.
 */
import { api } from "../api";

export type RematerializeThenGenerateArgs = {
  projectId: string;
  sceneId: string;
  generatorId?: string | null;
  durationSeconds?: number | null;
  draftMode?: boolean;
  /** Saved window text is on Master before Generate. Show it before the scene is treated as generating. */
  beforeGenerate?: (rematerialize: Record<string, unknown>) => Promise<void> | void;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export async function rematerializeSceneExecutionWindows(
  args: Omit<RematerializeThenGenerateArgs, "draftMode">,
): Promise<Record<string, unknown>> {
  const { projectId, sceneId } = args;
  const generatorId = String(args.generatorId || "").trim() || undefined;
  const durationSeconds =
    typeof args.durationSeconds === "number" && Number.isFinite(args.durationSeconds)
      ? args.durationSeconds
      : undefined;

  let remat = asRecord(
    await api.directorTimelineRematerializeExecutionWindows(projectId, sceneId, {
      generatorId,
      durationSeconds,
    }),
  );

  if (
    remat.ok === false &&
    (remat.error === "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE" || remat.requiresNewSceneTake === true)
  ) {
    const previousSceneTakeId = String(
      remat.currentSceneTakeId || remat.activeSceneTakeId || remat.previousSceneTakeId || "",
    ).trim() || undefined;
    const minted = asRecord(
      await api.directorTimelineBeginExecutionRevision(projectId, sceneId, {
        reason: "generator_switch_window_topology_change",
      }),
    );
    const takeRec = asRecord(minted.take);
    const masterRec = asRecord(minted.master);
    const allowSceneTakeId = String(
      minted.currentSceneTakeId ||
        minted.takeId ||
        takeRec.id ||
        minted.id ||
        masterRec.currentSceneTakeId ||
        "",
    ).trim();
    if (!allowSceneTakeId) {
      return {
        ok: false,
        error: "SCENE_TAKE_MINT_FAILED",
        message: String(minted.message || minted.error || "Could not mint a new SceneTake before rematerialize."),
        rematerialize: remat,
        sceneTake: minted,
      };
    }
    remat = asRecord(
      await api.directorTimelineRematerializeExecutionWindows(projectId, sceneId, {
        generatorId,
        durationSeconds,
        allowSceneTakeId,
        previousSceneTakeId,
      }),
    );
  }

  return remat;
}

export async function rematerializeThenGenerateScene(
  args: RematerializeThenGenerateArgs,
): Promise<Record<string, unknown>> {
  const remat = await rematerializeSceneExecutionWindows(args);
  if (remat.ok === false) {
    return remat;
  }
  if (args.beforeGenerate) {
    await args.beforeGenerate(remat);
  }

  const generate = asRecord(
    await api.directorTimelineGenerateScene(args.projectId, args.sceneId, {
      scope: "full",
      draftMode: args.draftMode,
    }),
  );
  return { ...generate, rematerialize: remat };
}
