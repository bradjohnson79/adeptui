import { describe, expect, it } from "vitest";
import type { BatchBlock, SceneTimelineMaster } from "./contracts";
import {
  findBatchOwnedAudioClip,
  masterHasBatchOwnedAudio,
  resolveDisplayAudioClips,
  sceneAbsoluteBatchAudioClips,
} from "./batchOwnedAudioClips";

function batch(partial: Partial<BatchBlock> & { id: string }): BatchBlock {
  return {
    sceneId: "s1",
    order: 0,
    label: "Batch 1",
    status: "Approved",
    generatorOverride: false,
    duration: { plannedDuration: 10 },
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

describe("batchOwnedAudioClips", () => {
  it("offsets batch-local Music/SFX clips to scene time across multi-batches", () => {
    const master = {
      batchBlocks: [
        batch({
          id: "bb1",
          order: 0,
          audioClips: [
            {
              id: "a1",
              kind: "audio",
              assetId: "music",
              start: 0,
              length: 10,
              label: "BGM B1",
              volume: 0.9,
              trimStart: 0,
              fade_in: 0,
              fade_out: 0,
            },
          ],
          sfxClips: [
            {
              id: "s1",
              kind: "sfx",
              assetId: "boots",
              start: 0,
              length: 10,
              label: "SFX B1",
              volume: 0.8,
              trimStart: 0,
              fade_in: 0,
              fade_out: 0,
            },
          ],
        }),
        batch({
          id: "bb2",
          order: 1,
          label: "Batch 2",
          audioClips: [
            {
              id: "a2",
              kind: "audio",
              assetId: "music",
              start: 0,
              length: 10,
              label: "BGM B2",
              volume: 0.9,
              trimStart: 0,
              fade_in: 0,
              fade_out: 0,
            },
          ],
          sfxClips: [
            {
              id: "s2",
              kind: "sfx",
              assetId: "boots2",
              start: 0,
              length: 10,
              label: "SFX B2",
              volume: 0.8,
              trimStart: 0,
              fade_in: 0,
              fade_out: 0,
            },
          ],
        }),
      ],
    } as SceneTimelineMaster;

    const music = sceneAbsoluteBatchAudioClips(master, "audio");
    expect(music.map((c) => [c.id, c.start, c.length])).toEqual([
      ["a1", 0, 10],
      ["a2", 10, 10],
    ]);
    const sfx = sceneAbsoluteBatchAudioClips(master, "sfx");
    expect(sfx.map((c) => [c.id, c.start, c.length])).toEqual([
      ["s1", 0, 10],
      ["s2", 10, 10],
    ]);
    expect(masterHasBatchOwnedAudio(master, "audio")).toBe(true);
    expect(findBatchOwnedAudioClip(master, "audio", "a2")?.windowStart).toBe(10);
  });

  it("prefers batch-owned clips over stale legacy timeline clips for display", () => {
    const master = {
      batchBlocks: [
        batch({
          id: "bb1",
          audioClips: [
            {
              id: "ba",
              kind: "audio",
              assetId: "m",
              start: 0,
              length: 10,
              label: "Score",
              volume: 1,
              trimStart: 0,
              fade_in: 0,
              fade_out: 0,
            },
          ],
        }),
      ],
    } as SceneTimelineMaster;
    const legacy = [{ id: "legacy", start: 0, length: 2, asset_id: "old" }];
    const display = resolveDisplayAudioClips(legacy, master, "audio");
    expect(display).toHaveLength(1);
    expect(display[0].id).toBe("ba");
    expect((display[0] as { start: number }).start).toBe(0);
  });

  it("falls back to legacy timeline clips when no batch owns audio", () => {
    const master = { batchBlocks: [batch({ id: "bb1" })] } as SceneTimelineMaster;
    const legacy = [{ id: "legacy", start: 0, length: 5 }];
    expect(resolveDisplayAudioClips(legacy, master, "audio")).toEqual(legacy);
  });
});
