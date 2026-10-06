/**
 * Spin Camera geometry helpers.
 *
 * Reuses the same adept-world-v1 mapping as character/prop/camera placement:
 *   - normalized x = -1..+1 maps to world x = -widthMeters/2 .. +widthMeters/2
 *   - normalized y = -1..+1 maps to world z = -depthMeters/2 .. +depthMeters/2
 * North (map up) is -Z, so the top of the normalized square (y = -1)
 * becomes the most negative z value.
 */
import { cellCenterNormalized, densityForScale, type GridScale } from "./gridGeometry";

/** Convert a placement-grid cell into world x/z meters. */
export function cellToWorldMeters(
  column: number,
  row: number,
  gridScale: GridScale,
  widthMeters: number,
  depthMeters: number,
): { x: number; z: number } {
  const density = densityForScale(gridScale);
  const center = cellCenterNormalized(column, row, density);
  return normalizedToWorldMeters(center.x, center.y, widthMeters, depthMeters);
}

/** Convert normalized map coordinates into world x/z meters. */
export function normalizedToWorldMeters(
  normalizedX: number,
  normalizedY: number,
  widthMeters: number,
  depthMeters: number,
): { x: number; z: number } {
  const halfW = Math.max(0, Number(widthMeters) || 0) / 2;
  const halfD = Math.max(0, Number(depthMeters) || 0) / 2;
  return {
    x: normalizedX * halfW,
    z: normalizedY * halfD,
  };
}

/** Inverse: world x/z meters back to normalized map coordinates. */
export function worldMetersToNormalized(
  x: number,
  z: number,
  widthMeters: number,
  depthMeters: number,
): { normalizedX: number; normalizedY: number } {
  const halfW = Math.max(1e-9, Number(widthMeters) || 1) / 2;
  const halfD = Math.max(1e-9, Number(depthMeters) || 1) / 2;
  return {
    normalizedX: x / halfW,
    normalizedY: z / halfD,
  };
}

/** Format a world-meter coordinate for creator-facing display. */
export function formatMeters(value: number): string {
  const v = Number(value);
  if (!Number.isFinite(v)) return "0.0";
  return v.toFixed(1);
}

/** Canonical order for the five spin-package views. */
export const SPIN_VIEW_ORDER: ReadonlyArray<"center" | "north" | "east" | "south" | "west"> = [
  "center",
  "north",
  "east",
  "south",
  "west",
];

/** Display label for each spin direction. */
export function spinViewLabel(direction: string): string {
  const d = String(direction).toLowerCase();
  if (d === "center") return "Center";
  if (d === "north") return "North";
  if (d === "east") return "East";
  if (d === "south") return "South";
  if (d === "west") return "West";
  return direction;
}

/** Default camera height, FOV, and lens for a Spin Camera. */
export const SPIN_CAMERA_DEFAULTS = {
  cameraHeight: 1.6,
  fov: 75,
  lensMm: 35,
};
