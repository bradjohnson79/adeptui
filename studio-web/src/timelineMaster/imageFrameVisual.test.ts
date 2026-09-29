/** Image-Frame Visual helpers — unit tests. */
import { describe, expect, it } from "vitest";
import {
  findImageFrameInRange,
  findImageFrameReferenceAssetId,
  imageFrameReferenceAssetId,
  isImageFrameClip,
} from "./imageFrameVisual";

describe("isImageFrameClip", () => {
  it("detects imgclip_ id", () => {
    expect(isImageFrameClip({ id: "imgclip_abc", asset_id: "img1" })).toBe(true);
  });
  it("detects media_type image", () => {
    expect(isImageFrameClip({ id: "x", media_type: "image", asset_id: "img1" })).toBe(true);
  });
  it("detects mediaType image", () => {
    expect(isImageFrameClip({ id: "x", mediaType: "image", asset_id: "img1" })).toBe(true);
  });
  it("detects metadata.role image_frame", () => {
    expect(isImageFrameClip({ id: "x", metadata: { role: "image_frame" }, asset_id: "img1" })).toBe(true);
  });
  it("rejects plain video / rtclip", () => {
    expect(isImageFrameClip({ id: "rtclip_1", media_type: "video", asset_id: "v1" })).toBe(false);
    expect(isImageFrameClip({ id: "bbclip_1", asset_id: "v1" })).toBe(false);
  });
});

describe("findImageFrameReferenceAssetId", () => {
  const clips = [
    { id: "orig-a", asset_id: "vid", start: 0, length: 2, media_type: "video" },
    {
      id: "imgclip_p1",
      asset_id: "still-asset",
      start: 2,
      length: 3,
      media_type: "image",
      metadata: { role: "image_frame", referenceImageAssetId: "still-asset" },
    },
    { id: "rtb_1", asset_id: "vid", start: 5, length: 5, media_type: "video", trim_start: 5 },
  ];

  it("returns referenceImageAssetId when marks cover imgclip", () => {
    expect(findImageFrameReferenceAssetId(clips, 2, 5)).toBe("still-asset");
    expect(findImageFrameInRange(clips, 2.5, 4)?.id).toBe("imgclip_p1");
  });

  it("returns null when marks miss imgclip", () => {
    expect(findImageFrameReferenceAssetId(clips, 0, 1.5)).toBeNull();
    expect(findImageFrameReferenceAssetId(clips, 5, 8)).toBeNull();
  });

  it("falls back to asset_id when metadata ref missing", () => {
    expect(
      imageFrameReferenceAssetId({
        id: "imgclip_x",
        asset_id: "fallback-img",
        metadata: { role: "image_frame" },
      }),
    ).toBe("fallback-img");
  });
});
