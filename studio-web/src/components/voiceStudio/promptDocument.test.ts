import { describe, expect, it } from "vitest";
import { applyManualPromptEdit, syncPromptDocument } from "./promptDocument";

describe("VoicePromptDocument sync", () => {
  it("updates age clause without wiping user additions", () => {
    const base = syncPromptDocument(null, {
      voiceType: "Female",
      age: "Young Adult",
      archetypes: ["Rebel"],
      accent: "American",
    });
    const edited = applyManualPromptEdit(base, `${base.compiledPrompt} Keep the laugh.`);
    expect(edited.userAdditions).toContain("Keep the laugh");
    const next = syncPromptDocument(edited, {
      voiceType: "Female",
      age: "Teenager",
      archetypes: ["Rebel"],
      accent: "American",
    });
    expect(next.compiledPrompt.toLowerCase()).toContain("teenager");
    expect(next.userAdditions).toContain("Keep the laugh");
  });
});
