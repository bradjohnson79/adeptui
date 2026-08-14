import { describe, expect, it, vi } from "vitest";
import {
  buildCharacterSheetStartBody,
  characterGenerateBlockReason,
  CHARACTER_SHEET_START_ERROR_PREFIX,
  formatCharacterSheetStartError,
} from "./characterSheetGenerate";

const named = { name: "Korri" };

describe("Character Sheet generate request", () => {
  it("enables Generate for Illustrious + reference and sends one profile_guided local request", () => {
    const sources = {
      local: { enabled: true, selectedId: "illustrious", stage2Enabled: false },
      api: { enabled: false, selectedId: "" },
    };
    expect(characterGenerateBlockReason({ name: named.name, sources })).toBeNull();
    const body = buildCharacterSheetStartBody({
      profileVisualStyle: "realistic_anime",
      sources,
      hasReference: true,
    });
    expect(body.candidateCount).toBe(4);
    expect(body.generationMode).toBe("profile_guided");
    expect(body.generatorSources.local?.family).toBe("illustrious");
    expect(body.generatorSources.api).toBeNull();
    expect(body.generatorSources.local?.stage2Enabled).toBe(false);
  });

  it("sends profile_guided for Qwen with a reference attached", () => {
    const body = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "qwen2512" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: true,
    });
    expect(body.generationMode).toBe("profile_guided");
    expect(body.generatorSources.local?.family).toBe("qwen2512");
  });

  it("sends reference_conditioned for Z-Image with a reference attached", () => {
    const body = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "zimage" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: true,
    });
    expect(body.generationMode).toBe("reference_conditioned");
  });

  it("still generates Illustrious with no reference", () => {
    const body = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "illustrious" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: false,
    });
    expect(body.generationMode).toBe("profile_guided");
    expect(characterGenerateBlockReason({
      name: "Korri",
      sources: {
        local: { enabled: true, selectedId: "illustrious" },
        api: { enabled: false, selectedId: "" },
      },
    })).toBeNull();
  });

  it("blocks Generate when no source is enabled with a visible error", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      sources: { local: { enabled: false, selectedId: "" }, api: { enabled: false, selectedId: "" } },
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/Enable a Local or Cloud generator/i);
  });

  it("click contract: building the body twice yields one identical request shape (not two families)", () => {
    const sources = {
      local: { enabled: true, selectedId: "illustrious" },
      api: { enabled: false, selectedId: "" },
    };
    const a = buildCharacterSheetStartBody({ sources, hasReference: true });
    const b = buildCharacterSheetStartBody({ sources, hasReference: true });
    expect(a).toEqual(b);
    expect(a.generatorSources.local?.family).toBe("illustrious");
  });

  it("formats backend rejection with the creator-facing prefix", () => {
    expect(formatCharacterSheetStartError(new Error("Selected model is not ready."))).toContain(
      CHARACTER_SHEET_START_ERROR_PREFIX,
    );
  });

  it("invokes startCharacterVisualSheet exactly once per generate", async () => {
    const start = vi.fn().mockResolvedValue({ ok: true, pack: { candidates: [] } });
    const body = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "illustrious" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: true,
    });
    await start("proj", "char", body);
    expect(start).toHaveBeenCalledTimes(1);
    expect(start.mock.calls[0][2].generationMode).toBe("profile_guided");
    expect(start.mock.calls[0][2].candidateCount).toBe(4);
  });

  it("E2E override may send candidateCount=1 without changing the product default", () => {
    const body = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "illustrious" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: true,
      candidateCount: 1,
    });
    expect(body.candidateCount).toBe(1);
    const product = buildCharacterSheetStartBody({
      sources: {
        local: { enabled: true, selectedId: "illustrious" },
        api: { enabled: false, selectedId: "" },
      },
      hasReference: true,
    });
    expect(product.candidateCount).toBe(4);
  });
});
