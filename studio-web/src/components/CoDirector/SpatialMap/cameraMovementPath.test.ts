import { describe, expect, it } from "vitest";
import {
  CAMERA_PATH_MIN_OFFSET_NORMALIZED,
  attachModeFromShotSize,
  arrowPoint,
  cameraFollowSubjectId,
  cameraPathLateralOffsetNormalized,
  computeCameraMovementArrows,
  isCameraFollowSubject,
  lateralNormal,
  movementAliasNumber,
  resolveCameraAttachMode,
  resolveCameraScrubPosition,
  resolveFollowCameraScrubPosition,
  resolvePovCameraScrubPosition,
} from "./cameraMovementPath";
import type { MovementArrow } from "./types";

const korriArrow: MovementArrow = {
  characterId: "korri",
  label: "Korri",
  fromAlias: "M1",
  toAlias: "M2",
  from: { normalizedX: -0.4, normalizedY: 0.2, gridRow: 3, gridColumn: 2 },
  to: { normalizedX: 0.5, normalizedY: -0.1, gridRow: 6, gridColumn: 7 },
};

const farCamM1 = { id: "cam1", normalizedX: 0.72, normalizedY: 0.31, cameraSlot: 0, label: "Camera" };
const farCamM2 = { id: "cam1", normalizedX: 0.78, normalizedY: 0.84, cameraSlot: 0, label: "Camera" };
const nearCamM1 = { id: "cam1", normalizedX: -0.4, normalizedY: 0.2, cameraSlot: 0, label: "Camera" };
const nearCamM2 = { id: "cam1", normalizedX: 0.5, normalizedY: -0.1, cameraSlot: 0, label: "Camera" };

const twoSegs = (
  m1: typeof farCamM1,
  m2: typeof farCamM2,
) => [
  { segmentNumber: 1, cameraStates: [m1] },
  { segmentNumber: 2, cameraStates: [m2] },
];

describe("primary subject helper (look-at, not attach)", () => {
  it("identifies a character subject vs auto/environment", () => {
    expect(isCameraFollowSubject("korri")).toBe(true);
    expect(isCameraFollowSubject("auto")).toBe(false);
    expect(isCameraFollowSubject("environment")).toBe(false);
    expect(cameraFollowSubjectId({ primarySubject: "korri" })).toBe("korri");
    expect(cameraFollowSubjectId({ primarySubject: "auto" })).toBeNull();
  });
});

describe("attach mode", () => {
  it("defaults to free -- never auto-follows a character", () => {
    expect(resolveCameraAttachMode({ primarySubject: "korri" })).toBe("free");
    expect(resolveCameraAttachMode({ primarySubject: "korri", attachMode: "follow" })).toBe("free");
    expect(resolveCameraAttachMode({ primarySubject: "auto" })).toBe("free");
    expect(attachModeFromShotSize("wide")).toBe("free");
    expect(attachModeFromShotSize("pov")).toBe("pov");
  });

  it("classifies POV from shotSize / shotType / attachMode only", () => {
    expect(resolveCameraAttachMode({ primarySubject: "korri", attachMode: "pov" })).toBe("pov");
    expect(resolveCameraAttachMode({ primarySubject: "korri", shotType: "pov" })).toBe("pov");
    expect(resolveCameraAttachMode({ primarySubject: "korri", shotSize: "pov" })).toBe("pov");
  });
});

describe("lateral offset", () => {
  it("never drops below the minimum so strokes cannot overlap", () => {
    expect(cameraPathLateralOffsetNormalized(1, 10)).toBeGreaterThanOrEqual(
      CAMERA_PATH_MIN_OFFSET_NORMALIZED,
    );
  });

  it("clears character + camera marker radii so C1 is never inside the red circle", () => {
    const density = 10;
    const cell = 2 / density;
    const markerR = cell * 0.288;
    const camHalf = markerR * 0.68;
    const offset = cameraPathLateralOffsetNormalized(1, density);
    expect(offset).toBeGreaterThan(markerR + camHalf);
  });

  it("uses a stable left-of-travel normal", () => {
    const n = lateralNormal(1, 0);
    expect(n).not.toBeNull();
    expect(Math.abs(n!.nx)).toBeLessThan(1e-12);
    expect(n!.ny).toBeCloseTo(1, 10);
  });
});

