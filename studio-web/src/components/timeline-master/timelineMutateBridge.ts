import type { DirectorTimeline } from "../DirectorTracks";

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

let boundTimeline: DirectorTimeline | null = null;
type SnapshotListener = (timeline: DirectorTimeline | null) => void;
const snapshotListeners = new Set<SnapshotListener>();

export function bindShellTimelineSnapshot(timeline: DirectorTimeline | null): void {
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

export function getBoundShellTimeline(): DirectorTimeline | null {
  return boundTimeline;
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
