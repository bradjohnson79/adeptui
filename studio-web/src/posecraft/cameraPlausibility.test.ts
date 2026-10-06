import { describe, expect, it } from "vitest";
import {
  aggregateFigureBounds,
  buildSafeCamera,
  isCameraPlausible,
  sanitizePersistedCamera,
  CAMERA_RADIUS_LIMITS,
  SAFE_CAMERA,
} from "./cameraPlausibility";
import { createFigure } from "./state";
import type { CameraState, FigureInstance } from "./types";

function cam(patch: Partial<CameraState> = {}): CameraState {
  return {
    lensMm: 35,
    aspect: "16:9",
    guides: [],
    alpha: -Math.PI / 2,
    beta: 1.12,
    radius: 7.5,
    target: { x: 0, y: 1.2, z: 0 },
    ...patch,
    target: { x: 0, y: 1.2, z: 0, ...(patch.target ?? {}) },
  };
}

function figureAt(archetype: Parameters<typeof createFigure>[0], x: number, z: number): FigureInstance {
  const f = createFigure(archetype);
  f.position = { x, z };
  return f;
}

/** The exact corrupt persisted camera proven by the empty-viewport audit. */
const AUDIT_CORRUPT = cam({
  radius: 13.948,
  target: { x: 4.262, y: 1.2, z: -3.627 },
});
const AUDIT_FIGURE = figureAt("adult-male", -1.4, 0); // height 1.84, y 0…1.85

describe("PoseCraft camera plausibility — hydration boundary", () => {
  it("classifies the audit's corrupt persisted camera as IMPLAUSIBLE", () => {
    expect(isCameraPlausible(AUDIT_CORRUPT, [AUDIT_FIGURE])).toBe(false);
  });

  it("restores a legitimate saved camera EXACTLY (valid framing preserved)", () => {
    // Creator's intentional off-center, non-default-zoom, user-angle framing.
    const saved = cam({
      alpha: -0.9,
      beta: 1.35,
      radius: 5.2,
      target: { x: -1.4, y: 1.0, z: 0.1 },
    });
    const result = sanitizePersistedCamera(saved, [AUDIT_FIGURE]);
    expect(result.sanitized).toBe(false);
    expect(result.camera).toEqual(saved);
  });

  it("keeps a large-radius (zoomed-out) camera valid when figure stays framed (Law 18)", () => {
    const zoomedOut = cam({ radius: CAMERA_RADIUS_LIMITS.upper, target: { x: -1.4, y: 1.0, z: 0 } });
    expect(isCameraPlausible(zoomedOut, [AUDIT_FIGURE])).toBe(true);
  });

  it("sanitizes an invalid camera to a figure-aware default (target on content, bounded radius)", () => {
    const { camera, sanitized } = sanitizePersistedCamera(AUDIT_CORRUPT, [AUDIT_FIGURE]);
    expect(sanitized).toBe(true);
    const bounds = aggregateFigureBounds([AUDIT_FIGURE])!;
    expect(camera.target.x).toBeCloseTo(bounds.cx, 5);
    expect(camera.target.z).toBeCloseTo(bounds.cz, 5);
    expect(camera.target.y).toBeCloseTo(bounds.centerY, 5);
    expect(camera.radius).toBeGreaterThan(CAMERA_RADIUS_LIMITS.lower);
    expect(camera.radius).toBeLessThanOrEqual(CAMERA_RADIUS_LIMITS.upper - 1);
    // The repaired camera must itself be plausible (no re-flag loop).
    expect(isCameraPlausible(camera, [AUDIT_FIGURE])).toBe(true);
  });

  it("falls back to the stage-origin safe default when NO figures exist (Law 15)", () => {
    const result = sanitizePersistedCamera(AUDIT_CORRUPT, []);
    expect(result.sanitized).toBe(true);
    expect(result.camera.target).toEqual({ ...SAFE_CAMERA.target });
    expect(result.camera.radius).toBe(SAFE_CAMERA.radius);
    expect(result.camera.alpha).toBe(SAFE_CAMERA.alpha);
    expect(result.camera.beta).toBe(SAFE_CAMERA.beta);
  });

  it("treats the no-figure stage default as valid (no oscillation)", () => {
    const emptyDefault = cam();
    const result = sanitizePersistedCamera(emptyDefault, []);
    expect(result.sanitized).toBe(false);
    expect(result.camera).toEqual(emptyDefault);
  });

  it("preserves a plausible camera framing a separated multi-figure stage (Law 14)", () => {
    const a = figureAt("adult-male", -3, -2);
    const b = figureAt("adult-female", 3, 2);
    const bounds = aggregateFigureBounds([a, b])!;
    const framing = cam({ radius: 8, target: { x: bounds.cx, y: bounds.centerY, z: bounds.cz } });
    expect(isCameraPlausible(framing, [a, b])).toBe(true);
  });

  it("handles non-finite camera fields as implausible", () => {
    expect(isCameraPlausible(cam({ radius: Number.NaN }), [AUDIT_FIGURE])).toBe(false);
    expect(isCameraPlausible(cam({ target: { x: Number.POSITIVE_INFINITY, y: 1, z: 0 } }), [AUDIT_FIGURE])).toBe(false);
  });

  it("never mutates figure coordinates when building a safe camera (Law 20)", () => {
    const f = figureAt("adult-male", -1.4, 0);
    const before = { ...f.position };
    buildSafeCamera(AUDIT_CORRUPT, [f]);
    expect(f.position).toEqual(before);
  });

  it("aggregate bounds derive from authoritative figure state, centered at torso height", () => {
    const bounds = aggregateFigureBounds([figureAt("adult-male", 2, 0)])!;
    expect(bounds.cx).toBe(2);
    expect(bounds.cz).toBe(0);
    expect(bounds.topY).toBeCloseTo(1.84, 5);
    expect(bounds.centerY).toBeGreaterThan(0);
    expect(bounds.centerY).toBeLessThan(1.84);
  });
});
