import { describe, expect, it } from "vitest";
import { approvedHistoricalRevisions, normalizeCharacterCandidate } from "./types";

describe("approvedHistoricalRevisions", () => {
  it("keeps only approved historical revisions and hides the current hero", () => {
    const history = [
      normalizeCharacterCandidate({ sheetAssetId: "old-approved", status: "approved", revision: 2 }),
      normalizeCharacterCandidate({ sheetAssetId: "rejected-draft", status: "done" }),
      normalizeCharacterCandidate({ sheetAssetId: "current-approved", approvalStatus: "approved", revision: 3 }),
    ];
    const kept = approvedHistoricalRevisions(history, "current-approved");
    expect(kept.map((item) => item.sheetAssetId)).toEqual(["old-approved"]);
  });

  it("hides the control list when nothing approved remains", () => {
    const history = [
      normalizeCharacterCandidate({ sheetAssetId: "draft", status: "done" }),
      normalizeCharacterCandidate({ sheetAssetId: "failed", status: "failed" }),
    ];
    expect(approvedHistoricalRevisions(history, "hero")).toEqual([]);
  });
});
