import { describe, expect, it } from "vitest";
import {
  MAGNETIC_SNAP_THRESHOLD_PX,
  buildMagneticSnapTargets,
  magneticSnapMovingEdge,
  magneticSnapTime,
  normalizeTimelineSeconds,
} from "./magneticSnap";

const TARGETS = buildMagneticSnapTargets({
  sceneEnd: 10,
  batches: [{ id: "b1", start: 0, length: 5, label: "Batch 1" }],
  clips: [],
  playhead: 2,
});

describe("magnetic snap", () => {
  it("returns raw time when Snap is off", () => {
    const result = magneticSnapTime(4.96, TARGETS, 90, false);
    expect(result.time).toBe(4.96);
    expect(result.target).toBeNull();
  });

  it("acquires a Batch end in screen space, not a 0.25s lattice", () => {
    const pxPerSec = 90;
    const near = 5 - (MAGNETIC_SNAP_THRESHOLD_PX - 1) / pxPerSec;
    const hit = magneticSnapTime(near, TARGETS, pxPerSec, true);
    expect(hit.time).toBe(5);
    expect(hit.target?.kind).toBe("batch");

    const far = 5 - (MAGNETIC_SNAP_THRESHOLD_PX + 2) / pxPerSec;
    const miss = magneticSnapTime(far, TARGETS, pxPerSec, true);
    expect(Math.abs(miss.time - far)).toBeLessThan(0.002);
    expect(miss.target).toBeNull();
  });

  it("allows crossing a Batch edge after the pull zone", () => {
    const pxPerSec = 90;
    const past = 5 + (MAGNETIC_SNAP_THRESHOLD_PX + 4) / pxPerSec;
    const result = magneticSnapTime(past, TARGETS, pxPerSec, true);
    expect(result.target).toBeNull();
    expect(result.time).toBeGreaterThan(5);
  });

  it("acquires the same Batch edge at min, 1x, and max zoom", () => {
    for (const zoom of [0.2, 1, 5]) {
      const pxPerSec = 90 * zoom;
      const within = 5 - 6 / pxPerSec;
      const hit = magneticSnapTime(within, TARGETS, pxPerSec, true);
      expect(hit.time, `zoom ${zoom}`).toBe(5);
    }
  });

  it("trims the moving end to the Batch edge instead of snapping length", () => {
    const result = magneticSnapMovingEdge({
      mode: "trim-right",
      start: 0,
      length: 4.96,
      targets: TARGETS,
      pxPerSec: 200,
      enabled: true,
    });
    expect(result.length).toBe(5);
    expect(result.start).toBe(0);
    expect(result.target?.kind).toBe("batch");
  });

  it("normalizes float noise without inventing a new timing system", () => {
    expect(normalizeTimelineSeconds(4.9999997)).toBe(5);
    expect(normalizeTimelineSeconds(4.961)).toBe(4.961);
  });

  it("does not mutate stored clip times when zoom changes", () => {
    expect(normalizeTimelineSeconds(5)).toBe(5);
    expect(magneticSnapTime(5, TARGETS, 18, false).time).toBe(5);
    expect(magneticSnapTime(5, TARGETS, 450, false).time).toBe(5);
  });
});
