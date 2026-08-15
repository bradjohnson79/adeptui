import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("Character Creator batch panel presence", () => {
  it("CharacterCore renders CharacterGeneratorPanel with checkbox and batchCount", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const core = readFileSync(join(here, "CharacterCore.tsx"), "utf8");
    const panel = readFileSync(join(here, "CharacterGeneratorPanel.tsx"), "utf8");
    expect(core).toContain("CharacterGeneratorPanel");
    expect(core).not.toContain("GeneratorSourceSelector");
    expect(panel).toContain("type=\"checkbox\"");
    expect(panel).toContain("batchCount");
    expect(panel).toContain("generator-auto-batch");
    expect(panel).toContain("character-generator-panel");
  });
});
