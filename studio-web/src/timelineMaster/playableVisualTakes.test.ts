import { describe, expect, it } from "vitest";
import {
  displayedVisualVideoClips,
  filterVideoClipsForSceneTake,
  playableAssetIdForBatch,
  playableVisualClipsFromMaster,
  removePlacedVisualClip,
  resolveVisualVideoClips,
} from "./playableVisualTakes";
import type { BatchBlock, SceneTimelineMaster } from "./contracts";

function batch(partial: Partial<BatchBlock> & { id: string }): BatchBlock {
  return {
    sceneId: "s1",
    order: 0,
    label: "Batch 1",
    status: "CandidateReady",
    generatorOverride: false,
    duration: { plannedDuration: 5 },
    sourceAnchors: [],
    promptSegments: [],
    visualClips: [],
    audioClips: [],
    sfxClips: [],
    cameraInstructions: [],
    generationJobs: [],
    candidateVersions: [],
    repairRanges: [],
    references: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    legacyImageClipIds: [],
    ...partial,
  } as BatchBlock;
}

describe("playableVisualTakes", () => {
  it("uses the latest candidate when nothing is approved", () => {
    const b = batch({
      id: "bb1",
      candidateVersions: [
        { id: "c1", executionSnapshotId: "s1", assetId: "old", label: "Take A", createdAt: "2026-01-01T00:00:00Z", approved: false },
        { id: "c2", executionSnapshotId: "s2", assetId: "fresh", label: "Take B", createdAt: "2026-01-02T00:00:00Z", approved: false },
      ],
    });
    expect(playableAssetIdForBatch(b)).toBe("fresh");
  });

  it("keeps the approved take when a newer candidate exists", () => {
    const b = batch({
      id: "bb1",
      approvedClip: { assetId: "take-a", playable: true },
      candidateVersions: [
        { id: "c1", executionSnapshotId: "s1", assetId: "take-a", label: "Take A", createdAt: "2026-01-01T00:00:00Z", approved: true },
        { id: "c2", executionSnapshotId: "s2", assetId: "take-b", label: "Take B", createdAt: "2026-01-02T00:00:00Z", approved: false },
      ],
    });
    expect(playableAssetIdForBatch(b)).toBe("take-a");
  });

  it("lays out playable takes in batch order", () => {
    const master = {
      batchBlocks: [
        batch({
          id: "bb1",
          order: 0,
          candidateVersions: [
            { id: "c1", executionSnapshotId: "s1", assetId: "a1", label: "A", createdAt: "2026-01-01T00:00:00Z", approved: false },
          ],
        }),
        batch({
          id: "bb2",
          order: 1,
          label: "Batch 2",
          approvedClip: { assetId: "a2", playable: true },
        }),
      ],
    } as SceneTimelineMaster;
    const clips = playableVisualClipsFromMaster(master);
    expect(clips.map((c) => ({ id: c.id, asset: c.asset_id, start: c.start }))).toEqual([
      { id: "bbclip_bb1", asset: "a1", start: 0 },
      { id: "bbclip_bb2", asset: "a2", start: 5 },
    ]);
  });

  it("passes through managed visualClips trimStart as trim_start (A|B offsets)", () => {
    const master = {
      batchBlocks: [
        batch({
          id: "bb1",
          order: 0,
          duration: { plannedDuration: 10, timelineVisibleDuration: 10 },
          visualClips: [
            {
              id: "orig-a",
              kind: "video",
              assetId: "orig-asset",
              start: 0,
              length: 2,
              trimStart: 0,
              label: "A",
              role: "original_a",
              volume: 1,
              fade_in: 0,
              fade_out: 0,
              metadata: { role: "original_a", markIn: 2, markOut: 5 },
            },
            {
              id: "rtclip_r1",
              kind: "video",
              assetId: "retake-asset",
              start: 2,
              length: 3,
              trimStart: 0,
              label: "Retake",
              role: "retake",
              volume: 1,
              fade_in: 0,
              fade_out: 0,
              metadata: { role: "retake", retakeId: "r1" },
            },
            {
              id: "rtb_1",
              kind: "video",
              assetId: "orig-asset",
              start: 5,
              length: 5,
              trimStart: 5,
              label: "B",
              role: "original_b",
              volume: 1,
              fade_in: 0,
              fade_out: 0,
              metadata: { role: "original_b", markOut: 5 },
            },
          ],
        }),
      ],
    } as SceneTimelineMaster;
    const clips = playableVisualClipsFromMaster(master);
    expect(clips).toHaveLength(3);
    expect(clips.map((c) => ({ id: c.id, trim: c.trim_start, asset: c.asset_id, role: c.metadata?.role }))).toEqual([
      { id: "orig-a", trim: 0, asset: "orig-asset", role: "original_a" },
      { id: "rtclip_r1", trim: 0, asset: "retake-asset", role: "retake" },
      { id: "rtb_1", trim: 5, asset: "orig-asset", role: "original_b" },
    ]);
  });

  it("previews another whole-scene Take from membership without stealing current media", () => {
    const master = {
      currentSceneTakeId: "stk_a",
      sceneTakes: [
        {
          id: "stk_a",
          label: "A",
          letterIndex: 1,
          status: "ready",
          createdAt: "2026-01-01T00:00:00Z",
          batches: [{ batchId: "bb1", order: 0, assetId: "take-a" }],
        },
        {
          id: "stk_b",
          label: "B",
          letterIndex: 2,
          status: "ready",
          createdAt: "2026-01-02T00:00:00Z",
          batches: [{ batchId: "bb1", order: 0, assetId: "take-b" }],
        },
      ],
      batchBlocks: [
        batch({
          id: "bb1",
          approvedClip: { assetId: "take-a", playable: true },
          candidateVersions: [
            { id: "c1", executionSnapshotId: "s1", assetId: "take-a", label: "A", createdAt: "2026-01-01T00:00:00Z", approved: true },
            { id: "c2", executionSnapshotId: "s2", assetId: "take-b", label: "B", createdAt: "2026-01-02T00:00:00Z", approved: false },
          ],
        }),
      ],
    } as SceneTimelineMaster;
    const current = playableVisualClipsFromMaster(master);
    const previewB = playableVisualClipsFromMaster(master, { takeId: "stk_b" });
    expect(current.map((c) => c.asset_id)).toEqual(["take-a"]);
    expect(previewB.map((c) => c.asset_id)).toEqual(["take-b"]);
  });

  it("keeps Re-Take clips on the take that owns them and hides them on later takes", () => {
    const takeA = {
      id: "stk_a",
      label: "A",
      letterIndex: 1,
      retakeIds: ["rr_old"],
      batches: [{ batchId: "bb1", order: 0, assetId: "take-a" }],
    };
    const takeC = {
      id: "stk_c",
      label: "C",
      letterIndex: 3,
      retakeIds: [],
      resultAssetId: "take-c-stitch",
      batches: [{ batchId: "bb1", order: 0, assetId: "take-c" }],
    };
    const clips = [
      { id: "rtclip_rr_old", asset_id: "retake-a", metadata: { retakeId: "rr_old" } },
    ];
    expect(filterVideoClipsForSceneTake(clips, takeA).map((c) => c.id)).toEqual(["rtclip_rr_old"]);
    expect(filterVideoClipsForSceneTake(clips, takeC)).toEqual([]);
  });

});

