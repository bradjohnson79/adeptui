/** Single Timeline zoom authority. Pixels-per-second scale with this value. */

export const TIMELINE_ZOOM_MIN = 0.2;
export const TIMELINE_ZOOM_MAX = 5;
export const TIMELINE_ZOOM_DEFAULT = 1;
/** Timeline V2 track scale. Separate from the Timeline Master 0.2×–5× range. */
export const FILM_TIMELINE_ZOOM_MIN = 1;
export const FILM_TIMELINE_ZOOM_MAX = 8;
export const FILM_TIMELINE_ZOOM_DEFAULT = 1;
/** Multiplicative button/wheel step so 1× stays finely controllable. */
export const TIMELINE_ZOOM_STEP_FACTOR = 1.08;

export function clampTimelineZoom(
  value: number,
  min = TIMELINE_ZOOM_MIN,
  max = TIMELINE_ZOOM_MAX,
): number {
  const fallback = min <= TIMELINE_ZOOM_DEFAULT && TIMELINE_ZOOM_DEFAULT <= max ? TIMELINE_ZOOM_DEFAULT : min;
  if (!Number.isFinite(value)) return fallback;
  return Math.min(max, Math.max(min, value));
}

export function zoomToSlider(zoom: number): number {
  const z = clampTimelineZoom(zoom);
  const a = Math.log(TIMELINE_ZOOM_MIN);
  const b = Math.log(TIMELINE_ZOOM_MAX);
  return (Math.log(z) - a) / (b - a);
}

export function sliderToZoom(unit: number): number {
  const t = Number.isFinite(unit) ? Math.min(1, Math.max(0, unit)) : zoomToSlider(TIMELINE_ZOOM_DEFAULT);
  const a = Math.log(TIMELINE_ZOOM_MIN);
  const b = Math.log(TIMELINE_ZOOM_MAX);
  return clampTimelineZoom(Math.exp(a + (b - a) * t));
}

export function stepTimelineZoom(zoom: number, direction: -1 | 1): number {
  const current = clampTimelineZoom(zoom);
  const next = direction > 0 ? current * TIMELINE_ZOOM_STEP_FACTOR : current / TIMELINE_ZOOM_STEP_FACTOR;
  return clampTimelineZoom(next);
}

export function pixelsPerSecond(
  zoom: number,
  basePxPerSec = 90,
  min = TIMELINE_ZOOM_MIN,
  max = TIMELINE_ZOOM_MAX,
): number {
  return Math.max(1, basePxPerSec * clampTimelineZoom(zoom, min, max));
}

/** Whole-stop Timeline V2 zoom. 1× through 8×, never past either end. */
export function stepFilmTimelineZoom(zoom: number, direction: -1 | 1): number {
  const current = clampTimelineZoom(zoom, FILM_TIMELINE_ZOOM_MIN, FILM_TIMELINE_ZOOM_MAX);
  return clampTimelineZoom(current + direction, FILM_TIMELINE_ZOOM_MIN, FILM_TIMELINE_ZOOM_MAX);
}
