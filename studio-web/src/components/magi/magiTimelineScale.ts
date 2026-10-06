/** Single time-space owner for the MAGI sequence timeline.
 * Ruler x=0, clip x=0, and playhead x=0 are all inside the lane that
 * starts at MAGI_TRACK_LABEL_WIDTH. Do not add a second offset.
 */

export const MAGI_TRACK_LABEL_WIDTH = 96;
export const MAGI_BASE_PX_PER_FRAME = 2;
export const MAGI_ZOOM_MIN = 1;
export const MAGI_ZOOM_MAX = 10;
/** Short media stays usable. This floor is a width, never a duration ceiling. */
export const MAGI_MIN_CONTENT_PX = 640;

export function clampMagiZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return MAGI_ZOOM_MIN;
  return Math.min(MAGI_ZOOM_MAX, Math.max(MAGI_ZOOM_MIN, Math.round(zoom)));
}

type MagiZoomStep = (direction: -1 | 1) => void;
let magiZoomStep: MagiZoomStep | null = null;

/** The sequence timeline owns zoom. Shortcuts ask that owner to step. */
export function bindMagiZoomStep(step: MagiZoomStep): () => void {
  magiZoomStep = step;
  return () => {
    if (magiZoomStep === step) magiZoomStep = null;
  };
}

export function stepMagiZoom(direction: -1 | 1): void {
  magiZoomStep?.(direction);
}

export function magiPxPerFrame(zoom: number): number {
  return MAGI_BASE_PX_PER_FRAME * clampMagiZoom(zoom);
}

/** Left edge of usable time, in sheet pixels. Labels occupy [0, origin). */
export function magiTimeOrigin(labelWidth = MAGI_TRACK_LABEL_WIDTH): number {
  return labelWidth;
}

/** Playhead and clip left, in time-lane pixels. Frame 0 is 0. */
export function magiPlayheadLeft(frame: number, zoom: number): number {
  return Math.max(0, frame) * magiPxPerFrame(zoom);
}

/** Sheet coordinate of a frame. Frame 0 sits on the lane edge, never inside the labels. */
export function magiFrameSheetX(frame: number, zoom: number, labelWidth = MAGI_TRACK_LABEL_WIDTH): number {
  return magiTimeOrigin(labelWidth) + magiPlayheadLeft(frame, zoom);
}

/** Lane width for a composition. Grows with duration × zoom. The 640px floor never caps a longer sequence. */
export function magiContentWidth(durationFrames: number, zoom: number): number {
  const frames = Math.max(0, Number(durationFrames) || 0);
  return Math.max(MAGI_MIN_CONTENT_PX, frames * magiPxPerFrame(zoom));
}

/** Inclusive clamp. `durationFrames` is the exclusive end, so the playhead may sit on that boundary. */
export function magiClampFrame(frame: number, durationFrames: number): number {
  const end = Math.max(0, Number(durationFrames) || 0);
  if (!Number.isFinite(frame)) return 0;
  return Math.max(0, Math.min(end, Math.round(frame)));
}

/** Ruler labels. Short sequences stay in seconds; a minute or longer uses m:ss. */
export function magiRulerLabel(seconds: number, durationSec: number): string {
  const sec = Math.max(0, Number(seconds) || 0);
  const nearest = Math.round(sec);
  if (Math.abs(sec - nearest) < 0.2) {
    if (Math.max(0, Number(durationSec) || 0) >= 60) {
      const minutes = Math.floor(nearest / 60);
      const rest = nearest % 60;
      return `${minutes}:${String(rest).padStart(2, "0")}`;
    }
    return `${nearest}s`;
  }
  if (Math.max(0, Number(durationSec) || 0) >= 60) {
    const total = Math.round(sec);
    const minutes = Math.floor(total / 60);
    const rest = total % 60;
    return `${minutes}:${String(rest).padStart(2, "0")}`;
  }
  const rounded = Number.isInteger(sec) ? sec : Math.round(sec * 10) / 10;
  return `${rounded}s`;
}
