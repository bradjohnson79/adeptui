/**
 * PoseCraft camera plausibility — hydration-boundary validation.
 *
 * Root-cause repair for the proven empty-viewport defect: a stale/corrupt
 * persisted camera was accepted verbatim and re-applied on every load, leaving
 * the figure as a tiny off-frame speck. This module decides, at the moment a
 * persisted camera is about to be restored, whether it plausibly frames the
 * active stage content. It is PURE (no Babylon) so it is unit-testable.
 *
 * Product law: a creator's legitimate saved framing is preserved exactly; only
 * a camera that frames NO meaningful stage content is replaced (camera fields
 * only — never figures, never the whole scene).
 */
import { FIGURE_ARCHETYPES } from "./constants";
import type { CameraState, FigureInstance } from "./types";

/** Established safe framing (matches createDefaultCamera / engine create()). */
export const SAFE_CAMERA = {
  alpha: -Math.PI / 2,
  beta: 1.12,
  radius: 7.5,
  target: { x: 0, y: 1.2, z: 0 },
} as const;

/** ArcRotateCamera limits from the engine (kept in sync; not a magic fix). */
export const CAMERA_RADIUS_LIMITS = { lower: 0.35, upper: 24 } as const;

/** Torso/eye-line height fraction of a standing figure. */
const TORSO_FRACTION = 0.55;

/** Stage ground half-extent (engine floor is 16×16). */
const STAGE_HALF_EXTENT = 8;

function archetypeHeight(figure: FigureInstance): number {
  const spec = FIGURE_ARCHETYPES.find((a) => a.id === figure.archetypeId);
  return (spec?.height ?? 1.8) * (figure.scale > 0 ? figure.scale : 1);
}

/**
 * Aggregate figure bounds derived from AUTHORITATIVE figure state
 * (position.x/z feet at y=0, archetype height). Never reads or mutates meshes.
 */
export function aggregateFigureBounds(figures: FigureInstance[]): {
  cx: number;
  cz: number;
  topY: number;
  centerY: number;
  maxRadius: number; // farthest figure footprint distance from centroid (x/z)
  maxHeight: number;
} | null {
  if (!figures.length) return null;
  let cx = 0;
  let cz = 0;
  let topY = 0;
  let maxHeight = 0;
  for (const f of figures) {
    cx += f.position.x;
    cz += f.position.z;
    const h = archetypeHeight(f);
    topY = Math.max(topY, h);
    maxHeight = Math.max(maxHeight, h);
  }
  cx /= figures.length;
  cz /= figures.length;
  let maxRadius = 0;
  for (const f of figures) {
    const dx = f.position.x - cx;
    const dz = f.position.z - cz;
    maxRadius = Math.max(maxRadius, Math.hypot(dx, dz));
  }
  return { cx, cz, topY, centerY: topY * TORSO_FRACTION, maxRadius, maxHeight };
}

/**
 * Distance from the camera target to the nearest meaningful content "anchor".
 * With figures: the figure aggregate centroid (x/z) at torso height.
 * Without figures: the stage origin (0, ~1.2, 0).
 */
function contentAnchor(figures: FigureInstance[]): { x: number; y: number; z: number } {
  const bounds = aggregateFigureBounds(figures);
  if (!bounds) return { x: SAFE_CAMERA.target.x, y: SAFE_CAMERA.target.y, z: SAFE_CAMERA.target.z };
  return { x: bounds.cx, y: bounds.centerY, z: bounds.cz };
}

/**
 * Decide whether a persisted camera plausibly frames the active stage content.
 *
 * NOT a single magic threshold — it composes several signals, and a large
 * radius alone is NOT corrupt (Law 18). A camera is implausible only when it
 * frames no meaningful content: the target is far from every figure AND from
 * the stage origin, OR the radius is pinned at the pathological upper limit
 * while the target is also displaced (the exact corrupt signature from audit).
 */
