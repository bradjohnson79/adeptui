import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  api: {
    directorTimelinePatchBatch: vi.fn(),
  },
}));

import { api } from "../api";
import type { BatchBlock, BatchClip, SceneTimelineMaster } from "./contracts";
import {
  patchMasterPrompt,
  projectMasterPreviewClips,
  removableVisualClipIds,
  applyPromptRemovalToMaster,
  removeMasterPrompts,
  syncMasterClips,
} from "./masterTimelineMutate";
import { masterPromptSegmentToView } from "../components/DirectorTracks";

function batch(partial: Partial<BatchBlock> & { id: string; order: number; planned: number }): BatchBlock {
  return {
    id: partial.id,
    sceneId: "s1",
    order: partial.order,
    label: partial.id,
    status: "Ready",
    generatorId: "minimax-h3",
    generatorOverride: false,
    duration: { plannedDuration: partial.planned },
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
    ...partial,
  } as unknown as BatchBlock;
}

/** 3 windows: b1 0-10, b2 10-25, b3 25-45 (mirrors disposable cert scene). */
function master(batches: BatchBlock[]): SceneTimelineMaster {
  return {
    id: "m1",
    sceneId: "s1",
    batchBlocks: batches,
  } as unknown as SceneTimelineMaster;
}

function imageClip(id: string, start: number, length = 5): BatchClip {
  return {
    id,
    kind: "image",
    assetId: `asset-${id}`,
    start,
    length,
    trimStart: 0,
    label: id,
    volume: 1,
    fade_in: 0,
    fade_out: 0,
  } as BatchClip;
}

beforeEach(() => {
  vi.mocked(api.directorTimelinePatchBatch).mockReset();
  vi.mocked(api.directorTimelinePatchBatch).mockResolvedValue({ ok: true } as never);
});

describe("patchMasterPrompt (Defect 1: Timed Prompt edits persist to Master)", () => {
  it("updates text on the existing segment inside its containing batch", async () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          { id: "ps1", start: 1, length: 4, text: "before", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v1", referenceBindingIds: [] },
        ],
      }),
      batch({ id: "b2", order: 1, planned: 15 }),
    ]);
    await patchMasterPrompt("p1", "s1", m, { id: "ps1", start: 1, length: 4, text: "after" });
    expect(api.directorTimelinePatchBatch).toHaveBeenCalledTimes(1);
    const [pid, sid, batchId, body] = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0];
    expect([pid, sid, batchId]).toEqual(["p1", "s1", "b1"]);
    const segs = (body as { promptSegments: Array<{ id: string; text: string }> }).promptSegments;
    expect(segs).toHaveLength(1);
    expect(segs[0]).toMatchObject({ id: "ps1", text: "after", start: 1, length: 4 });
  });

  it("passes movement + name bindings through on update (modal autosave fields)", async () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          { id: "ps1", start: 1, length: 4, text: "x", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v1", referenceBindingIds: [] },
        ],
      }),
    ]);
    await patchMasterPrompt("p1", "s1", m, {
      id: "ps1",
      start: 1,
      length: 4,
      text: "x",
      movementSegmentRef: { id: "mv1", segmentNumber: 2, alias: "M2" },
      movementSegmentRevision: 1,
      referenceNameBindings: [{ binding_id: "ers", prompt_name: "Korri", type: "character", tag: "@Korri" }],
      referenceBindingIds: ["ers"],
      productionPrompt: null,
    });
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      promptSegments: Array<Record<string, unknown>>;
    };
    expect(body.promptSegments[0].movementSegmentRef).toEqual({ id: "mv1", segmentNumber: 2, alias: "M2" });
    expect(body.promptSegments[0].movementSegmentRevision).toBe(1);
    expect(body.promptSegments[0].referenceNameBindings).toEqual([
      { binding_id: "ers", prompt_name: "Korri", type: "character", tag: "@Korri" },
    ]);
    expect(body.promptSegments[0].productionPrompt).toBeNull();
  });

  it("moves a segment across windows without duplicating it", async () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          { id: "ps1", start: 2, length: 3, text: "move me", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v1", referenceBindingIds: [] },
        ],
      }),
      batch({ id: "b2", order: 1, planned: 15 }),
    ]);
    await patchMasterPrompt("p1", "s1", m, { id: "ps1", start: 12, length: 3, text: "move me" });
    // Two PATCHes: source batch cleared, target batch gains the segment.
    expect(api.directorTimelinePatchBatch).toHaveBeenCalledTimes(2);
    const calls = vi.mocked(api.directorTimelinePatchBatch).mock.calls;
    const sourceCall = calls.find((c) => c[2] === "b1");
    const targetCall = calls.find((c) => c[2] === "b2");
    expect((sourceCall?.[3] as { promptSegments: unknown[] }).promptSegments).toHaveLength(0);
    const targetSegs = (targetCall?.[3] as { promptSegments: Array<{ id: string; start: number }> }).promptSegments;
    expect(targetSegs).toHaveLength(1);
    expect(targetSegs[0]).toMatchObject({ id: "ps1", start: 12 });
  });
});

