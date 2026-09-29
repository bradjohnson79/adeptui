import { describe, expect, it } from "vitest";
import type { SceneTake, SceneTimelineMaster } from "./contracts";
import {
  formatPreviewTakeStatusLabel,
  resolveDisplayedSceneTake,
  sceneTimelineStatusWord,
} from "./previewTakeStatus";

function take(partial: Partial<SceneTake> & Pick<SceneTake, "id" | "label">): SceneTake {
  return {
    letterIndex: 1,
    status: "ready",
    createdAt: "2026-09-14T00:00:00Z",
    batches: [],
    ...partial,
  };
}

function master(partial: Partial<SceneTimelineMaster> = {}): SceneTimelineMaster {
  return {
    version: 1,
    mode: "video_finishing",
    orchestratorMode: "sequential_continuity",
    repairOverlapPolicy: "block",
    preflightMode: "warnings_only",
    batchBlocks: [{ id: "b1", status: "Draft" } as SceneTimelineMaster["batchBlocks"][number]],
    executionSnapshots: {},
    migratedFromDirectorJson: false,
    ...partial,
  } as SceneTimelineMaster;
}

const takeA = take({
  id: "stk_a",
  label: "Take A",
  letterIndex: 1,
  resultAssetId: "asset-a",
  batches: [{ batchId: "b1", order: 0, assetId: "asset-a", status: "Draft" }],
});
const takeB = take({
  id: "stk_b",
  label: "B",
  letterIndex: 2,
  resultAssetId: "asset-b",
  batches: [{ batchId: "b1", order: 0, assetId: "asset-b", status: "Draft" }],
});
const takeC = take({
  id: "stk_c",
  label: "Take C",
  letterIndex: 3,
  resultAssetId: "asset-c",
  publishedAssetId: "pub-c",
  batches: [{ batchId: "b1", order: 0, assetId: "asset-c", status: "Draft" }],
});

describe("sceneTimelineStatusWord", () => {
  it("matches the existing Timeline scene-card algorithm", () => {
    expect(sceneTimelineStatusWord(master())).toBe("Draft");
    expect(sceneTimelineStatusWord(master({ batchBlocks: [{ id: "b1", status: "Ready" } as SceneTimelineMaster["batchBlocks"][number]] }))).toBe("Ready");
    expect(sceneTimelineStatusWord(master({ batchBlocks: [{ id: "b1", status: "Generating" } as SceneTimelineMaster["batchBlocks"][number]] }))).toBe("Working");
    expect(sceneTimelineStatusWord(master({ batchBlocks: [{ id: "b1", status: "Failed" } as SceneTimelineMaster["batchBlocks"][number]] }))).toBe("Needs Attention");
  });
});

