import { describe, expect, it } from "vitest";
import { speakingCharactersWithoutApprovedVoice } from "./CharacterVoiceGapNotice";

describe("speakingCharactersWithoutApprovedVoice", () => {
  const bindings = [
    { id: "b-k", asset_id: "ak", reference_type: "character", identity_id: "korri", asset_name: "Korri", alias: "Korri" },
    { id: "b-a", asset_id: "aa", reference_type: "character", identity_id: "anadriya", asset_name: "Anadriya", alias: "Anadriya" },
  ];

  it("does not invent a voice for a bound character without an approved profile", () => {
    const gaps = speakingCharactersWithoutApprovedVoice(
      [
        { binding_id: "b-k", prompt_name: "Korri", type: "character", tag: "@Korri" },
        { binding_id: "b-a", prompt_name: "Anadriya", type: "character", tag: "@Anadriya" },
      ],
      bindings,
      new Set(["korri"]),
    );
    expect(gaps).toEqual([{ characterId: "anadriya", name: "Anadriya" }]);
  });
});
