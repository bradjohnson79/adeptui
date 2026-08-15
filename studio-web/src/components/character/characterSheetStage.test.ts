import { describe, expect, it } from "vitest";
import {
  batchProgress,
  candidateErrorMessage,
  candidateStage,
  viewIsFinished,
  type CharacterCandidate,
} from "./types";

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
});
