import type { MovementArrow, MovementSegment, SpatialCharacterPlacement, SpatialMapDocument } from "./types";

export const MOVEMENT_MAX = 5;

export function movementAlias(segmentNumber: number | null | undefined): string {
  return `M${Number(segmentNumber || 0) || 1}`;
}

export function movementLabel(segment: Pick<MovementSegment, "segmentNumber" | "beatName">): string {
  const beat = (segment.beatName || "").trim();
  const alias = movementAlias(segment.segmentNumber);
  return beat ? `${alias} — ${beat}` : `Movement ${segment.segmentNumber}`;
}

export function listMovements(document: SpatialMapDocument | null | undefined): MovementSegment[] {
  return [...(document?.movementSegments || [])].sort((a, b) => a.segmentNumber - b.segmentNumber);
}

export function activeMovement(document: SpatialMapDocument | null | undefined): MovementSegment | null {
  const rows = listMovements(document);
  if (!rows.length) return null;
  const activeId = document?.activeMovementSegmentId || "";
  return rows.find((row) => row.id === activeId) || rows[0];
}

export function parseMovementAlias(text: string | null | undefined): number | null {
  const match = String(text || "").match(/(?:~)?\bM\s*([1-5])\b/i);
  if (!match) return null;
  return Number(match[1]);
}

export function movementChip(segment: Pick<MovementSegment, "segmentNumber"> | null | undefined): string {
  if (!segment) return "";
  return `~${movementAlias(segment.segmentNumber)}`;
}

function placementKey(item: SpatialCharacterPlacement): string {
  return item.characterId || item.id || item.label || "";
}

function coordKey(item: SpatialCharacterPlacement): string {
  return [
    item.normalizedX,
    item.normalizedY,
    item.gridRow,
    item.gridColumn,
    item.visible,
    item.yawDegrees,
  ].join(":");
}

export function computeClientArrows(
  document: SpatialMapDocument | null | undefined,
  selectedCharacterId?: string | null,
): MovementArrow[] {
  const rows = listMovements(document);
  if (rows.length < 2) return [];
  const active = activeMovement(document);
  const focus = (selectedCharacterId || "").trim();
  let pairs = rows.slice(0, -1).map((start, index) => [start, rows[index + 1]] as const);
  if (!focus && active) {
    const prior = rows.filter((row) => row.segmentNumber < active.segmentNumber).at(-1);
    if (prior) pairs = [[prior, active]];
  }
  const arrows: MovementArrow[] = [];
  for (const [start, end] of pairs) {
    const byId = new Map((start.characterStates || []).map((c) => [placementKey(c), c]));
    for (const dest of end.characterStates || []) {
      const key = placementKey(dest);
      const origin = byId.get(key);
      if (!origin) continue;
      if (focus && key !== focus && dest.id !== focus && dest.characterId !== focus) continue;
      if (coordKey(origin) === coordKey(dest)) continue;
      arrows.push({
        characterId: dest.characterId || key,
        label: dest.label || dest.tag || key,
        fromAlias: movementAlias(start.segmentNumber),
        toAlias: movementAlias(end.segmentNumber),
        from: {
          normalizedX: origin.normalizedX,
          normalizedY: origin.normalizedY,
          gridRow: origin.gridRow,
          gridColumn: origin.gridColumn,
        },
        to: {
          normalizedX: dest.normalizedX,
          normalizedY: dest.normalizedY,
          gridRow: dest.gridRow,
          gridColumn: dest.gridColumn,
        },
      });
    }
  }
  return arrows;
}
