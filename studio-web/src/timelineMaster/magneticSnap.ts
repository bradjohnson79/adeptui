/** Screen-space magnetic snap. Batch edges are mandatory targets; snap is not a wall. */

export const MAGNETIC_SNAP_THRESHOLD_PX = 9;

export type SnapTargetKind = "batch" | "scene" | "clip" | "playhead";

export type MagneticSnapTarget = {
  time: number;
  kind: SnapTargetKind;
  label?: string;
  sourceId?: string;
};

export type MagneticSnapResult = {
  time: number;
  target: MagneticSnapTarget | null;
};

export function normalizeTimelineSeconds(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round(Math.max(0, value) * 1000) / 1000;
}

export function magneticSnapTime(
  rawTime: number,
  targets: MagneticSnapTarget[],
  pxPerSec: number,
  enabled: boolean,
  opts?: { thresholdPx?: number; ignoreSourceId?: string },
): MagneticSnapResult {
  const raw = Math.max(0, rawTime);
  if (!enabled) return { time: normalizeTimelineSeconds(raw), target: null };
  const threshold = opts?.thresholdPx ?? MAGNETIC_SNAP_THRESHOLD_PX;
  const scale = Math.max(1, pxPerSec);
  let best: MagneticSnapTarget | null = null;
  let bestPx = threshold;
  for (const target of targets) {
    if (!Number.isFinite(target.time)) continue;
    if (opts?.ignoreSourceId && target.sourceId === opts.ignoreSourceId) continue;
    const px = Math.abs(raw - target.time) * scale;
    if (px <= bestPx + 1e-9) {
      bestPx = px;
      best = target;
    }
  }
  return {
    time: normalizeTimelineSeconds(best ? best.time : raw),
    target: best,
  };
}

export function magneticSnapMovingEdge(args: {
  mode: "move" | "trim-left" | "trim-right";
  start: number;
  length: number;
  targets: MagneticSnapTarget[];
  pxPerSec: number;
  enabled: boolean;
  ignoreSourceId?: string;
  minLength?: number;
}): MagneticSnapResult & { start: number; length: number } {
  const minLength = args.minLength ?? 0.15;
  const opts = { ignoreSourceId: args.ignoreSourceId };
  if (args.mode === "trim-left") {
    const snapped = magneticSnapTime(args.start, args.targets, args.pxPerSec, args.enabled, opts);
    const end = args.start + args.length;
    const start = Math.min(snapped.time, end - minLength);
    return { ...snapped, time: start, start, length: Math.max(minLength, end - start) };
  }
  if (args.mode === "trim-right") {
    const rawEnd = args.start + args.length;
    const snapped = magneticSnapTime(rawEnd, args.targets, args.pxPerSec, args.enabled, opts);
    const length = Math.max(minLength, snapped.time - args.start);
    return { ...snapped, start: args.start, length };
  }
  const startSnap = magneticSnapTime(args.start, args.targets, args.pxPerSec, args.enabled, opts);
  const endSnap = magneticSnapTime(args.start + args.length, args.targets, args.pxPerSec, args.enabled, opts);
  const startPx = Math.abs(args.start - startSnap.time) * Math.max(1, args.pxPerSec);
  const endPx = Math.abs(args.start + args.length - endSnap.time) * Math.max(1, args.pxPerSec);
  if (startSnap.target && (!endSnap.target || startPx <= endPx)) {
    return { ...startSnap, start: startSnap.time, length: args.length };
  }
  if (endSnap.target) {
    const start = Math.max(0, endSnap.time - args.length);
    return { ...endSnap, time: start, start, length: args.length };
  }
  return { time: startSnap.time, target: null, start: startSnap.time, length: args.length };
}

export function buildMagneticSnapTargets(args: {
  sceneEnd: number;
  batches: Array<{ id?: string; start: number; length: number; label?: string }>;
  clips: Array<{ id?: string; start: number; length: number }>;
  playhead?: number | null;
}): MagneticSnapTarget[] {
  const targets: MagneticSnapTarget[] = [
    { time: 0, kind: "scene", label: "Scene start" },
    { time: Math.max(0, args.sceneEnd), kind: "scene", label: "Scene end" },
  ];
  for (const batch of args.batches) {
    const start = Math.max(0, batch.start);
    const end = start + Math.max(0, batch.length);
    targets.push({ time: start, kind: "batch", label: `${batch.label || "Batch"} start`, sourceId: batch.id });
    targets.push({ time: end, kind: "batch", label: `${batch.label || "Batch"} end`, sourceId: batch.id });
  }
  for (const clip of args.clips) {
    targets.push({ time: Math.max(0, clip.start), kind: "clip", sourceId: clip.id });
    targets.push({ time: Math.max(0, clip.start + clip.length), kind: "clip", sourceId: clip.id });
  }
  if (typeof args.playhead === "number" && Number.isFinite(args.playhead)) {
    targets.push({ time: Math.max(0, args.playhead), kind: "playhead", label: "Playhead" });
  }
  return targets;
}
