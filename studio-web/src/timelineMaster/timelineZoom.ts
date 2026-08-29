/** Single Timeline zoom authority. Pixels-per-second scale with this value. */

export const TIMELINE_ZOOM_MIN = 0.2;
export const TIMELINE_ZOOM_MAX = 5;
export const TIMELINE_ZOOM_DEFAULT = 1;
/** Multiplicative button/wheel step so 1× stays finely controllable. */
export const TIMELINE_ZOOM_STEP_FACTOR = 1.08;

export function clampTimelineZoom(value: number): number {
  if (!Number.isFinite(value)) return TIMELINE_ZOOM_DEFAULT;
  return Math.min(TIMELINE_ZOOM_MAX, Math.max(TIMELINE_ZOOM_MIN, value));
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

export function pixelsPerSecond(zoom: number, basePxPerSec = 90): number {
  return Math.max(1, basePxPerSec * clampTimelineZoom(zoom));
}
