import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("Text to Video Preview Monitor binding", () => {
  const panel = readFileSync(join(__dirname, "./Txt2VidPanel.tsx"), "utf8");

  it("binds the completed output into LivePreviewMonitor as the page preview", () => {
    expect(panel).toContain("libraryAsset={previewAsset}");
    expect(panel).toContain("extractTxt2VidOutputAssetId");
    expect(panel).toContain("persistTxt2VidPreviewAssetId");
    expect(panel).toContain("readPersistedTxt2VidPreviewAssetId");
  });

  it("does not clear the last completed preview when a new generate is queued", () => {
    const start = panel.indexOf("const queueTxt2Vid = async");
    const end = panel.indexOf("const generate = async");
    const queueFn = panel.slice(start, end);
    expect(queueFn).toContain("setJob(j as Job)");
    expect(queueFn).not.toContain("setOutputAssetId(null)");
    expect(queueFn).not.toContain("clearPersistedTxt2VidPreviewAssetId");
  });

  it("only writes preview asset id on successful job completion", () => {
    expect(panel).toMatch(/if \(j\.status === "done"\) \{\s*const assetId = extractTxt2VidOutputAssetId/);
    const failedBlock = panel.match(/if \(j\.status === "failed"\) \{[\s\S]*?\n        \}/);
    const cancelledBlock = panel.match(/if \(j\.status === "cancelled"\) \{[\s\S]*?\n        \}/);
    expect(failedBlock?.[0] || "").not.toContain("setOutputAssetId");
    expect(cancelledBlock?.[0] || "").not.toContain("setOutputAssetId");
  });
});
