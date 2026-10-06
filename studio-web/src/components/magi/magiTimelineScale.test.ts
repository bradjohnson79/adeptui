import { describe, expect, it } from "vitest";
import { visualRulerTicks } from "../../filmTimeline/visualTrack";
import {
  MAGI_BASE_PX_PER_FRAME,
  MAGI_MIN_CONTENT_PX,
  MAGI_TRACK_LABEL_WIDTH,
  clampMagiZoom,
  magiClampFrame,
  magiContentWidth,
  magiFrameSheetX,
  magiPlayheadLeft,
  magiPxPerFrame,
  magiRulerLabel,
  magiTimeOrigin,
} from "./magiTimelineScale";

describe("MAGI timeline time-space", () => {
  it("keeps frame 0 on the lane edge after the label column", () => {
    expect(magiTimeOrigin()).toBe(MAGI_TRACK_LABEL_WIDTH);
    expect(magiPlayheadLeft(0, 1)).toBe(0);
    expect(magiFrameSheetX(0, 1)).toBe(MAGI_TRACK_LABEL_WIDTH);
    expect(magiFrameSheetX(0, 10)).toBe(MAGI_TRACK_LABEL_WIDTH);
  });

  it("scales pixels without moving the origin", () => {
    expect(magiPxPerFrame(1)).toBe(MAGI_BASE_PX_PER_FRAME);
    expect(magiPxPerFrame(10)).toBe(MAGI_BASE_PX_PER_FRAME * 10);
    expect(clampMagiZoom(0)).toBe(1);
    expect(clampMagiZoom(11)).toBe(10);
    const frame = 24;
    expect(magiPlayheadLeft(frame, 5)).toBe(frame * MAGI_BASE_PX_PER_FRAME * 5);
    expect(magiFrameSheetX(frame, 5) - magiTimeOrigin()).toBe(magiPlayheadLeft(frame, 5));
  });

  it("grows the lane with duration and zoom, and the short-media floor is not a ceiling", () => {
    const tenSeconds = 10 * 24;
    const fortyFive = 45 * 24;
    const twoMinutes = 120 * 24;
    expect(magiContentWidth(tenSeconds, 1)).toBe(MAGI_MIN_CONTENT_PX);
    expect(magiContentWidth(fortyFive, 1)).toBe(fortyFive * MAGI_BASE_PX_PER_FRAME);
    expect(magiContentWidth(fortyFive, 1)).toBeGreaterThan(magiContentWidth(tenSeconds, 1));
    expect(magiContentWidth(twoMinutes, 1)).toBe(twoMinutes * MAGI_BASE_PX_PER_FRAME);
    for (const zoom of [1, 2, 5, 10]) {
      expect(magiContentWidth(fortyFive, zoom)).toBe(fortyFive * MAGI_BASE_PX_PER_FRAME * zoom);
    }
  });

  it("clamps the playhead to the real sequence end", () => {
    expect(magiClampFrame(-4, 1080)).toBe(0);
    expect(magiClampFrame(37 * 24, 45 * 24)).toBe(37 * 24);
    expect(magiClampFrame(99999, 45 * 24)).toBe(45 * 24);
  });

  it("labels short sequences in seconds and long sequences as m:ss", () => {
    expect(magiRulerLabel(0, 45)).toBe("0s");
    expect(magiRulerLabel(15, 45)).toBe("15s");
    expect(magiRulerLabel(0, 125)).toBe("0:00");
    expect(magiRulerLabel(90, 125)).toBe("1:30");
  });

  it("spaces ruler ticks instead of labeling every second on a long timeline", () => {
    const pxPerSec = MAGI_BASE_PX_PER_FRAME * 24;
    const ticks = visualRulerTicks(120, pxPerSec);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBe(120);
    expect(ticks.length).toBeLessThan(70);
    expect(ticks).toContain(60);
    const fine = visualRulerTicks(45, pxPerSec * 10);
    expect(fine).toContain(1);
    expect(fine[fine.length - 1]).toBe(45);
  });
});
