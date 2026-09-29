import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "TimelineToolbar.tsx"), "utf8");

describe("TimelineToolbar Preflight help isolation", () => {
  it("Preflight click stays on the primary button; Help is a sibling", () => {
    const preflightIdx = src.indexOf('data-testid="timeline-toolbar-preflight"');
    expect(preflightIdx).toBeGreaterThan(-1);
    const window = src.slice(Math.max(0, preflightIdx - 400), preflightIdx + 500);
    expect(window).toContain("ActionWithHelp");
    expect(window).toContain("onClick={() => void preflight()}");
    expect(window).not.toContain("<Help id=\"preflight\" />");
    expect(window).toMatch(/<button[\s\S]*?>\s*Preflight\s*<\/button>/);
  });

  it("Help click cannot reach preflight because HelpTip stops propagation", () => {
    const helpTip = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../HelpTip.tsx"), "utf8");
    expect(helpTip).toContain("e.stopPropagation()");
    expect(helpTip).toContain("e.preventDefault()");
    expect(src).toContain("getTimelineHelp(\"preflight\")");
  });
});
