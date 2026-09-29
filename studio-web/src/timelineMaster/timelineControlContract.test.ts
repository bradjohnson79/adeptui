import { describe, expect, it } from "vitest";
import { clampTimelineZoom, sliderToZoom, zoomToSlider } from "./timelineZoom";
import { magneticSnapTime, buildMagneticSnapTargets } from "./magneticSnap";
import { creatorGeneratorLine } from "./generatorDuration";

describe("timeline control contract", () => {
  it("Snap identity is a boolean gate over magnetic targets", () => {
    const targets = buildMagneticSnapTargets({
      sceneEnd: 5,
      batches: [{ id: "b1", start: 0, length: 5, label: "Batch 1" }],
      clips: [],
    });
    expect(magneticSnapTime(4.96, targets, 200, false).target).toBeNull();
    expect(magneticSnapTime(4.96, targets, 200, true).target?.kind).toBe("batch");
  });

  it("Zoom identity is one authority from 0.2x to 5x", () => {
    expect(clampTimelineZoom(0.2)).toBe(0.2);
    expect(clampTimelineZoom(5)).toBe(5);
    expect(sliderToZoom(0)).toBe(0.2);
    expect(sliderToZoom(1)).toBe(5);
    expect(zoomToSlider(1)).toBeGreaterThan(0.3);
    expect(zoomToSlider(1)).toBeLessThan(0.7);
  });

  it("Video Generator identity is capability-driven creator copy", () => {
    expect(
      creatorGeneratorLine({
        label: "LTX 2.5 (Local)",
        executionType: "local",
        supportedDurations: [5, 8, 10, 15, 20],
      }),
    ).toBe("LTX 2.5 — Local · 20s");
  });
});
