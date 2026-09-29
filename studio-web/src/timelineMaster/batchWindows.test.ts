import { describe, expect, it } from "vitest";
import {
  batchInTime,
  batchOutTime,
  batchWindowAtTime,
  buildBatchTimeWindows,
  resolveBoundedRepair,
  resolveBoundedRetake,
} from "./batchWindows";

const FIVE = [
  { id: "b1", order: 0, duration: { plannedDuration: 5 } },
  { id: "b2", order: 1, duration: { plannedDuration: 5 } },
  { id: "b3", order: 2, duration: { plannedDuration: 5 } },
];

describe("batch time windows", () => {
  it("uses plannedDuration, not a hardcoded 5", () => {
    const windows = buildBatchTimeWindows([
      { id: "a", order: 0, duration: { plannedDuration: 3.5 } },
      { id: "b", order: 1, duration: { plannedDuration: 8 } },
    ]);
    expect(windows).toEqual([
      { id: "a", start: 0, end: 3.5 },
      { id: "b", start: 3.5, end: 11.5 },
    ]);
  });

  it("Go to In/Out follow the Batch that contains the playhead", () => {
    const windows = buildBatchTimeWindows(FIVE);
    expect(batchInTime(windows, 2.8)).toBe(0);
    expect(batchOutTime(windows, 2.8, 15)).toBe(5);
    expect(batchInTime(windows, 7.2)).toBe(5);
    expect(batchOutTime(windows, 7.2, 15)).toBe(10);
    expect(batchInTime(windows, 13.4)).toBe(10);
    expect(batchOutTime(windows, 13.4, 15)).toBe(15);
  });

  it("a Batch boundary belongs to the later Batch, so In stays put", () => {
    const windows = buildBatchTimeWindows(FIVE);
    expect(batchWindowAtTime(windows, 5)?.id).toBe("b2");
    expect(batchInTime(windows, 5)).toBe(5);
    expect(batchOutTime(windows, 5, 15)).toBe(10);
    expect(batchInTime(windows, 0)).toBe(0);
    expect(batchInTime(windows, 15)).toBe(10);
    expect(batchOutTime(windows, 15, 15)).toBe(15);
  });

  it("clamps Out to Scene end", () => {
    const windows = buildBatchTimeWindows(FIVE);
    expect(batchOutTime(windows, 13.4, 14)).toBe(14);
  });

  it("maps a Re-take mark onto one Batch and refuses a cross-shot mark", () => {
    const windows = buildBatchTimeWindows(FIVE);
    const inside = resolveBoundedRetake(windows, 6.2, 1.5);
    expect(inside).toEqual({
      ok: true,
      batchId: "b2",
      start: 1.2,
      length: 1.5,
      sceneStart: 6.2,
      sceneEnd: 7.7,
    });
    const cross = resolveBoundedRetake(windows, 4.2, 2);
    expect(cross.ok).toBe(false);
    if (!cross.ok) expect(cross.error).toMatch(/one shot/i);
    const repair = resolveBoundedRepair(windows, 6.2, 1.5);
    expect(repair).toMatchObject({ ok: true, batchId: "b2", start: 1.2, length: 1.5 });
    const repairCross = resolveBoundedRepair(windows, 4.2, 2);
    expect(repairCross.ok).toBe(false);
  });
});
