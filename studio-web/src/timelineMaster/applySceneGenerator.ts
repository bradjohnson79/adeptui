/** Shared persist path for Timeline Video Generator (dock + Inspector). */

import { api } from "../api";
import type { Scene } from "../types";
import type { SceneTimelineMaster } from "./contracts";
import type { TimelineBoardView } from "../components/DirectorTracks";
import { nextTurboLoraState, resolveGeneratorOption, type TimelineGeneratorOption } from "./draftCapabilities";
import {
  generatorMaxDurationSec,
  timelineBoardDurationSec,
  trimClipsToDuration,
} from "./generatorDuration";
import { timelineActionError } from "./timelineErrors";

export function collectTimedClips(timeline: TimelineBoardView | null): Array<{ start: number; length: number }> {
  if (!timeline) return [];
  // SINGLE-STORE: prompt segments live in Master batch.promptSegments, not
  // legacy promptSegments. Overflow/duration checks use media clips only.
  return [
    ...(timeline.imageClips || []),
    ...(timeline.videoClips || []),
    ...(timeline.cameraClips || []),
    ...(timeline.audioClips || []),
    ...(timeline.sfxClips || []),
    ...(timeline.lipsync?.tracks || []).flatMap((track) => track.clips || []),
  ];
}

function collectMediaTimedClips(timeline: TimelineBoardView | null): Array<{ start: number; length: number }> {
  if (!timeline) return [];
  return [
    ...(timeline.imageClips || []),
    ...(timeline.videoClips || []),
    ...(timeline.cameraClips || []),
    ...(timeline.audioClips || []),
    ...(timeline.sfxClips || []),
    ...(timeline.lipsync?.tracks || []).flatMap((track) => track.clips || []),
  ];
}

export function sceneWouldOverflow(
  timeline: TimelineBoardView | null,
  master: SceneTimelineMaster | null,
  scene: Scene,
  maxSec: number | null,
): boolean {
  if (maxSec == null) return false;
  void scene;
  const clips = collectMediaTimedClips(timeline);
  if (clips.some((clip) => clip.start + clip.length > maxSec + 1e-6) && (master?.batchBlocks.length || 1) <= 1) {
    return true;
  }
  if (clips.some((clip) => clip.length > maxSec + 1e-6)) return true;
  if ((master?.batchBlocks || []).some((batch) => (batch.duration.plannedDuration || 0) > maxSec + 1e-6)) return true;
  return false;
}

/** Align legacy scene.engine token with the product id — identity only, not duration. */
export function sceneEngineForGenerator(generatorId: string): Scene["engine"] | undefined {
  const id = String(generatorId || "").toLowerCase();
  if (!id) return undefined;
  if (id.startsWith("minimax-h3")) return "minimax-h3";
  if (id.startsWith("ltx-2.5") || id === "ltx-2.5") return "ltx-2.5";
  if (id.includes("seedance-2.5") || id.includes("fal_seedance_25")) return "seedance-2.5";
  if (id.includes("seedance")) return "seedance-2.0";
  if (id.includes("kling")) return "fal_kling";
  if (id.includes("veo")) return "fal_veo";
  if (id.includes("runway")) return "fal_runway";
  return undefined;
}

export async function applyTimelineSceneGenerator(args: {
  projectId: string;
  scene: Scene;
  master: SceneTimelineMaster | null;
  timeline: TimelineBoardView | null;
  options: TimelineGeneratorOption[];
  generatorId: string;
  trim: boolean;
  mutateTimeline: (
    mutator: (current: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
  onRefresh: () => void | Promise<void>;
}): Promise<void> {
  const option = resolveGeneratorOption(args.options, args.generatorId);
  const maxSec = generatorMaxDurationSec(option);
  const boardSec = timelineBoardDurationSec(args.master, args.timeline, args.scene);
  // Inspector / scene duration is authority. Switching generators must not
  // overwrite it unless the creator asked to trim an overflow.
  const nextDuration =
    args.trim && maxSec != null
      ? Math.min(boardSec || args.scene.duration_sec || maxSec, maxSec)
      : args.scene.duration_sec;
  if (args.trim && maxSec != null) {
    // SINGLE-STORE: trim media clips only. Master promptSegments are scene-
    // absolute and are not trimmed by generator duration caps.
    await args.mutateTimeline(
      (current) => ({
        ...current,
        duration_sec: nextDuration,
        imageClips: trimClipsToDuration(current.imageClips || [], maxSec),
        videoClips: trimClipsToDuration(current.videoClips || [], maxSec),
        cameraClips: trimClipsToDuration(current.cameraClips || [], maxSec),
        audioClips: trimClipsToDuration(current.audioClips || [], maxSec),
        sfxClips: trimClipsToDuration(current.sfxClips || [], maxSec),
      }),
      { refresh: false },
    );
  }
  const engine = sceneEngineForGenerator(args.generatorId);
  const scenePatch: Partial<Scene> = {};
  if (args.trim && Math.abs((args.scene.duration_sec || 0) - nextDuration) > 1e-6) {
    scenePatch.duration_sec = nextDuration;
  }
  if (engine && engine !== args.scene.engine) {
    scenePatch.engine = engine;
  }
  if (Object.keys(scenePatch).length) {
    await api.updateScene(args.projectId, args.scene.id, scenePatch);
  }
  if (args.master) {
  // Systems P5: put_master mints a fresh SceneTake (stk_) + bumps timelineRevision
  // when sceneGeneratorId / batch window topology changes. Same stk_ must not keep
  // VCM continuity across a generator switch — FE must refresh master after save.
    const saved = await api.directorTimelinePutMaster(args.projectId, args.scene.id, {
      ...args.master,
      sceneGeneratorId: args.generatorId,
      turboLora: nextTurboLoraState(args.master.turboLora, option),
      batchBlocks: args.master.batchBlocks.map((batch) => ({
        ...batch,
        generatorId: args.generatorId,
        duration: {
          ...batch.duration,
          plannedDuration:
            args.trim && maxSec != null
              ? Math.min(batch.duration.plannedDuration || maxSec, maxSec)
              : batch.duration.plannedDuration,
        },
      })),
    });
    const persistError = timelineActionError(saved);
    if (persistError) throw new Error(persistError);
  }
  await args.onRefresh();
}

export async function applyTimelineTurboLora(args: {
  projectId: string;
  sceneId: string;
  master: SceneTimelineMaster;
  options: TimelineGeneratorOption[];
  enabled: boolean;
  onRefresh: () => void | Promise<void>;
}): Promise<void> {
  const option = resolveGeneratorOption(
    args.options,
    args.master.sceneGeneratorId,
    args.master.batchBlocks[0]?.generatorId,
  );
  const turboLora = nextTurboLoraState(args.enabled, option);
  const saved = await api.directorTimelinePutMaster(args.projectId, args.sceneId, {
    ...args.master,
    turboLora,
  });
  const persistError = timelineActionError(saved);
  if (persistError) throw new Error(persistError);
  await args.onRefresh();
}
