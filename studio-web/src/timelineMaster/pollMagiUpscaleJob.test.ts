import { describe, expect, it } from "vitest";
import { jobAssetId, parseJobHistory } from "./pollMagiUpscaleJob";

describe("MAGI upscale job history", () => {
  it("parses JSON history and finds the derived asset id after completion", () => {
    const history = parseJobHistory(JSON.stringify({ ok: true, assetId: "up-9" }));
    expect(history.ok).toBe(true);
    expect(jobAssetId(history)).toBe("up-9");
  });

  it("does not treat a queued job as a finished asset", () => {
    expect(jobAssetId(parseJobHistory({ queued: true, jobId: "j1" }))).toBeNull();
  });
});
