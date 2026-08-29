/** Scene duration vs selected Video Generator — no silent clip destroy. */

export type TimedClip = { start: number; length: number };

export type DurationBatch = { duration?: { plannedDuration?: number | null } | null };

/** One board clock: sum of batches, else Timeline/Scene seconds. */
export function timelineBoardDurationSec(
  master: { batchBlocks?: DurationBatch[] } | null | undefined,
  timeline: { duration_sec?: number | null } | null | undefined,
  scene: { duration_sec?: number | null } | null | undefined,
): number {
  const batches = master?.batchBlocks || [];
  if (batches.length) {
    const sum = batches.reduce((total, batch) => total + Math.max(0, Number(batch.duration?.plannedDuration || 0)), 0);
    if (sum > 0) return sum;
  }
  const fromTimeline = Number(timeline?.duration_sec || 0);
  if (fromTimeline > 0) return fromTimeline;
  return Math.max(0, Number(scene?.duration_sec || 0));
}

export function generatorMaxDurationSec(option: { maxDurationSec?: number | null; supportedDurations?: number[] } | null | undefined): number | null {
  if (!option) return null;
  if (typeof option.maxDurationSec === "number" && Number.isFinite(option.maxDurationSec) && option.maxDurationSec > 0) {
    return option.maxDurationSec;
  }
  const supported = option.supportedDurations || [];
  if (supported.length) return Math.max(...supported.filter((n) => Number.isFinite(n) && n > 0));
  return null;
}

export function farthestClipEnd(clips: TimedClip[]): number {
  return clips.reduce((max, clip) => Math.max(max, Math.max(0, clip.start) + Math.max(0, clip.length)), 0);
}

export function clipsOverflowGeneratorMax(clips: TimedClip[], maxSec: number | null): boolean {
  if (maxSec == null || !Number.isFinite(maxSec) || maxSec <= 0) return false;
  return farthestClipEnd(clips) > maxSec + 1e-6;
}

export function trimClipsToDuration<T extends TimedClip>(clips: T[], maxSec: number): T[] {
  const cap = Math.max(0.15, maxSec);
  return clips
    .filter((clip) => clip.start < cap - 1e-6)
    .map((clip) => {
      const start = Math.max(0, clip.start);
      const end = Math.min(start + Math.max(0.15, clip.length), cap);
      return { ...clip, start, length: Math.max(0.15, end - start) };
    });
}

export function creatorGeneratorLine(option: {
  label: string;
  executionType?: string;
  locality?: string;
  maxDurationSec?: number | null;
  supportedDurations?: number[];
}): string {
  const short = option.label.replace(/\s*\(Local\)\s*/gi, " ").replace(/\s+/g, " ").trim();
  const hosted = option.executionType === "api" || option.locality === "hosted";
  const place = hosted ? "API" : "Local";
  const max = generatorMaxDurationSec(option);
  const dur = max != null ? ` · ${Number.isInteger(max) ? String(max) : max.toFixed(max % 1 === 0 ? 0 : 1)}s` : "";
  return `${short} — ${place}${dur}`;
}
