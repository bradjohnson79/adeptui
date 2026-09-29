import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("scene duration UI contract", () => {
  it("does not cap Inspector scene duration at H3 native 15s", () => {
    const inspector = readFileSync(new URL("../components/timeline-master/TimelineInspector.tsx", import.meta.url), "utf8");
    expect(inspector).toContain("persistCanonicalSceneDuration");
    expect(inspector).toContain("decideTimedPromptRange");
    expect(inspector).toContain("timeline-timed-prompt-overflow");
    expect(inspector).toContain("timeline-inspector-h3-extension-plan");
    expect(inspector).not.toMatch(/const cap = isH3 \? 15/);
    expect(inspector).not.toContain("MiniMax H3 can go up to 15 seconds");
    expect(inspector).not.toContain("max={120}");
  });

  it("Timeline scale keeps going past the scene sequence — no 15s counter cap", () => {
    const tracks = readFileSync(new URL("../components/DirectorTracks.tsx", import.meta.url), "utf8");
    const clock = readFileSync(new URL("./useTimelineClock.ts", import.meta.url), "utf8");
    expect(tracks).toContain("timelineVisibleScaleSec");
    expect(tracks).toContain("data-scale-sec");
    expect(tracks).toContain("timeline-sequence-end");
    expect(tracks).not.toContain("Array.from({ length: Math.floor(boardDuration) + 1 })");
    expect(clock).toContain("scrub is not capped at the scene/sequence end");
    expect(clock).not.toContain("Math.min(sceneEndRef.current");
  });

  it("Timed Prompt modal offers an explicit scene extend instead of silent mutation", () => {
    const modal = readFileSync(new URL("../components/timeline-master/TimedPromptEditorModal.tsx", import.meta.url), "utf8");
    expect(modal).toContain("sceneDurationSec");
    expect(modal).toContain("onExtendScene");
    expect(modal).toContain("timeline-timed-prompt-overflow");
    expect(modal).toContain("timeline-timed-prompt-extend-scene");
    expect(modal).toContain("delete meta.start");
    expect(modal).toContain("delete meta.length");
  });
});
