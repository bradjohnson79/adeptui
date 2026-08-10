import { describe, expect, it } from "vitest";
import { isTimelineMediaAsset, normalizeTimelineMediaKind } from "./timelineMediaTypes";

describe("timelineMediaTypes (TIMELINE_LIBRARY_MEDIA_ONLY)", () => {
  it("accepts image/video/audio kinds", () => {
    expect(normalizeTimelineMediaKind("image", "x.png")).toBe("image");
    expect(normalizeTimelineMediaKind("video", "x.mp4")).toBe("video");
    expect(normalizeTimelineMediaKind("audio", "x.mp3")).toBe("audio");
  });

  it("rejects documents and unknown kinds", () => {
    expect(normalizeTimelineMediaKind("document", "doc.pdf")).toBeNull();
    expect(normalizeTimelineMediaKind("application/pdf", "doc.pdf")).toBeNull();
    expect(normalizeTimelineMediaKind("archive", "x.zip")).toBeNull();
    expect(normalizeTimelineMediaKind(null, null)).toBeNull();
  });

  it("falls back to filename extension when kind is missing", () => {
    expect(normalizeTimelineMediaKind("", "scene.webm")).toBe("video");
    expect(normalizeTimelineMediaKind(null, "voice.m4a")).toBe("audio");
    expect(normalizeTimelineMediaKind(undefined, "photo.jpeg")).toBe("image");
  });

  it("rejects non-media extensions even with empty kind", () => {
    expect(normalizeTimelineMediaKind("", "notes.txt")).toBeNull();
    expect(normalizeTimelineMediaKind("", "data.json")).toBeNull();
  });

  it("isTimelineMediaAsset matches normalized kind", () => {
    expect(isTimelineMediaAsset({ kind: "image", filename: "a.png" })).toBe(true);
    expect(isTimelineMediaAsset({ kind: "document", filename: "a.pdf" })).toBe(false);
    expect(isTimelineMediaAsset({ kind: "", filename: "a.mov" })).toBe(true);
    expect(isTimelineMediaAsset({ kind: "", filename: "a.zip" })).toBe(false);
  });
});
