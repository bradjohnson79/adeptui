/**
 * Cartesian Spatial Map geometry — shared by Characters, Props, and Cameras.
 *
 * Authoritative physical location: normalizedX / normalizedY in [-1, 1]
 * (x: west→east, y: north→south, matching the circular map bitmap).
 *
 * Derived at the current Placement Precision density:
 *   gridColumn / gridRow of the nearest valid square cell.
 *
 * Changing Placement Precision MUST NOT mutate normalized coordinates.
 * A cell is valid iff its center lies inside the unit circle.
 */

export const MIN_GRID_SCALE = -5;
export const MAX_GRID_SCALE = 5;
export const DEFAULT_GRID_SCALE = 0;

export type GridScale = -5 | -4 | -3 | -2 | -1 | 0 | 1 | 2 | 3 | 4 | 5;

export const GRID_DENSITY: Record<GridScale, number> = {
  [-5]: 5,
  [-4]: 6,
  [-3]: 7,
  [-2]: 8,
  [-1]: 9,
  [0]: 10,
  [1]: 12,
  [2]: 14,
  [3]: 16,
  [4]: 18,
  [5]: 20,
};

export const CARDINAL_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const;
export type CardinalLabel = (typeof CARDINAL_LABELS)[number];

export type GridCell = { column: number; row: number };
export type NormalizedPoint = { x: number; y: number };

const CIRCLE_RADIUS = 1;

export function clampGridScale(scale: number): GridScale {
  const rounded = Math.round(Number.isFinite(scale) ? scale : 0);
  return Math.max(MIN_GRID_SCALE, Math.min(MAX_GRID_SCALE, rounded)) as GridScale;
}

export function densityForScale(scale: number): number {
  return GRID_DENSITY[clampGridScale(scale)];
}

export function gridScaleLabel(scale: number): string {
  const s = clampGridScale(scale);
  const n = densityForScale(s);
  if (s === 0) return `Neutral (${n}×${n})`;
  const prefix = s > 0 ? `+${s}` : `${s}`;
  return `${prefix} (${n}×${n})`;
}

export function isInsideCircle(x: number, y: number, radius = CIRCLE_RADIUS): boolean {
  return x * x + y * y <= radius * radius;
}

export function cellSizeNormalized(density: number): number {
  return 2 / Math.max(1, density);
}

export function cellCenterNormalized(column: number, row: number, density: number): NormalizedPoint {
  const size = cellSizeNormalized(density);
  return {
    x: -1 + (column + 0.5) * size,
    y: -1 + (row + 0.5) * size,
  };
}

export function isValidCell(column: number, row: number, density: number): boolean {
  if (column < 0 || row < 0 || column >= density || row >= density) return false;
  const center = cellCenterNormalized(column, row, density);
  return isInsideCircle(center.x, center.y);
}

export function cellLabel(column: number, row: number): string {
  return `C${column + 1}R${row + 1}`;
}

/** Spreadsheet cell matching studio-api metric.grid_cell_label. column 4, row 7 → E8. */
export function chessCellLabel(column: number, row: number): string {
  if (column < 0 || row < 0 || !Number.isFinite(column) || !Number.isFinite(row)) return "";
  let letters = "";
  let n = Math.floor(column);
  while (true) {
    letters = String.fromCharCode(65 + (n % 26)) + letters;
    n = Math.floor(n / 26) - 1;
    if (n < 0) break;
  }
  return `${letters}${Math.floor(row) + 1}`;
}

export function pixelToNormalized(px: number, py: number, size: number): NormalizedPoint {
  const half = size / 2;
  return {
    x: (px - half) / half,
    y: (py - half) / half,
  };
}

export function normalizedToPixel(x: number, y: number, size: number): { px: number; py: number } {
  const half = size / 2;
  return {
    px: (x + 1) * half,
    py: (y + 1) * half,
  };
}

