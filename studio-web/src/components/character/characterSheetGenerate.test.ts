import { describe, expect, it, vi } from "vitest";
import {
  buildCharacterSheetStartBody,
  characterGenerateBlockReason,
  CHARACTER_SHEET_START_ERROR_PREFIX,
  firstExecutableReadyLocal,
  formatCharacterSheetStartError,
  selectedLocalNotReadyCopy,
  useReadyLocalButtonLabel,
} from "./characterSheetGenerate";
import { DEFAULT_CHARACTER_GENERATOR_PLAN, type CharacterGeneratorPlan } from "./characterGeneratorPlan";

const localOptions = [
  { id: "illustrious", label: "Illustrious XL", executable: true, supportsReferences: false },
  { id: "qwen2512", label: "Qwen Image 2512", executable: true, supportsReferences: false },
  { id: "zimage", label: "Z-Image Turbo", executable: true, supportsReferences: true },
];

function plan(partial: Partial<CharacterGeneratorPlan> = {}): CharacterGeneratorPlan {
  return {
    ...DEFAULT_CHARACTER_GENERATOR_PLAN,
    localFamilies: [
      { family: "illustrious", enabled: false, batchCount: 1 },
      { family: "qwen2512", enabled: false, batchCount: 1 },
      { family: "zimage", enabled: false, batchCount: 1 },
    ],
    ...partial,
  };
}

