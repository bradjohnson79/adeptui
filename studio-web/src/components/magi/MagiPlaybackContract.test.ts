import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("MAGI published-master + playback contract", () => {
  it("does not increment playhead on a sequence-bound interval", () => {
    const src = readFileSync(new URL("./MagiEditorWorkspace.tsx", import.meta.url), "utf8");
    expect(src).not.toMatch(/setInterval\(\(\) => \{\s*setSequence/);
    expect(src).toContain("followMediaClock");
    expect(src).toContain("seekGeneration");
    expect(src).toContain("magi-unpublished-master");
    expect(src).toContain("This scene has not been published from Timeline yet.");
  });

  it("binds Split View MAGI pane to live finishing.clipGrades", () => {
    const src = readFileSync(new URL("./MagiEditorWorkspace.tsx", import.meta.url), "utf8");
    expect(src).toContain("liveGradeCssFilter(gradeParams, gradePreset)");
    expect(src).toContain("processedSrc={api.assetUrl(splitOriginalId)}");
    expect(src).toContain("processedFilter={splitRightFilter");
    expect(src).toContain("magi-grade-live-hint");
    expect(src).toContain("patchFinishingLive");
    expect(src).toContain("adept:codirector-project-mutated");
    expect(src).toContain("mergeRemoteClipGrades");
    expect(src).toContain("presetId: e.target.value");
    expect(src).toContain("lightingPresetId: activeGrade.lightingPresetId");
    expect(src).toContain("params: kept");
    expect(src).toContain("processedOverlay");
    expect(src).toContain("mergeGraphicsIntoSequence");
    expect(src).toContain('createGraphic("text")');
    expect(src).not.toMatch(/magi-tool-text[\s\S]{0,120}queueProposal\("overlay_text"\)/);
    expect(src).toMatch(/data-testid="magi-viewer-fit"[\s\S]{0,80}role="status"/);
    expect(src).not.toMatch(/<button[^>]*data-testid="magi-viewer-fit"/);
  });

  it("keeps Split View on one clock authority", () => {
    const src = readFileSync(new URL("./MagiSplitView.tsx", import.meta.url), "utf8");
    expect(src).toContain('clockRole="authority"');
    expect(src).toContain('clockRole="follower"');
    expect(src).not.toContain("autoPlay");
  });
});
