import { describe, expect, it } from "vitest";
import {
  cellToWorldMeters,
  formatMeters,
  normalizedToWorldMeters,
  spinViewLabel,
  SPIN_CAMERA_DEFAULTS,
  SPIN_VIEW_ORDER,
  worldMetersToNormalized,
} from "./spinCameraGeometry";

describe("Spin Camera geometry", () => {
  it("maps normalized origin to world origin on a 10m map", () => {
    const { x, z } = normalizedToWorldMeters(0, 0, 10, 10);
    expect(x).toBeCloseTo(0, 8);
    expect(z).toBeCloseTo(0, 8);
  });

  it("maps north-west cell to negative x and negative z", () => {
    // top-left-ish valid cell on a 10×10 density grid: column 1, row 1
    const { x, z } = cellToWorldMeters(1, 1, 0, 10, 10);
    expect(x).toBeLessThan(0);
    expect(z).toBeLessThan(0);
  });

  it("round-trips world meters back to normalized coordinates", () => {
    const width = 12;
    const depth = 8;
    const norm = { normalizedX: 0.5, normalizedY: -0.25 };
    const world = normalizedToWorldMeters(norm.normalizedX, norm.normalizedY, width, depth);
    expect(world.x).toBe(3);
    expect(world.z).toBe(-1);
    const back = worldMetersToNormalized(world.x, world.z, width, depth);
    expect(back.normalizedX).toBeCloseTo(norm.normalizedX, 8);
    expect(back.normalizedY).toBeCloseTo(norm.normalizedY, 8);
  });

  it("uses safe defaults for zero/invalid dimensions", () => {
    const world = normalizedToWorldMeters(1, 1, 0, 0);
    expect(world.x).toBe(0);
    expect(world.z).toBe(0);
  });

  it("formats meters to one decimal place", () => {
    expect(formatMeters(1.234)).toBe("1.2");
    expect(formatMeters(-0.75)).toBe("-0.8");
    expect(formatMeters(NaN)).toBe("0.0");
  });

  it("orders views Center → North → East → South → West", () => {
    expect(SPIN_VIEW_ORDER).toEqual(["center", "north", "east", "south", "west"]);
  });

  it("labels directions in creator-facing language", () => {
    expect(spinViewLabel("center")).toBe("Center");
    expect(spinViewLabel("NORTH")).toBe("North");
    expect(spinViewLabel("east")).toBe("East");
  });

  it("exposes sensible default camera parameters", () => {
    expect(SPIN_CAMERA_DEFAULTS.cameraHeight).toBe(1.6);
    expect(SPIN_CAMERA_DEFAULTS.fov).toBe(75);
    expect(SPIN_CAMERA_DEFAULTS.lensMm).toBe(35);
  });
});