describe("removeMasterPrompts (Defect 1: prompt delete persists)", () => {
  it("PATCHes the owning batch without the removed segment", async () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          { id: "ps1", start: 1, length: 2, text: "a", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v1" },
          { id: "ps2", start: 4, length: 2, text: "b", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v2" },
        ],
      }),
    ]);
    await removeMasterPrompts("p1", "s1", m, ["ps1"]);
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      promptSegments: Array<{ id: string }>;
    };
    expect(body.promptSegments.map((s) => s.id)).toEqual(["ps2"]);
  });
});


describe("applyPromptRemovalToMaster (universal clip delete)", () => {
  it("removes only the targeted Timed Prompt segment and keeps siblings", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          { id: "ps1", start: 1, length: 2, text: "keep-me-not", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v1" },
          { id: "ps2", start: 4, length: 2, text: "keep", role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled", versionId: "v2" },
        ],
      }),
    ]);
    const next = applyPromptRemovalToMaster(m, ["ps1"]);
    const ids = next.batchBlocks[0].promptSegments.map((s) => s.id);
    expect(ids).toEqual(["ps2"]);
    // Original Master unchanged (pure).
    expect(m.batchBlocks[0].promptSegments.map((s) => s.id)).toEqual(["ps1", "ps2"]);
  });

  it("matches legacyPromptSegmentId aliases", () => {
    const m = master([
      batch({
        id: "b1",
        order: 0,
        planned: 10,
        promptSegments: [
          {
            id: "ps_master",
            legacyPromptSegmentId: "legacy_ps",
            start: 0,
            length: 2,
            text: "x",
            role: "primary",
            strength: 1,
            anchorIds: [],
            executionStrategy: "compiled",
            versionId: "v1",
          } as never,
        ],
      }),
    ]);
    const next = applyPromptRemovalToMaster(m, ["legacy_ps"]);
    expect(next.batchBlocks[0].promptSegments).toEqual([]);
  });
});

describe("masterPromptSegmentToView (Defect 1: modal hydrates from Master)", () => {
  it("maps camelCase Master fields to the snake_case view shape", () => {
    const view = masterPromptSegmentToView({
      id: "ps1",
      start: 3,
      length: 5,
      text: "hello",
      role: "primary",
      strength: 0.8,
      anchorIds: [],
      executionStrategy: "compiled",
      versionId: "v1",
      referenceBindingIds: ["ers"],
      referenceNameBindings: [{ binding_id: "ers", prompt_name: "Korri", type: "character", tag: "@Korri" }],
      productionPrompt: "refined",
      dialogue: "line",
      movementSegmentRef: { id: "mv1", segmentNumber: 1, alias: "M1" },
      movementSegmentRevision: 2,
    } as never);
    expect(view).toMatchObject({
      id: "ps1",
      start: 3,
      length: 5,
      text: "hello",
      reference_binding_ids: ["ers"],
      production_prompt: "refined",
      dialogue: "line",
      movement_segment_ref: { id: "mv1", segmentNumber: 1, alias: "M1" },
      movement_segment_revision: 2,
    });
    expect(view.reference_name_bindings?.[0]).toMatchObject({ binding_id: "ers", prompt_name: "Korri" });
  });
});

