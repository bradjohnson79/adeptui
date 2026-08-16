import { describe, expect, it } from "vitest";
import { normalizeJobProgress } from "./normalizeJobProgress";

describe("normalizeJobProgress", () => {
  it("is indeterminate for coarse Comfy 0.2 queued bucket", () => {
    const n = normalizeJobProgress({ status: "queued", progress: 0.2, stage: "queued", message: "Queued" });
    expect(n.indeterminate).toBe(true);
    expect(n.progressPercent).toBeNull();
    expect(n.stage).toBe("Queued");
    expect(n.genuineSampler).toBe(false);
  });

  it("is indeterminate for coarse Comfy 0.55 running bucket", () => {
    const n = normalizeJobProgress({ status: "running", progress: 0.55, stage: "running", message: "Generating" });
    expect(n.indeterminate).toBe(true);
    expect(n.progressPercent).toBeNull();
    expect(n.stage).toBe("Generating");
    expect(n.genuineSampler).toBe(false);
  });

  it("does not invent 53 from a non-sampler progress value", () => {
    const n = normalizeJobProgress({ status: "running", progress: 0.53, stage: "running", message: "working" });
    expect(n.progressPercent).toBeNull();
    expect(n.indeterminate).toBe(true);
    expect(n.genuineSampler).toBe(false);
  });

  it("does not treat Kie fake +0.02 drift as a real percent", () => {
    const n = normalizeJobProgress({ status: "running", progress: 0.24, stage: "polling", message: "waiting" });
    expect(n.progressPercent).toBeNull();
    expect(n.indeterminate).toBe(true);
    expect(n.genuineSampler).toBe(false);
  });

  it("returns 100 on complete", () => {
    const n = normalizeJobProgress({ status: "done", progress: 1, stage: "completed", message: "saved" });
    expect(n.status).toBe("completed");
    expect(n.progressPercent).toBe(100);
    expect(n.indeterminate).toBe(false);
    expect(n.stage).toBe("Complete");
  });

  it("uses genuine sampler N/M from preview_json", () => {
    const n = normalizeJobProgress({
      status: "running",
      progress: 0.46,
      stage: "sampling",
      preview_json: JSON.stringify({ current_step: 14, total_steps: 30 }),
    });
    expect(n.genuineSampler).toBe(true);
    expect(n.indeterminate).toBe(false);
    expect(n.progressPercent).toBe(47);
    expect(n.stage).toContain("14/30");
  });

  it("uses labeled sampler text and ignores coarse buckets", () => {
    const n = normalizeJobProgress({
      status: "running",
      progress: 0.55,
      stage: "sampling 3/20",
      message: "sampling 3/20",
    });
    expect(n.genuineSampler).toBe(true);
    expect(n.progressPercent).toBe(15);
    expect(n.stage).toContain("3/20");
  });

  it("forwards preview url and final asset when present", () => {
    const n = normalizeJobProgress({
      status: "done",
      progress: 1,
      asset_id: "asset-final",
      preview_json: JSON.stringify({ preview_url: "http://example/preview.png" }),
    });
    expect(n.finalAssetId).toBe("asset-final");
    expect(n.previewUrl).toBe("http://example/preview.png");
  });
});
