import { describe, expect, it } from "vitest";
import {
  candidateErrorMessage,
  candidateIsFailed,
  candidateIsFinished,
  candidateProgress,
  type PropCandidate,
} from "./types";

function cand(partial: Partial<PropCandidate> = {}): PropCandidate {
  return {
    id: "c1",
    prop_id: "p1",
    index: 0,
    job_id: "j1",
    status: "queued",
    source: "local",
    family: "zimage",
    model: "zimage",
    provenance_label: "LOCAL - Z-Image Turbo - Description Guided",
    conditioning: "description_guided",
    take_label: "Look 1",
    ...partial,
  };
}

describe("prop creator failed-job hydration", () => {
  it("leaves Generating when hydration returns failed and shows the job message", () => {
    const c = cand({
      status: "failed",
      error: "Kie createTask failed for nano-banana",
    });
    expect(candidateIsFailed(c)).toBe(true);
    expect(candidateIsFinished(c)).toBe(true);
    expect(candidateErrorMessage(c)).toBe("Kie createTask failed for nano-banana");
  });

  it("strips --- details --- traceback from failed-card copy", () => {
    const c = cand({
      status: "failed",
      error: 'ComfyUI prompt failed\n\n--- details ---\nTraceback (most recent call last):\n  File "queue_worker.py", line 1',
    });
    expect(candidateErrorMessage(c)).toBe("ComfyUI prompt failed");
    expect(candidateErrorMessage(c)).not.toContain("details");
    expect(candidateErrorMessage(c)).not.toContain("Traceback");
  });

  it("treats error/cancelled as failed so cards do not stay Generating", () => {
    expect(candidateIsFailed(cand({ status: "error" }))).toBe(true);
    expect(candidateIsFailed(cand({ status: "cancelled" }))).toBe(true);
    expect(candidateIsFinished(cand({ status: "generating" }))).toBe(false);
    expect(candidateIsFinished(cand({ status: "queued" }))).toBe(false);
  });

  it("counts failed looks as finished so progress is not stuck at 0 of N", () => {
    const candidates = [
      cand({ id: "c0", index: 0, status: "failed", error: "Kie createTask failed for nano-banana" }),
      cand({ id: "c1", index: 1, status: "failed", error: "Kie createTask failed for seedream" }),
      cand({ id: "c2", index: 2, status: "complete", asset_id: "a1" }),
      cand({ id: "c3", index: 3, status: "generating" }),
    ];
    const progress = candidateProgress(candidates);
    expect(progress.total).toBe(4);
    expect(progress.done).toBe(3);
    expect(progress.percent).toBe(75);
  });

  it("does not treat queued looks as finished", () => {
    const progress = candidateProgress([
      cand({ status: "queued" }),
      cand({ status: "generating" }),
    ]);
    expect(progress.done).toBe(0);
    expect(progress.percent).toBe(0);
  });
});

describe("prop creator failed-job wiring", () => {
  it("resumes the existing GET poller when workspace candidates are not terminal", async () => {
    const fs = await import("node:fs");
    const hook = fs.readFileSync(new URL("./usePropCreator.ts", import.meta.url), "utf8");
    expect(hook).toContain("candidateIsFinished");
    expect(hook).toMatch(/propCreatorApi\s*\.get\(/);
    expect(hook).toContain("startPoll(selected.id)");
    expect(hook).not.toContain("CharacterGeneratorPanel");
    expect(hook).not.toMatch(/setInterval\([\s\S]{0,80}propCreatorApi\.(workspace|generate)/);
  });

  it("shows the hydrated job message on a failed card without importing Character Creator panel", async () => {
    const fs = await import("node:fs");
    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("candidateErrorMessage");
    expect(core).toContain("prop-creator-result-failed-msg");
    expect(core).toContain("GeneratorPlanPanel");
    expect(core).not.toContain("CharacterGeneratorPanel");
  });
});
