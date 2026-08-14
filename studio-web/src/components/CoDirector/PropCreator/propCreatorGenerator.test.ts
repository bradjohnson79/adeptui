import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  conditioningModeLabel,
  identityDisabledReason,
  isIdentityEligible,
  type GeneratorOption,
} from "../../generators/types";
import {
  DEFAULT_GENERATOR_PLAN,
  fallbackGenerateScalars,
  planHasExecutableWork,
  propProvenanceLabel,
  summarizeCandidatePlan,
  type CharacterGeneratorPlan,
} from "../../generators/generatorPlan";
import {
  candidateStatusLabel,
  persistGeneratorPayload,
  propGenerateBlockReason,
  propGenerateRequest,
  sourcesFromPropGenerator,
} from "./propGenerator";

const CORE = new URL("./PropCreatorCore.tsx", import.meta.url);
const HOOK = new URL("./usePropCreator.ts", import.meta.url);
const PANEL = new URL("../../generators/GeneratorPlanPanel.tsx", import.meta.url);
const PLAN = new URL("../../generators/generatorPlan.ts", import.meta.url);

function opt(partial: Partial<GeneratorOption> & Pick<GeneratorOption, "id" | "label">): GeneratorOption {
  return { executable: true, ...partial };
}

function plan(partial: Partial<CharacterGeneratorPlan> = {}): CharacterGeneratorPlan {
  return {
    ...DEFAULT_GENERATOR_PLAN,
    localFamilies: [
      { family: "illustrious", enabled: false, batchCount: 1 },
      { family: "qwen2512", enabled: false, batchCount: 1 },
      { family: "zimage", enabled: false, batchCount: 1 },
    ],
    apiModels: [],
    ...partial,
  };
}

