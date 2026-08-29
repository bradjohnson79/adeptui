import { describe, expect, it } from "vitest";
import {
  TIMELINE_ZOOM_DEFAULT,
  TIMELINE_ZOOM_MAX,
  TIMELINE_ZOOM_MIN,
  clampTimelineZoom,
  pixelsPerSecond,
  sliderToZoom,
  stepTimelineZoom,
  zoomToSlider,
} from "./timelineZoom";

describe("timeline zoom authority", () => {
  it("clamps to 0.2x–5x", () => {
    expect(clampTimelineZoom(0.05)).toBe(TIMELINE_ZOOM_MIN);
    expect(clampTimelineZoom(9)).toBe(TIMELINE_ZOOM_MAX);
    expect(clampTimelineZoom(Number.NaN)).toBe(TIMELINE_ZOOM_DEFAULT);
    expect(clampTimelineZoom(1)).toBe(1);
  });

  it("log slider reaches both physical endpoints and 1x", () => {
    expect(sliderToZoom(0)).toBe(TIMELINE_ZOOM_MIN);
    expect(sliderToZoom(1)).toBe(TIMELINE_ZOOM_MAX);
    expect(sliderToZoom(zoomToSlider(1))).toBeCloseTo(1, 10);
    expect(sliderToZoom(zoomToSlider(TIMELINE_ZOOM_MIN))).toBeCloseTo(TIMELINE_ZOOM_MIN, 10);
    expect(sliderToZoom(zoomToSlider(TIMELINE_ZOOM_MAX))).toBeCloseTo(TIMELINE_ZOOM_MAX, 10);
  });

  it("pixels-per-second scales with zoom", () => {
    expect(pixelsPerSecond(1, 90)).toBe(90);
    expect(pixelsPerSecond(0.2, 90)).toBe(18);
    expect(pixelsPerSecond(5, 90)).toBe(450);
  });

  it("button steps are small and stay inside the authority", () => {
    const inOnce = stepTimelineZoom(1, 1);
    expect(inOnce).toBeGreaterThan(1);
    expect(inOnce).toBeLessThan(1.2);
    const outOnce = stepTimelineZoom(1, -1);
    expect(outOnce).toBeLessThan(1);
    expect(outOnce).toBeGreaterThan(0.8);
    expect(stepTimelineZoom(TIMELINE_ZOOM_MIN, -1)).toBe(TIMELINE_ZOOM_MIN);
    expect(stepTimelineZoom(TIMELINE_ZOOM_MAX, 1)).toBe(TIMELINE_ZOOM_MAX);
  });
});
