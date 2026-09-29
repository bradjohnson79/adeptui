/** Canonical Batch time windows — same cumulative plannedDuration clock as resolveBatchAtTime. */

export type BatchTimeWindow = {
  id: string;
  start: number;
  end: number;
};

type TimedBatch = {
  id: string;
  order: number;
  duration?: { plannedDuration?: number | null } | null;
};

export function buildBatchTimeWindows(batches: TimedBatch[] | null | undefined): BatchTimeWindow[] {
  const sorted = (batches || []).slice().sort((a, b) => a.order - b.order);
  const windows: BatchTimeWindow[] = [];
  let cursor = 0;
  for (const batch of sorted) {
    const length = Math.max(0.1, Number(batch.duration?.plannedDuration || 0));
    windows.push({ id: batch.id, start: cursor, end: cursor + length });
    cursor += length;
  }
  return windows;
}

/**
 * Half-open [start, end) so a boundary belongs to the later Batch.
 * Exact Scene end (t >= last.end) stays on the last Batch so Go to In does not walk backward.
 */
export function batchWindowAtTime(windows: BatchTimeWindow[], time: number): BatchTimeWindow | null {
  if (!windows.length) return null;
  const t = Number.isFinite(time) ? Math.max(0, time) : 0;
  for (const window of windows) {
    if (t >= window.start && t < window.end) return window;
  }
  const last = windows[windows.length - 1];
  if (t >= last.end) return last;
  return windows[0];
}

export function batchInTime(windows: BatchTimeWindow[], time: number): number {
  return batchWindowAtTime(windows, time)?.start ?? 0;
}

export function batchOutTime(windows: BatchTimeWindow[], time: number, sceneEnd: number): number {
  const cap = Math.max(0, sceneEnd);
  const window = batchWindowAtTime(windows, time);
  if (!window) return cap;
  return Math.min(cap, window.end);
}

export type BoundedRetake =
  | {
      ok: true;
      batchId: string;
      start: number;
      length: number;
      sceneStart: number;
      sceneEnd: number;
    }
  | { ok: false; error: string };

/** Map a scene-time mark onto one Batch. Crossing shots is refused. */
export function resolveBoundedRetake(
  windows: BatchTimeWindow[],
  start: number,
  length: number,
): BoundedRetake {
  const a = Math.min(start, start + length);
  const b = Math.max(start, start + length);
  if (b - a < 0.15) return { ok: false, error: "Mark a longer region to replace." };
  const first = batchWindowAtTime(windows, a + 1e-6);
  const last = batchWindowAtTime(windows, Math.max(a, b - 1e-6));
  if (!first || !last) return { ok: false, error: "Mark a region on a shot." };
  if (first.id !== last.id) {
    return { ok: false, error: "Mark a region inside one shot. This edit cannot cross shots." };
  }
  const startInBatch = Math.max(0, a - first.start);
  const endInBatch = Math.min(first.end - first.start, b - first.start);
  const clipped = endInBatch - startInBatch;
  if (clipped < 0.15) return { ok: false, error: "Mark a longer region to replace." };
  const startRounded = Math.round(startInBatch * 1000) / 1000;
  const lengthRounded = Math.round(clipped * 1000) / 1000;
  return {
    ok: true,
    batchId: first.id,
    start: startRounded,
    length: lengthRounded,
    sceneStart: Math.round((first.start + startRounded) * 1000) / 1000,
    sceneEnd: Math.round((first.start + startRounded + lengthRounded) * 1000) / 1000,
  };
}

/** Same batch mapping as Re-take. Repair cannot cross shots. */
export function resolveBoundedRepair(
  windows: BatchTimeWindow[],
  start: number,
  length: number,
): BoundedRetake {
  const resolved = resolveBoundedRetake(windows, start, length);
  if (resolved.ok) return resolved;
  return {
    ok: false,
    error: resolved.error.replace("Re-take", "Repair").replace("replace", "repair"),
  };
}
