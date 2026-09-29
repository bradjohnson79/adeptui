import type { TimelineBoardView } from "../DirectorTracks";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { applyPromptRemovalToMaster } from "../../timelineMaster/masterTimelineMutate";

/**
 * Bridge so Timeline clip modals (mounted on DirectorTracks) can write through
 * the same shell `mutateTimeline` that TimelineInspector already uses.
 * Inspector registers the live function; no second clip store.
 */
export type TimelineMutateFn = (
  mutator: (timeline: TimelineBoardView) => TimelineBoardView,
  opts?: { refresh?: boolean },
) => Promise<void>;

let bound: TimelineMutateFn | null = null;

export function bindShellTimelineMutate(fn: TimelineMutateFn | null): void {
  bound = fn;
}

export function getBoundShellTimelineMutate(): TimelineMutateFn | null {
  return bound;
}

let boundTimeline: TimelineBoardView | null = null;
type SnapshotListener = (timeline: TimelineBoardView | null) => void;
const snapshotListeners = new Set<SnapshotListener>();

export function bindShellTimelineSnapshot(timeline: TimelineBoardView | null): void {
  boundTimeline = timeline;
  for (const listener of snapshotListeners) listener(timeline);
}

export function subscribeShellTimelineSnapshot(listener: SnapshotListener): () => void {
  snapshotListeners.add(listener);
  listener(boundTimeline);
  return () => {
    snapshotListeners.delete(listener);
  };
}

export function getBoundShellTimeline(): TimelineBoardView | null {
  return boundTimeline;
}

/** Copy shared Timed Prompt fields from the shell snapshot onto track memory.
 *
 * SINGLE-STORE: legacy promptSegments merge is retired. This is a no-op
 * pass-through kept only for import compatibility during the transition; new
 * code must read Master batch.promptSegments directly.
 */
export function applyShellPromptSnapshot(
  memory: TimelineBoardView,
  _snapshot: TimelineBoardView,
): TimelineBoardView {
  return memory;
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

let promptSelectionUnlockAt = 0;

/** Chrome (drawer handle, inspector tabs) must not steal the selected clip. */
export function lockPromptSelection(ms = 750): void {
  promptSelectionUnlockAt = Date.now() + ms;
}

export function isPromptSelectionLocked(): boolean {
  return Date.now() < promptSelectionUnlockAt;
}

export function dropPromptIdsFromMaster(
  master: SceneTimelineMaster,
  ids: Iterable<string>,
): SceneTimelineMaster {
  // Canonical pure helper — same contract as Toolbar / Delete / CD Master remove.
  return applyPromptRemovalToMaster(master, ids);
}