describe("resolveVisualVideoClips", () => {
  const takes = [
    { id: "bbclip_bb1", asset_id: "a1" },
    { id: "bbclip_bb2", asset_id: "a2" },
  ];

  it("falls back to playable takes when video_clips empty and not in video mode", () => {
    expect(resolveVisualVideoClips([], takes, "image").map((c) => c.id)).toEqual([
      "bbclip_bb1",
      "bbclip_bb2",
    ]);
    expect(resolveVisualVideoClips([], takes, null).map((c) => c.id)).toEqual([
      "bbclip_bb1",
      "bbclip_bb2",
    ]);
  });

  it("keeps empty video_clips authoritative once media_mode is video (delete must stick)", () => {
    expect(resolveVisualVideoClips([], takes, "video")).toEqual([]);
  });

  it("prefers explicit video_clips over playable takes", () => {
    const clips = [{ id: "vc1", asset_id: "x" }];
    expect(resolveVisualVideoClips(clips, takes, "image")).toEqual(clips);
    expect(resolveVisualVideoClips(clips, takes, "video")).toEqual(clips);
  });

  it("simulates Visual track X delete of last playable take", () => {
    const before = resolveVisualVideoClips([], takes, "image");
    expect(before).toHaveLength(2);
    const afterDelete = before.filter((c) => c.id !== "bbclip_bb1" && c.id !== "bbclip_bb2");
    // removeClip writes media_mode video + filtered video_clips
    const shown = resolveVisualVideoClips(afterDelete, takes, "video");
    expect(shown).toEqual([]);
  });
});

