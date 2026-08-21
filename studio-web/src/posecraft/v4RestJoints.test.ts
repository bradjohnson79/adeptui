import { describe, expect, it } from "vitest";
import { FIGURE_ARCHETYPES } from "./constants";
import { BODY_REGIONS } from "./humanMeshBuilder";
import {
  V4_FABLE_ROOT_PIVOTS,
  V4_HANG_REST_LOCAL,
  V4_PIVOT_TOLERANCE_M,
  V4_REGION_BIND_ROTATION_Z,
  V4_REST_LOCAL,
  hangRestLocalFromFableRoot,
  isLoadCurrent,
  measureV4PivotDeltas,
  restLocalFromFableRoot,
} from "./v4RestJoints";
import type { ArchetypeId } from "./types";

const SPEC_BY_ARCHETYPE = Object.fromEntries(
  FIGURE_ARCHETYPES.map((spec) => [spec.id, spec]),
) as Record<ArchetypeId, (typeof FIGURE_ARCHETYPES)[number]>;

describe("V4 pivot binding law", () => {
  it("measures 17 regions on all four figures and requires rest correction", () => {
    const rows = measureV4PivotDeltas(SPEC_BY_ARCHETYPE);
    expect(rows).toHaveLength(17 * 4);
    expect(rows.every((row) => BODY_REGIONS.includes(row.region))).toBe(true);
    const maxDelta = Math.max(...rows.map((row) => row.deltaM));
    expect(maxDelta).toBeGreaterThan(V4_PIVOT_TOLERANCE_M);
    expect(rows.filter((row) => row.bind === "correct-rest").length).toBeGreaterThan(0);
    for (const row of rows.filter((row) => !row.withinTolerance)) {
      expect(row.bind).toBe("correct-rest");
    }
  });

  it("derives rest locals from Fable root pivots without changing Euler math", () => {
    const local = restLocalFromFableRoot(V4_FABLE_ROOT_PIVOTS["adult-female"]);
    expect(local.leftElbow.x).toBeCloseTo(V4_REST_LOCAL["adult-female"].leftElbow.x, 3);
    expect(local.leftElbow.y).toBeCloseTo(0, 3);
    expect(local.pelvis.y).toBeCloseTo(0.898, 2);
  });

  it("discards stale loads after dispose", () => {
    expect(isLoadCurrent(2, 2, "LOADING")).toBe(true);
    expect(isLoadCurrent(3, 2, "LOADING")).toBe(false);
    expect(isLoadCurrent(2, 2, "DISPOSED")).toBe(false);
  });
});

describe("hanging-arm semantic rest + bind rotations", () => {
  it("hangs the arm chain along −Y using Fable segment lengths", () => {
    const hang = hangRestLocalFromFableRoot(V4_FABLE_ROOT_PIVOTS["adult-female"]);
    const fable = V4_FABLE_ROOT_PIVOTS["adult-female"];
    expect(hang.leftElbow.x).toBeCloseTo(0, 5);
    expect(hang.leftElbow.z).toBeCloseTo(0, 5);
    expect(hang.leftElbow.y).toBeCloseTo(-(Math.abs(fable.leftLowerArm.x - fable.leftUpperArm.x)), 5);
    expect(hang.rightElbow.y).toBeCloseTo(-(Math.abs(fable.rightLowerArm.x - fable.rightUpperArm.x)), 5);
    expect(hang.leftWrist.y).toBeLessThan(0);
    expect(hang.rightWrist.y).toBeLessThan(0);
  });

  it("publishes hang rest locals for every archetype", () => {
    for (const id of ["adult-male", "adult-female", "child-boy", "child-girl"] as const) {
      expect(V4_HANG_REST_LOCAL[id].leftElbow.y).toBeLessThan(0);
      expect(V4_HANG_REST_LOCAL[id].rightElbow.y).toBeLessThan(0);
      expect(V4_HANG_REST_LOCAL[id].pelvis.y).toBeGreaterThan(0.4);
    }
  });

  it("binds T-pose arm geometry onto the hanging skeleton (±90° Z)", () => {
    expect(V4_REGION_BIND_ROTATION_Z.leftUpperArm).toBeCloseTo(Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.leftLowerArm).toBeCloseTo(Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.leftHand).toBeCloseTo(Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.rightUpperArm).toBeCloseTo(-Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.rightLowerArm).toBeCloseTo(-Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.rightHand).toBeCloseTo(-Math.PI / 2, 8);
    expect(V4_REGION_BIND_ROTATION_Z.head).toBe(0);
    expect(V4_REGION_BIND_ROTATION_Z.pelvis).toBe(0);
    expect(V4_REGION_BIND_ROTATION_Z.leftUpperLeg).toBe(0);
  });
});
