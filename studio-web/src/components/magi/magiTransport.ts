/** MAGI transport numbers. Commands come from the Timeline board clock. */
import type { MagiSequenceDocument } from "../../magiSequence/types";
import { recomputeDuration } from "../../magiSequence/engine";
import { skipSceneTime } from "../../filmTimeline/visualTrack";
import { batchWindowAtTime, type BatchTimeWindow } from "../../timelineMaster/batchWindows";
import { resolveTimelineTransportBounds } from "../../timelineMaster/timelineTransport";

const PICTURE_KINDS = new Set(["video", "image"]);

export function magiBoardDurationSec(doc: MagiSequenceDocument): number {
  const fps = Math.max(1, doc.frameRate);
  return recomputeDuration(doc) / fps;
}

type MagiWindow = BatchTimeWindow & { picture: boolean };

function magiWindows(doc: MagiSequenceDocument): MagiWindow[] {
  const fps = Math.max(1, doc.frameRate);
  const picture = new Map(doc.tracks.map((track) => [track.id, PICTURE_KINDS.has(track.kind)]));
  return doc.clips
    .map((clip) => ({
      id: clip.id,
      start: clip.startFrame / fps,
      end: (clip.startFrame + clip.durationFrames) / fps,
      picture: picture.get(clip.trackId) === true,
    }))
    .sort((a, b) => a.start - b.start || Number(b.picture) - Number(a.picture) || a.id.localeCompare(b.id));
}

/** Clips as batch windows, in timeline order. */
export function magiBatchWindows(doc: MagiSequenceDocument): BatchTimeWindow[] {
  return magiWindows(doc).map(({ id, start, end }) => ({ id, start, end }));
}

/**
 * The clip the playhead is inside. Picture wins over a bed that spans the
 * same moment. A gap uses Timeline's batchWindowAtTime rule.
 */
export function magiActiveWindow(doc: MagiSequenceDocument, playheadSec: number): BatchTimeWindow | null {
  const windows = magiWindows(doc);
  if (!windows.length) return null;
  const time = Math.max(0, playheadSec);
  const containing = windows.filter((window) => time >= window.start && time < window.end);
  const picture = containing.filter((window) => window.picture);
  const pool = picture.length ? picture : containing;
  if (pool.length) {
    const tightest = [...pool].sort((a, b) => a.end - a.start - (b.end - b.start) || a.start - b.start)[0];
    return { id: tightest.id, start: tightest.start, end: tightest.end };
  }
  const fallback = batchWindowAtTime(windows, time);
  return fallback ? { id: fallback.id, start: fallback.start, end: fallback.end } : null;
}

export function magiTransportAt(doc: MagiSequenceDocument, playheadFrame: number) {
  const fps = Math.max(1, doc.frameRate);
  const windows = magiBatchWindows(doc);
  const playheadSec = Math.max(0, playheadFrame) / fps;
  const bounds = resolveTimelineTransportBounds({
    windows,
    playheadSec,
    boardDurationSec: magiBoardDurationSec(doc),
  });
  const piece = magiActiveWindow(doc, playheadSec);
  return {
    fps,
    windows,
    playheadSec,
    bounds: piece
      ? { ...bounds, activeBatchStart: piece.start, activeBatchEnd: Math.min(bounds.sceneEnd, piece.end) }
      : bounds,
    piece,
    hasPicture: windows.length > 0,
    extentFrames: recomputeDuration(doc),
  };
}

export function magiSeekFrame(doc: MagiSequenceDocument, seconds: number): number {
  const fps = Math.max(1, doc.frameRate);
  const extent = recomputeDuration(doc);
  const frame = Math.round(Math.max(0, seconds) * fps);
  return Math.max(0, Math.min(extent, frame));
}

export function magiSkipFrame(doc: MagiSequenceDocument, playheadFrame: number, deltaSec: number): number {
  const clock = magiTransportAt(doc, playheadFrame);
  return magiSeekFrame(doc, skipSceneTime(clock.playheadSec, deltaSec, clock.bounds.sceneEnd));
}
