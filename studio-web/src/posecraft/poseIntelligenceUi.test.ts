import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Pose Intelligence UI copy", () => {
  it("uses filmmaking language and hides JEPA jargon", () => {
    const src = readFileSync(new URL("../components/GenerationTools/PoseCraftWorkspace.tsx", import.meta.url), "utf8");
    expect(src).toContain("Co-Director Pose Intelligence");
    expect(src).toContain("Analyze Pose");
    expect(src).toContain("Check Motion Continuity");
    expect(src).toContain("Send to Scene Creator");
    expect(src).toContain("Send to Timeline");
    expect(src).toContain("posecraft-analyze-pose");
    expect(src).toContain("Your pose is unchanged");
    expect(src).not.toMatch(/data-testid="[^"]*jepa/i);
    const accordion = src.slice(src.indexOf("pose-intelligence"), src.indexOf("id=\"camera\""));
    expect(accordion).not.toMatch(/\bJEPA\b/);
    expect(accordion).not.toMatch(/embedding/i);
    expect(accordion).not.toMatch(/latent/i);
  });
});
