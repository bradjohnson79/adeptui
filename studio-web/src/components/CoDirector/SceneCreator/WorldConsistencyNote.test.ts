import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("World consistency note", () => {
  it("uses creator language and hides JEPA jargon", () => {
    const src = readFileSync(new URL("./WorldConsistencyNote.tsx", import.meta.url), "utf8");
    expect(src).toContain("world-consistency-note");
    expect(src).toContain("This change is on purpose");
    expect(src).not.toMatch(/JEPA|V-JEPA|embedding|cosine|anomaly/i);
    expect(src).toContain("api.worldIntelligence");
    expect(src).toContain(".advisory(");
  });

  it("is wired into Scene Creator status", () => {
    const core = readFileSync(new URL("./SceneCreatorCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("WorldConsistencyNote");
  });
});