export function pointerToCell(px: number, py: number, mapSize: number, density: number): GridCell | null {
  const { x, y } = pixelToNormalized(px, py, mapSize);
  const column = Math.floor(((x + 1) / 2) * density);
  const row = Math.floor(((y + 1) / 2) * density);
  if (!isValidCell(column, row, density)) return null;
  return { column, row };
}

export function nearestValidCell(x: number, y: number, density: number): GridCell | null {
  const guessedColumn = Math.round(((x + 1) / 2) * density - 0.5);
  const guessedRow = Math.round(((y + 1) / 2) * density - 0.5);
  const column = Math.max(0, Math.min(density - 1, guessedColumn));
  const row = Math.max(0, Math.min(density - 1, guessedRow));
  if (isValidCell(column, row, density)) return { column, row };

  let best: GridCell | null = null;
  let bestDist = Number.POSITIVE_INFINITY;
  for (let r = 0; r < density; r += 1) {
    for (let c = 0; c < density; c += 1) {
      if (!isValidCell(c, r, density)) continue;
      const center = cellCenterNormalized(c, r, density);
      const dx = center.x - x;
      const dy = center.y - y;
      const dist = dx * dx + dy * dy;
      if (dist < bestDist) {
        bestDist = dist;
        best = { column: c, row: r };
      }
    }
  }
  return best;
}

export function adjacentCell(
  column: number,
  row: number,
  deltaColumn: number,
  deltaRow: number,
  density: number,
): GridCell | null {
  const next = { column: column + deltaColumn, row: row + deltaRow };
  if (!isValidCell(next.column, next.row, density)) return null;
  return next;
}

export function remapDerivedCell(x: number, y: number, density: number): GridCell | null {
  return nearestValidCell(x, y, density);
}

/** Required Cartesian engine names. Existing helpers stay as the implementation. */
export function cellToNormalized(column: number, row: number, density: number): NormalizedPoint {
  return cellCenterNormalized(column, row, density);
}

export function normalizedToNearestCell(x: number, y: number, density: number): GridCell | null {
  return nearestValidCell(x, y, density);
}

export function isCellInsideCircle(column: number, row: number, density: number): boolean {
  return isValidCell(column, row, density);
}

export function remapPositionToDensity(x: number, y: number, density: number): GridCell | null {
  return remapDerivedCell(x, y, density);
}

export const ALL_GRID_SCALES: GridScale[] = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];

/**
 * Convert a legacy polar (ring, spoke) coordinate into normalized map space.
 * ring 0 = innermost, spoke 0 = North, clockwise.
 */
export function legacyPolarToNormalized(ring: number, spoke: number): NormalizedPoint {
  const ringCount = 5;
  const spokeCount = 8;
  const r = Math.max(0, Math.min(ringCount - 1, ring));
  const s = ((spoke % spokeCount) + spokeCount) % spokeCount;
  const radius = ((r + 1) / ringCount) * 0.92;
  const angle = (s / spokeCount) * Math.PI * 2 - Math.PI / 2;
  return {
    x: radius * Math.cos(angle),
    y: radius * Math.sin(angle),
  };
}

export function orientationToYaw(orientation: string): number {
  const idx = CARDINAL_LABELS.indexOf(orientation.toUpperCase() as CardinalLabel);
  if (idx < 0) return 0;
  return idx * 45;
}

export function yawToOrientation(yawDegrees: number): CardinalLabel {
  const idx = (((Math.round(yawDegrees / 45) % 8) + 8) % 8);
  return CARDINAL_LABELS[idx];
}

export function rotateOrientation(orientation: string, steps: number): CardinalLabel {
  let idx = CARDINAL_LABELS.indexOf(orientation.toUpperCase() as CardinalLabel);
  if (idx < 0) idx = 0;
  idx = (idx + steps) % 8;
  if (idx < 0) idx += 8;
  return CARDINAL_LABELS[idx];
}

