import { describe, expect, it } from "vitest";
import {
  MAGI_PLAY_DRIFT_SEC,
  advanceTimelineFrame,
  secondsToPlayheadFrame,
  shouldWriteMediaTime,
  timelineFrameFromMediaSeconds,
  type MagiMediaClockClip,
} from "./magiPlaybackClock";

describe("MAGI playback clock", () => {
  it("does not write currentTime for sub-threshold drift while playing", () => {
    expect(
      shouldWriteMediaTime({
        playing: true,
        mediaTime: 10,
        targetTime: 10.08,
      }),
    ).toBe(false);
    expect(
      shouldWriteMediaTime({
        playing: true,
        mediaTime: 10,
        targetTime: 10 + MAGI_PLAY_DRIFT_SEC + 0.05,
      }),
    ).toBe(true);
  });

  it("writes on pause/scrub when playhead moves more than a frame", () => {
    expect(
      shouldWriteMediaTime({
        playing: false,
        mediaTime: 5,
        targetTime: 5.2,
      }),
    ).toBe(true);
    expect(
      shouldWriteMediaTime({
        playing: false,
        mediaTime: 5,
        targetTime: 5.01,
      }),
    ).toBe(false);
  });

  it("force-writes only when the media is actually off the requested time", () => {
    expect(
      shouldWriteMediaTime({
        playing: true,
        mediaTime: 8,
        targetTime: 8,
        force: true,
      }),
    ).toBe(false);
    expect(
      shouldWriteMediaTime({
        playing: true,
        mediaTime: 8,
        targetTime: 12,
        force: true,
      }),
    ).toBe(true);
  });

  it("maps media seconds onto the sequence playhead", () => {
    expect(secondsToPlayheadFrame(10, 24, 720)).toBe(240);
    expect(secondsToPlayheadFrame(-1, 24, 720)).toBe(0);
    expect(secondsToPlayheadFrame(40, 24, 720)).toBe(719);
  });

  it("keeps a rippled clip at 1x instead of fast-forwarding through the source", () => {
    // Right piece after a middle chunk is ripple-deleted: timeline moved
    // earlier, source in-point stayed where the file still begins.
    const clip: MagiMediaClockClip = {
      startFrame: 100,
      durationFrames: 400,
      inPoint: 160,
      outPoint: 560,
    };
    expect(timelineFrameFromMediaSeconds(clip, 160 / 24, 24)).toBe(100);
    let playhead = 100;
    let source = 160;
    for (let step = 0; step < 48; step += 1) {
      source += 1;
      const mapped = timelineFrameFromMediaSeconds(clip, source / 24, 24);
      expect(mapped).toBe(playhead + 1);
      playhead = mapped as number;
    }
    expect(playhead).toBe(148);
    // The unmapped clock would already be 60 frames ahead of the timeline.
    expect(secondsToPlayheadFrame(208 / 24, 24, 1082)).toBe(208);
    expect(timelineFrameFromMediaSeconds(clip, 560 / 24, 24)).toBe("past-out");
  });

  it("walks a gap in timeline time instead of skipping by the removed source", () => {
    expect(advanceTimelineFrame(500, 1 / 24, 24, 1082)).toBe(501);
    expect(advanceTimelineFrame(500, 0.01, 24, 1082)).toBe(500);
    expect(advanceTimelineFrame(1080, 1, 24, 1082)).toBe(1082);
  });
});
