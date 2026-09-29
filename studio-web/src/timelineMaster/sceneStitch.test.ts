import { describe, expect, it } from "vitest";
import {
  completedApprovedBatches,
  masterHasMusicOrSfxStems,
  sceneStitchCoveredEndSec,
  shouldPreviewSceneStitch,
} from "./sceneStitch";
import type { SceneTimelineMaster } from "./contracts";

const master = {
  batchBlocks: [
    { id: "bb1", order: 0, status: "Approved", duration: { plannedDuration: 5 }, approvedClip: { assetId: "a1" } },
    { id: "bb2", order: 1, status: "Approved", duration: { plannedDuration: 5 }, approvedClip: { assetId: "a2" } },
    { id: "bb3", order: 2, status: "CandidateReady", duration: { plannedDuration: 5 }, approvedClip: { assetId: "a3" } },
  ],
  sceneStitch: {
    assetId: "stitch",
    sourceBatchIds: ["bb1", "bb2"],
    sourceAssetIds: ["a1", "a2"],
  },
} as unknown as SceneTimelineMaster;

describe("scene stitch helpers", () => {
  it("collects only reviewed approved batches", () => {
    expect(completedApprovedBatches(master).map((batch) => batch.id)).toEqual(["bb1", "bb2"]);
  });

  it("covers only stitched batch windows", () => {
    expect(sceneStitchCoveredEndSec(master)).toBe(10);
  });

  it("plays the stitch unless a batch is being inspected while paused", () => {
    expect(
      shouldPreviewSceneStitch({
        master,
        selection: { kind: null },
        playheadSec: 6,
        timelinePlaying: true,
      }),
    ).toBe(true);
    expect(
      shouldPreviewSceneStitch({
        master,
        selection: { kind: "batch", id: "bb2" },
        playheadSec: 6,
        timelinePlaying: false,
      }),
    ).toBe(false);
    expect(
      shouldPreviewSceneStitch({
        master,
        selection: { kind: "batch", id: "bb2" },
        playheadSec: 6,
        timelinePlaying: true,
      }),
    ).toBe(true);
    expect(
      shouldPreviewSceneStitch({
        master,
        selection: { kind: null },
        playheadSec: 12,
        timelinePlaying: true,
      }),
    ).toBe(false);
  });

  it("detects Music/SFX stems on batch buses", () => {
    expect(masterHasMusicOrSfxStems(master)).toBe(false);
    const withStems = {
      ...master,
      batchBlocks: [
        {
          ...master.batchBlocks[0],
          audioClips: [{ id: "a1", assetId: "music-uuid", start: 0, length: 5 }],
        },
        ...master.batchBlocks.slice(1),
      ],
    } as unknown as SceneTimelineMaster;
    expect(masterHasMusicOrSfxStems(withStems)).toBe(true);
  });

  it("does not preview stitch when Music/SFX stems are present", () => {
    const withStems = {
      ...master,
      batchBlocks: [
        {
          ...master.batchBlocks[0],
          audioClips: [{ id: "a1", assetId: "music-uuid", start: 0, length: 5 }],
          sfxClips: [{ id: "s1", assetId: "sfx-uuid", start: 1, length: 1 }],
        },
        ...master.batchBlocks.slice(1),
      ],
    } as unknown as SceneTimelineMaster;
    expect(
      shouldPreviewSceneStitch({
        master: withStems,
        selection: { kind: null },
        playheadSec: 6,
        timelinePlaying: true,
      }),
    ).toBe(false);
  });
});