describe("formatPreviewTakeStatusLabel", () => {
  it("returns null when no takes exist — never hardcodes Take A", () => {
    expect(formatPreviewTakeStatusLabel(master())).toBeNull();
  });

  it("returns null when takes exist but no generation has completed", () => {
    const emptyA = take({ id: "stk_a", label: "A", letterIndex: 1, status: "incomplete", batches: [] });
    const emptyB = take({ id: "stk_b", label: "B", letterIndex: 2, status: "incomplete", batches: [] });
    const m = master({
      sceneTakes: [emptyA, emptyB],
      currentSceneTakeId: "stk_b",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBeNull();
  });

  it("migrated current render is Take A", () => {
    const m = master({
      sceneTakes: [takeA],
      currentSceneTakeId: "stk_a",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take A");
    expect(formatPreviewTakeStatusLabel(m, null)).toBe("Draft - Take A");
  });

  it("uses the previewed take, not the latest created take", () => {
    const m = master({
      sceneTakes: [takeA, takeB, takeC],
      currentSceneTakeId: "stk_a",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take A");
    expect(formatPreviewTakeStatusLabel(m, "stk_b")).toBe("Draft - Take B");
    expect(formatPreviewTakeStatusLabel(m, "stk_c")).toBe("Draft - Take C");
  });

  it("does not label a rendering take until it is the displayed result", () => {
    const renderingB = take({
      id: "stk_b",
      label: "Take B",
      letterIndex: 2,
      status: "rendering",
      batches: [{ batchId: "b1", order: 0, status: "Generating" }],
    });
    const m = master({
      batchBlocks: [{ id: "b1", status: "Generating" } as SceneTimelineMaster["batchBlocks"][number]],
      sceneTakes: [takeA, renderingB],
      currentSceneTakeId: "stk_a",
      activeSceneTakeId: "stk_b",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take A");
    expect(formatPreviewTakeStatusLabel(m, "stk_b")).toBe("Draft - Take A");
    expect(resolveDisplayedSceneTake(m, "stk_b")?.id).toBe("stk_a");
  });

  it("does not label Take A Rendering when a later take owns the active job", () => {
    const staleA = take({
      id: "stk_a",
      label: "Take A",
      letterIndex: 1,
      status: "rendering",
      resultAssetId: "asset-a",
      batches: [{ batchId: "b1", order: 0, assetId: "asset-a", status: "Approved" }],
    });
    const renderingB = take({
      id: "stk_b",
      label: "Take B",
      letterIndex: 2,
      status: "rendering",
    });
    const m = master({
      sceneTakes: [staleA, renderingB],
      currentSceneTakeId: "stk_a",
      activeSceneTakeId: "stk_b",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Ready - Take A");
  });

  it("labels Rendering only when the viewed take is the displayed rendering result", () => {
    const renderingB = take({
      id: "stk_b",
      label: "Take B",
      letterIndex: 2,
      status: "rendering",
      resultAssetId: "asset-b-partial",
      batches: [{ batchId: "b1", order: 0, assetId: "asset-b-partial", status: "Generating" }],
    });
    const m = master({
      sceneTakes: [takeA, renderingB],
      currentSceneTakeId: "stk_b",
      activeSceneTakeId: "stk_b",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Rendering - Take B");
  });

  it("Published only when the viewed take is the published take", () => {
    const m = master({
      sceneTakes: [takeA, takeC],
      currentSceneTakeId: "stk_a",
      scenePublish: {
        publishedAssetId: "pub-c",
        publishedAt: "2026-09-14T00:00:00Z",
        sourceSceneStitchAssetId: "stitch-c",
        lifecycleStatusSnapshot: "SCENE_FINISHED",
        contentFingerprint: "fp",
        version: 1,
        takeId: "stk_c",
        takeLabel: "Take C",
      },
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take A");
    expect(formatPreviewTakeStatusLabel(m, "stk_c")).toBe("Published - Take C");
  });

  it("Re-Take keeps the same whole-scene take label", () => {
    const takeBWithRetake = take({
      ...takeB,
      retakeIds: ["rt_1"],
    });
    const m = master({
      sceneTakes: [takeA, takeBWithRetake],
      currentSceneTakeId: "stk_b",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take B");
  });

  it("Ready uses the existing scene-card word when batches are Ready", () => {
    const readyC = take({ ...takeC, id: "stk_c" });
    const m = master({
      batchBlocks: [{ id: "b1", status: "Ready" } as SceneTimelineMaster["batchBlocks"][number]],
      sceneTakes: [readyC],
      currentSceneTakeId: "stk_c",
    });
    expect(formatPreviewTakeStatusLabel(m)).toBe("Ready - Take C");
  });

  it("does not paint Take A Working from leftover Queued with no live job", () => {
    const incompleteA = take({
      id: "stk_a",
      label: "A",
      letterIndex: 1,
      status: "incomplete",
      batches: [{ batchId: "b2", order: 1, assetId: "hist-a", status: "CandidateReady" }],
    });
    const m = master({
      batchBlocks: [
        { id: "b1", status: "Draft" } as SceneTimelineMaster["batchBlocks"][number],
        { id: "b2", status: "Queued" } as SceneTimelineMaster["batchBlocks"][number],
      ],
      sceneTakes: [incompleteA],
      currentSceneTakeId: "stk_a",
      activeSceneTakeId: null,
    });
    expect(sceneTimelineStatusWord(m)).toBe("Draft");
    expect(formatPreviewTakeStatusLabel(m)).toBe("Draft - Take A");
  });
});
