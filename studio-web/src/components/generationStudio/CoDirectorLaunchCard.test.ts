import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const src = readFileSync(new URL("./CoDirectorLaunchCard.tsx", import.meta.url), "utf8");

describe("CoDirectorLaunchCard Home feature card", () => {
  it("is a visual feature card, not an inline Co-Director composer", () => {
    expect(src).not.toContain("codirector-launch-composer");
    expect(src).not.toContain("gs-composer");
    expect(src).not.toContain("PROMPT_STARTERS");
    expect(src).not.toContain("<textarea");
    expect(src).toContain("codirector-launch-image");
    expect(src).toContain("Enter Co-Director");
    expect(src).toContain('data-testid="enter-codirector"');
    expect(src).toContain("Your intelligent production partner across Adept UI.");
  });

  it("opens existing fullscreen Co-Director and keeps project context", () => {
    expect(src).toContain("fullscreen: true");
    expect(src).toContain("codirector-project-context");
    expect(src).toContain("Active project:");
    expect(src).toContain("dashboardImages.codirector");
    expect(src).not.toMatch(/data:image\//);
    expect(src).not.toMatch(/base64,/);
  });
});
