import { describe, expect, it } from "vitest";
import { canonicalSceneBatches, nextShotNumber, pendingSceneBatch, previewShotIdentity, shotTag, trackHasBatches } from "./sceneBatches";

describe("scene batches", () => {
  it("keeps an empty scene off the track", () => {
    expect(trackHasBatches([])).toBe(false);
    expect(canonicalSceneBatches([])).toEqual([]);
  });

  it("ignores failed and cancelled work and sorts by scene order", () => {
    const segments = [
      { id: "b", order: 2, durationSec: 7, status: "completed", assetId: "second", shotNumber: 2 },
      { id: "x", order: 3, durationSec: 5, status: "failed", assetId: "nope", shotNumber: 9 },
      { id: "y", order: 4, durationSec: 5, status: "cancelled", assetId: "nope", shotNumber: 8 },
      { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "first", shotNumber: 1 },
    ];
    const batches = canonicalSceneBatches(segments);
    expect(batches.map((item) => item.label)).toEqual(["Shot 1 · 15s", "Shot 2 · 7s"]);
    expect(batches.map((item) => item.shotNumber)).toEqual([1, 2]);
    expect(batches.map((item) => item.assetId)).toEqual(["first", "second"]);
    expect(trackHasBatches(segments)).toBe(true);
  });

  it("shows an in-progress batch without treating it as finished", () => {
    const segments = [
      { id: "a", order: 0, durationSec: 10, status: "completed", assetId: "pic" },
      { id: "b", order: 1, durationSec: 12, status: "generating", assetId: null },
    ];
    expect(canonicalSceneBatches(segments)).toHaveLength(1);
    expect(pendingSceneBatch(segments)?.label).toBe("Generating · 12 seconds");
    expect(pendingSceneBatch(segments)?.placement).toBe("end");
  });

  it("names the shot being generated even while the playhead is still on the previous shot", () => {
    const segments = [
      { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "first", shotNumber: 1 },
      { id: "b", order: 1, durationSec: 15, status: "generating", assetId: null, shotNumber: 2 },
    ];
    expect(previewShotIdentity(segments, 4, "a")).toBe("Shot 2");
    expect(pendingSceneBatch(segments)?.label).toBe("Shot 2 · 15s");
  });

  it("follows the selected shot once nothing is generating", () => {
    const segments = [
      { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "first", shotNumber: 1 },
      { id: "b", order: 1, durationSec: 15, status: "completed", assetId: "second", shotNumber: 2 },
      { id: "c", order: 2, durationSec: 15, status: "completed", assetId: "third", shotNumber: 3 },
    ];
    expect(previewShotIdentity(segments, 0)).toBe("Shot 1");
    expect(previewShotIdentity(segments, 0, "b")).toBe("Shot 2");
    expect(previewShotIdentity(segments, 40)).toBe("Shot 3");
  });

  it("places an earlier shot before the finished picture", () => {
    const segments = [
      { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "pic" },
      { id: "b", order: 1, durationSec: 7, status: "generating", generationMetadata: { prepend: { targetSegmentId: "a" }, compositionHold: true } },
    ];
    expect(canonicalSceneBatches(segments)).toHaveLength(1);
    expect(pendingSceneBatch(segments)?.placement).toBe("start");
  });

  it("keeps shot identity when a later shot is placed first", () => {
    const batches = canonicalSceneBatches([
      { id: "newer", order: 0, durationSec: 8, status: "completed", assetId: "pre", shotNumber: 2 },
      { id: "older", order: 1, durationSec: 15, status: "completed", assetId: "first", shotNumber: 1 },
    ]);
    expect(batches.map((item) => item.label)).toEqual(["Shot 2 · 8s", "Shot 1 · 15s"]);
  });

  it("does not reuse a deleted number", () => {
    expect(nextShotNumber(3, [1, 3])).toBe(4);
    expect(shotTag(4)).toBe("#Shot4");
    expect(shotTag(nextShotNumber(0, []))).toBe("#Shot1");
  });

  it("keeps the current picture on the track while a Re-Take is rendering", () => {
    const segments = [
      { id: "a", order: 0, durationSec: 15, status: "completed", assetId: "shot-4", shotNumber: 4 },
      {
        id: "b",
        order: 1,
        durationSec: 15,
        status: "generating",
        assetId: "shot-5",
        shotNumber: 5,
        generationMetadata: { retakePreviousAssetId: "shot-5" },
      },
    ];
    const batches = canonicalSceneBatches(segments);
    expect(batches.map((item) => item.id)).toEqual(["a", "b"]);
    expect(batches.map((item) => item.assetId)).toEqual(["shot-4", "shot-5"]);
    expect(pendingSceneBatch(segments)).toBeNull();
    expect(previewShotIdentity(segments, 0, "a")).toBe("Shot 5");
  });

  it("labels a retake with the parent shot number", () => {
    const batches = canonicalSceneBatches([
      { id: "head", order: 0, durationSec: 7, status: "completed", assetId: "a", shotNumber: 1, compositionRole: "source" },
      { id: "mid", order: 1, durationSec: 3, status: "completed", assetId: "b", shotNumber: 1, compositionRole: "retake" },
      { id: "tail", order: 2, durationSec: 5, status: "completed", assetId: "a", shotNumber: 1, compositionRole: "source" },
    ]);
    expect(batches.map((item) => item.label)).toEqual(["Shot 1 · 7s", "Shot 1 · Re-Take · 3s", "Shot 1 · 5s"]);
    expect(new Set(batches.map((item) => item.shotNumber))).toEqual(new Set([1]));
  });
});
