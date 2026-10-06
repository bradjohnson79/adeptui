import { clipAtTime, visualWindows } from "./visualTrack";

/** Generated picture batches in scene order. Failed and cancelled work is not a batch. */

export type BatchSegment = {
  id: string;
  order: number;
  durationSec: number;
  status: string;
  assetId?: string | null;
  shotNumber?: number | null;
  compositionRole?: string | null;
  sourceSegmentId?: string | null;
  origin?: string | null;
  trimInSec?: number | null;
  trimOutSec?: number | null;
  generationMetadata?: {
    compositionHold?: boolean;
    segmentedRetake?: unknown;
    prepend?: unknown;
    retakePreviousAssetId?: string;
  } | null;
};

const ACTIVE = new Set(["queued", "generating", "processing", "downloading"]);

export type SceneBatch = {
  id: string;
  order: number;
  durationSec: number;
  assetId: string;
  label: string;
  shotNumber: number;
  compositionRole?: string;
  sourceSegmentId?: string;
  origin?: string;
  trimInSec: number;
  trimOutSec: number | null;
};

/** Compact track label. Identity comes from the stored shot number, not the clip index. */
export function shotTrackLabel(shotNumber: number, durationSec: number, role?: string | null): string {
  const seconds = Math.round(Number(durationSec) || 0);
  const n = Math.floor(Number(shotNumber) || 0);
  const identity = n > 0 ? `Shot ${n}` : "Shot";
  if (role === "retake") return `${identity} · Re-Take · ${seconds}s`;
  return `${identity} · ${seconds}s`;
}

/** Next number from the persisted high-water mark. The same rule the service uses. */
export function nextShotNumber(highestShotNumber: number, shotNumbers: Array<number | null | undefined>): number {
  let high = Math.max(0, Math.floor(Number(highestShotNumber) || 0));
  for (const value of shotNumbers) high = Math.max(high, Math.floor(Number(value) || 0));
  return high + 1;
}

export function shotTag(shotNumber: number): string {
  return `#Shot${Math.max(1, Math.floor(Number(shotNumber) || 1))}`;
}

function wholeSeconds(value: number) {
  const seconds = Math.round(Number(value) || 0);
  return seconds === 1 ? "1 second" : `${seconds} seconds`;
}

function retakeStillHoldingPicture(item: BatchSegment): boolean {
  return Boolean(item.assetId && item.generationMetadata?.retakePreviousAssetId);
}

export function canonicalSceneBatches(segments: BatchSegment[] | null | undefined): SceneBatch[] {
  return [...(segments || [])]
    .filter((item) => {
      if (item.generationMetadata?.compositionHold) return false;
      if (item.status === "completed" && item.assetId) return true;
      // A Re-Take keeps the current picture on the track until the new one is saved.
      return ACTIVE.has(item.status) && retakeStillHoldingPicture(item);
    })
    .sort((a, b) => a.order - b.order)
    .map((item) => ({
      id: item.id,
      order: item.order,
      durationSec: item.durationSec,
      assetId: String(item.assetId),
      shotNumber: Math.floor(Number(item.shotNumber) || 0),
      compositionRole: item.compositionRole || "generated",
      sourceSegmentId: String(item.sourceSegmentId || ""),
      origin: String(item.origin || "generated"),
      trimInSec: Math.max(0, Number(item.trimInSec) || 0),
      trimOutSec: item.trimOutSec == null ? null : Number(item.trimOutSec),
      label: shotTrackLabel(Number(item.shotNumber) || 0, item.durationSec, item.compositionRole),
    }));
}

export function pendingSceneBatch(
  segments: BatchSegment[] | null | undefined,
): { id: string; label: string; durationSec: number; placement: "start" | "end" } | null {
  const active = [...(segments || [])]
    .filter(
      (item) =>
        ACTIVE.has(item.status) &&
        !item.generationMetadata?.segmentedRetake &&
        !item.generationMetadata?.retakePreviousAssetId,
    )
    .sort((a, b) => a.order - b.order);
  const item = active[0];
  if (!item) return null;
  const seconds = Math.max(0, Number(item.durationSec) || 0);
  const shotNumber = Math.floor(Number(item.shotNumber) || 0);
  return {
    id: item.id,
    label: shotNumber > 0 ? shotTrackLabel(shotNumber, seconds) : `Generating · ${wholeSeconds(seconds)}`,
    durationSec: seconds,
    placement: item.generationMetadata?.prepend ? "start" : "end",
  };
}

export function trackHasBatches(segments: BatchSegment[] | null | undefined): boolean {
  return canonicalSceneBatches(segments).length > 0;
}

/**
 * Label under the monitor and on the progress line.
 * An in-flight segment wins, because the picture still on screen may be the
 * previous shot. Otherwise the selected clip, then the clip under the playhead.
 * The number is the one stored on the segment.
 */
export function previewShotIdentity(
  segments: BatchSegment[] | null | undefined,
  playheadSec: number,
  selectedId?: string,
): string {
  const active = [...(segments || [])]
    .filter((item) => ACTIVE.has(item.status))
    .sort((a, b) => a.order - b.order)[0];
  const activeNumber = Math.floor(Number(active?.shotNumber) || 0);
  if (activeNumber > 0) return `Shot ${activeNumber}`;
  const windows = visualWindows(canonicalSceneBatches(segments));
  const selected = selectedId ? windows.find((item) => item.id === selectedId) : undefined;
  const clip = selected || clipAtTime(windows, playheadSec);
  return clip && clip.shotNumber > 0 ? `Shot ${clip.shotNumber}` : "";
}
