/**
 * Camera movement path overlay from the camera's own per-movement poses.
 *
 * Non-POV (default / free): C1 is a free Spatial Map entity like a Character.
 * User places it; M1/M2 restore that camera's saved pose for the segment.
 * Green path connects the camera's own M1->M2 positions. If that path is in
 * the vicinity of a character path, offset it beside purple -- never overlapping
 * and never meaning "stuck to character."
 *
 * POV (Shot Size = POV only): C-glyph attaches to the Primary Subject character.
 * No green path. Leaving POV restores free-entity mode.
 */
import type { SpatialCamera } from "./types";
import type { MovementArrow } from "./types";
import { cellCenterNormalized, cellSizeNormalized } from "./gridGeometry";

/** ~1.5 cm physical target; clamped so SVG strokes stay side-by-side. */
export const CAMERA_PATH_OFFSET_CM = 1.5;
/** Minimum normalized offset so purple/green strokes never share the same pixels. */
export const CAMERA_PATH_MIN_OFFSET_NORMALIZED = 0.035;
/**
 * Character marker radius as a fraction of cell size (SpatialGrid: cellCircleR=0.4*cell,
 * markerR=0.72*cellCircleR => 0.288*cell). Used so green path clears the red circle.
 */
export const CHARACTER_MARKER_RADIUS_CELL_FRACTION = 0.288;
/** Camera half-size ~ markerR * 0.68 (SpatialGrid cameraSize ~ markerR*2*0.68). */
export const CAMERA_MARKER_HALF_CELL_FRACTION = CHARACTER_MARKER_RADIUS_CELL_FRACTION * 0.68;
/** Extra pad beyond marker radii so C1 never looks "inside" the character circle. */
export const CAMERA_PATH_MARKER_PAD_NORMALIZED = 0.012;
/** Nearby corridor: camera endpoints within this multiple of clearance of character path. */
export const CAMERA_PATH_VICINITY_MULTIPLE = 2.25;

export type CameraAttachMode = "pov" | "free";

export type CameraMovementArrow = {
  cameraId: string;
  subjectCharacterId: string;
  label: string;
  fromAlias: string;
  toAlias: string;
  from: { normalizedX: number; normalizedY: number };
  to: { normalizedX: number; normalizedY: number };
};

export type CameraPoseLike = {
  id?: string;
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridRow?: number;
  gridColumn?: number;
  visible?: boolean;
  shotSize?: string | null;
  attachMode?: string | null;
  primarySubject?: string | null;
  shotType?: string | null;
  label?: string | null;
  cameraSlot?: number | null;
};

export type CameraSegmentSnapshot = {
  segmentNumber: number;
  cameraStates?: CameraPoseLike[] | null;
};

export function isCameraFollowSubject(primarySubject: string | null | undefined): boolean {
  const raw = String(primarySubject || "auto").trim().toLowerCase();
  return Boolean(raw) && raw !== "auto" && raw !== "environment";
}

export function cameraFollowSubjectId(
  camera: Pick<SpatialCamera, "primarySubject"> | { primarySubject?: string | null },
): string | null {
  if (!isCameraFollowSubject(camera.primarySubject)) return null;
  return String(camera.primarySubject).trim();
}

export function attachModeFromShotSize(shotSize: string | null | undefined): CameraAttachMode {
  const v = String(shotSize || "").trim().toLowerCase().replace(/[ -]/g, "_");
  return v === "pov" ? "pov" : "free";
}

/**
 * Classify attach mode. POV only when Shot Size / shotType / attachMode is pov.
 * Legacy attachMode "follow" is treated as free -- cameras do not auto-ride characters.
 */
export function resolveCameraAttachMode(
  camera:
    | Pick<SpatialCamera, "primarySubject" | "attachMode" | "shotSize">
    | {
        primarySubject?: string | null;
        attachMode?: string | null;
        shotSize?: string | null;
        shotType?: string | null;
      },
): CameraAttachMode {
  const explicit = String((camera as { attachMode?: string | null }).attachMode || "")
    .trim()
    .toLowerCase();
  if (explicit === "pov") return "pov";
  const shotType = String((camera as { shotType?: string | null }).shotType || "")
    .trim()
    .toLowerCase()
    .replace(/[ -]/g, "_");
  const shotSize = String(camera.shotSize || "")
    .trim()
    .toLowerCase()
    .replace(/[ -]/g, "_");
  if (shotType === "pov" || shotSize === "pov") return "pov";
  return "free";
}

