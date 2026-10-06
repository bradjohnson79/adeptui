import type { SceneBatch } from "./sceneBatches";
import {
  FILM_TIMELINE_ZOOM_MAX,
  FILM_TIMELINE_ZOOM_MIN,
  pixelsPerSecond,
} from "../timelineMaster/timelineZoom";
import { timelineRulerTickStepSec, timelineRulerTicks } from "../timelineMaster/timelineVisibleScale";

/** One scale for the ruler, the clips, the playhead, and the Re-Take range. */
export const VISUAL_TRACK_BASE_PX_PER_SEC = 48;
export { FILM_TIMELINE_ZOOM_MIN, FILM_TIMELINE_ZOOM_MAX };

export function visualPixelsPerSecond(zoom = 1): number {
  return pixelsPerSecond(zoom, VISUAL_TRACK_BASE_PX_PER_SEC, FILM_TIMELINE_ZOOM_MIN, FILM_TIMELINE_ZOOM_MAX);
}

export const VISUAL_TRACK_PX_PER_SEC = visualPixelsPerSecond(1);

const RETAKE_TOLERANCE_SEC = 0.05;

export type VisualClip = {
  id: string;
  assetId: string;
  order: number;
  label: string;
  shotNumber: number;
  durationSec: number;
  start: number;
  end: number;
  sourceSegmentId: string;
  origin: string;
  trimInSec: number;
  trimOutSec: number | null;
};

export function visualWindows(batches: SceneBatch[]): VisualClip[] {
  let cursor = 0;
  return batches.map((batch) => {
    const durationSec = Math.max(0, Number(batch.durationSec) || 0);
    const start = cursor;
    const end = start + durationSec;
    cursor = end;
    return {
      id: batch.id,
      assetId: batch.assetId,
      order: batch.order,
      shotNumber: batch.shotNumber,
      durationSec,
      start,
      end,
      label: batch.label,
      sourceSegmentId: batch.sourceSegmentId || "",
      origin: batch.origin || "generated",
      trimInSec: batch.trimInSec || 0,
      trimOutSec: batch.trimOutSec,
    };
  });
}

/** Contiguous Re-Take pieces share one source and move together. */
export function compositionUnitBounds(clips: Array<{ id: string; sourceSegmentId?: string | null }>): Map<string, { earlier: boolean; later: boolean }> {
  const units: string[][] = [];
  for (const clip of clips) {
    const source = String(clip.sourceSegmentId || "");
    const last = units[units.length - 1];
    const lastSource = last ? String(clips.find((item) => item.id === last[0])?.sourceSegmentId || "") : "";
    if (source && last && lastSource === source) last.push(clip.id);
    else units.push([clip.id]);
  }
  const bounds = new Map<string, { earlier: boolean; later: boolean }>();
  units.forEach((unit, index) => {
    for (const id of unit) bounds.set(id, { earlier: index > 0, later: index < units.length - 1 });
  });
  return bounds;
}

export function sceneDuration(clips: VisualClip[]): number {
  return clips.length ? clips[clips.length - 1].end : 0;
}

/** Scene-time skip. Clamped to the assembled scene, not the current shot. */
export function skipSceneTime(current: number, delta: number, duration: number): number {
  const limit = Math.max(0, Number(duration) || 0);
  const time = Math.max(0, Number(current) || 0);
  return Math.max(0, Math.min(limit, time + delta));
}

/** How far the track can scroll. Zero means the whole scene already fits. */
export function trackViewportOverflow(scrollWidth: number, clientWidth: number): number {
  return Math.max(0, Math.round(scrollWidth) - Math.round(clientWidth));
}

/**
 * Scroll just enough to keep the playhead in view.
 * Returns null when it is already inside, so playback does not drag the viewport every frame.
 */
