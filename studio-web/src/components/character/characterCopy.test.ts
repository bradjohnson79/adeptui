import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Character Creator Revision B copy", () => {
  it("parks previous versions under Advanced and uses one Approve", () => {
    const core = readFileSync(new URL("./CharacterCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("Advanced — Previous versions");
    expect(core).toContain("Uses your photo");
    expect(core).not.toContain("onUpdateIdentity");
    expect(core).not.toContain("Update Character Identity");
  });

  it("does not add stills perception to generation blockers", () => {
    const src = readFileSync(new URL("../CapabilityPanel.tsx", import.meta.url), "utf8");
    expect(src).toContain("REQUIRED_FOR_GENERATION");
    expect(src).not.toContain("grounding_dino");
    expect(src).not.toContain("sam21");
    expect(src).not.toContain("depth_anything");
  });
});
