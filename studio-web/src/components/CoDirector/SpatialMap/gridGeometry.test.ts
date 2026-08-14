import { describe, expect, it } from "vitest";
import {
  adjacentCell,
  ALL_GRID_SCALES,
  CARDINAL_LABELS,
  cellCenterNormalized,
  cellLabel,
  cellSizeNormalized,
  cellToNormalized,
  clampGridScale,
  DEFAULT_GRID_SCALE,
  densityForScale,
  GRID_DENSITY,
  gridScaleLabel,
  isCellInsideCircle,
  isInsideCircle,
  isValidCell,
  legacyPolarToNormalized,
  MAX_GRID_SCALE,
  MIN_GRID_SCALE,
  nearestValidCell,
  normalizedToNearestCell,
  normalizedToPixel,
  pixelToNormalized,
  pointerToCell,
  remapDerivedCell,
  remapPositionToDensity,
  rotateOrientation,
  orientationToYaw,
  yawToOrientation,
} from "./gridGeometry";

describe("gridGeometry cartesian", () => {
  it("Neutral is exactly 10×10", () => {
    expect(DEFAULT_GRID_SCALE).toBe(0);
    expect(densityForScale(0)).toBe(10);
    expect(GRID_DENSITY[0]).toBe(10);
    expect(gridScaleLabel(0)).toBe("Neutral (10×10)");
  });

  it("supports 11 Placement Precision levels", () => {
    expect(MIN_GRID_SCALE).toBe(-5);
    expect(MAX_GRID_SCALE).toBe(5);
    expect(densityForScale(-5)).toBe(5);
    expect(densityForScale(-4)).toBe(6);
    expect(densityForScale(-3)).toBe(7);
    expect(densityForScale(-2)).toBe(8);
    expect(densityForScale(-1)).toBe(9);
    expect(densityForScale(1)).toBe(12);
    expect(densityForScale(2)).toBe(14);
    expect(densityForScale(3)).toBe(16);
    expect(densityForScale(4)).toBe(18);
    expect(densityForScale(5)).toBe(20);
    expect(gridScaleLabel(-5)).toBe("-5 (5×5)");
    expect(gridScaleLabel(5)).toBe("+5 (20×20)");
  });

  it("cell center maps to normalized coordinates and back", () => {
    const density = 10;
    const center = cellCenterNormalized(4, 4, density);
    expect(center.x).toBeCloseTo(-0.1, 6);
    expect(center.y).toBeCloseTo(-0.1, 6);
    const cell = nearestValidCell(center.x, center.y, density);
    expect(cell).toEqual({ column: 4, row: 4 });
  });

  it("pointer maps to the cell whose square contains it", () => {
    const density = 10;
    const size = 500;
    const center = cellCenterNormalized(3, 6, density);
    const pixel = normalizedToPixel(center.x, center.y, size);
    expect(pointerToCell(pixel.px, pixel.py, size, density)).toEqual({ column: 3, row: 6 });
  });

  it("rejects cells whose center is outside the circle", () => {
    expect(isValidCell(0, 0, 10)).toBe(false);
    expect(isValidCell(9, 9, 10)).toBe(false);
    expect(isValidCell(4, 4, 10)).toBe(true);
    const corner = cellCenterNormalized(0, 0, 10);
    expect(isInsideCircle(corner.x, corner.y)).toBe(false);
    expect(pointerToCell(1, 1, 500, 10)).toBeNull();
  });

  it("keeps partially clipped perimeter cells when the center is inside", () => {
    // 10×10 cell (1,4): west-ish, center should be inside.
    expect(isValidCell(1, 4, 10)).toBe(true);
    const center = cellCenterNormalized(1, 4, 10);
    expect(isInsideCircle(center.x, center.y)).toBe(true);
  });

  it("adjacent-cell movement is exactly one valid square", () => {
    const next = adjacentCell(4, 4, 1, 0, 10);
    expect(next).toEqual({ column: 5, row: 4 });
    const invalid = adjacentCell(0, 0, -1, 0, 10);
    expect(invalid).toBeNull();
  });

  it("changing density remaps to the nearest cell without changing normalized position", () => {
    const origin = { x: -0.1, y: -0.12 };
    const atNeutral = remapDerivedCell(origin.x, origin.y, 10);
    const atPlus5 = remapDerivedCell(origin.x, origin.y, 20);
    const atMinus5 = remapDerivedCell(origin.x, origin.y, 5);
    const back = remapDerivedCell(origin.x, origin.y, 10);
    expect(atNeutral).toEqual(back);
    expect(atPlus5).not.toBeNull();
    expect(atMinus5).not.toBeNull();
    const plusCenter = cellCenterNormalized(atPlus5!.column, atPlus5!.row, 20);
    const minusCenter = cellCenterNormalized(atMinus5!.column, atMinus5!.row, 5);
    const distPlus = Math.hypot(plusCenter.x - origin.x, plusCenter.y - origin.y);
    const distMinus = Math.hypot(minusCenter.x - origin.x, minusCenter.y - origin.y);
    expect(distPlus).toBeLessThan(0.15);
    expect(distMinus).toBeLessThan(0.35);
  });

  it("pixelToNormalized and normalizedToPixel are inverse", () => {
    const { x, y } = pixelToNormalized(128, 256, 512);
    expect(x).toBeCloseTo(-0.5, 6);
    expect(y).toBeCloseTo(0, 6);
    const pixel = normalizedToPixel(x, y, 512);
    expect(pixel.px).toBeCloseTo(128, 6);
    expect(pixel.py).toBeCloseTo(256, 6);
  });

  it("legacy polar conversion lands inside the circle", () => {
    const north = legacyPolarToNormalized(2, 0);
    expect(north.x).toBeCloseTo(0, 1);
    expect(north.y).toBeLessThan(0);
    expect(isInsideCircle(north.x, north.y)).toBe(true);
    const cell = nearestValidCell(north.x, north.y, 10);
    expect(cell).not.toBeNull();
  });

  it("cellLabel uses column/row", () => {
    expect(cellLabel(0, 0)).toBe("C1R1");
    expect(cellLabel(4, 2)).toBe("C5R3");
  });

  it("camera orientation helpers remain 8-direction 45° steps", () => {
    expect(CARDINAL_LABELS).toHaveLength(8);
    expect(orientationToYaw("N")).toBe(0);
    expect(orientationToYaw("NE")).toBe(45);
    expect(yawToOrientation(90)).toBe("E");
    expect(rotateOrientation("N", 1)).toBe("NE");
    expect(rotateOrientation("N", -1)).toBe("NW");
  });
});

