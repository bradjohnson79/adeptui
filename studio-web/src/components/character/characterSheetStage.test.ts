import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  batchCoarseLabel,
  batchCoarseStage,
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

  it("treats a finished Front-only V2 view as a usable identity image", () => {
    const c: CharacterCandidate = {
      status: "done",
      assetId: "front-only",
      viewJobs: [{ role: "hero_identity", status: "done", assetId: "front-only" }],
    };
    expect(candidateStage(c)).toBe("complete");
    expect(canUseCharacterLook(c)).toBe(true);
  });

  it("does not fall back generatorName to workflowKey", () => {
    expect(gridSrc).toContain("c.provenance || c.modelVariant || c.model || \"Local generator\"");
    expect(gridSrc).not.toContain("c.workflowKey");
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

describe("Character Reference Sheet progress honesty", () => {
  it("never reports 100% while generation is still active", () => {
    const src = readFileSync(new URL("./GenerationProgressBar.tsx", import.meta.url), "utf8");
    expect(src).toContain("Generating Character Reference Sheet");
    expect(src).toContain("Math.min(percent, 99)");
  });

  it("does not clear the candidate grid when a new generate starts", () => {
    const src = readFileSync(new URL("./CharacterSheetGenerator.tsx", import.meta.url), "utf8");
    expect(src).toContain('data-testid="character-generate"');
    expect(src).not.toContain("onCandidates([])");
  });

  it("does not restart the 60-minute poll budget after it is exhausted", () => {
    const src = readFileSync(new URL("./CharacterSheetGenerator.tsx", import.meta.url), "utf8");
    expect(src).toContain("pollExhaustedRef");
    expect(src).toContain("pollExhaustedRef.current = true");
    expect(src).toContain("pollExhaustedRef.current) return");
  });

  it("makes the 30s still-queued fast-fail binding (no infinite timeout reset)", () => {
    const src = readFileSync(new URL("./CharacterSheetGenerator.tsx", import.meta.url), "utf8");
    // The 30s "Still queued" branch must mark the poll cycle done so the 4s
    // tick cannot restart it with a fresh budget (the SenseNova stuck-loader
    // loop). It must set pollExhaustedRef immediately before returning.
    expect(src).toContain("Still queued with no views after 30 seconds");
    expect(src).toMatch(/Still queued[\s\S]*pollExhaustedRef\.current = true/);
  });

  it("does not swallow all poll errors silently (bounded + vanished-job fast-fail)", () => {
    const src = readFileSync(new URL("./CharacterSheetGenerator.tsx", import.meta.url), "utf8");
    expect(src).toContain("consecutiveErrorsRef");
    expect(src).toContain("POLL_ERROR_THRESHOLD");
    // Vanished job (404/410/gone) must fast-fail, not loop forever.
    expect(src).toMatch(/gone[\s\S]*The runtime lost this job/);
  });
});

describe("Character Reference Sheet coarse stage (no fake 0%)", () => {
  it("reports loading_model for an active single-node candidate with no view jobs (SenseNova)", () => {
    // SenseNova CRS is a single SenseNovaU1LocalImageEdit node — no per-view
    // jobs hydrate while the model loads. This must NOT read as a frozen
    // "0 of 1 sheets complete"; it is an active model load.
    const c: CharacterCandidate = { status: "generating" };
    expect(batchCoarseStage([c], true)).toBe("loading_model");
    expect(batchCoarseLabel(batchCoarseStage([c], true))).toBe("Loading model…");
  });

  it("reports generating when a view is running", () => {
    const c: CharacterCandidate = {
      status: "generating",
      viewJobs: [
        { role: "hero_identity", status: "running" },
        { role: "full_body_side_left", status: "queued" },
      ],
    };
    expect(batchCoarseStage([c], true)).toBe("generating");
  });

  it("reports composing when all views are done but no sheet yet", () => {
    const c: CharacterCandidate = {
      status: "generating",
      viewJobs: [
        { role: "hero_identity", status: "done", assetId: "a1" },
        { role: "full_body_side_left", status: "done", assetId: "a2" },
      ],
    };
    expect(batchCoarseStage([c], true)).toBe("composing");
  });

  it("reports complete when the sheet asset is present", () => {
    const c: CharacterCandidate = { status: "done", sheetAssetId: "sheet-1" };
    expect(batchCoarseStage([c], false)).toBe("complete");
  });

  it("reports failed when a candidate failed", () => {
    const c: CharacterCandidate = { status: "failed", error: "boom" };
    expect(batchCoarseStage([c], true)).toBe("failed");
  });

  it("GenerationProgressBar uses the coarse label so a no-views active job is not frozen at 0 of 1", () => {
    const src = readFileSync(new URL("./GenerationProgressBar.tsx", import.meta.url), "utf8");
    expect(src).toContain("batchCoarseLabel");
    expect(src).toContain("hasMeasurableProgress");
  });
});
