/** MAGI transport clock — one authority, bounded drift correction, no seek-on-tick. */

export const MAGI_PLAY_DRIFT_SEC = 0.3;
export const MAGI_SCRUB_DRIFT_SEC = 0.04;

export type MagiClockRole = "authority" | "follower";

export const magiPlaybackStats = {
  currentTimeWrites: 0,
  driftCorrections: 0,
  reset() {
    this.currentTimeWrites = 0;
    this.driftCorrections = 0;
  },
};

export function bindMagiPlaybackStats(): typeof magiPlaybackStats {
  if (typeof window !== "undefined") {
    (window as Window & { __MAGI_PLAYBACK_STATS__?: typeof magiPlaybackStats }).__MAGI_PLAYBACK_STATS__ =
      magiPlaybackStats;
  }
  return magiPlaybackStats;
}

export function recordMediaTimeWrite(kind: "seek" | "drift" = "seek"): void {
  magiPlaybackStats.currentTimeWrites += 1;
  if (kind === "drift") magiPlaybackStats.driftCorrections += 1;
  bindMagiPlaybackStats();
}

export function shouldWriteMediaTime(opts: {
  playing: boolean;
  mediaTime: number;
  targetTime: number;
  force?: boolean;
}): boolean {
  if (!Number.isFinite(opts.mediaTime) || !Number.isFinite(opts.targetTime)) return false;
  const delta = Math.abs(opts.mediaTime - opts.targetTime);
  if (opts.force) return delta > 0.01;
  return delta > (opts.playing ? MAGI_PLAY_DRIFT_SEC : MAGI_SCRUB_DRIFT_SEC);
}

export function secondsToPlayheadFrame(seconds: number, frameRate: number, durationFrames: number): number {
  const fps = Math.max(1, frameRate);
  const last = Math.max(0, durationFrames - 1);
  return Math.max(0, Math.min(last, Math.round(Math.max(0, seconds) * fps)));
}

/** Clip window the picture element is currently playing. Times are frames. */
export type MagiMediaClockClip = {
  startFrame: number;
  durationFrames: number;
  inPoint: number;
  outPoint: number;
};

/**
 * Map a media element's source time back onto the timeline.
 * Source seconds are timeline seconds only while inPoint === startFrame.
 * A ripple or a move leaves inPoint behind, and treating source time as the
 * playhead makes every seek jump further ahead.
 * Returns "past-out" once the element has played through this clip's source
 * out point, so the caller advances in timeline time instead of following
 * the rest of the file.
 */
export function timelineFrameFromMediaSeconds(
  clip: MagiMediaClockClip,
  sourceSeconds: number,
  frameRate: number,
): number | "past-out" {
  const fps = Math.max(1, frameRate);
  const sourceFrame = Math.max(0, sourceSeconds) * fps;
  if (sourceFrame >= clip.outPoint - 0.5) return "past-out";
  const timeline = clip.startFrame + (sourceFrame - clip.inPoint);
  const last = clip.startFrame + Math.max(1, clip.durationFrames) - 1;
  return Math.max(clip.startFrame, Math.min(last, Math.round(timeline)));
}

/** Step the playhead in timeline time while no picture clip owns the clock (a gap). */
export function advanceTimelineFrame(
  playheadFrame: number,
  elapsedSeconds: number,
  frameRate: number,
  durationFrames: number,
): number {
  const fps = Math.max(1, frameRate);
  const frames = Math.floor(Math.max(0, elapsedSeconds) * fps);
  if (frames < 1) return playheadFrame;
  const end = Math.max(0, durationFrames);
  return Math.max(0, Math.min(end, playheadFrame + frames));
}
