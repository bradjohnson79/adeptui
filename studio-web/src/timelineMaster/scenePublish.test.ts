import { describe, expect, it } from "vitest";
import type { SceneTimelineMaster } from "./contracts";
import {
  isFullStitchMagiAsset,
  isPublishReady,
  publishAcceptedIssues,
  resolvePublishChrome,
} from "./scenePublish";

function master(partial: Partial<SceneTimelineMaster> & Record<string, unknown>): SceneTimelineMaster {
  return {
    version: 1,
    mode: "video_finishing",
    orchestratorMode: "sequential_continuity",
    repairOverlapPolicy: "block",
    preflightMode: "warnings_only",
    batchBlocks: [],
    executionSnapshots: {},
    migratedFromDirectorJson: false,
    ...partial,
  } as SceneTimelineMaster;
}

describe("scenePublish readiness gate", () => {
  it("refuses before Final Check PASS / accepted-issues", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1", "b2"], sourceAssetIds: ["a1", "a2"] },
      sceneFinalCheck: { lifecycleStatus: "FINAL_CHECK", categories: [] },
    });
    expect(isPublishReady(m)).toBe(false);
    const chrome = resolvePublishChrome(m);
    expect(chrome.showPublish).toBe(false);
    expect(chrome.showUpscaleWithMagi).toBe(false);
  });

  it("refuses without stitch even when SCENE_FINISHED", () => {
    const m = master({
      sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [], creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED" },
    });
    expect(isPublishReady(m)).toBe(false);
  });

  it("ready after SCENE_FINISHED with stitch — shows PUBLISH + UPSCALE", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1", "b2"], sourceAssetIds: ["a1", "a2"] },
      sceneFinalCheck: {
        lifecycleStatus: "SCENE_FINISHED",
        categories: [],
        creatorVerdict: "FINAL CHECK PASSED / SCENE FINISHED",
      },
    });
    expect(isPublishReady(m)).toBe(true);
    const chrome = resolvePublishChrome(m);
    expect(chrome.showPublish).toBe(true);
    expect(chrome.showUpdatePublished).toBe(false);
    expect(chrome.showUpscaleWithMagi).toBe(true);
  });

  it("ready after accepted-issues with honest flag", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1"], sourceAssetIds: ["a1"] },
      sceneFinalCheck: {
        lifecycleStatus: "SCENE_FINISHED_WITH_ACCEPTED_ISSUES",
        categories: [],
        creatorVerdict: "SCENE FINISHED ISSUES ACCEPTED BY CREATOR",
      },
    });
    expect(isPublishReady(m)).toBe(true);
    expect(publishAcceptedIssues(m.sceneFinalCheck)).toBe(true);
    expect(resolvePublishChrome(m).showPublish).toBe(true);
  });

  it("after publish with same stitch — no PUBLISH, no UPDATE, UPSCALE remains", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1", "b2"], sourceAssetIds: ["a1", "a2"] },
      sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [] },
      scenePublish: {
        publishedAssetId: "pub-1",
        publishedAt: "2026-09-14T00:00:00Z",
        sourceSceneStitchAssetId: "stitch-1",
        lifecycleStatusSnapshot: "SCENE_FINISHED",
        creatorVerdictSnapshot: "FINAL CHECK PASSED / SCENE FINISHED",
        acceptedIssues: false,
        contentFingerprint: "abc",
        version: 1,
      },
    });
    const chrome = resolvePublishChrome(m);
    expect(chrome.showPublish).toBe(false);
    expect(chrome.showUpdatePublished).toBe(false);
    expect(chrome.changesPending).toBe(false);
    expect(chrome.showUpscaleWithMagi).toBe(true);
  });

  it("edits after publish (new stitch asset) → Changes Pending + UPDATE PUBLISHED", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-2", sourceBatchIds: ["b1", "b2", "b3"], sourceAssetIds: ["a1", "a2", "a3"] },
      sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [] },
      scenePublish: {
        publishedAssetId: "pub-1",
        publishedAt: "2026-09-14T00:00:00Z",
        sourceSceneStitchAssetId: "stitch-1",
        lifecycleStatusSnapshot: "SCENE_FINISHED",
        acceptedIssues: false,
        contentFingerprint: "abc",
        version: 1,
      },
    });
    const chrome = resolvePublishChrome(m);
    expect(chrome.changesPending).toBe(true);
    expect(chrome.changesPendingLabel).toBe("Changes Pending");
    expect(chrome.showUpdatePublished).toBe(true);
    expect(chrome.showPublish).toBe(false);
  });

  it("after publish + MAGI derivative pending — shows UPDATE PUBLISHED", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1"], sourceAssetIds: ["a1"] },
      sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [] },
      scenePublish: {
        publishedAssetId: "pub-1",
        publishedAt: "2026-09-14T00:00:00Z",
        sourceSceneStitchAssetId: "stitch-1",
        lifecycleStatusSnapshot: "SCENE_FINISHED",
        acceptedIssues: false,
        contentFingerprint: "abc",
        version: 1,
        upscaledAssetId: "magi-1",
        upscalePendingPublish: true,
      },
    });
    const chrome = resolvePublishChrome(m);
    expect(chrome.showUpdatePublished).toBe(true);
    expect(chrome.changesPending).toBe(true);
    expect(chrome.showPublish).toBe(false);
  });

  it("MAGI full-stitch only — batch asset blocked", () => {
    const m = master({
      sceneStitch: { assetId: "stitch-1", sourceBatchIds: ["b1"], sourceAssetIds: ["batch-asset-1"] },
      sceneFinalCheck: { lifecycleStatus: "SCENE_FINISHED", categories: [] },
    });
    expect(isFullStitchMagiAsset(m, "stitch-1")).toBe(true);
    expect(isFullStitchMagiAsset(m, "batch-asset-1")).toBe(false);
    expect(isFullStitchMagiAsset(m, "random")).toBe(false);
  });
});
