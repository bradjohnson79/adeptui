import { describe, expect, it } from "vitest";
import { timelineActionError, timelineGenerateEmpty } from "./timelineErrors";

describe("timelineActionError", () => {
  it("reads message fields out of error objects", () => {
    expect(
      timelineActionError({
        ok: false,
        errors: [
          {
            batchBlockId: "bb1",
            error: "DURATION_EXCEEDS_GENERATOR",
            message: "Planned duration 16s exceeds MiniMax H3 max 15s — no silent truncate.",
            plannedDuration: 16,
            maxDurationSec: 15,
          },
        ],
      }),
    ).toBe("This shot is 16s. The selected engine can run up to 15s. Shorten it or split it into batches.");
  });

  it("does not stringify objects as [object Object]", () => {
    const text = timelineActionError({
      ok: false,
      errors: [{ batchBlockId: "bb1", error: "GENERATOR_UNKNOWN", message: "Engine missing." }],
    });
    expect(text).toBe("Engine missing.");
    expect(text).not.toContain("[object Object]");
  });

  it("treats a success with no jobs as empty", () => {
    expect(timelineGenerateEmpty({ ok: true, jobs: [], message: "Scene generation submitted." })).toBe(true);
    expect(timelineGenerateEmpty({ ok: true, jobs: [{ id: "j1" }] })).toBe(false);
    expect(timelineGenerateEmpty({ ok: false, jobs: [] })).toBe(false);
  });
});