describe("required cartesian engine API", () => {
  it("exposes all 11 Placement Precision densities", () => {
    expect(ALL_GRID_SCALES).toEqual([-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]);
    const expected = [5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20];
    expect(ALL_GRID_SCALES.map(densityForScale)).toEqual(expected);
  });

  it("cellToNormalized and normalizedToNearestCell round-trip on every density", () => {
    for (const scale of ALL_GRID_SCALES) {
      const density = densityForScale(scale);
      const mid = Math.floor(density / 2);
      expect(isCellInsideCircle(mid, mid, density)).toBe(true);
      const center = cellToNormalized(mid, mid, density);
      expect(center).toEqual(cellCenterNormalized(mid, mid, density));
      const back = normalizedToNearestCell(center.x, center.y, density);
      expect(back).toEqual({ column: mid, row: mid });
      expect(isInsideCircle(center.x, center.y)).toBe(true);
    }
  });

  it("pointerToCell hits the containing square on every density", () => {
    const size = 800;
    for (const scale of ALL_GRID_SCALES) {
      const density = densityForScale(scale);
      const mid = Math.floor(density / 2);
      const center = cellToNormalized(mid, mid, density);
      const pixel = normalizedToPixel(center.x, center.y, size);
      expect(pointerToCell(pixel.px, pixel.py, size, density)).toEqual({ column: mid, row: mid });
    }
  });

  it("rejects corner cells whose center is outside the circle on every density", () => {
    for (const scale of ALL_GRID_SCALES) {
      const density = densityForScale(scale);
      expect(isCellInsideCircle(0, 0, density)).toBe(false);
      expect(isCellInsideCircle(density - 1, density - 1, density)).toBe(false);
      expect(isValidCell(0, 0, density)).toBe(false);
    }
  });

  it("adjacentCell stays on valid squares across densities", () => {
    for (const scale of ALL_GRID_SCALES) {
      const density = densityForScale(scale);
      const mid = Math.floor(density / 2);
      const east = adjacentCell(mid, mid, 1, 0, density);
      expect(east).toEqual({ column: mid + 1, row: mid });
      expect(isCellInsideCircle(east!.column, east!.row, density)).toBe(true);
      expect(adjacentCell(0, 0, -1, 0, density)).toBeNull();
    }
  });

  it("remapPositionToDensity keeps normalized position stable across all 11 densities", () => {
    const origin = { x: -0.18, y: 0.22 };
    expect(isInsideCircle(origin.x, origin.y)).toBe(true);
    const cells = ALL_GRID_SCALES.map((scale) => {
      const density = densityForScale(scale);
      const cell = remapPositionToDensity(origin.x, origin.y, density);
      expect(cell).not.toBeNull();
      expect(cell).toEqual(remapDerivedCell(origin.x, origin.y, density));
      expect(cell).toEqual(normalizedToNearestCell(origin.x, origin.y, density));
      return { density, cell: cell! };
    });
    for (const { density, cell } of cells) {
      const center = cellToNormalized(cell.column, cell.row, density);
      const dist = Math.hypot(center.x - origin.x, center.y - origin.y);
      expect(dist).toBeLessThan(cellSizeFor(density));
    }
    const back = remapPositionToDensity(origin.x, origin.y, 10);
    expect(back).toEqual(cells.find((c) => c.density === 10)?.cell);
  });
});

