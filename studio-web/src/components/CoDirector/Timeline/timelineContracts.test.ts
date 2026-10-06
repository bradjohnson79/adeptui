import { describe, expect, it } from "vitest";
import { CONTENT_NAV } from "../navEntries";

describe("Timeline Express doorway", () => {
  it("places Timeline immediately after Scene Creator", () => {
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(tabs.indexOf("timeline")).toBe(tabs.indexOf("scene_creator") + 1);
    const entry = CONTENT_NAV.find((item) => item.kind === "tab" && item.id === "timeline");
    expect(entry && entry.kind === "tab" ? entry.label : "").toBe("Timeline");
  });

  it("keeps Express as a launcher into Standard, not a second editor", async () => {
    const fs = await import("node:fs");
    const launcher = fs.readFileSync(new URL("./TimelineExpressLauncher.tsx", import.meta.url), "utf8");
    const panel = fs.readFileSync(new URL("./TimelinePanel.tsx", import.meta.url), "utf8");
    const content = fs.readFileSync(new URL("../CoDirectorProjectContent.tsx", import.meta.url), "utf8");
    const shell = fs.readFileSync(new URL("../CoDirectorShell.tsx", import.meta.url), "utf8");
    expect(panel).toContain("TimelineExpressLauncher");
    expect(panel).not.toContain("TimelineEditorShell");
    expect(launcher).toContain("timeline-open-standard");
    expect(launcher).toContain("Open Timeline");
    expect(launcher).toContain("openExpressStandardWorkspace");
    expect(launcher).toContain('openExpressStandardWorkspace(onGoTab, "timeline"');
    expect(launcher).toContain("markOpenPopupAfterNav");
    expect(launcher).not.toContain("generate");
    expect(content).toContain("TimelinePanel");
    expect(content).toContain('tab === "timeline"');
    expect(content).toContain("<TimelinePanel projectId={projectId} onGoTab={onGoTab} />");
    expect(shell).toContain('value === "timeline"');
  });

  it("keeps FilmTimelineShell as the only Timeline product path on creator routes", async () => {
    const fs = await import("node:fs");
    const { fileURLToPath } = await import("node:url");
    const editor = fs.readFileSync(new URL("../../../pages/ProjectEditor.tsx", import.meta.url), "utf8");
    expect(editor).toContain("FilmTimelineShell");
    expect(editor).not.toContain("TimelineEditorShell");
    expect(editor).not.toContain("TimelineMasterPanel");
    expect(editor).not.toContain("SpatialMapEditor");
    expect(editor).not.toContain("SpatialSceneWorkspace");
    expect(fs.existsSync(fileURLToPath(new URL("../../../components/SpatialMap.tsx", import.meta.url)))).toBe(false);
    expect(fs.existsSync(fileURLToPath(new URL("../../../components/SpatialSceneWorkspace.tsx", import.meta.url)))).toBe(false);
  });
});
