import type { DirectorTimeline } from "../DirectorTracks";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";

/**
 * Bridge so Timeline clip modals (mounted on DirectorTracks) can write through
 * the same shell `mutateTimeline` that TimelineInspector already uses.
 * Inspector registers the live function; no second clip store.
 */
export type TimelineMutateFn = (
  mutator: (timeline: DirectorTimeline) => DirectorTimeline,
  opts?: { refresh?: boolean },
) => Promise<void>;

let bound: TimelineMutateFn | null = null;

export function bindShellTimelineMutate(fn: TimelineMutateFn | null): void {
  bound = fn;
}

export function getBoundShellTimelineMutate(): TimelineMutateFn | null {
  return bound;
}

let inspectingPromptId: string | null = null;
type InspectListener = (id: string | null) => void;
const inspectListeners = new Set<InspectListener>();

export function bindInspectingPrompt(id: string | null): void {
  inspectingPromptId = id;
  for (const listener of inspectListeners) listener(id);
}

export function getInspectingPrompt(): string | null {
  return inspectingPromptId;
}

export function subscribeInspectingPrompt(listener: InspectListener): () => void {
  inspectListeners.add(listener);
  listener(inspectingPromptId);
  return () => {
    inspectListeners.delete(listener);
  };
}

export function dropPromptIdsFromMaster(
  master: SceneTimelineMaster,
  ids: Iterable<string>,
): SceneTimelineMaster {
  const removed = new Set(Array.from(ids).filter(Boolean));
  if (!removed.size) return master;
  return {
    ...master,
    batchBlocks: master.batchBlocks.map((batch) => ({
      ...batch,
      promptSegments: (batch.promptSegments || []).filter(
        (seg) => !removed.has(seg.id) && !removed.has(seg.legacyPromptSegmentId || ""),
      ),
    })),
  };
}
