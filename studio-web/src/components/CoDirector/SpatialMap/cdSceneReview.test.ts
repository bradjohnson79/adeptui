import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("CD Scene Review chrome", () => {
  it("is labeled CD Scene Review, not Auto Map", () => {
    const src = readFileSync(new URL("./CdSceneReview.tsx", import.meta.url), "utf8");
    expect(src).toContain("CD Scene Review");
    expect(src).toContain("Review this scene");
    expect(src).toContain('data-testid="cd-scene-review"');
    expect(src).not.toMatch(/Auto Map/);
    expect(src).toContain("inFlight.current");
    expect(src).toContain("SCENE_REVIEW_START_FAILED");
    expect(src).toContain("cd-scene-review-retry");
    expect(src).not.toContain("err instanceof Error ? err.message");
  });

  it("keeps manual 4+4+4 slots on the Spatial Map", () => {
    const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");
    expect(panel).toContain("CdSceneReview");
    expect(panel).toContain("spatial-map__slots");
    expect(panel).toContain("CHARACTER_SLOTS.map");
    expect(panel).toContain("PROP_SLOTS.map");
  });
});