/** Lateral offset in normalized map units -- clears character + camera marker radii. */
export function cameraPathLateralOffsetNormalized(
  metersPerCell: number = 1,
  density: number = 10,
): number {
  const dens = Math.max(1, density);
  const cell = cellSizeNormalized(dens);
  const meters = Math.max(1e-6, Number(metersPerCell) || 1);
  const fromCm = (CAMERA_PATH_OFFSET_CM / 100) * (cell / meters);
  const markerClearance =
    cell * (CHARACTER_MARKER_RADIUS_CELL_FRACTION + CAMERA_MARKER_HALF_CELL_FRACTION) +
    CAMERA_PATH_MARKER_PAD_NORMALIZED;
  return Math.max(CAMERA_PATH_MIN_OFFSET_NORMALIZED, fromCm, markerClearance);
}

/** Prefer normalized coords; fall back to grid cell centers. */
export function arrowPoint(
  p: { normalizedX?: number | null; normalizedY?: number | null; gridColumn?: number; gridRow?: number },
  density: number = 10,
): { x: number; y: number } | null {
  if (typeof p.normalizedX === "number" && typeof p.normalizedY === "number") {
    return { x: p.normalizedX, y: p.normalizedY };
  }
  const col = Number(p.gridColumn);
  const row = Number(p.gridRow);
  if (Number.isFinite(col) && Number.isFinite(row) && col >= 0 && row >= 0) {
    const center = cellCenterNormalized(col, row, Math.max(1, density));
    return { x: center.x, y: center.y };
  }
  return null;
}

/** Perpendicular unit normal (left of travel). Stable side -- never flips mid-path. */
export function lateralNormal(dx: number, dy: number): { nx: number; ny: number } | null {
  const len = Math.hypot(dx, dy);
  if (!(len > 1e-9)) return null;
  return { nx: -dy / len, ny: dx / len };
}

export function movementAliasNumber(alias: string | null | undefined): number | null {
  const match = String(alias || "").match(/\bM\s*([1-5])\b/i);
  if (!match) return null;
  return Number(match[1]);
}

function posesEqual(
  a: { x: number; y: number },
  b: { x: number; y: number },
  eps = 1e-6,
): boolean {
  return Math.abs(a.x - b.x) <= eps && Math.abs(a.y - b.y) <= eps;
}

function cameraKey(cam: CameraPoseLike): string {
  return String(cam.id || "").trim();
}

function findPose(states: CameraPoseLike[] | null | undefined, id: string): CameraPoseLike | null {
  const wanted = String(id || "").trim();
  if (!wanted) return null;
  return (states || []).find((c) => cameraKey(c) === wanted) || null;
}

/**
 * If the camera's own path sits in the corridor of a character path, push it
 * laterally to clearance. Far-away free placements are left exactly as saved.
 */
export function offsetCameraPathIfNearCharacter(
  camFrom: { x: number; y: number },
  camTo: { x: number; y: number },
  characterArrows: MovementArrow[] | null | undefined,
  density: number = 10,
  metersPerCell: number = 1,
): { from: { x: number; y: number }; to: { x: number; y: number }; subjectCharacterId: string } {
  const clearance = cameraPathLateralOffsetNormalized(metersPerCell, density);
  const vicinity = clearance * CAMERA_PATH_VICINITY_MULTIPLE;
  let bestSubject = "";
  let bestFrom = camFrom;
  let bestTo = camTo;
  let bestScore = Number.POSITIVE_INFINITY;

  for (const arrow of characterArrows || []) {
    const cFrom = arrowPoint(arrow.from, density);
    const cTo = arrowPoint(arrow.to, density);
    if (!cFrom || !cTo) continue;
    const dFrom = Math.hypot(camFrom.x - cFrom.x, camFrom.y - cFrom.y);
    const dTo = Math.hypot(camTo.x - cTo.x, camTo.y - cTo.y);
    if (dFrom > vicinity && dTo > vicinity) continue;
    const n = lateralNormal(cTo.x - cFrom.x, cTo.y - cFrom.y);
    if (!n) continue;
    const score = Math.min(dFrom, dTo);
    if (score >= bestScore) continue;
    bestScore = score;
    bestSubject = String(arrow.characterId || "");
    bestFrom = pushAwayFromPoint(camFrom, cFrom, n, clearance);
    bestTo = pushAwayFromPoint(camTo, cTo, n, clearance);
  }
  return { from: bestFrom, to: bestTo, subjectCharacterId: bestSubject };
}

