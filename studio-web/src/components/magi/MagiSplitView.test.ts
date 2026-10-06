import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("MAGI Split View contract", () => {
  it("drives both panes with MagiVideoStage and shared preview time", () => {
    const src = readFileSync(new URL("./MagiSplitView.tsx", import.meta.url), "utf8");
    expect(src).toContain("MagiVideoStage");
    expect(src).toContain("timeSeconds");
    expect(src).toContain("playing");
    expect(src).not.toContain("autoPlay");
    expect(src).toContain("Original");
    expect(src).toContain("MAGI");
    expect(src).toContain('data-grade="raw"');
    expect(src).toContain('data-grade="live"');
    expect(src).toContain("processedFilter");
    expect(src).toContain("processedOverlay");
    expect(src).not.toMatch(/magi-split-original[\s\S]{0,400}filter=\{/);
    expect(src).not.toMatch(/magi-split-original[\s\S]{0,800}processedOverlay/);
  });

  it("Before / After opens Split View, not Compare", () => {
    const src = readFileSync(new URL("./MagiEditorWorkspace.tsx", import.meta.url), "utf8");
    expect(src).toMatch(/setViewerMode\("split"\)[\s\S]{0,80}Before \/ After/);
    expect(src).not.toMatch(/setViewerMode\("compare"\)[\s\S]{0,80}Before \/ After/);
    expect(src).toContain('"split"');
    expect(src).toContain("Split View");
  });
});