export function isCameraPlausible(camera: CameraState, figures: FigureInstance[]): boolean {
  const { radius, target } = camera;
  if (!Number.isFinite(radius) || !Number.isFinite(target.x) || !Number.isFinite(target.y) || !Number.isFinite(target.z)) {
    return false;
  }
  const anchor = contentAnchor(figures);
  const dx = target.x - anchor.x;
  const dy = target.y - anchor.y;
  const dz = target.z - anchor.z;
  const targetDrift = Math.hypot(dx, dy, dz);

  // Content's own scale: how spread out / tall the active stage is. A camera
  // target is meaningful only if it sits within the content's framing envelope.
  const bounds = aggregateFigureBounds(figures);
  const contentSpread = bounds ? Math.max(bounds.maxRadius, bounds.maxHeight) : 2;

  // Signal A — target far from ALL content. An ArcRotateCamera points at its
  // target, so a figure is framed only when it lies within the view frustum
  // around the target plane. The visible half-extent at the target plane is
  // ~R·tan(fov/2); with the engine's ~35mm lens (vertical FOV ≈ 0.75 rad) that
  // is ~0.38·R. Crucially, a corruptly-LARGE radius must not inflate this
  // allowance without bound — so we cap the radius contribution at a sane
  // framing distance (a creator framing a ~2m figure reasonably stays within
  // ~2× the content spread). This makes the audit's corrupt camera (target
  // drift ≈ 6.7 from a ~1.8m figure at spread 1.84) classify implausible while
  // leaving a genuinely zoomed-out-but-on-target creator camera untouched.
  const radiusAllowance = Math.min(Math.max(radius, 0) * 0.38, contentSpread * 2);
  let framingReach = radiusAllowance + contentSpread;
  if (!bounds) {
    // Empty stage: the only meaningful content is the stage origin itself. A
    // target dragged several meters from the origin at a large radius frames no
    // useful workspace, so bound the reach to a modest absolute envelope rather
    // than letting a corrupt large radius inflate it (Law 15).
    framingReach = Math.min(framingReach, STAGE_HALF_EXTENT / 2);
  }
  const targetIsOffContent = targetDrift > framingReach;

  // Signal B — pinned at the pathological upper radius limit while the target
  // is also dragged away from content. radius == upperRadiusLimit ALONE is only
  // a signal (Law 18): a creator zoomed to max with the figure still framed is
  // valid. It is corrupt only when combined with a displaced target.
  const pinnedAtMaxRadius = radius >= CAMERA_RADIUS_LIMITS.upper - 1e-3;
  const pinnedAndDrifted = pinnedAtMaxRadius && targetDrift > contentSpread + 2;

  // Signal C — target thrown far outside the stage with no figure near it.
  const farOutsideStage =
    Math.hypot(target.x, target.z) > STAGE_HALF_EXTENT + framingReach && targetIsOffContent;

  return !(targetIsOffContent || pinnedAndDrifted || farOutsideStage);
}

/**
 * Build a safe, figure-aware replacement camera for an implausible persisted
 * camera. Camera fields only — never touches figures. Reuses the established
 * safe framing; when figures exist, centers the target on their aggregate
 * bounds (Law 9) with a radius derived from figure height, kept within limits.
 */
export function buildSafeCamera(camera: CameraState, figures: FigureInstance[]): CameraState {
  const bounds = aggregateFigureBounds(figures);
  if (!bounds) {
    return { ...camera, ...SAFE_CAMERA, target: { ...SAFE_CAMERA.target } };
  }
  // Center on aggregate figure bounds at torso height; radius ~2.5× height so
  // the figure fills a useful portion of frame, bounded to the camera limits.
  const derived = Math.max(bounds.maxHeight * 2.5, bounds.maxRadius * 2 + 2, 4);
  const radius = Math.min(CAMERA_RADIUS_LIMITS.upper - 1, Math.max(CAMERA_RADIUS_LIMITS.lower + 0.5, derived));
  return {
    ...camera,
    alpha: SAFE_CAMERA.alpha,
    beta: SAFE_CAMERA.beta,
    radius,
    target: { x: bounds.cx, y: bounds.centerY, z: bounds.cz },
  };
}

/**
 * Hydration boundary: validate a persisted camera; if implausible, return a
 * sanitized replacement (camera fields only). Returns `{ camera, sanitized }`.
 */
export function sanitizePersistedCamera(
  camera: CameraState,
  figures: FigureInstance[],
): { camera: CameraState; sanitized: boolean } {
  if (isCameraPlausible(camera, figures)) return { camera, sanitized: false };
  return { camera: buildSafeCamera(camera, figures), sanitized: true };
}
