import { describe, expect, it } from "vitest";
import { nextTimelineBatchPayload } from "./addTimelineBatch";
import type { SceneTimelineMaster } from "./contracts";

describe("nextTimelineBatchPayload", () => {
  it("copies the last planned duration and names the next batch", () => {
    const master = {
      batchBlocks: [
        { order: 1, duration: { plannedDuration: 8 }, label: "Batch 1" },
        { order: 0, duration: { plannedDuration: 5 }, label: "Batch 2" },
      ],
    } as unknown as SceneTimelineMaster;
    expect(nextTimelineBatchPayload(master)).toEqual({ plannedDuration: 8, label: "Batch 3" });
  });

  it("defaults to H3 15s when the timeline has no batches", () => {
    expect(nextTimelineBatchPayload(null)).toEqual({ plannedDuration: 15, label: "Batch 1" });
    expect(nextTimelineBatchPayload(null, "minimax-h3")).toEqual({ plannedDuration: 15, label: "Batch 1" });
  });

  it("defaults to LTX 20s when engine is LTX and there are no batches", () => {
    expect(nextTimelineBatchPayload(null, "ltx-2.5")).toEqual({ plannedDuration: 20, label: "Batch 1" });
  });
});
