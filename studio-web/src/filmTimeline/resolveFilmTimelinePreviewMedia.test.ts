import { describe, expect, it } from "vitest";
import { resolveFilmTimelinePreviewMedia } from "./resolveFilmTimelinePreviewMedia";

describe("resolveFilmTimelinePreviewMedia", () => {
  it("does not show a reference in the preview", () => {
    const media = resolveFilmTimelinePreviewMedia({
      segments: [],
    });
    expect(media.kind).toBe("empty");
    expect(media.source).toBe("none");
  });

  it("keeps a completed video when a later segment is cancelled", () => {
    const media = resolveFilmTimelinePreviewMedia({
      segments: [
        { assetId: "video-1", status: "completed", order: 0 },
        { assetId: "partial", status: "cancelled", order: 1 },
      ],
    });
    expect(media.assetId).toBe("video-1");
    expect(media.kind).toBe("video");
  });

  it("prefers a ready stitch over the latest segment", () => {
    const media = resolveFilmTimelinePreviewMedia({
      stitchAssetId: "stitch-1",
      stitchStatus: "ready",
      segments: [{ assetId: "video-2", status: "completed", order: 2 }],
    });
    expect(media.assetId).toBe("stitch-1");
    expect(media.source).toBe("stitch");
  });

  it("does not present a stale stitch as the current shot", () => {
    const media = resolveFilmTimelinePreviewMedia({
      stitchAssetId: "stitch-1",
      stitchStatus: "stale",
      segments: [
        { assetId: "video-1", status: "completed", order: 0 },
        { assetId: "video-2", status: "completed", order: 1 },
        { assetId: "video-3", status: "completed", order: 2 },
      ],
    });
    expect(media.assetId).toBe("video-3");
    expect(media.source).toBe("latest");
  });

  it("does not present a failed stitch as the current shot", () => {
    const media = resolveFilmTimelinePreviewMedia({
      stitchAssetId: "stitch-1",
      stitchStatus: "failed",
      segments: [{ assetId: "video-1", status: "completed", order: 0 }],
    });
    expect(media.assetId).toBe("video-1");
    expect(media.source).toBe("latest");
  });

  it("still uses an unlabelled stitch asset for legacy payloads", () => {
    const media = resolveFilmTimelinePreviewMedia({
      stitchAssetId: "stitch-1",
      segments: [{ assetId: "video-1", status: "completed", order: 0 }],
    });
    expect(media.assetId).toBe("stitch-1");
    expect(media.source).toBe("stitch");
  });
});