export function trackFollowScroll(scrollLeft: number, clientWidth: number, playheadPx: number, pad = 32): number | null {
  const left = Math.max(0, scrollLeft);
  const width = Math.max(0, clientWidth);
  const right = left + width;
  const at = Math.max(0, playheadPx);
  if (at < left + pad) return Math.max(0, at - pad);
  if (at > right - pad) return Math.max(0, at - width + pad);
  return null;
}

export function secondsToPx(seconds: number, pxPerSec = VISUAL_TRACK_PX_PER_SEC): number {
  return Math.max(0, seconds) * pxPerSec;
}

export function pxToSeconds(px: number, pxPerSec = VISUAL_TRACK_PX_PER_SEC): number {
  if (!(pxPerSec > 0)) return 0;
  return Math.max(0, px) / pxPerSec;
}

export function visualRulerTicks(durationSec: number, pxPerSec = VISUAL_TRACK_PX_PER_SEC): number[] {
  const duration = Math.max(0, durationSec);
  const step = timelineRulerTickStepSec(pxPerSec);
  const ticks = timelineRulerTicks(duration, step);
  if (!ticks.length) return [0];
  return ticks;
}

export function clipAtTime(clips: VisualClip[], sceneTime: number): VisualClip | null {
  if (!clips.length) return null;
  const time = Math.max(0, sceneTime);
  for (const clip of clips) {
    if (time >= clip.start && time < clip.end) return clip;
  }
  const last = clips[clips.length - 1];
  if (time >= last.end - 1e-6) return last;
  return clips[0];
}

/** Preview currentTime is scene time only while the stitch is showing. */
export function sceneTimeFromPreview(
  source: string,
  localTime: number,
  clips: VisualClip[],
  assetId: string,
): number {
  const local = Math.max(0, Number(localTime) || 0);
  if (source === "stitch") return local;
  const clip = clips.find((item) => item.assetId === assetId);
  if (!clip) return local;
  return clip.start + local;
}

export type RetakeRangeClass =
  | { ok: true; code: "WHOLE_BATCH" | "INTERIOR"; clipId: string }
  | { ok: false; code: "RETAKE_RANGE" | "PARTIAL_RETAKE_UNSUPPORTED"; message: string };

/** A range inside one clip can be replaced. A range across two clips cannot. */
export function classifyRetakeRange(clips: VisualClip[], start: number, end: number): RetakeRangeClass {
  const markIn = Math.min(start, end);
  const markOut = Math.max(start, end);
  if (!(markOut - markIn > 0)) {
    return { ok: false, code: "RETAKE_RANGE", message: "Mark a region with some length." };
  }
  const total = sceneDuration(clips);
  if (markIn < -RETAKE_TOLERANCE_SEC || markOut > total + RETAKE_TOLERANCE_SEC) {
    return { ok: false, code: "RETAKE_RANGE", message: "That range is outside this shot." };
  }
  const match = clips.find(
    (clip) => Math.abs(clip.start - markIn) <= RETAKE_TOLERANCE_SEC && Math.abs(clip.end - markOut) <= RETAKE_TOLERANCE_SEC,
  );
  if (match) return { ok: true, code: "WHOLE_BATCH", clipId: match.id };
  const inside = clips.filter((clip) => markIn >= clip.start - RETAKE_TOLERANCE_SEC && markOut <= clip.end + RETAKE_TOLERANCE_SEC);
  if (inside.length === 1) return { ok: true, code: "INTERIOR", clipId: inside[0].id };
  const crossed = clips.filter((clip) => clip.end > markIn + RETAKE_TOLERANCE_SEC && clip.start < markOut - RETAKE_TOLERANCE_SEC);
  const named = crossed.map((clip) => `${Math.round(clip.start)}s–${Math.round(clip.end)}s`).join(" and ");
  return {
    ok: false,
    code: "PARTIAL_RETAKE_UNSUPPORTED",
    message: named
      ? `${Math.round(markIn)}s–${Math.round(markOut)}s crosses more than one batch (${named}). Mark a range inside one batch.`
      : "Mark a range inside one batch. Neighboring picture stays as it is.",
  };
}
