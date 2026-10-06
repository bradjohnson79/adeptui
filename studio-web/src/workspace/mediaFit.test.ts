import { describe, expect, it } from "vitest";
import { mediaContainRect } from "./mediaFit";

describe("mediaContainRect Fit / contain", () => {
  it("letterboxes 16:9 inside a wide monitor", () => {
    const rect = mediaContainRect(1600, 600, 1920, 1080);
    expect(rect.h).toBeCloseTo(600);
    expect(rect.w).toBeCloseTo(600 * (16 / 9));
    expect(rect.y).toBeCloseTo(0);
    expect(rect.x).toBeGreaterThan(0);
    expect(rect.scale).toBeCloseTo(600 / 1080);
  });

  it("pillarboxes 16:9 inside a tall monitor", () => {
    const rect = mediaContainRect(800, 900, 1920, 1080);
    expect(rect.w).toBeCloseTo(800);
    expect(rect.h).toBeCloseTo(800 * (9 / 16));
    expect(rect.x).toBeCloseTo(0);
    expect(rect.y).toBeGreaterThan(0);
    expect(rect.scale).toBeCloseTo(800 / 1920);
  });

  it("fits 2K to the same logical size as 1080p in the same monitor", () => {
    const hd = mediaContainRect(800, 450, 1920, 1080);
    const uhd = mediaContainRect(800, 450, 2560, 1440);
    expect(hd.w).toBeCloseTo(uhd.w);
    expect(hd.h).toBeCloseTo(uhd.h);
    expect(hd.x).toBeCloseTo(uhd.x);
    expect(hd.y).toBeCloseTo(uhd.y);
    expect(uhd.scale).toBeLessThan(hd.scale);
  });

  it("never exceeds the monitor on either axis", () => {
    const rect = mediaContainRect(640, 360, 3840, 2160);
    expect(rect.w).toBeLessThanOrEqual(640 + 0.01);
    expect(rect.h).toBeLessThanOrEqual(360 + 0.01);
  });
});
