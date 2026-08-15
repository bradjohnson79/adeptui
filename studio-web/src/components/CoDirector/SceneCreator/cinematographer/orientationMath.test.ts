import { describe, expect, it } from "vitest";
import {
  SNAP_PRESETS,
  clampPitch,
  clampRoll,
  clampZoom,
  getSnapPreset,
  wrapYaw,
  zoomToLens,
} from "./orientationMath";

describe("orientationMath", () => {
  it("wraps yaw into (-180, 180]", () => {
    expect(wrapYaw(0)).toBe(0);
    expect(wrapYaw(32)).toBe(32);
    expect(wrapYaw(180)).toBe(180);
    expect(wrapYaw(190)).toBe(-170);
    expect(wrapYaw(360)).toBe(0);
    expect(wrapYaw(-190)).toBe(170);
    expect(wrapYaw(-180)).toBe(180);
    expect(wrapYaw(540)).toBe(180);
  });

  it("clamps pitch to [-60, 60]", () => {
    expect(clampPitch(0)).toBe(0);
    expect(clampPitch(-18)).toBe(-18);
    expect(clampPitch(-60)).toBe(-60);
    expect(clampPitch(60)).toBe(60);
    expect(clampPitch(-90)).toBe(-60);
    expect(clampPitch(90)).toBe(60);
  });

  it("clamps roll to [-25, 25]", () => {
    expect(clampRoll(3)).toBe(3);
    expect(clampRoll(-25)).toBe(-25);
    expect(clampRoll(25)).toBe(25);
    expect(clampRoll(-40)).toBe(-25);
    expect(clampRoll(40)).toBe(25);
  });

  it("clamps zoom to [0.5, 3]", () => {
    expect(clampZoom(1)).toBe(1);
    expect(clampZoom(1.35)).toBe(1.35);
    expect(clampZoom(0.1)).toBe(0.5);
    expect(clampZoom(5)).toBe(3);
  });

  it("converts optical zoom to lens mm without moving the camera", () => {
    expect(zoomToLens(1)).toBe(35);
    expect(zoomToLens(2)).toBe(70);
    expect(zoomToLens(0.5)).toBe(17.5);
    expect(zoomToLens(2, 50)).toBe(100);
    expect(zoomToLens(8)).toBe(105);
  });

  it("exposes the snap view presets", () => {
    expect(SNAP_PRESETS).toHaveLength(13);
    expect(getSnapPreset("front")).toEqual({
      id: "front",
      label: "Front",
      yawDegrees: 0,
      pitchDegrees: 0,
      rollDegrees: 0,
    });
    expect(getSnapPreset("three_quarter_left")?.yawDegrees).toBe(-45);
    expect(getSnapPreset("three_quarter_right")?.yawDegrees).toBe(45);
    expect(getSnapPreset("profile_left")?.yawDegrees).toBe(-90);
    expect(getSnapPreset("profile_right")?.yawDegrees).toBe(90);
    expect(getSnapPreset("rear")?.yawDegrees).toBe(180);
    expect(getSnapPreset("high_angle")?.pitchDegrees).toBe(-30);
    expect(getSnapPreset("low_angle")?.pitchDegrees).toBe(30);
    expect(getSnapPreset("birds_eye")?.pitchDegrees).toBe(-60);
    expect(getSnapPreset("worms_eye")?.pitchDegrees).toBe(60);
    expect(getSnapPreset("eye_level")?.pitchDegrees).toBe(0);
  });
});
