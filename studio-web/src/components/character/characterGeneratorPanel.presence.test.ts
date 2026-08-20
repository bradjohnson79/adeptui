import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

describe("Character Creator single CRS panel", () => {
  it("CharacterCore uses a two-option CRS selector without candidate grid chrome", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const core = readFileSync(join(here, "CharacterCore.tsx"), "utf8");
    const panel = readFileSync(join(here, "CharacterGeneratorPanel.tsx"), "utf8");
    expect(core).toContain("CharacterGeneratorPanel");
    expect(core).not.toContain("CharacterCandidateGrid");
    expect(core).not.toContain("Previous Generations / Candidates");
    expect(panel).toContain("character-generator-select");
    expect(panel).toContain("CRS_QWEN_FAMILY");
    expect(panel).toContain("CRS_GPT_IMAGE_2");
    expect(panel).not.toContain("character-more-generators");
    expect(panel).not.toContain("character-generator-batch");
  });
});
