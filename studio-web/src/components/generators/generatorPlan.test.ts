import { describe, expect, it } from "vitest";
import {
  DEFAULT_GENERATOR_PLAN,
  buildPropGeneratorSourcesPayload,
  fallbackGenerateScalars,
  groupDiscoveredModelsByProvider,
  hydrateGeneratorPlan,
  planHasExecutableWork,
  propProvenanceLabel,
  summarizeCandidatePlan,
  type CharacterGeneratorPlan,
} from "./generatorPlan";

function plan(partial: Partial<CharacterGeneratorPlan> = {}): CharacterGeneratorPlan {
  return {
    ...DEFAULT_GENERATOR_PLAN,
    localFamilies: [
      { family: "illustrious", enabled: false, batchCount: 1 },
      { family: "zimage", enabled: false, batchCount: 1 },
    ],
    apiModels: [],
    ...partial,
  };
}

describe("shared generator plan (Prop candidate-image math)", () => {
  it("counts candidate images, not 4-view sheets", () => {
    const mixed = plan({
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [
        { family: "illustrious", enabled: true, batchCount: 2 },
        { family: "zimage", enabled: true, batchCount: 1 },
      ],
    });
    const summary = summarizeCandidatePlan(mixed);
    expect(summary.totalImages).toBe(3);
    expect(summary.totalSheets).toBe(3);
    expect(summary.totalImages).not.toBe(12);
  });

  it("omits api jobs when Cloud Generators master is off", () => {
    const cloudOff = plan({
      localEnabled: false,
      apiEnabled: false,
      apiModels: [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          enabled: true,
          batchCount: 4,
        },
      ],
    });
    const payload = buildPropGeneratorSourcesPayload(cloudOff);
    expect(payload.api).toBeNull();
    expect(fallbackGenerateScalars(cloudOff).candidate_count).toBe(0);
    expect(planHasExecutableWork(cloudOff)).toBe(false);
  });

  it("groups discovered models by provider", () => {
    const groups = groupDiscoveredModelsByProvider([
      {
        providerId: "fal",
        modelId: "flux",
        model: "flux",
        displayName: "Flux",
        capabilities: [],
        supportsReferences: false,
        availability: "Connected",
        executable: true,
      },
      {
        providerId: "kie",
        modelId: "nano-banana-pro",
        model: "nano-banana-kie",
        displayName: "Nano Banana Pro",
        capabilities: [],
        supportsReferences: true,
        availability: "Connected",
        executable: true,
      },
    ]);
    expect(groups.map((g) => g.providerId)).toEqual(["kie", "fal"]);
    expect(groups[0].label).toBe("Kie.ai");
  });

  it("hydrates old scalar generator JSON without enabling unchecked API", () => {
    const hydrated = hydrateGeneratorPlan({
      local_enabled: true,
      api_enabled: false,
      local_family: "zimage",
      api_model: "fal:krea",
    });
    expect(hydrated.localEnabled).toBe(true);
    expect(hydrated.apiEnabled).toBe(false);
    expect(hydrated.autoSelect.enabled).toBe(false);
  });

  it("builds provenance labels for local and API rows", () => {
    expect(propProvenanceLabel({ sourceType: "local", modelLabel: "Qwen Image 2512", mode: "Description Guided" })).toBe(
      "LOCAL — Qwen Image 2512 — Description Guided",
    );
    expect(
      propProvenanceLabel({
        sourceType: "api",
        providerLabel: "Kie.ai",
        modelLabel: "Nano Banana Pro",
        mode: "Reference Conditioned",
      }),
    ).toBe("API — Kie.ai / Nano Banana Pro — Reference Conditioned");
  });
});