describe("Prop Creator generator UI", () => {
  it("uses the parameterized GeneratorPlanPanel instead of dropdowns or CharacterGeneratorPanel", () => {
    const src = readFileSync(CORE, "utf8");
    expect(src).toContain('from "../../generators/GeneratorPlanPanel"');
    expect(src).toContain("<GeneratorPlanPanel");
    expect(src).toContain('textModeLabel="Description Guided"');
    expect(src).toContain('imageNoun="Prop Image"');
    expect(src).toContain('imageNounPlural="Prop Images"');
    expect(src).toContain('purpose="prop"');
    expect(src).not.toContain("GeneratorSourceSelector");
    expect(src).not.toContain("CharacterGeneratorPanel");
    expect(src).not.toContain("prop-creator-local-enable");
    expect(src).not.toContain("Local Image Generator");
    expect(src).not.toContain("API Generation — Not Available");
    expect(src).not.toContain("local_families");
    expect(src).not.toContain("Profile Guided");
    expect(src).not.toContain("Character Sheet");
    expect(src).not.toContain("4-view");
    expect(src).not.toContain("totalViews");
  });

  it("does not import CharacterGeneratorPanel as-is", () => {
    const panel = readFileSync(PANEL, "utf8");
    expect(panel).not.toContain("CharacterGeneratorPanel");
    expect(panel).toContain("hostedProvidersDiscoveredModels");
    expect(panel).toContain('"image"');
    expect(panel).toContain("Cloud Generators (uses credits)");
    expect(panel).toContain("Local Identity Engine");
    expect(panel).toContain("Style Engine (optional)");
    expect(panel).toContain("Batches");
    expect(panel).toContain("groupDiscoveredModelsByProvider");
    expect(panel).toContain("summarizeCandidatePlan");
    expect(panel).not.toContain("Character Sheet");
    expect(panel).not.toContain("total views");
  });

  it("labels every generator checkbox in the plan panel", () => {
    const panel = readFileSync(PANEL, "utf8");
    const checkboxes = [...panel.matchAll(/type="checkbox"/g)];
    expect(checkboxes.length).toBeGreaterThanOrEqual(4);
    expect(panel).toContain("<span>Local Identity Engine</span>");
    expect(panel).toContain("<span>Auto Select</span>");
    expect(panel).toContain("<span>Style Engine (optional)</span>");
    expect(panel).toContain("<span>Cloud Generators (uses credits)</span>");
    const unlabeled = panel.match(/type="checkbox"[\s\S]{0,240}?\/>\s*(?![\s\S]{0,80}<span>)/);
    expect(unlabeled).toBeNull();
  });

  it("exposes local and API per-model checkboxes plus batches 1–4", () => {
    const panel = readFileSync(PANEL, "utf8");
    expect(panel).toContain("generator-local-enable-");
    expect(panel).toContain("generator-local-batch-");
    expect(panel).toContain("generator-api-enable-");
    expect(panel).toContain("generator-api-batch-");
    expect(panel).toContain("GENERATOR_BATCH_MIN");
    expect(panel).toContain("GENERATOR_BATCH_MAX");
    const planSrc = readFileSync(PLAN, "utf8");
    expect(planSrc).toContain("GENERATOR_BATCH_MIN = 1");
    expect(planSrc).toContain("GENERATOR_BATCH_MAX = 4");
  });

  it("loads local inventory from imagegenModels and API shortlist from hosted discovery", () => {
    const panel = readFileSync(PANEL, "utf8");
    expect(panel).toContain(".imagegenModels()");
    expect(panel).toContain('m.group !== "auto"');
    expect(panel).toContain('hostedProvidersDiscoveredModels("image")');
    expect(panel).toContain("Add a provider in Setup");
    expect(panel).not.toContain("API Generation — Not Available");
    const core = readFileSync(CORE, "utf8");
    expect(core).not.toContain("workspace?.local_families");
  });

  it("does not disable Illustrious or Qwen when a reference is present", () => {
    const illustrious = opt({
      id: "illustrious",
      label: "Illustrious XL 1.0 (Anime)",
      supportsReferences: false,
      executable: true,
    });
    const qwen = opt({
      id: "qwen2512",
      label: "Qwen Image 2512",
      supportsReferences: false,
      executable: true,
    });
    const zimage = opt({
      id: "zimage",
      label: "Z-Image Turbo",
      supportsReferences: true,
      executable: true,
    });
    expect(isIdentityEligible(illustrious)).toBe(true);
    expect(isIdentityEligible(qwen)).toBe(true);
    expect(isIdentityEligible(zimage)).toBe(true);
    expect(identityDisabledReason(illustrious)).toBeNull();
    expect(conditioningModeLabel(illustrious, true, "Description Guided")).toBe("Description Guided");
    expect(conditioningModeLabel(qwen, true, "Description Guided")).toBe("Description Guided");
    expect(conditioningModeLabel(zimage, true, "Description Guided")).toBe("Reference Conditioned");
    expect(conditioningModeLabel(zimage, false, "Description Guided")).toBeNull();
  });

  it("uses Description Guided labels for Prop, not Character Profile Guided wording", () => {
    const src = readFileSync(CORE, "utf8");
    expect(src).toContain('textModeLabel="Description Guided"');
    expect(src).not.toContain("Profile Guided");
    expect(src).not.toContain("gender");
    expect(src).not.toContain("apparent_age");
    expect(src).not.toContain("hair");
    expect(src).not.toContain("voice");
  });

  it("adds Use as Prop Identity beside Reference Image", () => {
    const src = readFileSync(CORE, "utf8");
    expect(src).toContain("Use as Prop Identity");
    expect(src).toContain('data-testid="prop-use-as-identity"');
    expect(src).toContain("function ReferenceBlock");
    const refBlock = src.slice(src.indexOf("function ReferenceBlock"), src.indexOf("function GeneratorBlock"));
    expect(refBlock).toContain("prop-use-as-identity");
    expect(refBlock).toContain("Use as Prop Identity");
    const hook = readFileSync(HOOK, "utf8");
    expect(hook).toContain("useAsIdentity");
    expect(hook).toContain("approved_asset_id");
    expect(hook).toContain("use_as_identity");
    expect(hook.indexOf("const save =")).toBeGreaterThan(-1);
    const saveFn = hook.slice(hook.indexOf("const save ="), hook.indexOf("const newProp ="));
    expect(saveFn).toContain("persist({ useAsIdentity");
    expect(saveFn).toContain("persistSaveFeedback(true)");
    expect(saveFn).toContain("flashNotice");
  });

  it("treats unchecked sources as zero planned jobs", () => {
    const bothOff = plan({
      localEnabled: false,
      apiEnabled: false,
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [{ family: "zimage", enabled: true, batchCount: 4 }],
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
    expect(summarizeCandidatePlan(bothOff).totalImages).toBe(0);
    expect(planHasExecutableWork(bothOff)).toBe(false);
    const req = propGenerateRequest(bothOff);
    expect(req.generatorSources.local).toBeNull();
    expect(req.generatorSources.api).toBeNull();
    expect(req.local_enabled).toBe(false);
    expect(req.api_enabled).toBe(false);
    expect(req.candidate_count).toBe(0);
    expect(propGenerateBlockReason({ name: "Hero Sword", plan: bothOff })).toBe(
      "Enable a Local or Cloud generator to create prop images.",
    );

    const cloudMasterOff = plan({
      localEnabled: false,
      apiEnabled: false,
      apiModels: [
        {
          providerId: "kie",
          modelId: "nano-banana-pro",
          model: "nano-banana-kie",
          enabled: true,
          batchCount: 3,
        },
      ],
    });
    const cloudOffReq = propGenerateRequest(cloudMasterOff);
    expect(cloudOffReq.generatorSources.api).toBeNull();
    expect(cloudOffReq.api_enabled).toBe(false);
    expect(cloudOffReq.candidate_count).toBe(0);

    const localOnly = plan({
      localEnabled: true,
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [
        { family: "qwen2512", enabled: true, batchCount: 2 },
        { family: "zimage", enabled: false, batchCount: 4 },
      ],
      apiEnabled: false,
    });
    const localReq = propGenerateRequest(localOnly);
    expect(localReq.local_enabled).toBe(true);
    expect(localReq.api_enabled).toBe(false);
    expect(localReq.local_family).toBe("qwen2512");
    expect(localReq.candidate_count).toBe(2);
    expect(localReq.generatorSources.local?.find((r) => r.family === "zimage")?.enabled).toBe(false);
    expect(localReq.generatorSources.api).toBeNull();
    expect(propGenerateBlockReason({ name: "Hero Sword", plan: localOnly })).toBeNull();
    expect(propGenerateBlockReason({ name: "", plan: localOnly })).toBe("Name the Prop to generate images.");
  });

  it("sends generatorSources local[]/api[]/styleEngine and keeps old scalars as fallback", () => {
    const mixed = plan({
      localEnabled: true,
      autoSelect: { enabled: false, batchCount: 1 },
      localFamilies: [{ family: "zimage", enabled: true, batchCount: 3 }],
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
          providerId: "fal",
          modelId: "flux-pro",
          model: "flux-pro",
          enabled: false,
          batchCount: 4,
        },
      ],
      stage2Enabled: true,
      stage2Family: "flux",
    });
    const req = propGenerateRequest(mixed);
    expect(req.generatorSources.local).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ family: "zimage", enabled: true, batchCount: 3 }),
      ]),
    );
    expect(req.generatorSources.api?.find((m) => m.modelId === "nano-banana-pro")).toMatchObject({
      providerId: "kie",
      modelId: "nano-banana-pro",
      enabled: true,
      batchCount: 2,
    });
    expect(req.generatorSources.api?.find((m) => m.modelId === "flux-pro")?.enabled).toBe(false);
    expect(req.generatorSources.styleEngine).toEqual({ enabled: true, family: "flux" });
    expect(req.candidate_count).toBe(5);
    expect(req.local_enabled).toBe(true);
    expect(req.api_enabled).toBe(true);
    expect(fallbackGenerateScalars(mixed).candidate_count).toBe(5);
  });

  it("hydrates and persists source flags without silently enabling a disabled pool", () => {
    expect(sourcesFromPropGenerator({ local_enabled: false, api_enabled: false, local_family: "illustrious", api_model: "" })).toMatchObject({
      localEnabled: false,
      apiEnabled: false,
    });
    const persisted = persistGeneratorPayload(
      plan({
        localEnabled: false,
        apiEnabled: false,
        localFamilies: [{ family: "illustrious", enabled: false, batchCount: 1 }],
      }),
    );
    expect(persisted.local_enabled).toBe(false);
    expect(persisted.api_enabled).toBe(false);
    expect(persisted.local).toBeNull();
    expect(persisted.api).toBeNull();
  });

  it("wires generate through the shared plan helpers", () => {
    const hook = readFileSync(HOOK, "utf8");
    expect(hook).toContain("propGenerateRequest");
    expect(hook).toContain("persistGeneratorPayload");
    expect(hook).toContain("setPlan");
    expect(hook).not.toContain("api_enabled: false");
  });

  it("uses Generating / Complete / Failed / Retry status language", () => {
    expect(candidateStatusLabel("queued")).toBe("Generating");
    expect(candidateStatusLabel("generating")).toBe("Generating");
    expect(candidateStatusLabel("complete")).toBe("Complete");
    expect(candidateStatusLabel("failed")).toBe("Failed");
    const src = readFileSync(CORE, "utf8");
    expect(src).toContain("candidateStatusLabel");
    expect(src).toContain("Retry");
  });

  it("formats provenance as LOCAL — Model — Mode and API — Provider / Model — Mode", () => {
    expect(propProvenanceLabel({ sourceType: "local", modelLabel: "Z-Image Turbo", mode: "Description Guided" })).toBe(
      "LOCAL — Z-Image Turbo — Description Guided",
    );
    expect(
      propProvenanceLabel({
        sourceType: "api",
        modelLabel: "Nano Banana Pro",
        providerLabel: "Kie.ai",
        mode: "Reference Conditioned",
      }),
    ).toBe("API — Kie.ai / Nano Banana Pro — Reference Conditioned");
  });

  it("keeps the Prop profile saved confirmation on the shared save path", () => {
    const hook = readFileSync(HOOK, "utf8");
    expect(hook).toContain('PROP_PROFILE_SAVED_NOTICE = "Prop profile saved"');
    const saveFn = hook.slice(hook.indexOf("const save ="), hook.indexOf("const newProp ="));
    expect(saveFn.indexOf("await persist(")).toBeLessThan(saveFn.indexOf("persistSaveFeedback(true)"));
    expect(saveFn).toContain("flashNotice");
    const core = readFileSync(CORE, "utf8");
    expect(core).toContain("void pc.save()");
    expect(core).toContain("PROP_PROFILE_SAVED_NOTICE");
    expect(core).toContain("<StatusBlock pc={pc} />");
  });
});
