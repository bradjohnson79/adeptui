import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Spatial Map Standard three-route start chooser", () => {
  const src = readFileSync(new URL("./SpatialMapStartChooser.tsx", import.meta.url), "utf8");

  it("presents design, reconstruct, and existing Atlas as separate methods", () => {
    expect(src).toContain("Create Environment with Co-Director");
    expect(src).toContain("Reconstruct from Location Image");
    expect(src).toContain("Use Existing Spatial Map");
    expect(src).toContain("Upload Spatial Map");
    expect(src).toContain("no generation");
    expect(src).toContain("Paid API");
    expect(src).toContain("Free / Local");
    expect(src).toContain("Recommended");
    expect(src).not.toContain("Improve Spatial Understanding");
    expect(src).not.toContain("Qwen");
  });

  it("does not treat Recommended as mandatory", () => {
    expect(src).toContain("gptConfigured");
    expect(src).toContain("spatial-map-recommended-badge");
    expect(src).toContain("You can use the free local reconstruction method");
  });
});