describe("syncMasterClips removal (Defect 2: clip removal persists)", () => {
  it("removes a creator image clip from Master visualClips", async () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10, visualClips: [imageClip("clip_a", 1), imageClip("clip_b", 4)] }),
    ]);
    await syncMasterClips("p1", "s1", m, { attr: "visualClips", removeIds: new Set(["clip_a"]) });
    expect(api.directorTimelinePatchBatch).toHaveBeenCalledTimes(1);
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      visualClips: Array<{ id: string }>;
    };
    expect(body.visualClips.map((c) => c.id)).toEqual(["clip_b"]);
  });

  it("composes removal + upsert into ONE PATCH per batch (no resurrection, no dropped adds)", async () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10, visualClips: [imageClip("clip_a", 1), imageClip("clip_b", 4)] }),
    ]);
    await syncMasterClips("p1", "s1", m, {
      attr: "visualClips",
      removeIds: new Set(["clip_a"]),
      upserts: [{ id: "clip_c", kind: "image", assetId: "asset-c", start: 6, length: 2, label: "C" }],
    });
    expect(api.directorTimelinePatchBatch).toHaveBeenCalledTimes(1);
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      visualClips: Array<{ id: string }>;
    };
    expect(body.visualClips.map((c) => c.id).sort()).toEqual(["clip_b", "clip_c"]);
  });

  it("removes a lone whole-window video and remembers that asset", async () => {
    const take = imageClip("bbvclip_b1", 0, 10);
    take.kind = "video";
    take.assetId = "asset-take";
    take.role = "take";
    const m = master([batch({ id: "b1", order: 0, planned: 10, visualClips: [take] })]);
    const removable = removableVisualClipIds(m, ["bbvclip_b1"]);
    expect([...removable]).toEqual(["bbvclip_b1"]);
    await syncMasterClips("p1", "s1", m, { attr: "visualClips", removeIds: removable, upserts: [] });
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      visualClips: unknown[];
      dismissedVisualAssetId?: string;
    };
    expect(body.visualClips).toEqual([]);
    expect(body.dismissedVisualAssetId).toBe("asset-take");
  });

  it("refuses to remove generation-managed takes / composition pieces", async () => {
    const managed = imageClip("bbvclip_b1", 0, 10);
    managed.kind = "video";
    const piece = imageClip("imgclip_x", 2, 3);
    piece.metadata = { role: "image_frame", sourceBatchId: "b1" };
    const creator = imageClip("clip_mine", 1, 2);
    const m = master([batch({ id: "b1", order: 0, planned: 10, visualClips: [managed, piece, creator] })]);
    const removable = removableVisualClipIds(m, ["bbvclip_b1", "imgclip_x", "clip_mine"]);
    expect([...removable]).toEqual(["clip_mine"]);
  });

  it("removes a library still that reuses imgclip_ without a composition stamp", async () => {
    const still = imageClip("imgclip_library", 0, 15);
    still.metadata = { role: "image_frame", referenceImageAssetId: "asset-1" };
    const m = master([batch({ id: "b1", order: 0, planned: 15, visualClips: [still] })]);
    const removable = removableVisualClipIds(m, ["imgclip_library"]);
    expect([...removable]).toEqual(["imgclip_library"]);
    await syncMasterClips("p1", "s1", m, { attr: "visualClips", removeIds: removable, upserts: [] });
    const body = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0][3] as {
      visualClips: unknown[];
    };
    expect(body.visualClips).toEqual([]);
  });

  it("refuses to create synthetic bbclip_ playable-preview rows", async () => {
    const m = master([batch({ id: "b1", order: 0, planned: 10 })]);
    await syncMasterClips("p1", "s1", m, {
      attr: "visualClips",
      upserts: [{ id: "bbclip_b1", kind: "video", assetId: "a", start: 0, length: 10, label: "synthetic" }],
    });
    expect(api.directorTimelinePatchBatch).not.toHaveBeenCalled();
  });
});

describe("batch-local coordinate law", () => {
  it("projectMasterPreviewClips adds the window start (batch-local → scene-absolute)", () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10 }),
      batch({ id: "b2", order: 1, planned: 15, visualClips: [imageClip("clip_w2", 2, 5)] }),
      batch({ id: "b3", order: 2, planned: 20, audioClips: [{ ...imageClip("clip_a3", 1, 3), kind: "audio" }] }),
    ]);
    const clips = projectMasterPreviewClips(m);
    expect(clips.imageClips[0]).toMatchObject({ id: "clip_w2", start: 12 });
    expect(clips.audioClips[0]).toMatchObject({ id: "clip_a3", start: 26 });
  });

  it("syncMasterClips converts scene-absolute view starts to batch-local on write", async () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10 }),
      batch({ id: "b2", order: 1, planned: 15 }),
    ]);
    await syncMasterClips("p1", "s1", m, {
      attr: "visualClips",
      upserts: [{ id: "clip_new", kind: "image", assetId: "a", start: 12, length: 5, label: "N" }],
    });
    const [,, batchId, body] = vi.mocked(api.directorTimelinePatchBatch).mock.calls[0];
    expect(batchId).toBe("b2");
    expect((body as { visualClips: Array<{ start: number }> }).visualClips[0].start).toBe(2);
  });

  it("round-trips: a projected clip re-upserted unchanged produces no PATCH", async () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10 }),
      batch({ id: "b2", order: 1, planned: 15, visualClips: [imageClip("clip_w2", 2, 5)] }),
    ]);
    const projected = projectMasterPreviewClips(m);
    const view = projected.imageClips[0];
    expect(view.start).toBe(12);
    await syncMasterClips("p1", "s1", m, {
      attr: "visualClips",
      upserts: [{ id: view.id, kind: "image", assetId: view.asset_id, start: view.start, length: view.length, label: view.label }],
    });
    expect(api.directorTimelinePatchBatch).not.toHaveBeenCalled();
  });

  it("moves a clip across windows without duplicating it", async () => {
    const m = master([
      batch({ id: "b1", order: 0, planned: 10, visualClips: [imageClip("clip_mv", 2, 3)] }),
      batch({ id: "b2", order: 1, planned: 15 }),
    ]);
    await syncMasterClips("p1", "s1", m, {
      attr: "visualClips",
      upserts: [{ id: "clip_mv", kind: "image", assetId: "asset-clip_mv", start: 12, length: 3, label: "clip_mv" }],
    });
    expect(api.directorTimelinePatchBatch).toHaveBeenCalledTimes(2);
    const calls = vi.mocked(api.directorTimelinePatchBatch).mock.calls;
    const b1 = calls.find((c) => c[2] === "b1");
    const b2 = calls.find((c) => c[2] === "b2");
    expect((b1?.[3] as { visualClips: unknown[] }).visualClips).toHaveLength(0);
    const b2Clips = (b2?.[3] as { visualClips: Array<{ id: string; start: number }> }).visualClips;
    expect(b2Clips).toHaveLength(1);
    expect(b2Clips[0]).toMatchObject({ id: "clip_mv", start: 2 });
  });
});
