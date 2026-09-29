/** Scene duration vs selected Video Generator — no silent clip destroy. */

export type TimedClip = { start: number; length: number };

export type DurationBatch = { duration?: { plannedDuration?: number | null } | null };

/** One board clock: Scene duration authority, never shorter than live batch windows. */
export function timelineBoardDurationSec(
  master: { batchBlocks?: DurationBatch[] } | null | undefined,
  timeline: { duration_sec?: number | null } | null | undefined,
  scene: { duration_sec?: number | null } | null | undefined,
): number {
  const fromScene = Number(scene?.duration_sec || 0);
  const fromTimeline = Number(timeline?.duration_sec || 0);
  const sceneAuthority = fromScene > 0 ? fromScene : fromTimeline;
  const batches = master?.batchBlocks || [];
  const batchSum = batches.reduce(
    (total, batch) => total + Math.max(0, Number(batch.duration?.plannedDuration || 0)),
    0,
  );
  return Math.max(sceneAuthority, batchSum);
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

function isMinimaxH3Label(option: { id?: string; label: string }): boolean {
  const id = String(option.id || "").toLowerCase();
  if (id.startsWith("minimax-h3")) return true;
  return /^minimax h3\b/i.test(option.label);
}

export function creatorGeneratorLine(option: {
  label: string;
  id?: string;
  executionType?: string;
  locality?: string;
  maxDurationSec?: number | null;
  supportedDurations?: number[];
  readiness?: string;
  disabledReason?: string;
}): string {
  const short = option.label.replace(/\s*\(Local\)\s*/gi, " ").replace(/\s+/g, " ").trim();
  const hosted = option.executionType === "api" || option.locality === "hosted";
  const place = hosted ? "API" : "Local";
  // MiniMax H3 duration lives on the Inspector control, not the generator identity.
  const max = isMinimaxH3Label(option) ? null : generatorMaxDurationSec(option);
  const dur = max != null ? ` · ${Number.isInteger(max) ? String(max) : max.toFixed(max % 1 === 0 ? 0 : 1)}s` : "";
  const status = option.readiness ? ` · ${option.readiness}` : "";
  return `${short} — ${place}${dur}${status}`;
}
