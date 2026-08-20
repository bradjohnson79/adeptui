import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  AUTO_SELECT_FAMILY,
  DEFAULT_GENERATOR_FAMILY,
  anyExplicitLocalFamilyEnabled,
  applyDefaultGeneratorIfIdle,
  buildGeneratorSourcesPayload,
  clampBatchCount,
  cloudModelStatusLabel,
  DEFAULT_CHARACTER_GENERATOR_PLAN,
  groupDiscoveredImageModelsByProvider,
  hasExecutableSource,
  hydratePlanFromPreferences,
  isAutoSelectActive,
  mergePlanWithInventory,
  normalizeDiscoveredImageModel,
  primaryGeneratorValue,
  returnToAutoSelectOnly,
  selectedCrsGenerator,
  setCrsGenerator,
  setPrimaryLocalGenerator,
  summarizeGenerationPlan,
  type CharacterGeneratorPlan,
  type NormalizedDiscoveredImageModel,
} from "./characterGeneratorPlan";

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

describe("Character generator plan", () => {
  it("setCrsGenerator enables exactly one Qwen or GPT Image 2 source", () => {
    const qwen = setCrsGenerator(plan({
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 3 },
        { family: "qwen2512", enabled: false, batchCount: 2 },
      ],
    }), "qwen2512");
    expect(selectedCrsGenerator(qwen)).toBe("qwen2512");
    expect(qwen.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(qwen.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
    expect(summarizeGenerationPlan(qwen).totalSheets).toBe(1);

    const gpt = setCrsGenerator(qwen, "gpt-image-2");
    expect(selectedCrsGenerator(gpt)).toBe("gpt-image-2");
    expect(gpt.apiEnabled).toBe(true);
    expect(gpt.localEnabled).toBe(false);
    expect(gpt.apiModels.some((row) => row.enabled && row.modelId === "gpt-image-2")).toBe(true);
  });

  it("defaults to Qwen Image 2512 with Auto Select off", () => {
    expect(DEFAULT_CHARACTER_GENERATOR_PLAN.defaultGenerator).toBe(DEFAULT_GENERATOR_FAMILY);
    expect(DEFAULT_CHARACTER_GENERATOR_PLAN.autoSelect.enabled).toBe(false);
  });

  it("enables Qwen on empty prefs when the family is executable", () => {
    const hydrated = hydratePlanFromPreferences(null, [
      { id: "illustrious", label: "Illustrious XL", executable: true },
      { id: "qwen2512", label: "Qwen Image 2512", executable: true },
    ], []);
    expect(hydrated.autoSelect.enabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(hydrated.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
    expect(primaryGeneratorValue(hydrated)).toBe("qwen2512");
  });

  it("does not silently enable Auto Select or Illustrious when Qwen is unavailable", () => {
    const hydrated = hydratePlanFromPreferences(null, [
      { id: "illustrious", label: "Illustrious XL", executable: true },
      { id: "qwen2512", label: "Qwen Image 2512", executable: false },
    ], []);
    expect(hydrated.autoSelect.enabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
    expect(applyDefaultGeneratorIfIdle(hydrated, [
      { id: "qwen2512", label: "Qwen", executable: false },
    ]).localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBeFalsy();
  });

  it("coerces a saved Illustrious preference to the Qwen CRS default", () => {
    const hydrated = hydratePlanFromPreferences(
      {
        local: [
          { family: "auto", enabled: false, batchCount: 1 },
          { family: "illustrious", enabled: true, batchCount: 2 },
        ],
        api: null,
      },
      [
        { id: "illustrious", label: "Illustrious XL", executable: true },
        { id: "qwen2512", label: "Qwen Image 2512", executable: true },
      ],
      [],
    );
    expect(hydrated.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(hydrated.autoSelect.enabled).toBe(false);
  });

  it("migrates Auto-Select-only saved prefs to the Qwen default", () => {
    const hydrated = hydratePlanFromPreferences(
      {
        local: [
          { family: "auto", enabled: true, batchCount: 1 },
          { family: "illustrious", enabled: false, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
        ],
        api: null,
      },
      [
        { id: "illustrious", label: "Illustrious XL", executable: true },
        { id: "qwen2512", label: "Qwen Image 2512", executable: true },
      ],
      [],
    );
    expect(hydrated.autoSelect.enabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(hydrated.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
  });

  it("compact generator pick enables only that local family and clears Cloud", () => {
    const next = setPrimaryLocalGenerator(
      plan({
        apiEnabled: true,
        apiModels: [
          { providerId: "kie", modelId: "nano-banana-pro", model: "nano-banana-kie", enabled: true, batchCount: 1 },
        ],
        localFamilies: [
          { family: "illustrious", enabled: true, batchCount: 1 },
          { family: "qwen2512", enabled: false, batchCount: 1 },
        ],
      }),
      "qwen2512",
      1,
    );
    expect(next.autoSelect.enabled).toBe(false);
    expect(next.apiEnabled).toBe(false);
    expect(next.apiModels.every((row) => !row.enabled)).toBe(true);
    expect(next.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(next.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
  });

  it("clamps batch counts to 1–4 and defaults to 1", () => {
    expect(clampBatchCount(undefined)).toBe(1);
    expect(clampBatchCount(0)).toBe(1);
    expect(clampBatchCount(1)).toBe(1);
    expect(clampBatchCount(4)).toBe(4);
    expect(clampBatchCount(9)).toBe(4);
  });

  it("makes Auto Select inactive when any explicit local family is checked", () => {
    const mixed = plan({
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 2 },
        { family: "qwen2512", enabled: false, batchCount: 1 },
      ],
    });
    expect(anyExplicitLocalFamilyEnabled(mixed)).toBe(true);
    expect(isAutoSelectActive(mixed)).toBe(false);
    const summary = summarizeGenerationPlan(mixed);
    expect(summary.totalSheets).toBe(2);
    expect(summary.sheets.every((s) => s.family === "illustrious")).toBe(true);
    const payload = buildGeneratorSourcesPayload(mixed);
    const auto = payload.local?.find((r) => r.family === "auto");
    expect(auto?.enabled).toBe(false);
  });

  it("does not add Auto Select candidates on top of explicit families", () => {
    const mixed = plan({
      autoSelect: { enabled: true, batchCount: 2 },
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 2 },
        { family: "qwen2512", enabled: true, batchCount: 1 },
      ],
    });
    const summary = summarizeGenerationPlan(mixed);
    expect(summary.totalSheets).toBe(3);
    expect(summary.totalViews).toBe(12);
    expect(summary.sheets.some((s) => s.family === "auto")).toBe(false);
    expect(summary.localLines.map((l) => `${l.label}×${l.count}`)).toEqual([
      "Illustrious XL×2",
      "Qwen Image 2512×1",
    ]);
  });

  it("returns to Auto Select-only when the creator chooses Auto Select again", () => {
    const mixed = plan({
      localFamilies: [{ family: "illustrious", enabled: true, batchCount: 2 }],
    });
    const autoOnly = returnToAutoSelectOnly(mixed);
    expect(isAutoSelectActive(autoOnly)).toBe(true);
    expect(anyExplicitLocalFamilyEnabled(autoOnly)).toBe(false);
    expect(summarizeGenerationPlan(autoOnly).totalSheets).toBe(1);
  });

  it("treats unchecked sources as zero work at every master and row level", () => {
    const localOff = plan({
      localEnabled: false,
      localFamilies: [{ family: "illustrious", enabled: true, batchCount: 4 }],
    });
    expect(summarizeGenerationPlan(localOff).totalSheets).toBe(0);

    const cloudOff = plan({
      apiEnabled: false,
      apiModels: [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          displayName: "Nano Banana Pro",
          enabled: true,
          batchCount: 4,
        },
      ],
    });
    expect(summarizeGenerationPlan(cloudOff).apiSheetCount).toBe(0);

    const oneChecked = plan({
      localEnabled: false,
      apiEnabled: true,
      apiModels: [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          displayName: "Nano Banana Pro",
          enabled: true,
          batchCount: 2,
        },
        {
          providerId: "wavespeed",
          modelId: "seedream",
          model: "seedream-wavespeed",
          displayName: "Seedream",
          enabled: false,
          batchCount: 4,
        },
      ],
    });
    const summary = summarizeGenerationPlan(oneChecked);
    expect(summary.totalSheets).toBe(2);
    expect(summary.apiSheetCount).toBe(2);
    expect(summary.apiLines).toEqual([{ label: "Nano Banana Pro — Kie.ai", count: 2 }]);
    const payload = buildGeneratorSourcesPayload(oneChecked);
    expect(payload.local).toBeNull();
    expect(payload.api?.find((m) => m.modelId === "seedream")?.enabled).toBe(false);
    expect(payload.api?.find((m) => m.modelId === "nano-banana-pro")).toMatchObject({
      providerId: "kie",
      modelId: "nano-banana-pro",
      enabled: true,
      batchCount: 2,
    });
  });

  it("always shows the Generation Plan totals without inventing costs", () => {
    const mixed = plan({
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 2 },
        { family: "qwen2512", enabled: true, batchCount: 1 },
      ],
      apiEnabled: true,
      apiModels: [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          displayName: "Nano Banana Pro",
          enabled: true,
          batchCount: 2,
        },
      ],
    });
    const summary = summarizeGenerationPlan(mixed);
    expect(summary.totalSheets).toBe(5);
    expect(summary.totalViews).toBe(20);
    expect(summary.apiSheetCount).toBe(2);
  });

  it("normalizes Setup discovered models using providerId not provider", () => {
    const normalized = normalizeDiscoveredImageModel({
      id: "nano-banana-kie",
      providerId: "kie",
      providerModelId: "nano-banana-pro",
      displayName: "Nano Banana Pro",
      modality: "image",
      capabilities: ["text_to_image"],
      executable: true,
    });
    expect(normalized).toMatchObject({
      providerId: "kie",
      modelId: "nano-banana-pro",
      model: "nano-banana-kie",
      supportsReferences: false,
    });
    expect(normalized?.displayName).toContain("Kie.ai");
  });

  it("does not create a Character Creator catalog from video/upscaler rows", () => {
    expect(
      normalizeDiscoveredImageModel({
        id: "seedance-kie",
        providerId: "kie",
        providerModelId: "seedance",
        modality: "video",
        capabilities: ["text_to_video"],
      }),
    ).toBeNull();
  });

  it("hydrates prefs without enabling unchecked API models", () => {
    const localOptions = [
      { id: "illustrious", label: "Illustrious XL", executable: true },
      { id: "qwen2512", label: "Qwen Image 2512", executable: true },
    ];
    const apiModels = [
      {
        providerId: "kie",
        modelId: "nano-banana-pro",
        model: "nano-banana-kie",
        displayName: "Nano Banana Pro — Kie.ai",
        providerLabel: "Kie.ai",
        capabilities: ["text_to_image"],
        supportsReferences: false,
        availability: "Connected",
        executable: true,
        adapterAvailable: true,
        accountAccessible: true,
      },
    ];
    const hydrated = hydratePlanFromPreferences(
      {
        local: [
          { family: "auto", enabled: false, batchCount: 1 },
          { family: "illustrious", enabled: true, batchCount: 2 },
        ],
        api: null,
      },
      localOptions,
      apiModels,
    );
    expect(hydrated.localEnabled).toBe(true);
    expect(hydrated.apiEnabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "illustrious")?.enabled).toBe(false);
    expect(hydrated.localFamilies.find((r) => r.family === "qwen2512")?.enabled).toBe(true);
    expect(hydrated.apiModels[0].enabled).toBe(false);
  });

  it("changing batchCount in the next plan does not require mutating inventory identity", () => {
    const merged = mergePlanWithInventory(
      plan({
        localFamilies: [{ family: "illustrious", enabled: true, batchCount: 2 }],
      }),
      [{ id: "illustrious", label: "Illustrious XL", executable: true }],
      [],
    );
    expect(merged.localFamilies[0]).toMatchObject({ family: "illustrious", enabled: true, batchCount: 2 });
    const next = { ...merged, localFamilies: merged.localFamilies.map((r) => ({ ...r, batchCount: 1 })) };
    expect(next.localFamilies[0].batchCount).toBe(1);
    expect(merged.localFamilies[0].batchCount).toBe(2);
  });

  it("counts zero Auto Select sheets when the local inventory is empty (CDX-009)", () => {
    const summary = summarizeGenerationPlan(plan(), []);
    expect(summary.totalSheets).toBe(0);
    expect(summary.sheets).toHaveLength(0);
    expect(summary.localLines).toEqual([]);
  });

  it("counts zero Auto Select sheets when the inventory has no executable family", () => {
    const summary = summarizeGenerationPlan(plan(), [
      { id: "qwen2512", label: "Qwen Image 2512", executable: false },
      { id: "zimage", label: "Z-Image Turbo", executable: false },
    ]);
    expect(summary.totalSheets).toBe(0);
    expect(summary.localLines).toEqual([]);
  });

  it("counts Auto Select sheets when an executable local family exists", () => {
    const summary = summarizeGenerationPlan(
      plan({ autoSelect: { enabled: true, batchCount: 1 } }),
      [{ id: "qwen2512", label: "Qwen Image 2512", executable: true }],
    );
    expect(summary.totalSheets).toBe(1);
    expect(summary.localLines).toEqual([{ label: "Auto Select", count: 1 }]);
    expect(summary.sheets[0].family).toBe(AUTO_SELECT_FAMILY);
  });

  it("counts only executable explicit families when inventory is known (CDX-009)", () => {
    const mixed = plan({
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 2 },
        { family: "qwen2512", enabled: true, batchCount: 1 },
        { family: "zimage", enabled: true, batchCount: 1 },
      ],
    });
    const summary = summarizeGenerationPlan(mixed, [
      { id: "illustrious", label: "Illustrious XL", executable: true },
      { id: "qwen2512", label: "Qwen Image 2512", executable: false },
    ]);
    expect(summary.totalSheets).toBe(2);
    expect(summary.localLines).toEqual([{ label: "Illustrious XL", count: 2 }]);
  });

  it("hasExecutableSource reflects inventory truth for Auto Select and Cloud", () => {
    expect(hasExecutableSource(plan(), [])).toBe(false);
    const autoOn = plan({ autoSelect: { enabled: true, batchCount: 1 } });
    expect(hasExecutableSource(autoOn, undefined)).toBe(true);
    expect(hasExecutableSource(autoOn, [{ id: "qwen2512", label: "Qwen", executable: true }])).toBe(true);
    const cloudOn = plan({
      apiEnabled: true,
      apiModels: [
        { providerId: "kie", modelId: "nano-banana-pro", model: "nano-banana-kie", enabled: true, batchCount: 1 },
      ],
    });
    expect(hasExecutableSource(cloudOn, [])).toBe(true);
  });
});

