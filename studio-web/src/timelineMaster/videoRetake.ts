/** Video Re-Take — range + prompt (+ optional No BG). Scene UUID stays identity. */

import type { PreviewComposition } from "../components/timeline-master/TimelinePreviewComposer";
import { resolveBoundedRetake, type BatchTimeWindow, type BoundedRetake } from "./batchWindows";

export const RETAKE_MIN_RANGE_SEC = 0.15;

export type VideoRetakeSession = {
  open: boolean;
  rangeStart: number | null;
  rangeEnd: number | null;
  referenceFrameTime: number;
  prompt: string;
  removeBackgroundUsed: boolean;
  busy: boolean;
  stage: string | null;
  error: string | null;
  jobId: string | null;
  disclosure: string | null;
  /** Eligibility empty hint — e.g. Generate a take first (not Approve). */
  emptyCopy: string | null;
};

export const EMPTY_VIDEO_RETAKE: VideoRetakeSession = {
  open: false,
  rangeStart: null,
  rangeEnd: null,
  referenceFrameTime: 0,
  prompt: "",
  removeBackgroundUsed: false,
  busy: false,
  stage: null,
  error: null,
  jobId: null,
  disclosure: null,
  emptyCopy: null,
};

/** Canonical close: one empty session. Pill, X, Escape, and Cancel all reset to this. */
export function closedVideoRetakeSession(): VideoRetakeSession {
  return { ...EMPTY_VIDEO_RETAKE };
}

export function nextRetakeLauncherAction(open: boolean): "open" | "close" {
  return open ? "close" : "open";
}

export function isVideoSrc(src: string | null | undefined): boolean {
  return Boolean(src && /\.(mp4|webm|mov)(\?|$)/i.test(src));
}

/** Capability from the actual Preview Monitor media, not filename guessing alone. */
export function isVideoRetakeComposition(composition: PreviewComposition | null | undefined): boolean {
  if (!composition) return false;
  if (composition.kind === "library") return false;
  if (composition.kind === "idle" || composition.kind === "preparing") return false;
  if (composition.kind === "failed" || composition.kind === "cancelled") return false;
  if (composition.kind === "timeline_frame") return composition.mediaKind === "video";
  if (composition.kind === "final_output") return composition.mediaKind === "video";
  if (composition.kind === "generation_draft") return isVideoSrc(composition.previewSrc);
  return false;
}

export function formatRetakeClock(sec: number): string {
  const t = Math.max(0, Number.isFinite(sec) ? sec : 0);
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  const whole = Math.floor(s);
  const frac = Math.round((s - whole) * 100);
  const paddedFrac = String(frac).padStart(2, "0");
  return `${String(m).padStart(2, "0")}:${String(whole).padStart(2, "0")}.${paddedFrac}`;
}

export function resolveRetakeMarks(
  rangeStart: number | null,
  rangeEnd: number | null,
): { ok: true; start: number; end: number; length: number } | { ok: false; error: string } {
  if (rangeStart == null || rangeEnd == null) {
    return { ok: false, error: "Mark In and Mark Out first." };
  }
  const start = Math.min(rangeStart, rangeEnd);
  const end = Math.max(rangeStart, rangeEnd);
  const length = end - start;
  if (length < RETAKE_MIN_RANGE_SEC) {
    return { ok: false, error: "Mark a longer region to change." };
  }
  return { ok: true, start, end, length };
}

export function canSubmitVideoRetake(session: Pick<
  VideoRetakeSession,
  "prompt" | "removeBackgroundUsed" | "rangeStart" | "rangeEnd" | "busy"
>): { ok: true } | { ok: false; error: string } {
  if (session.busy) return { ok: false, error: "Re-Take is already running." };
  const marks = resolveRetakeMarks(session.rangeStart, session.rangeEnd);
  if (!marks.ok) return marks;
  const prompt = session.prompt.trim();
  if (!prompt && !session.removeBackgroundUsed) {
    return { ok: false, error: "Describe what you want to change." };
  }
  return { ok: true };
}

export function boundRetakeToBatch(
  windows: BatchTimeWindow[],
  rangeStart: number | null,
  rangeEnd: number | null,
): BoundedRetake {
  const marks = resolveRetakeMarks(rangeStart, rangeEnd);
  if (!marks.ok) return { ok: false, error: marks.error };
  return resolveBoundedRetake(windows, marks.start, marks.length);
}

export function retakeProgressLabel(args: {
  stage?: string | null;
  jobStatus?: string | null;
  jobStage?: string | null;
}): string {
  if (args.stage) return args.stage;
  const status = String(args.jobStatus || "").toLowerCase();
  const jobStage = String(args.jobStage || "").toLowerCase();
  if (jobStage.includes("extract") || jobStage.includes("frame")) return "Extracting reference frame";
  if (jobStage.includes("mask")) return "Preparing mask";
  if (jobStage.includes("apply") || jobStage.includes("compos")) return "Applying selected range";
  if (jobStage.includes("save")) return "Saving";
  if (status === "queued") return "Preparing Re-Take";
  if (status === "running") return "Generating repair";
  if (status === "done" || status === "completed") return "Complete";
  return "Preparing Re-Take";
}

export { mediaContainRect } from "../workspace/mediaFit";

export function effectiveRetakePrompt(session: Pick<VideoRetakeSession, "prompt" | "removeBackgroundUsed">): string {
  const prompt = session.prompt.trim();
  if (prompt) return prompt;
  if (session.removeBackgroundUsed) return "Remove the background.";
  return "";
}