function pushAwayFromPoint(
  point: { x: number; y: number },
  other: { x: number; y: number },
  n: { nx: number; ny: number },
  clearance: number,
): { x: number; y: number } {
  const dx = point.x - other.x;
  const dy = point.y - other.y;
  const dist = Math.hypot(dx, dy);
  if (dist >= clearance - 1e-9) return point;
  // Prefer the side the camera already sits on; if coincident, use left-of-travel.
  let side = dx * n.nx + dy * n.ny;
  if (Math.abs(side) < 1e-9) side = 1;
  const sign = side >= 0 ? 1 : -1;
  return {
    x: other.x + n.nx * clearance * sign,
    y: other.y + n.ny * clearance * sign,
  };
}

export type ComputeCameraMovementArrowsOptions = {
  metersPerCell?: number;
  density?: number;
};

/**
 * Green path from the camera's own ordered segment poses.
 * POV cameras are skipped. Same-pose segments emit nothing.
 */
export function computeCameraMovementArrows(
  segments: CameraSegmentSnapshot[] | null | undefined,
  cameras:
    | Array<
        Pick<
          SpatialCamera,
          "id" | "visible" | "label" | "cameraSlot" | "normalizedX" | "normalizedY" | "gridRow" | "gridColumn"
        > & {
          attachMode?: string | null;
          shotSize?: string | null;
          shotType?: string | null;
          primarySubject?: string | null;
        }
      >
    | null
    | undefined,
  characterArrows?: MovementArrow[] | null,
  options?: ComputeCameraMovementArrowsOptions,
): CameraMovementArrow[] {
  const rows = [...(segments || [])].sort((a, b) => Number(a.segmentNumber || 0) - Number(b.segmentNumber || 0));
  if (rows.length < 2) return [];

  const metersPerCell = options?.metersPerCell ?? 1;
  const density = options?.density ?? 10;
  const live = (cameras || []).filter((cam) => cam.visible !== false && String(cam.id || "").trim());
  if (!live.length) return [];

  live.sort((a, b) => {
    const slot = (a.cameraSlot ?? 0) - (b.cameraSlot ?? 0);
    if (slot !== 0) return slot;
    return String(a.id).localeCompare(String(b.id));
  });

  const out: CameraMovementArrow[] = [];
  for (const cam of live) {
    if (resolveCameraAttachMode(cam) === "pov") continue;
    const camLabel =
      cam.cameraSlot != null && cam.cameraSlot >= 0
        ? `C${cam.cameraSlot + 1}`
        : String(cam.label || "Camera").trim() || "Camera";
    for (let i = 0; i < rows.length - 1; i += 1) {
      const start = rows[i];
      const end = rows[i + 1];
      const origin = findPose(start.cameraStates, cam.id) || (start.segmentNumber === rows[0].segmentNumber ? cam : null);
      const dest = findPose(end.cameraStates, cam.id);
      if (!origin || !dest) continue;
      const from = arrowPoint(origin, density);
      const to = arrowPoint(dest, density);
      if (!from || !to) continue;
      if (posesEqual(from, to)) continue;
      const nudged = offsetCameraPathIfNearCharacter(from, to, characterArrows, density, metersPerCell);
      out.push({
        cameraId: cam.id,
        subjectCharacterId: nudged.subjectCharacterId,
        label: `${camLabel} ${start.segmentNumber}->${end.segmentNumber}`,
        fromAlias: `M${start.segmentNumber}`,
        toAlias: `M${end.segmentNumber}`,
        from: { normalizedX: nudged.from.x, normalizedY: nudged.from.y },
        to: { normalizedX: nudged.to.x, normalizedY: nudged.to.y },
      });
    }
  }
  return out;
}

export type FollowCameraScrubPoint = {
  normalizedX: number;
  normalizedY: number;
  alias: string;
  attachMode: CameraAttachMode;
};

/**
 * Bind a free camera glyph to its own green path at the active movement index.
 * Display helper only -- hydrate from cameraStates is the persistence authority.
 */