describe("Character Creator generator UI contract", () => {
  it("CharacterGeneratorPanel exposes only Qwen and GPT Image 2", () => {
    const panel = readFileSync(new URL("./CharacterGeneratorPanel.tsx", import.meta.url), "utf8");
    expect(panel).toContain('data-testid="character-generator-compact"');
    expect(panel).toContain('data-testid="character-generator-select"');
    expect(panel).toContain("CRS_QWEN_FAMILY");
    expect(panel).toContain("CRS_GPT_IMAGE_2");
    expect(panel).not.toContain("character-more-generators");
    expect(panel).not.toContain("More Generators");
    expect(panel).not.toContain("function BatchSelect");
  });

  it("Character Creator still discovers GPT Image 2 without exposing a cloud checkbox grid", () => {
    const panel = readFileSync(new URL("./CharacterGeneratorPanel.tsx", import.meta.url), "utf8");
    expect(panel).toContain('fetchDiscoveredHostedModelRows("image")');
    expect(panel).toContain("normalizeDiscoveredImageModel");
    expect(panel).toContain("mergePlanWithInventory");
    expect(panel).not.toContain("character-core__api-group");
    expect(panel).not.toContain("character-core__api-group-label");
    expect(panel).not.toContain("CHARACTER_SHEET_BATCH_MIN");
    expect(panel).not.toContain("CHARACTER_SHEET_BATCH_MAX");
    const plan = readFileSync(new URL("./characterGeneratorPlan.ts", import.meta.url), "utf8");
    expect(plan).toContain("listed, adapter not ready");
    expect(plan).toContain("adapterAvailable");
    const core = readFileSync(new URL("./CharacterCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("CharacterGeneratorPanel");
    expect(core).toContain("CharacterActiveCrsCard");
    expect(core).toContain("LibraryQuickPreviewModal");
    const refCtrl = readFileSync(new URL("./CharacterReferenceControl.tsx", import.meta.url), "utf8");
    expect(refCtrl).toContain("Ask Co-Director to create a Character Reference Sheet");
    expect(refCtrl).toContain('data-testid="character-reference-tip"');
    expect(refCtrl).toContain("single-view image");
    expect(refCtrl).toContain("multi-view Character Reference Sheet");
  });

  it("plan contract: every local family and API model has enabled checkbox plus batchCount", () => {
    const merged = mergePlanWithInventory(
      DEFAULT_CHARACTER_GENERATOR_PLAN,
      [
        { id: "illustrious", label: "Illustrious XL", executable: true },
        { id: "qwen2512", label: "Qwen Image 2512", executable: true },
      ],
      [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          displayName: "Nano Banana Pro",
          providerLabel: "Kie.ai",
          capabilities: ["text_to_image"],
          supportsReferences: false,
          availability: "Connected",
          executable: true,
          adapterAvailable: true,
          accountAccessible: true,
        },
        {
          providerId: "kie",
          modelId: "gpt-image-2",
          model: "gpt-image-2-kie",
          displayName: "GPT Image 2",
          providerLabel: "Kie.ai",
          capabilities: ["text_to_image"],
          supportsReferences: false,
          availability: "Connected",
          executable: true,
          adapterAvailable: true,
          accountAccessible: true,
        },
        {
          providerId: "kie",
          modelId: "seedream",
          model: "seedream-kie",
          displayName: "Seedream",
          providerLabel: "Kie.ai",
          capabilities: ["text_to_image"],
          supportsReferences: false,
          availability: "Connected",
          executable: true,
          adapterAvailable: true,
          accountAccessible: true,
        },
      ],
    );
    expect(merged.localFamilies.every((row) => typeof row.enabled === "boolean" && typeof row.batchCount === "number")).toBe(true);
    expect(merged.apiModels.every((row) => typeof row.enabled === "boolean" && typeof row.batchCount === "number")).toBe(true);
    expect(merged.apiModels.map((row) => row.modelId)).toEqual([
      "nano-banana-pro",
      "gpt-image-2",
      "seedream",
    ]);
    const oneOn = {
      ...merged,
      apiEnabled: true,
      apiModels: merged.apiModels.map((row) =>
        row.modelId === "gpt-image-2" ? { ...row, enabled: true, batchCount: 3 } : row,
      ),
    };
    const summary = summarizeGenerationPlan(oneOn);
    expect(summary.apiSheetCount).toBe(3);
    expect(summary.apiLines).toHaveLength(1);
    expect(summary.apiLines[0].label).toContain("GPT Image 2");
    expect(summary.apiLines[0].label).toContain("Kie.ai");
    expect(summary.apiLines[0].count).toBe(3);
    const payload = buildGeneratorSourcesPayload(oneOn);
    expect(payload.api?.find((m) => m.modelId === "nano-banana-pro")?.enabled).toBe(false);
    expect(payload.api?.find((m) => m.modelId === "gpt-image-2")).toMatchObject({
      enabled: true,
      batchCount: 3,
    });
    expect(payload.api?.find((m) => m.modelId === "seedream")?.enabled).toBe(false);
  });

  it("groups discovered image rows by provider and keeps models without an adapter", () => {
    const flux = normalizeDiscoveredImageModel({
      id: "flux-kie",
      providerId: "kie",
      providerModelId: "flux",
      displayName: "FLUX",
      label: "FLUX — Kie.ai",
      modality: "image",
      capabilities: ["text_to_image", "edit"],
      adapterAvailable: true,
      accountAccessible: true,
      capabilityLabel: "Certified",
      readiness: "Ready",
      executable: true,
    });
    const listed = normalizeDiscoveredImageModel({
      id: "flux-wavespeed",
      providerId: "wavespeed",
      providerModelId: "wavespeed-ai/flux-dev",
      displayName: "FLUX Dev",
      label: "FLUX Dev — WaveSpeed.ai",
      modality: "image",
      capabilities: ["text_to_image"],
      adapterAvailable: false,
      accountAccessible: true,
      capabilityLabel: "Unsupported",
      readiness: "Requires Adapter",
      executable: false,
      selectable: false,
    });
    const fal = normalizeDiscoveredImageModel({
      id: "krea2-turbo-fal",
      providerId: "fal",
      providerModelId: "fal-ai/krea-2/turbo",
      displayName: "Krea 2 Turbo",
      label: "Krea 2 Turbo — fal.ai",
      modality: "image",
      capabilities: ["text_to_image"],
      adapterAvailable: true,
      accountAccessible: true,
      capabilityLabel: "Certified",
      readiness: "Ready",
      executable: true,
    });
    expect(flux).not.toBeNull();
    expect(listed).not.toBeNull();
    expect(fal).not.toBeNull();
    expect(flux?.adapterAvailable).toBe(true);
    expect(listed?.adapterAvailable).toBe(false);
    expect(flux?.providerLabel).toBe("Kie.ai");
    expect(listed?.providerLabel).toBe("WaveSpeed.ai");
    expect(fal?.providerLabel).toBe("fal.ai");
    expect(cloudModelStatusLabel(flux as NormalizedDiscoveredImageModel)).toBe("Certified");
    expect(cloudModelStatusLabel(listed as NormalizedDiscoveredImageModel)).toBe("listed, adapter not ready");
    const groups = groupDiscoveredImageModelsByProvider([
      fal as NormalizedDiscoveredImageModel,
      listed as NormalizedDiscoveredImageModel,
      flux as NormalizedDiscoveredImageModel,
    ]);
    expect(groups.map((g) => g.providerId)).toEqual(["kie", "wavespeed", "fal"]);
    expect(groups.map((g) => g.providerLabel)).toEqual(["Kie.ai", "WaveSpeed.ai", "fal.ai"]);
    expect(groups.every((g) => g.models.length > 0)).toBe(true);
    expect(groups.find((g) => g.providerId === "wavespeed")?.models[0].modelId).toBe("wavespeed-ai/flux-dev");
  });

  it("omits a provider heading when the discovered-models key is not configured", () => {
    const noKey = normalizeDiscoveredImageModel({
      id: "flux-kie",
      providerId: "kie",
      providerModelId: "flux",
      displayName: "FLUX",
      label: "FLUX — Kie.ai",
      modality: "image",
      capabilities: ["text_to_image"],
      adapterAvailable: true,
      accountAccessible: false,
      capabilityLabel: "Requires Setup",
      readiness: "Requires Setup",
      executable: false,
    });
    expect(noKey?.accountAccessible).toBe(false);
    const groups = groupDiscoveredImageModelsByProvider([noKey as NormalizedDiscoveredImageModel]);
    expect(groups).toEqual([]);
  });
});

