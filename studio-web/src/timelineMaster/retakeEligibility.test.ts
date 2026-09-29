import { describe, expect, it } from "vitest";
import type { BatchBlock } from "./contracts";
import {
  hasGeneratedTakeForRetake,
  latestGeneratedCandidate,
  resolveRetakeSource,
  retakeEmptyCopy,
} from "./retakeEligibility";

function batch(partial: Partial<BatchBlock>): BatchBlock {
  return {
    id: "b1",
    sceneId: "s1",
    order: 0,
    label: "B1",
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

describe("hasGeneratedTakeForRetake", () => {
  it("uses latest candidateVersions assetId — not approvedClip", () => {
    const withApprovedOnly = batch({
      approvedClip: { assetId: "approved-only", executionSnapshotId: "e", approvedAt: "t", playable: true },
      candidateVersions: [],
    });
    expect(hasGeneratedTakeForRetake(withApprovedOnly)).toBe(false);

    const withCandidates = batch({
      approvedClip: null,
      candidateVersions: [
        {
          id: "c1",
          executionSnapshotId: "e",
          assetId: "old",
          label: "Take 1",
          createdAt: "2026-01-01T00:00:00Z",
          approved: false,
          takeId: "take-1",
        },
        {
          id: "c2",
          executionSnapshotId: "e",
          assetId: "new",
          label: "Take 2",
          createdAt: "2026-01-02T00:00:00Z",
          approved: false,
          takeId: "take-2",
        },
      ],
    });
    expect(hasGeneratedTakeForRetake(withCandidates)).toBe(true);
    expect(latestGeneratedCandidate(withCandidates)?.assetId).toBe("new");
  });
});

describe("resolveRetakeSource", () => {
  it("returns currentTakeId + assetId from latest generated candidate", () => {
    const b = batch({
      candidateVersions: [
        {
          id: "c9",
          executionSnapshotId: "e",
          assetId: "asset-9",
          label: "Take",
          createdAt: "2026-01-03T00:00:00Z",
          approved: false,
          takeId: "take-9",
        },
      ],
    });
    expect(resolveRetakeSource(b)).toEqual({ assetId: "asset-9", currentTakeId: "take-9" });
  });

  it("falls back to candidate id when takeId missing", () => {
    const b = batch({
      candidateVersions: [
        {
          id: "cand-id",
          executionSnapshotId: "e",
          assetId: "a1",
          label: "Take",
          createdAt: "t",
          approved: false,
        },
      ],
    });
    expect(resolveRetakeSource(b)).toEqual({ assetId: "a1", currentTakeId: "cand-id" });
  });
});

describe("retakeEmptyCopy", () => {
  it("never says Approve a take first", () => {
    const copy = retakeEmptyCopy(false, false);
    expect(copy).toContain("Generate a take first");
    expect(copy.toLowerCase()).not.toContain("approve a take first");
  });
});
