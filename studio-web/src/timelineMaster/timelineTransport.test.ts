import { describe, expect, it } from "vitest";
import { buildBatchTimeWindows } from "./batchWindows";
import { timelineBoardDurationSec } from "./generatorDuration";
import { resolveTimelineTransportBounds, sceneEndTime, sceneStartTime } from "./timelineTransport";

const MULTI = [
  { id: "b1", order: 0, duration: { plannedDuration: 8 } },
  { id: "b2", order: 1, duration: { plannedDuration: 10 } },
  { id: "b3", order: 2, duration: { plannedDuration: 7 } },
];

describe("canonical Timeline transport bounds", () => {
  it("uses first batch start as scene origin, not a hardcoded click handler zero", () => {
    const windows = buildBatchTimeWindows(MULTI);
    expect(sceneStartTime(windows)).toBe(0);
    expect(sceneStartTime([{ id: "late", start: 1.25, end: 4 }])).toBe(1.25);
    expect(sceneStartTime([])).toBe(0);
  });

  it("uses the board clock as scene end, not generator max or the selected batch", () => {
    const windows = buildBatchTimeWindows(MULTI);
    const board = timelineBoardDurationSec({ batchBlocks: MULTI }, { duration_sec: 99 }, { duration_sec: 5 });
    expect(board).toBe(25);
    expect(sceneEndTime(board)).toBe(25);
    const mid = resolveTimelineTransportBounds({
      windows,
      playheadSec: 12,
      boardDurationSec: board,
      selectedBatchId: "b2",
    });
    expect(mid.sceneStart).toBe(0);
    expect(mid.sceneEnd).toBe(25);
    expect(mid.activeBatchStart).toBe(8);
    expect(mid.activeBatchEnd).toBe(18);
    expect(mid.sceneEnd).not.toBe(mid.activeBatchEnd);
    expect(mid.sceneEnd).not.toBe(99);
  });

  it("keeps Scene Start/End distinct from Batch In/Out on a one-batch scene even when timestamps match", () => {
    const one = [{ id: "only", order: 0, duration: { plannedDuration: 8 } }];
    const windows = buildBatchTimeWindows(one);
    const board = timelineBoardDurationSec({ batchBlocks: one }, null, { duration_sec: 8 });
    const bounds = resolveTimelineTransportBounds({
      windows,
      playheadSec: 3,
      boardDurationSec: board,
    });
    expect(bounds.sceneStart).toBe(bounds.activeBatchStart);
    expect(bounds.sceneEnd).toBe(bounds.activeBatchEnd);
    expect(bounds.sceneStart).toBe(0);
    expect(bounds.sceneEnd).toBe(8);
  });

  it("falls back to playhead batch windows when no batch is selected", () => {
    const windows = buildBatchTimeWindows(MULTI);
    const atFirst = resolveTimelineTransportBounds({
      windows,
      playheadSec: 2,
      boardDurationSec: 25,
    });
    expect(atFirst.activeBatchStart).toBe(0);
    expect(atFirst.activeBatchEnd).toBe(8);
    expect(atFirst.sceneEnd).toBe(25);
  });

  it("ignores an unknown selected batch id and uses the playhead window", () => {
    const windows = buildBatchTimeWindows(MULTI);
    const bounds = resolveTimelineTransportBounds({
      windows,
      playheadSec: 20,
      boardDurationSec: 25,
      selectedBatchId: "missing",
    });
    expect(bounds.activeBatchStart).toBe(18);
    expect(bounds.activeBatchEnd).toBe(25);
  });

  it("grows scene end when a batch is added and shrinks when one is removed", () => {
    const two = MULTI.slice(0, 2);
    const afterAdd = timelineBoardDurationSec({ batchBlocks: MULTI }, null, { duration_sec: 8 });
    const afterRemove = timelineBoardDurationSec({ batchBlocks: two }, null, { duration_sec: 8 });
    expect(afterAdd).toBe(25);
    expect(afterRemove).toBe(18);
    expect(
      resolveTimelineTransportBounds({
        windows: buildBatchTimeWindows(two),
        playheadSec: 0,
        boardDurationSec: afterRemove,
      }).sceneEnd,
    ).toBe(18);
  });

  it("draft scenes without batches use the board fallback, not a generator cap", () => {
    const board = timelineBoardDurationSec(null, { duration_sec: 12 }, { duration_sec: 12 });
    const bounds = resolveTimelineTransportBounds({
      windows: [],
      playheadSec: 4,
      boardDurationSec: board,
    });
    expect(bounds.sceneStart).toBe(0);
    expect(bounds.sceneEnd).toBe(12);
    expect(bounds.activeBatchStart).toBe(0);
    expect(bounds.activeBatchEnd).toBe(12);
  });
});
