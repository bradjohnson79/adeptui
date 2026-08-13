/**
 * Circular/radial Spatial Map geometry.
 *
 * The authoritative placement store uses integer (ring, spoke) coordinates:
 *   - ring: 0 = innermost ring, RING_COUNT-1 = outermost ring
 *   - spoke: 0 = North, 1 = North-East, ..., 7 = North-West (clockwise, 45° steps)
 *
 * The grid scale (-3 .. +3) only affects the visual radius of the rings and the
 * size of markers. It never mutates the stored placement coordinate.
 *
 * All positions are normalized to [-1, 1] relative to the map center, so grid
 * scale changes are drift-free.
 */

export const RING_COUNT = 5;
export const SPOKE_COUNT = 8;

export const MIN_GRID_SCALE = -3;
export const MAX_GRID_SCALE = 3;
export const DEFAULT_GRID_SCALE = 0;

export type GridScale = -3 | -2 | -1 | 0 | 1 | 2 | 3;

export const SPOKE_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

/** Convert a spoke index to its compass label. */
export function spokeLabel(spoke: number): string {
  return SPOKE_LABELS[(spoke + SPOKE_COUNT) % SPOKE_COUNT] || "";
}

/** Convert a cell (ring, spoke) to a normalized (x, z) position. */
export function cellToNormalized(ring: number, spoke: number): { x: number; z: number } {
  const r = Math.max(0, Math.min(RING_COUNT - 1, ring));
  const s = ((spoke % SPOKE_COUNT) + SPOKE_COUNT) % SPOKE_COUNT;
  // Radius from 0 (center) to 1 (outer edge). Leave a small margin.
  const radius = ((r + 1) / RING_COUNT) * 0.92;
  // Angle: 0 = North (-90° in SVG), increase clockwise.
  const angle = (s / SPOKE_COUNT) * Math.PI * 2 - Math.PI / 2;
  return {
    x: radius * Math.cos(angle),
    z: radius * Math.sin(angle),
  };
}

/** Convert a normalized (x, z) position to the nearest (ring, spoke). */
export function normalizedToCell(x: number, z: number): { ring: number; spoke: number } {
  const radius = Math.sqrt(x * x + z * z);
  const ring = Math.max(0, Math.min(RING_COUNT - 1, Math.round((radius / 0.92) * RING_COUNT - 1)));
  let angle = Math.atan2(z, x) + Math.PI / 2;
  if (angle < 0) angle += Math.PI * 2;
  const spoke = Math.round((angle / (Math.PI * 2)) * SPOKE_COUNT) % SPOKE_COUNT;
  return { ring, spoke };
}

/** Convert a pixel coordinate within a square map to normalized (x, z). */
export function pixelToNormalized(px: number, py: number, size: number): { x: number; z: number } {
  return {
    x: (px - size / 2) / (size / 2),
    z: (py - size / 2) / (size / 2),
  };
}

/** Convert a normalized (x, z) position to pixel coordinates within a square map. */
export function normalizedToPixel(x: number, z: number, size: number): { px: number; py: number } {
  return {
    px: (x + 1) * (size / 2),
    py: (z + 1) * (size / 2),
  };
}

/** Scale factor for a given GridScale. Neutral = 1.0, -3 = 0.5, +3 = 2.0. */
export function scaleFactor(scale: GridScale): number {
  return 1 + scale * 0.25;
}

/** Visual base radius for the outer ring at a given scale. */
export function outerRingRadiusPx(mapSize: number, scale: GridScale): number {
  return (mapSize / 2) * 0.92 * scaleFactor(scale);
}

/** Cell label for display: R1N, R2NE, etc. */
export function cellLabel(ring: number, spoke: number): string {
  return `R${ring + 1}${spokeLabel(spoke)}`;
}

/** Convert camera orientation (N, NE, E, ...) to yaw degrees (0 = North, clockwise). */
export function orientationToYaw(orientation: string): number {
  const idx = SPOKE_LABELS.indexOf(orientation.toUpperCase());
  if (idx < 0) return 0;
  return idx * 45;
}

/** Convert yaw degrees to the nearest orientation. */
export function yawToOrientation(yawDegrees: number): string {
  const idx = (Math.round(yawDegrees / 45) % SPOKE_COUNT + SPOKE_COUNT) % SPOKE_COUNT;
  return SPOKE_LABELS[idx];
}

/** Rotate an orientation by a number of 45° steps. */
export function rotateOrientation(orientation: string, steps: number): string {
  let idx = SPOKE_LABELS.indexOf(orientation.toUpperCase());
  if (idx < 0) idx = 0;
  idx = (idx + steps) % SPOKE_COUNT;
  if (idx < 0) idx += SPOKE_COUNT;
  return SPOKE_LABELS[idx];
}