describe("computeCameraMovementArrows from camera own poses", () => {
  it("emits a green path between the camera's saved M1 and M2 poses", () => {
    const rows = computeCameraMovementArrows(twoSegs(farCamM1, farCamM2), [farCamM1]);
    expect(rows).toHaveLength(1);
    expect(rows[0].cameraId).toBe("cam1");
    expect(rows[0].fromAlias).toBe("M1");
    expect(rows[0].toAlias).toBe("M2");
    expect(rows[0].from.normalizedX).toBeCloseTo(0.72, 8);
    expect(rows[0].from.normalizedY).toBeCloseTo(0.31, 8);
    expect(rows[0].to.normalizedX).toBeCloseTo(0.78, 8);
    expect(rows[0].to.normalizedY).toBeCloseTo(0.84, 8);
  });

  it("does not snap a far free camera onto the character path", () => {
    const rows = computeCameraMovementArrows(
      twoSegs(farCamM1, farCamM2),
      [farCamM1],
      [korriArrow],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].from.normalizedX).toBeCloseTo(0.72, 8);
    expect(rows[0].to.normalizedY).toBeCloseTo(0.84, 8);
    const d1 = Math.hypot(
      rows[0].from.normalizedX - korriArrow.from.normalizedX!,
      rows[0].from.normalizedY - korriArrow.from.normalizedY!,
    );
    expect(d1).toBeGreaterThan(0.5);
  });

  it("offsets beside purple when the camera path is in the character corridor", () => {
    const rows = computeCameraMovementArrows(
      twoSegs(nearCamM1, nearCamM2),
      [nearCamM1],
      [korriArrow],
    );
    expect(rows).toHaveLength(1);
    const d1 = Math.hypot(
      rows[0].from.normalizedX - korriArrow.from.normalizedX!,
      rows[0].from.normalizedY - korriArrow.from.normalizedY!,
    );
    const d2 = Math.hypot(
      rows[0].to.normalizedX - korriArrow.to.normalizedX!,
      rows[0].to.normalizedY - korriArrow.to.normalizedY!,
    );
    const minClear = cameraPathLateralOffsetNormalized(1, 10) - 1e-9;
    expect(d1).toBeGreaterThanOrEqual(minClear);
    expect(d2).toBeGreaterThanOrEqual(minClear);
    expect(rows[0].from.normalizedX).not.toBeCloseTo(korriArrow.from.normalizedX!, 3);
    expect(rows[0].to.normalizedX).not.toBeCloseTo(korriArrow.to.normalizedX!, 3);
  });

  it("emits nothing when camera poses are unchanged across segments", () => {
    expect(
      computeCameraMovementArrows(twoSegs(farCamM1, { ...farCamM1 }), [farCamM1]),
    ).toEqual([]);
  });

  it("emits no green path for POV cameras", () => {
    const rows = computeCameraMovementArrows(
      twoSegs(farCamM1, farCamM2),
      [{ ...farCamM1, shotSize: "pov" }],
    );
    expect(rows).toEqual([]);
  });

  it("ignores hidden cameras and does not mutate segment input", () => {
    const segs = twoSegs(farCamM1, farCamM2);
    const snapshot = JSON.stringify(segs);
    const rows = computeCameraMovementArrows(segs, [
      { ...farCamM1, visible: false },
      { id: "cam2", normalizedX: 0.1, normalizedY: 0.1, cameraSlot: 1, visible: true },
    ]);
    expect(rows.map((r) => r.cameraId)).toEqual([]);
    expect(JSON.stringify(segs)).toBe(snapshot);
  });

  it("falls back to grid cell centers when normalized coords are absent", () => {
    const gridOnlyFrom = { id: "cam1", gridRow: 2, gridColumn: 2, cameraSlot: 0 };
    const gridOnlyTo = { id: "cam1", gridRow: 2, gridColumn: 5, cameraSlot: 0 };
    const from = arrowPoint(gridOnlyFrom, 10);
    const to = arrowPoint(gridOnlyTo, 10);
    expect(from).not.toBeNull();
    expect(to).not.toBeNull();
    const rows = computeCameraMovementArrows(
      [
        { segmentNumber: 1, cameraStates: [gridOnlyFrom] },
        { segmentNumber: 2, cameraStates: [gridOnlyTo] },
      ],
      [gridOnlyFrom],
      [],
      { density: 10, metersPerCell: 1 },
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].from.normalizedX).toBeCloseTo(from!.x, 8);
    expect(rows[0].to.normalizedX).toBeCloseTo(to!.x, 8);
  });
});

