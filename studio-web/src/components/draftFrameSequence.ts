/** Draft live-preview frame sequence helpers (Approach A).
 *
 * Server still publishes JPEG/PNG stills via preview_bus (mediaType=image).
 * The monitor buffers successive draft URLs and plays them as a low-FPS loop
 * so creators see rough motion during LIVE PREVIEW / Draft quality.
 * Preview failure / empty buffers never invent frames.
 */

export const DRAFT_SEQUENCE_FPS = 6;
export const DRAFT_SEQUENCE_MAX_FRAMES = 48;

/** Append a new draft still URL; dedupe consecutive duplicates; cap length. */
export function appendDraftFrame(frames: string[], url: string, max = DRAFT_SEQUENCE_MAX_FRAMES): string[] {
  const next = String(url || "").trim();
  if (!next) return frames;
  if (frames.length && frames[frames.length - 1] === next) return frames;
  const out = frames.length >= max ? frames.slice(frames.length - max + 1) : frames.slice();
  out.push(next);
  return out;
}

/** Reset when the active job changes or draft mode ends. */
export function shouldResetDraftBuffer(args: {
  showDraft: boolean;
  jobId: string | null | undefined;
  prevJobId: string | null | undefined;
}): boolean {
  if (!args.showDraft) return true;
  const job = args.jobId || null;
  const prev = args.prevJobId || null;
  return Boolean(prev && job && prev !== job);
}

export function draftPlaybackMode(frameCount: number): "empty" | "still" | "sequence" {
  if (frameCount <= 0) return "empty";
  if (frameCount === 1) return "still";
  return "sequence";
}