describe("removePlacedVisualClip", () => {
  const takes = [
    { id: "bbclip_bb1", asset_id: "a1", start: 0, length: 5 },
    { id: "bbclip_bb2", asset_id: "a2", start: 5, length: 5 },
  ];
  const leftover = [{ id: "libclip_other", asset_id: "x", start: 0, length: 4 }];

  it("detaches a displayed playable take even when video_clips has a different row", () => {
    const displayed = displayedVisualVideoClips(leftover, takes, "image");
    expect(displayed.map((c) => c.id)).toEqual(["libclip_other"]);
    const detached = removePlacedVisualClip({
      clipId: "libclip_other",
      displayedClips: displayed,
    });
    expect(detached.media_mode).toBe("video");
    expect(detached.video_clips).toEqual([]);
    expect(resolveVisualVideoClips(detached.video_clips, takes, detached.media_mode)).toEqual([]);
  });

  it("materializes remaining displayed takes and keeps empty authoritative", () => {
    const displayed = displayedVisualVideoClips([], takes, "image");
    expect(displayed).toEqual(takes);
    const detached = removePlacedVisualClip({
      clipId: "bbclip_bb1",
      displayedClips: displayed,
    });
    expect(detached.video_clips.map((c) => c.id)).toEqual(["bbclip_bb2"]);
    expect(detached.media_mode).toBe("video");
    expect(resolveVisualVideoClips(detached.video_clips, takes, "video").map((c) => c.id)).toEqual([
      "bbclip_bb2",
    ]);
    const last = removePlacedVisualClip({
      clipId: "bbclip_bb2",
      displayedClips: detached.video_clips,
    });
    expect(last.video_clips).toEqual([]);
    expect(resolveVisualVideoClips(last.video_clips, takes, last.media_mode)).toEqual([]);
  });

  it("does not mutate take/candidate objects passed in", () => {
    const candidates = [{ id: "c1", assetId: "a1" }];
    const detached = removePlacedVisualClip({
      clipId: "bbclip_bb1",
      displayedClips: takes,
    });
    expect(candidates).toEqual([{ id: "c1", assetId: "a1" }]);
    expect(takes).toHaveLength(2);
    expect(detached.video_clips).toHaveLength(1);
  });

  it("leaves a removed video off Visual after reload", () => {
    const block = batch({
      id: "bb1",
      dismissedVisualAssetId: "asset-gone",
      candidateVersions: [{ id: "c1", assetId: "asset-gone", createdAt: "2026-01-01T00:00:00Z" } as never],
      visualClips: [],
    });
    const master = {
      batchBlocks: [block],
      sceneTakes: [
        {
          id: "t1",
          label: "A",
          letterIndex: 0,
          status: "incomplete",
          createdAt: "2026-01-01T00:00:00Z",
          batches: [{ batchId: "bb1", order: 0, assetId: "asset-gone", durationSec: 5 }],
        },
      ],
      currentSceneTakeId: "t1",
    } as SceneTimelineMaster;
    expect(playableVisualClipsFromMaster(master)).toEqual([]);
    const shown = displayedVisualVideoClips([], playableVisualClipsFromMaster(master), "image");
    expect(shown).toEqual([]);
  });
});