describe("free-camera path scrub helper (display only)", () => {
  const path = computeCameraMovementArrows(twoSegs(farCamM1, farCamM2), [farCamM1]);

  it("Movement 1 / Movement 2 bind to the camera's own endpoints", () => {
    const m1 = resolveFollowCameraScrubPosition("cam1", path, "M1");
    const m2 = resolveFollowCameraScrubPosition("cam1", path, "M2");
    expect(m1!.attachMode).toBe("free");
    expect(m2!.attachMode).toBe("free");
    expect(m1!.normalizedX).toBeCloseTo(path[0].from.normalizedX, 10);
    expect(m2!.normalizedX).toBeCloseTo(path[0].to.normalizedX, 10);
    expect(m2!.normalizedX).not.toBeCloseTo(m1!.normalizedX, 5);
  });

  it("switching back to M1 restores the prior camera endpoint", () => {
    resolveFollowCameraScrubPosition("cam1", path, "M2");
    const m1 = resolveFollowCameraScrubPosition("cam1", path, "M1");
    expect(m1!.normalizedX).toBeCloseTo(path[0].from.normalizedX, 10);
  });

  it("returns null when camera has no path", () => {
    expect(resolveFollowCameraScrubPosition("cam1", [], "M1")).toBeNull();
  });

  it("parses movement aliases", () => {
    expect(movementAliasNumber("M1")).toBe(1);
    expect(movementAliasNumber("m 2")).toBe(2);
    expect(movementAliasNumber("nope")).toBeNull();
  });
});

describe("POV attach vs free display bind", () => {
  it("POV scrub attaches to live character position", () => {
    const subject = {
      normalizedX: korriArrow.from.normalizedX,
      normalizedY: korriArrow.from.normalizedY,
    };
    const scrub = resolvePovCameraScrubPosition(subject, "M1");
    expect(scrub).not.toBeNull();
    expect(scrub!.attachMode).toBe("pov");
    expect(scrub!.normalizedX).toBeCloseTo(korriArrow.from.normalizedX!, 10);
  });

  it("unified resolver attaches only for POV; free returns null (use saved pose)", () => {
    const pov = resolveCameraScrubPosition(
      { id: "cam1", primarySubject: "korri", shotSize: "pov" },
      [],
      "M2",
      { normalizedX: korriArrow.to.normalizedX, normalizedY: korriArrow.to.normalizedY },
    );
    expect(pov!.attachMode).toBe("pov");
    expect(pov!.normalizedX).toBeCloseTo(korriArrow.to.normalizedX!, 10);

    const free = resolveCameraScrubPosition(
      { id: "cam1", primarySubject: "korri", shotSize: "wide" },
      [],
      "M1",
      { normalizedX: korriArrow.from.normalizedX, normalizedY: korriArrow.from.normalizedY },
    );
    expect(free).toBeNull();
  });
});