export function resolveFollowCameraScrubPosition(
  cameraId: string,
  cameraArrows: CameraMovementArrow[] | null | undefined,
  activeAlias: string | null | undefined,
): FollowCameraScrubPoint | null {
  const id = String(cameraId || "").trim();
  if (!id) return null;
  const pathRows = (cameraArrows || [])
    .filter((a) => a.cameraId === id)
    .slice()
    .sort((a, b) => {
      const an = movementAliasNumber(a.fromAlias) ?? 0;
      const bn = movementAliasNumber(b.fromAlias) ?? 0;
      if (an !== bn) return an - bn;
      return (movementAliasNumber(a.toAlias) ?? 0) - (movementAliasNumber(b.toAlias) ?? 0);
    });
  if (!pathRows.length) return null;

  const active = String(activeAlias || "").trim().toUpperCase() || "M1";
  const activeNum = movementAliasNumber(active) ?? 1;
  const asFree = (x: number, y: number, alias: string): FollowCameraScrubPoint => ({
    normalizedX: x,
    normalizedY: y,
    alias,
    attachMode: "free",
  });

  for (const arrow of pathRows) {
    if (String(arrow.fromAlias || "").trim().toUpperCase() === active) {
      return asFree(arrow.from.normalizedX, arrow.from.normalizedY, arrow.fromAlias);
    }
  }
  for (const arrow of pathRows) {
    if (String(arrow.toAlias || "").trim().toUpperCase() === active) {
      return asFree(arrow.to.normalizedX, arrow.to.normalizedY, arrow.toAlias);
    }
  }

  const first = pathRows[0];
  const last = pathRows[pathRows.length - 1];
  const firstFrom = movementAliasNumber(first.fromAlias) ?? 1;
  const lastTo = movementAliasNumber(last.toAlias) ?? firstFrom;
  if (activeNum <= firstFrom) {
    return asFree(first.from.normalizedX, first.from.normalizedY, first.fromAlias);
  }
  if (activeNum >= lastTo) {
    return asFree(last.to.normalizedX, last.to.normalizedY, last.toAlias);
  }
  let best: FollowCameraScrubPoint = asFree(
    first.from.normalizedX,
    first.from.normalizedY,
    first.fromAlias,
  );
  for (const arrow of pathRows) {
    const fromN = movementAliasNumber(arrow.fromAlias) ?? 0;
    const toN = movementAliasNumber(arrow.toAlias) ?? 0;
    if (fromN <= activeNum) {
      best = asFree(arrow.from.normalizedX, arrow.from.normalizedY, arrow.fromAlias);
    }
    if (toN <= activeNum) {
      best = asFree(arrow.to.normalizedX, arrow.to.normalizedY, arrow.toAlias);
    }
  }
  return best;
}

export type SubjectPlacementPoint = {
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridColumn?: number;
  gridRow?: number;
};

/** POV scrub: attach C-glyph to the live character marker. */
export function resolvePovCameraScrubPosition(
  subject: SubjectPlacementPoint | null | undefined,
  activeAlias: string | null | undefined,
  density: number = 10,
): FollowCameraScrubPoint | null {
  if (!subject) return null;
  const alias = String(activeAlias || "").trim().toUpperCase() || "M1";
  if (typeof subject.normalizedX === "number" && typeof subject.normalizedY === "number") {
    return {
      normalizedX: subject.normalizedX,
      normalizedY: subject.normalizedY,
      alias,
      attachMode: "pov",
    };
  }
  const col = Number(subject.gridColumn);
  const row = Number(subject.gridRow);
  if (Number.isFinite(col) && Number.isFinite(row) && col >= 0 && row >= 0) {
    const center = cellCenterNormalized(col, row, Math.max(1, density));
    return {
      normalizedX: center.x,
      normalizedY: center.y,
      alias,
      attachMode: "pov",
    };
  }
  return null;
}

/**
 * Unified display bind: POV attaches to character. Free returns null so the
 * glyph uses the hydrated/saved camera pose (never auto-rides the character).
 */
export function resolveCameraScrubPosition(
  camera: {
    id: string;
    primarySubject?: string | null;
    attachMode?: string | null;
    shotSize?: string | null;
    shotType?: string | null;
  },
  cameraArrows: CameraMovementArrow[] | null | undefined,
  activeAlias: string | null | undefined,
  subjectPlacement?: SubjectPlacementPoint | null,
  density: number = 10,
): FollowCameraScrubPoint | null {
  void cameraArrows;
  const mode = resolveCameraAttachMode(camera);
  if (mode === "pov") {
    return resolvePovCameraScrubPosition(subjectPlacement, activeAlias, density);
  }
  return null;
}
