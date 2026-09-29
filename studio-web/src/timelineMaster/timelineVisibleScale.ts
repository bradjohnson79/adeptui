/**
 * Premiere-style Timeline scale.
 *
 * Sequence (Scene.duration_sec) is how long this scene is.
 * The visible ruler / playhead counter is not that sequence — it keeps going.
 * There is no 15 / 20 / 30 / 120 product cap on the counter.
 */

/** Empty time after the sequence so opening Timeline never dead-ends at H3's 15s pass. */
export const TIMELINE_SCALE_MIN_TAIL_SEC = 30;

export function timelineSequenceSec(sceneSec: number, contentEndSec = 0): number {
  const scene = Math.max(0, Number(sceneSec) || 0);
  const content = Math.max(0, Number(contentEndSec) || 0);
  return Math.max(scene, content);
}

export function timelineViewportSec(viewportPx: number, pxPerSec: number): number {
  if (!(viewportPx > 0) || !(pxPerSec > 0)) return 0;
  return viewportPx / pxPerSec;
}

export function timelineVisibleScaleSec(args: {
  sequenceSec: number;
  viewportSec?: number;
  extraSec?: number;
}): number {
  const sequence = Math.max(0, Number(args.sequenceSec) || 0);
  const viewport = Math.max(0, Number(args.viewportSec) || 0);
  const extra = Math.max(0, Number(args.extraSec) || 0);
  const tail = Math.max(TIMELINE_SCALE_MIN_TAIL_SEC, viewport);
  return sequence + tail + extra;
}

export function timelineScaleShouldGrow(args: {
  scrollLeftPx: number;
  viewportPx: number;
  boardWidthPx: number;
  thresholdPx?: number;
}): boolean {
  const left = Math.max(0, Number(args.scrollLeftPx) || 0);
  const view = Math.max(0, Number(args.viewportPx) || 0);
  const board = Math.max(0, Number(args.boardWidthPx) || 0);
  if (board <= 0 || view <= 0) return false;
  const remaining = board - (left + view);
  const threshold = args.thresholdPx ?? Math.max(80, view * 0.15);
  return remaining <= threshold;
}

export function nextTimelineScaleExtraSec(currentExtraSec: number, viewportSec: number): number {
  const step = Math.max(TIMELINE_SCALE_MIN_TAIL_SEC, Math.max(0, Number(viewportSec) || 0));
  return Math.max(0, Number(currentExtraSec) || 0) + step;
}

/** Major tick step so a long, growing scale stays readable. */
export function timelineRulerTickStepSec(pxPerSec: number): number {
  const pps = Math.max(1, Number(pxPerSec) || 1);
  if (pps >= 72) return 1;
  if (pps >= 36) return 2;
  if (pps >= 18) return 5;
  if (pps >= 8) return 10;
  if (pps >= 3) return 30;
  return 60;
}

export function timelineRulerTicks(scaleSec: number, stepSec: number): number[] {
  const scale = Math.max(0, Number(scaleSec) || 0);
  const step = Math.max(1, Number(stepSec) || 1);
  const ticks: number[] = [];
  for (let t = 0; t <= scale + 1e-9; t += step) {
    ticks.push(Number(t.toFixed(3)));
  }
  const last = ticks[ticks.length - 1] ?? 0;
  if (last < scale - 1e-6) ticks.push(scale);
  return ticks;
}
