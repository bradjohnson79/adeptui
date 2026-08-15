import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  batchProgress,
  canUseCharacterLook,
  candidateErrorMessage,
  candidateStage,
  isLayoutNoncompliant,
  normalizeCharacterCandidate,
  viewIsFinished,
  type CharacterCandidate,
} from "./types";

const gridSrc = readFileSync(new URL("./CharacterCandidateGrid.tsx", import.meta.url), "utf8");

function kieFailedCandidate(index: number, message: string): CharacterCandidate {
  return {
    candidateIndex: index,
    status: "failed",
    error: message,
    providerKind: "api",
    provider: "kie",
    model: "nano-banana-kie",
    provenance: "API — nano-banana-kie — Profile Guided",
    viewJobs: [
      { role: "hero_identity", status: "failed", error: message },
      { role: "full_body_side_left", status: "failed", error: message },
      { role: "full_body_back", status: "failed", error: message },
      { role: "closeup_front", status: "failed", error: message },
    ],
  };
}

describe("character sheet failed-job hydration", () => {
  it("leaves Generating when hydration returns failed views and shows the job message", () => {
    const c = kieFailedCandidate(0, "Kie createTask failed for nano-banana");
    expect(candidateStage(c)).toBe("failed");
    expect(candidateErrorMessage(c)).toBe("Kie createTask failed for nano-banana");
  });

  it("treats view-only failed status as a failed card even if candidate status is still generating", () => {
    const c: CharacterCandidate = {
      status: "generating",
      viewJobs: [
        { role: "hero_identity", status: "failed", error: "Kie createTask failed for seedream/5-pro-text-to-image" },
        { role: "full_body_side_left", status: "queued" },
        { role: "full_body_back", status: "queued" },
        { role: "closeup_front", status: "queued" },
      ],
    };
    expect(candidateStage(c)).toBe("failed");
    expect(candidateErrorMessage(c)).toBe("Kie createTask failed for seedream/5-pro-text-to-image");
  });

  it("counts failed views as finished so progress is not stuck at 0 of 12", () => {
    const candidates = [
      kieFailedCandidate(0, "Kie createTask failed for nano-banana"),
      kieFailedCandidate(1, "Kie createTask failed for gpt-image-2-text-to-image"),
      kieFailedCandidate(2, "Kie createTask failed for seedream/5-pro-text-to-image"),
    ];
    const progress = batchProgress(candidates);
    expect(progress.totalViews).toBe(12);
    expect(progress.doneViews).toBe(12);
    expect(progress.doneSheets).toBe(0);
    expect(candidates.every((c) => candidateStage(c) === "failed")).toBe(true);
  });

  it("still counts successful views and does not treat queued views as finished", () => {
    const candidates: CharacterCandidate[] = [
      {
        status: "generating",
        viewJobs: [
          { role: "hero_identity", status: "done", assetId: "a1" },
          { role: "full_body_side_left", status: "failed" },
          { role: "full_body_back", status: "queued" },
          { role: "closeup_front", status: "running" },
        ],
      },
    ];
    expect(viewIsFinished(candidates[0].viewJobs![0])).toBe(true);
    expect(viewIsFinished(candidates[0].viewJobs![1])).toBe(true);
    expect(viewIsFinished(candidates[0].viewJobs![2])).toBe(false);
    expect(viewIsFinished(candidates[0].viewJobs![3])).toBe(false);
    const progress = batchProgress(candidates);
    expect(progress.doneViews).toBe(2);
    expect(progress.totalViews).toBe(4);
  });

  it("rewrites hero_identity to Front and strips --- details --- traceback", () => {
    const details = "hero_identity: Kie createTask failed for nano-banana\n\n--- details ---\nTraceback (most recent call last):\n  File \"queue_worker.py\", line 1";
    const c: CharacterCandidate = {
      status: "failed",
      error: details,
      viewJobs: [
        { role: "hero_identity", status: "failed", error: details },
      ],
    };
    expect(gridSrc).toContain(">Generation failed:</span>");
    expect(candidateErrorMessage(c)).toBe("Front: Kie createTask failed for nano-banana");
    expect(candidateErrorMessage(c)).not.toContain("details");
    expect(candidateErrorMessage(c)).not.toContain("Traceback");
    expect(candidateErrorMessage(c)).not.toContain("hero_identity");
  });

  it("shows Front when the failed view role has no short job message", () => {
    const c: CharacterCandidate = {
      status: "failed",
      error: "hero_identity:",
      viewJobs: [{ role: "hero_identity", status: "failed" }],
    };
    expect(gridSrc).toContain(">Generation failed:</span>");
    expect(candidateErrorMessage(c)).toBe("Front");
  });
});

describe("character sheet layout-noncompliant hook", () => {
  it("normalizes snake_case layout_noncompliant onto the candidate", () => {
    const c = normalizeCharacterCandidate({
      status: "done",
      sheetAssetId: "sheet-1",
      layout_noncompliant: true,
    });
    expect(c.layoutNoncompliant).toBe(true);
    expect(isLayoutNoncompliant(c)).toBe(true);
  });

  it("reads camelCase layoutNoncompliant from the wire", () => {
    const c = normalizeCharacterCandidate({
      status: "done",
      sheetAssetId: "sheet-1",
      layoutNoncompliant: true,
    });
    expect(isLayoutNoncompliant(c)).toBe(true);
    expect(canUseCharacterLook(c)).toBe(false);
  });

  it("does not treat a layout-noncompliant complete result as a usable look", () => {
    const c: CharacterCandidate = {
      status: "done",
      sheetAssetId: "sheet-1",
      assetId: "sheet-1",
      layoutNoncompliant: true,
    };
    expect(candidateStage(c)).toBe("complete");
    expect(canUseCharacterLook(c)).toBe(false);
    expect(isLayoutNoncompliant({ layout_noncompliant: true })).toBe(true);
    expect(isLayoutNoncompliant({})).toBe(false);
  });

  it("still allows Use This Look when the flag is absent", () => {
    const c: CharacterCandidate = {
      status: "done",
      sheetAssetId: "sheet-1",
    };
    expect(canUseCharacterLook(c)).toBe(true);
  });
});
