/**
 * Canonical Timeline transport bounds.
 *
 * One board clock:
 *   sceneStart  = first batch window start (0 unless the architecture has a
 *                 non-zero origin)
 *   sceneEnd    = timelineBoardDurationSec — never generator.maxDuration,
 *                 never the selected batch end unless that is also the scene
 *   activeBatch = selected batch when a batch is selected, else the window
 *                 that contains the playhead (existing Batch In/Out)
 *
 * Seek commands consume these numbers. They do not invent a second duration.
 */
import { batchInTime, batchOutTime, type BatchTimeWindow } from "./batchWindows";

export type TimelineTransportBounds = {
  sceneStart: number;
  sceneEnd: number;
  activeBatchStart: number;
  activeBatchEnd: number;
};

export function sceneStartTime(windows: BatchTimeWindow[]): number {
  return windows[0]?.start ?? 0;
}

export function sceneEndTime(boardDurationSec: number): number {
  return Math.max(0, Number(boardDurationSec) || 0);
}

export function resolveTimelineTransportBounds(input: {
  windows: BatchTimeWindow[];
  playheadSec: number;
  boardDurationSec: number;
  selectedBatchId?: string | null;
}): TimelineTransportBounds {
  const windows = input.windows || [];
  const sceneStart = sceneStartTime(windows);
  const sceneEnd = sceneEndTime(input.boardDurationSec);
  const selected = input.selectedBatchId
    ? windows.find((window) => window.id === input.selectedBatchId)
    : undefined;
  const playhead = Number.isFinite(input.playheadSec) ? input.playheadSec : sceneStart;
  return {
    sceneStart,
    sceneEnd,
    activeBatchStart: selected ? selected.start : batchInTime(windows, playhead),
    activeBatchEnd: selected ? Math.min(sceneEnd, selected.end) : batchOutTime(windows, playhead, sceneEnd),
  };
}