function cellSizeFor(density: number): number {
  return 2 / density + 1e-9;
}

describe("Work Order E frontend-testable geometry", () => {
  it("click inside a cell square maps to that cell identity, not a fractional offset", () => {
    const density = 10;
    const size = 500;
    const cell = { column: 3, row: 6 };
    expect(isValidCell(cell.column, cell.row, density)).toBe(true);
    const center = cellToNormalized(cell.column, cell.row, density);
    const sizeN = cellSizeNormalized(density);
    const offset = { x: center.x + sizeN * 0.25, y: center.y + sizeN * 0.25 };
    const pixel = normalizedToPixel(offset.x, offset.y, size);
    expect(pointerToCell(pixel.px, pixel.py, size, density)).toEqual(cell);
    const placed = cellToNormalized(cell.column, cell.row, density);
    expect(placed).toEqual(center);
    expect(placed.x).not.toBeCloseTo(offset.x, 6);
    expect(placed.y).not.toBeCloseTo(offset.y, 6);
  });

  it("clicks at opposite corners of the same cell still resolve to that cell center", () => {
    const density = 10;
    const size = 800;
    const cell = { column: 4, row: 4 };
    const center = cellToNormalized(cell.column, cell.row, density);
    const half = cellSizeNormalized(density) / 2;
    const insets = [
      { x: center.x - half + 1e-6, y: center.y - half + 1e-6 },
      { x: center.x + half - 1e-6, y: center.y + half - 1e-6 },
    ];
    for (const pt of insets) {
      const pixel = normalizedToPixel(pt.x, pt.y, size);
      expect(pointerToCell(pixel.px, pixel.py, size, density)).toEqual(cell);
    }
    expect(cellToNormalized(cell.column, cell.row, density)).toEqual(center);
  });

  it("zoom is view-only: cell identity and placement coords do not depend on display size", () => {
    const density = 10;
    const rel = { x: 0.42, y: 0.58 };
    const cells = [256, 512, 800, 1024].map((mapSize) =>
      pointerToCell(rel.x * mapSize, rel.y * mapSize, mapSize, density),
    );
    expect(cells[0]).not.toBeNull();
    for (const cell of cells) {
      expect(cell).toEqual(cells[0]);
    }
    const placed = cellToNormalized(cells[0]!.column, cells[0]!.row, density);
    for (const mapSize of [256, 512, 800, 1024]) {
      const again = pointerToCell(rel.x * mapSize, rel.y * mapSize, mapSize, density)!;
      expect(cellToNormalized(again.column, again.row, density)).toEqual(placed);
    }
  });

  it("cellSizeNormalized is 2/density and remap keeps normalized placement stable", () => {
    const origin = { x: -0.1, y: -0.12 };
    expect(cellSizeNormalized(5)).toBeCloseTo(0.4, 10);
    expect(cellSizeNormalized(10)).toBeCloseTo(0.2, 10);
    expect(cellSizeNormalized(20)).toBeCloseTo(0.1, 10);
    const at5 = remapPositionToDensity(origin.x, origin.y, 5);
    const at10 = remapPositionToDensity(origin.x, origin.y, 10);
    const at20 = remapPositionToDensity(origin.x, origin.y, 20);
    expect(at5).not.toBeNull();
    expect(at10).not.toBeNull();
    expect(at20).not.toBeNull();
    expect(origin).toEqual({ x: -0.1, y: -0.12 });
    expect(at5).not.toEqual(at20);
  });

  it("rejects pointer hits and coordinates outside the valid circle or grid", () => {
    const density = 10;
    const size = 500;
    expect(pointerToCell(0, 0, size, density)).toBeNull();
    expect(pointerToCell(size - 1, size - 1, size, density)).toBeNull();
    expect(pointerToCell(-10, 250, size, density)).toBeNull();
    expect(isValidCell(-1, 4, density)).toBe(false);
    expect(isValidCell(4, 10, density)).toBe(false);
    expect(isInsideCircle(1, 1)).toBe(false);
    expect(isInsideCircle(0, 0)).toBe(true);
    expect(isCellInsideCircle(0, 0, density)).toBe(false);
  });

  it("clampGridScale stays on the 11-level density table", () => {
    expect(clampGridScale(-99)).toBe(-5);
    expect(clampGridScale(99)).toBe(5);
    expect(clampGridScale(0.4)).toBe(0);
    expect(clampGridScale(0.6)).toBe(1);
    expect(densityForScale(99)).toBe(20);
    expect(densityForScale(-99)).toBe(5);
  });

  it("camera orientation wraps on 45-degree cardinals; unknown labels default to 0", () => {
    expect(orientationToYaw("unknown")).toBe(0);
    expect(orientationToYaw("s")).toBe(180);
    expect(yawToOrientation(405)).toBe("NE");
    expect(rotateOrientation("NW", 1)).toBe("N");
    expect(rotateOrientation("N", 8)).toBe("N");
  });
});