describe("Character Sheet generate request", () => {
  it("enables Generate for Illustrious + reference and sends one profile_guided local request", () => {
    const next = plan({
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 1 },
        { family: "qwen2512", enabled: false, batchCount: 1 },
        { family: "zimage", enabled: false, batchCount: 1 },
      ],
    });
    expect(characterGenerateBlockReason({ name: "Korri", plan: next, localOptions })).toBeNull();
    const body = buildCharacterSheetStartBody({
      profileVisualStyle: "realistic_anime",
      plan: next,
      hasReference: true,
      localOptions,
    });
    expect(body.candidateCount).toBe(1);
    expect(body.taskType).toBe("CRS_GENERATION");
    expect(body.layout).toBe("single_view");
    expect(body.requiredViews).toEqual(["front_full"]);
    expect(body.fourViewSingleOutput).toBe(false);
    expect(body.generationMode).toBe("profile_guided");
    expect(body.generatorSources.local?.find((r) => r.family === "illustrious")).toMatchObject({
      enabled: true,
      batchCount: 1,
    });
    expect(body.generatorSources.local?.find((r) => r.family === "auto")?.enabled).toBe(false);
    expect(body.generatorSources.api).toBeNull();
  });

  it("sends reference_conditioned for Qwen when the family reports reference support", () => {
    const qwenRef = [
      { id: "qwen2512", label: "Qwen Image 2512", executable: true, supportsReferences: true },
    ];
    const body = buildCharacterSheetStartBody({
      plan: plan({
        autoSelect: { enabled: false, batchCount: 1 },
        localFamilies: [{ family: "qwen2512", enabled: true, batchCount: 1 }],
      }),
      hasReference: true,
      localOptions: qwenRef,
    });
    expect(body.generationMode).toBe("reference_conditioned");
  });

  it("sends reference_conditioned for Z-Image with a reference attached", () => {
    const body = buildCharacterSheetStartBody({
      plan: plan({
        localFamilies: [
          { family: "illustrious", enabled: false, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
          { family: "zimage", enabled: true, batchCount: 1 },
        ],
      }),
      hasReference: true,
      localOptions,
    });
    expect(body.generationMode).toBe("reference_conditioned");
    expect(body.candidateCount).toBe(1);
  });

  it("always requests one Character Reference Sheet even if leftover plan rows have batches", () => {
    const body = buildCharacterSheetStartBody({
      plan: plan({
        localFamilies: [
          { family: "illustrious", enabled: true, batchCount: 2 },
          { family: "qwen2512", enabled: true, batchCount: 1 },
          { family: "zimage", enabled: false, batchCount: 1 },
        ],
        apiEnabled: false,
      }),
      hasReference: false,
      localOptions,
    });
    expect(body.candidateCount).toBe(1);
    expect(body.generatorSources.api).toBeNull();
  });

  it("blocks Generate when no source is enabled with a visible error", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan({ localEnabled: false, apiEnabled: false }),
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/Enable a Local or Cloud generator/i);
  });

  it("blocks Generate with empty local inventory + Auto Select + cloud off (CDX-009)", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan(),
      localOptions: [],
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/local generator/i);
    expect(reason).toMatch(/Cloud/i);
  });

  it("blocks explicit Qwen Image Edit 2509 when Not Ready", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan({
        autoSelect: { enabled: false, batchCount: 1 },
        localFamilies: [
          { family: "qwen_edit_2509", enabled: true, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
        ],
      }),
      localOptions: [
        { id: "qwen_edit_2509", label: "Qwen Image Edit 2509", executable: false },
        { id: "qwen2512", label: "Qwen Image", executable: true },
      ],
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/Qwen Image Edit 2509 is installed but not Runtime Ready/i);
  });

  it("blocks Generate when the inventory has no executable family and cloud is off", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan(),
      localOptions: [{ id: "qwen2512", label: "Qwen Image 2512", executable: false }],
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/local generator/i);
  });

  it("does not block Auto Select when an executable local family exists", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan({ autoSelect: { enabled: true, batchCount: 1 } }),
      localOptions,
    });
    expect(reason).toBeNull();
  });

  it("blocks Generate when the only checked local family is not executable and cloud is off", () => {
    const reason = characterGenerateBlockReason({
      name: "Korri",
      plan: plan({
        autoSelect: { enabled: false, batchCount: 1 },
        localFamilies: [
          { family: "illustrious", enabled: true, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
          { family: "zimage", enabled: false, batchCount: 1 },
        ],
      }),
      localOptions: [
        { id: "illustrious", label: "Illustrious XL", executable: false },
        { id: "qwen2512", label: "Qwen Image 2512", executable: true },
        { id: "zimage", label: "Z-Image Turbo", executable: true },
      ],
    });
    expect(reason).toContain(CHARACTER_SHEET_START_ERROR_PREFIX);
    expect(reason).toMatch(/Enable a Local or Cloud generator/i);
  });

  it("click contract: building the body twice yields one identical request shape", () => {
    const next = plan({
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 1 },
        { family: "qwen2512", enabled: false, batchCount: 1 },
        { family: "zimage", enabled: false, batchCount: 1 },
      ],
    });
    const a = buildCharacterSheetStartBody({ plan: next, hasReference: true, localOptions });
    const b = buildCharacterSheetStartBody({ plan: next, hasReference: true, localOptions });
    expect(a).toEqual(b);
  });

  it("formats backend rejection with the creator-facing prefix", () => {
    expect(formatCharacterSheetStartError(new Error("Selected model is not ready."))).toContain(
      CHARACTER_SHEET_START_ERROR_PREFIX,
    );
  });

  it("invokes startCharacterVisualSheet exactly once per generate", async () => {
    const start = vi.fn().mockResolvedValue({ ok: true, pack: { candidates: [] } });
    const body = buildCharacterSheetStartBody({
      plan: plan({
        localFamilies: [
          { family: "illustrious", enabled: true, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
          { family: "zimage", enabled: false, batchCount: 1 },
        ],
      }),
      hasReference: true,
      localOptions,
    });
    await start("proj", "char", body);
    expect(start).toHaveBeenCalledTimes(1);
    expect(start.mock.calls[0][2].candidateCount).toBe(1);
    expect(start.mock.calls[0][2].generatorSources.local.find((r: { family: string }) => r.family === "illustrious").enabled).toBe(true);
  });

  it("product default is one sheet per enabled generator, not a global four", () => {
    const body = buildCharacterSheetStartBody({
      plan: plan({
        localFamilies: [
          { family: "illustrious", enabled: true, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
          { family: "zimage", enabled: false, batchCount: 1 },
        ],
      }),
      hasReference: true,
      localOptions,
    });
    expect(body.candidateCount).toBe(1);
  });
});

describe("not-ready local selection recovery", () => {
  it("keeps 2509 selected and names the first executable ready local (FLUX when first)", () => {
    const locals = [
      { id: "qwen_edit_2509", label: "Qwen Image Edit 2509", executable: false },
      { id: "flux", label: "FLUX.1 Kontext", executable: true },
      { id: "qwen2512", label: "Qwen Image", executable: true },
    ];
    expect(firstExecutableReadyLocal(locals)?.id).toBe("flux");
    expect(useReadyLocalButtonLabel(firstExecutableReadyLocal(locals)!)).toBe("FLUX");
    expect(selectedLocalNotReadyCopy("Qwen Image Edit 2509")).toBe(
      "Qwen Image Edit 2509 is installed but not Runtime Ready.",
    );
  });
});
