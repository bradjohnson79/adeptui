import { describe, expect, it } from "vitest";
import { resolveTimelineAtTime } from "./resolveTimelineAtTime";

describe("resolveTimelineAtTime approved take", () => {
  const master = {
    batchBlocks: [
      {
        id: "bb1",
        order: 0,
        label: "Batch 1",
        duration: { plannedDuration: 5 },
        visualClips: [],
        approvedClip: { assetId: "approved-b1", playable: true },
      },
      {
        id: "bb2",
        order: 1,
        label: "Batch 2",
        duration: { plannedDuration: 5 },
        visualClips: [],
        approvedClip: { assetId: "approved-b2", playable: true },
      },
    ],
  } as never;

  it("uses the approved take when visualClips is empty", () => {
    const atB1 = resolveTimelineAtTime(null, master, 1);
    expect(atB1.activeVisual?.assetId).toBe("approved-b1");
    expect(atB1.activeVisual?.kind).toBe("video");
    expect(atB1.visualLocalTime).toBeCloseTo(1);
    const atB2 = resolveTimelineAtTime(null, master, 6);
    expect(atB2.activeVisual?.assetId).toBe("approved-b2");
    expect(atB2.activeVisual?.kind).toBe("video");
    expect(atB2.visualLocalTime).toBeCloseTo(1);
  });

  it("uses the latest candidate when nothing is approved", () => {
    const draftMaster = {
      batchBlocks: [
        {
          id: "bb1",
          order: 0,
          label: "Batch 1",
          duration: { plannedDuration: 5 },
          visualClips: [],
          candidateVersions: [
            { id: "c1", assetId: "draft-take", createdAt: "2026-01-02T00:00:00Z", label: "Take A" },
          ],
        },
      ],
    } as never;
    const atDraft = resolveTimelineAtTime(null, draftMaster, 1);
    expect(atDraft.activeVisual?.assetId).toBe("draft-take");
    expect(atDraft.activeVisual?.kind).toBe("video");
  });

  it("keeps the last approved take at the inclusive scene end", () => {
    const atBoundary = resolveTimelineAtTime(null, master, 5);
    expect(atBoundary.activeVisual?.assetId).toBe("approved-b2");
    expect(atBoundary.batchLocalTime).toBeCloseTo(0);
    const atEnd = resolveTimelineAtTime(null, master, 10);
    expect(atEnd.activeVisual?.assetId).toBe("approved-b2");
    expect(atEnd.activeBatch?.id).toBe("bb2");
  });
});

describe("resolveTimelineAtTime A|Retake|B video_clips trim_start", () => {
  const timeline = {
    video_clips: [
      {
        id: "orig-a",
        asset_id: "orig-asset",
        start: 0,
        length: 2,
        trim_start: 0,
        label: "A",
        metadata: { role: "original_a" },
      },
      {
        id: "rtclip_r1",
        asset_id: "retake-asset",
        start: 2,
        length: 3,
        trim_start: 0,
        label: "Retake",
        metadata: { role: "retake", retakeId: "r1" },
      },
      {
        id: "rtb_1",
        asset_id: "orig-asset",
        start: 5,
        length: 5,
        trim_start: 5,
        label: "B",
        metadata: { role: "original_b" },
      },
    ],
  } as never;

  const master = {
    batchBlocks: [
      {
        id: "bb1",
        order: 0,
        label: "Batch 1",
        duration: { plannedDuration: 10 },
        visualClips: [],
        approvedClip: { assetId: "approved-should-not-win", playable: true },
      },
    ],
  } as never;

  it("prefers timeline video_clips over approved take", () => {
    const atRetake = resolveTimelineAtTime(timeline, master, 3);
    expect(atRetake.activeVisual?.clipId).toBe("rtclip_r1");
    expect(atRetake.activeVisual?.assetId).toBe("retake-asset");
    expect(atRetake.visualLocalTime).toBeCloseTo(1);
  });

  it("adds trim_start for B so scrub at markOut hits correct source frame", () => {
    // playhead 5.0 -> B start; timelineLocal=0; source local = 0 + trim_start(5) = 5
    const atMarkOut = resolveTimelineAtTime(timeline, master, 5);
    expect(atMarkOut.activeVisual?.clipId).toBe("rtb_1");
    expect(atMarkOut.activeVisual?.assetId).toBe("orig-asset");
    expect(atMarkOut.visualLocalTime).toBeCloseTo(5);

    // playhead 7 -> timelineLocal=2; source = 2+5 = 7
    const midB = resolveTimelineAtTime(timeline, master, 7);
    expect(midB.activeVisual?.clipId).toBe("rtb_1");
    expect(midB.visualLocalTime).toBeCloseTo(7);
  });

  it("keeps A at source origin (trim_start 0)", () => {
    const atA = resolveTimelineAtTime(timeline, master, 1);
    expect(atA.activeVisual?.clipId).toBe("orig-a");
    expect(atA.visualLocalTime).toBeCloseTo(1);
  });
});


