import { describe, expect, it } from "vitest";
import {
  ingestMasterAssetId,
  resolveSplitOriginalAssetId,
  resolveSplitProcessed,
  walkToOriginalAssetId,
} from "./splitViewSource";

const PUB = "a85c2632-dd04-4450-be5d-214aa191e209";
const CHILD = "child-2k";
const SIBLING = "other-child";

describe("splitViewSource", () => {
  it("prefers published master over a MAGI child", () => {
    expect(
      resolveSplitOriginalAssetId({
        publishedAssetId: PUB,
        currentAssetId: CHILD,
        assets: [
          { id: CHILD, parent_asset_id: PUB, prompt_meta: { op: "upscale" } },
          { id: PUB },
        ],
      }),
    ).toBe(PUB);
  });

  it("walks parent_asset_id when publish id is absent", () => {
    expect(
      walkToOriginalAssetId(CHILD, [
        { id: CHILD, parent_asset_id: PUB, prompt_meta: { op: "color_grade" } },
        { id: PUB },
      ]),
    ).toBe(PUB);
  });

  it("never returns a MAGI child as LEFT when publish exists", () => {
    const left = resolveSplitOriginalAssetId({
      publishedAssetId: PUB,
      ingestMasterAssetId: PUB,
      currentAssetId: CHILD,
      assets: [{ id: CHILD, parent_asset_id: PUB, prompt_meta: { op: "upscale" } }, { id: PUB }],
    });
    expect(left).toBe(PUB);
    expect(left).not.toBe(CHILD);
  });

  it("uses ingest published_master clip when scene publish is unknown", () => {
    expect(
      ingestMasterAssetId(
        [{ id: "c1", trackId: "v", assetId: PUB, startFrame: 0, durationFrames: 10, inPoint: 0, outPoint: 10, ingestRole: "published_master", sceneId: "s12b" }],
        "s12b",
      ),
    ).toBe(PUB);
  });

  it("prefers visualResult over an arbitrary sibling", () => {
    const processed = resolveSplitProcessed({
      originalAssetId: PUB,
      visualResultAssetId: CHILD,
      assets: [
        { id: CHILD, parent_asset_id: PUB, prompt_meta: { op: "upscale" } },
        { id: SIBLING, parent_asset_id: PUB, prompt_meta: { op: "color_grade" } },
        { id: PUB },
      ],
    });
    expect(processed.assetId).toBe(CHILD);
    expect(processed.liveGrade).toBe(false);
  });

  it("uses the published master when a live grade is active, even if a bake exists", () => {
    const processed = resolveSplitProcessed({
      originalAssetId: PUB,
      visualResultAssetId: CHILD,
      liveGradeActive: true,
      assets: [
        { id: CHILD, parent_asset_id: PUB, prompt_meta: { op: "upscale" } },
        { id: PUB },
      ],
    });
    expect(processed.assetId).toBe(PUB);
    expect(processed.liveGrade).toBe(true);
  });

  it("falls back to original + live grade when no baked child is current", () => {
    const processed = resolveSplitProcessed({
      originalAssetId: PUB,
      assets: [{ id: PUB }, { id: SIBLING, parent_asset_id: "someone-else" }],
    });
    expect(processed.assetId).toBe(PUB);
    expect(processed.liveGrade).toBe(true);
  });

  it("stops the original walk at the published master, not Timeline stitch", () => {
    const stitch = "9170c85b-stitch";
    const grade = "grade-child";
    const twoK = "child-2k-grand";
    const assets = [
      { id: twoK, parent_asset_id: grade, prompt_meta: { op: "upscale" } },
      { id: grade, parent_asset_id: PUB, prompt_meta: { op: "color_grade" } },
      { id: PUB, parent_asset_id: stitch },
      { id: stitch },
    ];
    expect(walkToOriginalAssetId(twoK, assets)).toBe(PUB);
    expect(walkToOriginalAssetId(PUB, assets)).toBe(PUB);
    const processed = resolveSplitProcessed({
      originalAssetId: PUB,
      visualResultAssetId: twoK,
      assets,
    });
    expect(processed.assetId).toBe(twoK);
    expect(processed.liveGrade).toBe(false);
  });
});
