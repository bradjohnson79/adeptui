import { describe, expect, it } from "vitest";
import type { PreviewComposition } from "../components/timeline-master/TimelinePreviewComposer";
import {
  boundRetakeToBatch,
  canSubmitVideoRetake,
  closedVideoRetakeSession,
  formatRetakeClock,
  isVideoRetakeComposition,
  mediaContainRect,
  nextRetakeLauncherAction,
  resolveRetakeMarks,
} from "./videoRetake";

const videoFrame: PreviewComposition = {
  kind: "timeline_frame",
  visualSrc: "/media/clip.mp4",
  mediaKind: "video",
  promptText: "Korri walks",
  promptLabel: "Batch 1",
  batchId: "b1",
  batchLocalTime: 0,
  visualLocalTime: 0,
  videoAssetId: "vid-1",
  sourceClipId: "clip-1",
};

describe("isVideoRetakeComposition", () => {
  it("shows for Timeline video and hides for stills and library", () => {
    expect(isVideoRetakeComposition(videoFrame)).toBe(true);
    expect(isVideoRetakeComposition({ ...videoFrame, mediaKind: "image", visualSrc: "/still.png" })).toBe(false);
    expect(
      isVideoRetakeComposition({
        kind: "library",
        asset: { id: "a" } as never,
        src: "/lib.mp4",
        mediaKind: "video",
      }),
    ).toBe(false);
    expect(isVideoRetakeComposition({ kind: "final_output", src: "/out.mp4", mediaKind: "video" })).toBe(true);
    expect(isVideoRetakeComposition({ kind: "final_output", src: "/out.png", mediaKind: "image" })).toBe(false);
    expect(isVideoRetakeComposition({ kind: "idle" })).toBe(false);
  });
});

describe("resolveRetakeMarks", () => {
  it("requires both marks and swaps inverted times", () => {
    expect(resolveRetakeMarks(null, 3).ok).toBe(false);
    expect(resolveRetakeMarks(1, 1.05).ok).toBe(false);
    const ok = resolveRetakeMarks(3, 1);
    expect(ok).toEqual({ ok: true, start: 1, end: 3, length: 2 });
  });
});

describe("canSubmitVideoRetake", () => {
  it("allows prompt-only and rembg-only; requires marks", () => {
    expect(
      canSubmitVideoRetake({
        prompt: "Make the lights flicker red",
        removeBackgroundUsed: false,
        rangeStart: 1,
        rangeEnd: 3,
        busy: false,
      }).ok,
    ).toBe(true);
    expect(
      canSubmitVideoRetake({
        prompt: "   ",
        removeBackgroundUsed: true,
        rangeStart: 1,
        rangeEnd: 3,
        busy: false,
      }).ok,
    ).toBe(true);
    const blocked = canSubmitVideoRetake({
      prompt: "",
      removeBackgroundUsed: false,
      rangeStart: 1,
      rangeEnd: 3,
      busy: false,
    });
    expect(blocked.ok).toBe(false);
  });
});

describe("mediaContainRect", () => {
  it("maps only the real media rectangle, not letterbox bars", () => {
    const rect = mediaContainRect(200, 100, 16, 9);
    expect(rect.x).toBeCloseTo(11.11, 1);
    expect(rect.y).toBe(0);
    expect(rect.h).toBe(100);
  });
});

describe("boundRetakeToBatch", () => {
  it("refuses a mark that crosses shots", () => {
    const windows = [
      { id: "a", start: 0, end: 5 },
      { id: "b", start: 5, end: 10 },
    ];
    expect(boundRetakeToBatch(windows, 4, 7).ok).toBe(false);
    expect(boundRetakeToBatch(windows, 1, 3).ok).toBe(true);
  });
});

describe("retake close is one action", () => {
  it("toggles the launcher and resets pending editor state", () => {
    expect(nextRetakeLauncherAction(false)).toBe("open");
    expect(nextRetakeLauncherAction(true)).toBe("close");
    const closed = closedVideoRetakeSession();
    expect(closed.open).toBe(false);
    expect(closed.prompt).toBe("");
    expect(closed.rangeStart).toBeNull();
    expect(closed.rangeEnd).toBeNull();
    expect(closed.removeBackgroundUsed).toBe(false);
    expect(closed.jobId).toBeNull();
  });
});

describe("formatRetakeClock", () => {
  it("formats 1s as 00:01.00", () => {
    expect(formatRetakeClock(1)).toBe("00:01.00");
    expect(formatRetakeClock(3)).toBe("00:03.00");
  });
});
