import { describe, expect, it } from "vitest";
import { canonicalSceneBatches } from "./sceneBatches";
import { stitchCoversClips, windowReachedEnd } from "./scenePlayback";
import {
  VISUAL_TRACK_PX_PER_SEC,
  classifyRetakeRange,
  compositionUnitBounds,
  sceneDuration,
  sceneTimeFromPreview,
  pxToSeconds,
  secondsToPx,
  skipSceneTime,
  trackFollowScroll,
  trackViewportOverflow,
  visualPixelsPerSecond,
  visualRulerTicks,
  visualWindows,
} from "./visualTrack";
import { getFilmTimelineZoom, setFilmTimelineZoom } from "./filmTimelineZoom";
import { stepFilmTimelineZoom } from "../timelineMaster/timelineZoom";

const batches = canonicalSceneBatches([
  { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "first" },
  { id: "b", order: 1, durationSec: 5, status: "completed", assetId: "second" },
  { id: "c", order: 2, durationSec: 10, status: "completed", assetId: "third" },
]);

describe("visual track scale", () => {
  const clips = visualWindows(batches);

  it("places batches flush in scene order", () => {
    expect(clips.map((clip) => [clip.start, clip.end])).toEqual([
      [0, 15],
      [15, 20],
      [20, 30],
    ]);
    expect(clips[1].start).toBe(clips[0].end);
    expect(clips[2].start).toBe(clips[1].end);
    expect(sceneDuration(clips)).toBe(30);
  });

  it("draws a 15 second clip three times a 5 second clip", () => {
    const wide = secondsToPx(15);
    const narrow = secondsToPx(5);
    expect(wide / narrow).toBe(3);
    expect(wide).toBe(15 * VISUAL_TRACK_PX_PER_SEC);
  });

  it("scales every clip with zoom and keeps neighboring edges on the same pixel", () => {
    for (const zoom of [1, 2, 4, 8]) {
      const px = visualPixelsPerSecond(zoom);
      expect(px).toBe(48 * zoom);
      const shot4Width = secondsToPx(15, px);
      const shot5Start = secondsToPx(15, px);
      expect(shot4Width).toBe(15 * px);
      expect(shot5Start).toBe(shot4Width);
      expect(secondsToPx(30, px)).toBe(shot4Width + secondsToPx(15, px));
    }
    expect(visualPixelsPerSecond(0)).toBe(48);
    expect(visualPixelsPerSecond(9)).toBe(48 * 8);
  });

  it("keeps a playhead time when the pixel scale changes", () => {
    const time = 31.5;
    const wide = visualPixelsPerSecond(8);
    expect(pxToSeconds(secondsToPx(time, wide), wide)).toBeCloseTo(time, 6);
    expect(pxToSeconds(secondsToPx(time, visualPixelsPerSecond(1)), visualPixelsPerSecond(1))).toBeCloseTo(time, 6);
  });

  it("uses finer ruler ticks at 8× than at 1×, on the same duration", () => {
    const close = visualRulerTicks(45, visualPixelsPerSecond(1));
    const fine = visualRulerTicks(45, visualPixelsPerSecond(8));
    expect(close[0]).toBe(0);
    expect(close[close.length - 1]).toBe(45);
    expect(fine[0]).toBe(0);
    expect(fine[fine.length - 1]).toBe(45);
    expect(fine.length).toBeGreaterThan(close.length);
    expect(fine).toContain(31);
  });

  it("steps and remembers zoom inside 1×–8× for the editing session", () => {
    setFilmTimelineZoom(1);
    expect(getFilmTimelineZoom()).toBe(1);
    expect(stepFilmTimelineZoom(1, -1)).toBe(1);
    expect(stepFilmTimelineZoom(8, 1)).toBe(8);
    setFilmTimelineZoom(stepFilmTimelineZoom(1, 1));
    expect(getFilmTimelineZoom()).toBe(2);
    setFilmTimelineZoom(4);
    expect(getFilmTimelineZoom()).toBe(4);
    setFilmTimelineZoom(20);
    expect(getFilmTimelineZoom()).toBe(8);
    setFilmTimelineZoom(1);
  });

  it("shares the ruler with the scene duration", () => {
    const ticks = visualRulerTicks(30);
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]).toBe(30);
    expect(ticks.every((tick, index) => index === 0 || tick > ticks[index - 1])).toBe(true);
  });

  it("treats stitch time as scene time and a batch as a local offset", () => {
    expect(sceneTimeFromPreview("stitch", 16, clips, "stitch-file")).toBe(16);
    expect(sceneTimeFromPreview("segment", 1.5, clips, "second")).toBe(16.5);
  });

  it("accepts a range inside one batch and refuses a range that crosses two", () => {
    expect(classifyRetakeRange(clips, 15, 20)).toEqual({ ok: true, code: "WHOLE_BATCH", clipId: "b" });
    expect(classifyRetakeRange(clips, 6.2, 10.8)).toEqual({ ok: true, code: "INTERIOR", clipId: "a" });
    const crossed = classifyRetakeRange(clips, 14, 18);
    expect(crossed.ok).toBe(false);
    if (!crossed.ok) expect(crossed.code).toBe("PARTIAL_RETAKE_UNSUPPORTED");
  });
});

describe("scene skip and track viewport", () => {
  it("skips five seconds across the assembled scene and stays inside it", () => {
    expect(skipSceneTime(13, 5, 30)).toBe(18);
    expect(skipSceneTime(2, -5, 30)).toBe(0);
    expect(skipSceneTime(28, 5, 30)).toBe(30);
  });

  it("reports no overflow when the scene already fits", () => {
    expect(trackViewportOverflow(400, 800)).toBe(0);
    expect(trackViewportOverflow(1400, 800)).toBe(600);
  });

  it("moves a retake run together and leaves the end clips fixed", () => {
    const bounds = compositionUnitBounds([
      { id: "head", sourceSegmentId: "src" },
      { id: "mid", sourceSegmentId: "src" },
      { id: "tail", sourceSegmentId: "src" },
      { id: "next", sourceSegmentId: "" },
    ]);
    expect(bounds.get("mid")).toEqual({ earlier: false, later: true });
    expect(bounds.get("next")).toEqual({ earlier: true, later: false });
  });

  it("treats a stitch as current only when its order matches the track", () => {
    expect(stitchCoversClips("ready", "asset", ["a", "b"], ["a", "b"])).toBe(true);
    expect(stitchCoversClips("ready", "asset", ["b", "a"], ["a", "b"])).toBe(false);
    expect(stitchCoversClips("stale", "asset", ["a", "b"], ["a", "b"])).toBe(false);
    expect(windowReachedEnd(0, null, 15, 14.96)).toBe(true);
    expect(windowReachedEnd(0, null, 15, 4)).toBe(false);
  });

  it("follows the playhead only after it leaves the visible track", () => {
    expect(trackFollowScroll(0, 400, 200)).toBeNull();
    expect(trackFollowScroll(0, 400, 390)).toBe(22);
    expect(trackFollowScroll(200, 400, 40)).toBe(8);
  });
});
