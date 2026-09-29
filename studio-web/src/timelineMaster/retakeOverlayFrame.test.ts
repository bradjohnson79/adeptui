import { describe, expect, it } from "vitest";
import {
  RETAKE_OVERLAY_MIN_H,
  RETAKE_OVERLAY_MIN_W,
  RETAKE_OVERLAY_PAD,
  clampOverlayFrame,
  defaultRetakeOverlayFrame,
  moveOverlayFrame,
  resizeOverlayFrame,
} from "./retakeOverlayFrame";

const parent = { w: 800, h: 400 };

describe("clampOverlayFrame", () => {
  it("keeps the menu inside the Preview Monitor", () => {
    const next = clampOverlayFrame({ x: -40, y: 900, w: 252, h: 98 }, parent);
    expect(next.x).toBe(RETAKE_OVERLAY_PAD);
    expect(next.y).toBe(parent.h - next.h - RETAKE_OVERLAY_PAD);
    expect(next.w).toBe(252);
  });

  it("shrinks when the monitor is narrower than the menu", () => {
    const next = clampOverlayFrame({ x: 0, y: 0, w: 400, h: 200 }, { w: 220, h: 160 });
    expect(next.w).toBe(220 - RETAKE_OVERLAY_PAD * 2);
    expect(next.h).toBe(160 - RETAKE_OVERLAY_PAD * 2);
    expect(next.x).toBe(RETAKE_OVERLAY_PAD);
    expect(next.y).toBe(RETAKE_OVERLAY_PAD);
  });
});

describe("defaultRetakeOverlayFrame", () => {
  it("opens as a compact top-center strip", () => {
    const next = defaultRetakeOverlayFrame(parent, 90);
    expect(next.y).toBe(RETAKE_OVERLAY_PAD);
    expect(next.x).toBeGreaterThan(200);
    expect(next.w).toBeLessThanOrEqual(252);
    expect(next.h).toBe(90);
  });
});

describe("moveOverlayFrame", () => {
  it("stops at the monitor edges", () => {
    const start = { x: 10, y: 10, w: 200, h: 90 };
    const left = moveOverlayFrame(start, -400, 0, parent);
    expect(left.x).toBe(RETAKE_OVERLAY_PAD);
    const bottom = moveOverlayFrame(start, 0, 800, parent);
    expect(bottom.y).toBe(parent.h - start.h - RETAKE_OVERLAY_PAD);
  });
});

describe("resizeOverlayFrame", () => {
  it("grows from the southeast corner", () => {
    const start = { x: 20, y: 20, w: 220, h: 90 };
    const next = resizeOverlayFrame(start, "se", 40, 20, parent);
    expect(next.w).toBe(260);
    expect(next.h).toBe(110);
    expect(next.x).toBe(20);
    expect(next.y).toBe(20);
  });

  it("does not drift when west resize hits the minimum width", () => {
    const start = { x: 80, y: 12, w: RETAKE_OVERLAY_MIN_W, h: RETAKE_OVERLAY_MIN_H };
    const next = resizeOverlayFrame(start, "w", 80, 0, parent);
    expect(next.w).toBe(RETAKE_OVERLAY_MIN_W);
    expect(next.x).toBe(80);
  });

  it("moves origin when shrinking from the northwest", () => {
    const start = { x: 80, y: 40, w: 240, h: 120 };
    const next = resizeOverlayFrame(start, "nw", 20, 10, parent);
    expect(next.w).toBe(220);
    expect(next.h).toBe(110);
    expect(next.x).toBe(100);
    expect(next.y).toBe(50);
  });
});