describe("resolveTimelineAtTime Image-Frame still", () => {
  const timeline = {
    video_clips: [
      {
        id: "orig-a",
        asset_id: "orig-asset",
        start: 0,
        length: 2,
        trim_start: 0,
        label: "A",
        media_type: "video",
      },
      {
        id: "imgclip_p1",
        asset_id: "still-asset",
        start: 2,
        length: 3,
        trim_start: 0,
        label: "Image",
        media_type: "image",
        metadata: { role: "image_frame", referenceImageAssetId: "still-asset", markIn: 2, markOut: 5 },
      },
      {
        id: "rtb_1",
        asset_id: "orig-asset",
        start: 5,
        length: 5,
        trim_start: 5,
        label: "B",
        media_type: "video",
      },
    ],
  } as never;

  it("Preview still for imgclip_/media_type=image", () => {
    const mid = resolveTimelineAtTime(timeline, null, 3.5);
    expect(mid.activeVisual?.clipId).toBe("imgclip_p1");
    expect(mid.activeVisual?.kind).toBe("image");
    expect(mid.activeVisual?.assetId).toBe("still-asset");
  });

  it("keeps A and B as video", () => {
    expect(resolveTimelineAtTime(timeline, null, 1).activeVisual?.kind).toBe("video");
    expect(resolveTimelineAtTime(timeline, null, 6).activeVisual?.kind).toBe("video");
  });
});

describe("resolveTimelineAtTime visual detach vs take", () => {
  const master = {
    batchBlocks: [
      {
        id: "bb1",
        order: 0,
        label: "Batch 1",
        duration: { plannedDuration: 5 },
        visualClips: [{ id: "managed", kind: "video", assetId: "managed-still-there", start: 0, length: 5 }],
        approvedClip: { assetId: "approved-b1", playable: true },
        candidateVersions: [
          { id: "c1", assetId: "candidate-b1", createdAt: "2026-01-02T00:00:00Z", label: "Take A" },
        ],
      },
    ],
  } as never;

  it("keeps empty video_clips authoritative once media_mode is video", () => {
    const timeline = { media_mode: "video", video_clips: [] } as never;
    const at = resolveTimelineAtTime(timeline, master, 1);
    expect(at.activeVisual).toBeNull();
    expect(at.activeBatch?.id).toBe("bb1");
  });

  it("does not fall back to approved take in a gap after a remaining clip", () => {
    const timeline = {
      media_mode: "video",
      video_clips: [{ id: "bbclip_other", asset_id: "kept", start: 5, length: 5 }],
    } as never;
    const atRemovedSlot = resolveTimelineAtTime(timeline, master, 1);
    expect(atRemovedSlot.activeVisual).toBeNull();
  });

  it("still plays batch-owned media when timeline is null", () => {
    const at = resolveTimelineAtTime(null, master, 1);
    expect(at.activeVisual?.assetId).toBe("managed-still-there");
  });

  it("still plays approved take when timeline is null and visualClips are empty", () => {
    const approvedOnly = {
      batchBlocks: [
        {
          id: "bb1",
          order: 0,
          label: "Batch 1",
          duration: { plannedDuration: 5 },
          visualClips: [],
          approvedClip: { assetId: "approved-b1", playable: true },
        },
      ],
    } as never;
    expect(resolveTimelineAtTime(null, approvedOnly, 1).activeVisual?.assetId).toBe("approved-b1");
  });
});
