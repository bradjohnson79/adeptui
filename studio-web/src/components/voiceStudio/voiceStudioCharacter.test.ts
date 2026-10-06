import { describe, expect, it } from "vitest";
import { voiceStudioCoDirectorChips } from "./constants";
import {
  isCurrentCharacterRequest,
  rememberedCharacterToRestore,
  resolveVoiceStudioActiveCharacterId,
  voiceStudioSearchForCharacter,
} from "./voiceStudioCharacter";

const KORRI = "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed";
const ANADRIYA = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
const knownIds = [KORRI, ANADRIYA];

describe("Voice Studio active character authority", () => {
  it("uses the URL characterId and never substitutes another character", () => {
    expect(
      resolveVoiceStudioActiveCharacterId({ urlCharacterId: ANADRIYA, knownIds }),
    ).toBe(ANADRIYA);
    expect(
      resolveVoiceStudioActiveCharacterId({ urlCharacterId: KORRI, knownIds }),
    ).toBe(KORRI);
  });

  it("treats a missing URL characterId as the chooser, even if Korri is remembered", () => {
    expect(resolveVoiceStudioActiveCharacterId({ urlCharacterId: "", knownIds })).toBe("");
    expect(
      rememberedCharacterToRestore({
        urlCharacterId: "",
        rememberedCharacterId: KORRI,
        knownIds,
      }),
    ).toBe(KORRI);
  });

  it("does not restore a remembered character after Choose Another Character clears the URL", () => {
    expect(
      resolveVoiceStudioActiveCharacterId({
        urlCharacterId: "",
        knownIds,
      }),
    ).toBe("");
  });

  it("does not fall back to a character who has an approved voice when the URL names someone else", () => {
    expect(
      resolveVoiceStudioActiveCharacterId({
        urlCharacterId: ANADRIYA,
        knownIds,
      }),
    ).toBe(ANADRIYA);
    expect(
      rememberedCharacterToRestore({
        urlCharacterId: ANADRIYA,
        rememberedCharacterId: KORRI,
        knownIds,
      }),
    ).toBe("");
  });

  it("does not substitute a known character when the URL id is unknown", () => {
    expect(
      resolveVoiceStudioActiveCharacterId({
        urlCharacterId: "missing-character",
        knownIds,
      }),
    ).toBe("");
  });

  it("writes and clears characterId without dropping Voice Studio workspace context", () => {
    const current = "?workspace=voicestudio&characterId=" + KORRI + "&returnWorkspace=codirector";
    expect(voiceStudioSearchForCharacter(current, ANADRIYA)).toBe(
      "?workspace=voicestudio&characterId=" + ANADRIYA + "&returnWorkspace=codirector",
    );
    expect(voiceStudioSearchForCharacter(current, null)).toBe(
      "?workspace=voicestudio&returnWorkspace=codirector",
    );
  });

  it("rejects stale async responses from a previous character", () => {
    expect(isCurrentCharacterRequest(KORRI, ANADRIYA)).toBe(false);
    expect(isCurrentCharacterRequest(ANADRIYA, ANADRIYA)).toBe(true);
    expect(isCurrentCharacterRequest("", ANADRIYA)).toBe(false);
  });

  it("does not keep Korri Co-Director chips after the workspace moves to Anadriya", () => {
    expect(voiceStudioCoDirectorChips("Anadriya")[0]).toBe("Make Anadriya more sarcastic");
    expect(voiceStudioCoDirectorChips("Korri")[0]).toBe("Make Korri more sarcastic");
    expect(voiceStudioCoDirectorChips("Anadriya").join(" ")).not.toContain("Korri");
  });
});
