import { describe, expect, it } from "vitest";
import {
  TIMELINE_SCALE_MIN_TAIL_SEC,
  nextTimelineScaleExtraSec,
  timelineRulerTickStepSec,
  timelineRulerTicks,
  timelineScaleShouldGrow,
  timelineSequenceSec,
  timelineViewportSec,
  timelineVisibleScaleSec,
} from "./timelineVisibleScale";

describe("Premiere-style Timeline scale", () => {
  it("keeps a 15s H3 sequence from being the counter end", () => {
    expect(timelineSequenceSec(15, 15)).toBe(15);
    const scale = timelineVisibleScaleSec({ sequenceSec: 15 });
    expect(scale).toBe(15 + TIMELINE_SCALE_MIN_TAIL_SEC);
    expect(scale).toBeGreaterThan(15);
    expect(timelineRulerTicks(scale, 1).some((t) => t > 15)).toBe(true);
  });

  it("has no 15/20/30/120 product cap — extra growth keeps going", () => {
    let extra = 0;
    for (let i = 0; i < 8; i += 1) {
      extra = nextTimelineScaleExtraSec(extra, 40);
    }
    const scale = timelineVisibleScaleSec({ sequenceSec: 15, viewportSec: 12, extraSec: extra });
    expect(scale).toBeGreaterThan(120);
    expect(Number.isFinite(scale)).toBe(true);
  });

  it("uses the viewport as a tail when it is longer than the minimum", () => {
    expect(timelineViewportSec(900, 90)).toBe(10);
    expect(timelineVisibleScaleSec({ sequenceSec: 8, viewportSec: 40 })).toBe(48);
  });

  it("grows when the creator scrolls near the right edge", () => {
    expect(
      timelineScaleShouldGrow({
        scrollLeftPx: 3600,
        viewportPx: 800,
        boardWidthPx: 4200,
      }),
    ).toBe(true);
    expect(
      timelineScaleShouldGrow({
        scrollLeftPx: 0,
        viewportPx: 800,
        boardWidthPx: 4200,
      }),
    ).toBe(false);
  });

  it("thins ruler ticks when zoomed out", () => {
    expect(timelineRulerTickStepSec(90)).toBe(1);
    expect(timelineRulerTickStepSec(18)).toBe(5);
    expect(timelineRulerTicks(10, 5)).toEqual([0, 5, 10]);
  });
});
