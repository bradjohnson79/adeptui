import { describe, expect, it } from "vitest";
import {
  ERS_GENERATOR_DEFAULT,
  ERS_GENERATOR_OPTIONS,
  ERS_GPT_HOSTED_ID,
  ERS_GPT_OFFICIAL_ID,
  ERS_GPT_T2I_ID,
  ERS_NO_SOURCE_MESSAGE,
  ERS_QWEN_OFFICIAL_ID,
  ERS_QWEN_PROVIDER_ID,
  ERS_QWEN_WORKFLOW_KEY,
  GPT_I2I_NOT_READY_MESSAGE,
  GPT_NOT_READY_MESSAGE,
  QWEN_I2I_NOT_READY_MESSAGE,
  QWEN_NOT_READY_MESSAGE,
  buildErsStartContext,
  ersGeneratorOptionDisabled,
  formatErsProvenance,
  generatorBlockReason,
  hasAuthoritativeEnvironmentSource,
  isGptImage2I2IReady,
  isGptImage2Ready,
  isQwenReady,
  provenanceModelFromSelection,
  resolveErsGeneratorFromModel,
} from "./ersGenerator";

describe("ERS generator selector", () => {
  it("defaults to Qwen Image local with the catalog official id", () => {
    expect(ERS_GENERATOR_DEFAULT).toBe("qwen2512");
    expect(ERS_QWEN_OFFICIAL_ID).toBe("qwen2512");
    expect(ERS_QWEN_PROVIDER_ID).toBe("qwen-image-2512-local");
    expect(ERS_GENERATOR_OPTIONS[0]?.id).toBe("qwen2512");
    expect(ERS_GENERATOR_OPTIONS.map((o) => o.id)).toEqual(["qwen2512", "gpt-image-2"]);
  });

  it("builds startExecution context with image-conditioned official ids only", () => {
    const qwen = buildErsStartContext("qwen2512");
    expect(qwen.model).toBe("qwen2512");
    expect(qwen.modelFamilyPreference).toBe("qwen2512");
    expect(qwen.forceWorkflowKey).toBe(ERS_QWEN_WORKFLOW_KEY);
    expect(qwen.source).toBe("local");
    expect(qwen.hostedModelId).toBeUndefined();
    expect(qwen.kieImageModelId).toBeUndefined();

    const gpt = buildErsStartContext("gpt-image-2");
    expect(gpt.hostedModelId).toBe(ERS_GPT_HOSTED_ID);
    expect(gpt.hosted_model_id).toBe("gpt-image-2-kie");
    expect(gpt.kieImageModelId).toBe(ERS_GPT_OFFICIAL_ID);
    expect(gpt.kie_image_model_id).toBe("gpt-image-2-image-to-image");
    expect(gpt.kie_image_model_id).not.toBe(ERS_GPT_T2I_ID);
    expect(gpt.source).toBe("api");
    expect(gpt.modelFamilyPreference).toBeUndefined();
  });

  it("changing the dropdown only changes the selected context — it is not a generate POST", () => {
    const after = buildErsStartContext("gpt-image-2");
    expect(after.hostedModelId).toBe("gpt-image-2-kie");
    expect(after.kieImageModelId).toBe("gpt-image-2-image-to-image");
    expect(JSON.stringify(after)).not.toContain("gpt-image-2-text-to-image");
  });

  it("formats provenance as the real image-conditioned operation, never Text to Image", () => {
    expect(formatErsProvenance({ model: "qwen2512", sourceKind: "Local" })).toBe(
      "Generating with Qwen Image · Reference",
    );
    expect(formatErsProvenance({ model: "qwen2512.ref", sourceKind: "Local" })).toBe(
      "Generating with Qwen Image · Reference",
    );
    expect(formatErsProvenance({ model: "qwen2512.txt2img", sourceKind: "Local" })).toBe(
      "Generating with Qwen Image · Reference",
    );
    expect(formatErsProvenance({ model: "gpt-image-2-image-to-image", sourceKind: "API" })).toBe(
      "Generating with GPT Image 2 · Image Edit",
    );
    expect(formatErsProvenance({ model: "gpt-image-2-kie", sourceKind: "API" })).toBe(
      "Generating with GPT Image 2 · Image Edit",
    );
    expect(formatErsProvenance({ model: ERS_GPT_T2I_ID, sourceKind: "API" })).not.toContain(
      "Text to Image",
    );
    expect(formatErsProvenance({ model: "qwen2512.txt2img", sourceKind: "Local" })).not.toContain(
      "txt2img",
    );
    expect(formatErsProvenance({ model: "qwen2512", sourceKind: "Local" })).not.toMatch(
      /text\s*to\s*image/i,
    );
  });

  it("pins provenance model ids to the image-conditioned operations", () => {
    expect(provenanceModelFromSelection("qwen2512")).toEqual({
      model: "qwen2512.ref",
      sourceKind: "Local",
    });
    expect(provenanceModelFromSelection("gpt-image-2")).toEqual({
      model: "gpt-image-2-image-to-image",
      sourceKind: "API",
    });
  });

  it("reconnects selection from a live execution model", () => {
    expect(resolveErsGeneratorFromModel({ model: "qwen2512.txt2img" })).toBe("qwen2512");
    expect(resolveErsGeneratorFromModel({ model: "qwen2512.ref" })).toBe("qwen2512");
    expect(resolveErsGeneratorFromModel({ model: "gpt-image-2-text-to-image" })).toBe("gpt-image-2");
    expect(resolveErsGeneratorFromModel({ model: "gpt-image-2-image-to-image" })).toBe("gpt-image-2");
    expect(resolveErsGeneratorFromModel({ model: "unknown" })).toBeNull();
  });

  it("never silently falls back when the selected generator is not ready", () => {
    expect(isQwenReady([])).toBe(false);
    expect(isGptImage2Ready([])).toBe(false);
    expect(isQwenReady([{ id: "qwen-image-2512-local", family: "qwen2512", readiness: "not_installed" }])).toBe(
      false,
    );
    expect(isGptImage2Ready([{ id: "gpt-image-2-kie", readiness: "needs_auth" }])).toBe(false);
    expect(isQwenReady([{ id: "qwen-image-2512-local", family: "qwen2512", readiness: "ready" }])).toBe(true);
    expect(isGptImage2Ready([{ id: "gpt-image-2-kie", readiness: "ready" }])).toBe(true);

    expect(generatorBlockReason("qwen2512", false, true)).toBe(QWEN_NOT_READY_MESSAGE);
    expect(generatorBlockReason("qwen2512", false, true)).not.toContain("GPT Image 2 is not ready");
    expect(generatorBlockReason("gpt-image-2", true, false)).toBe(GPT_NOT_READY_MESSAGE);
    expect(generatorBlockReason("gpt-image-2", true, false)).not.toContain("Qwen Image is not ready");
    expect(generatorBlockReason("qwen2512", true, false, true)).toBeNull();
    expect(generatorBlockReason("gpt-image-2", false, true, false, true)).toBeNull();
  });

  it("blocks GPT for ERS when I2I capability is missing even if the dock is ready", () => {
    expect(
      isGptImage2I2IReady([
        { id: "gpt-image-2-kie", readiness: "ready", metadata: { supports: ["text_to_image"] } },
      ]),
    ).toBe(false);
    expect(
      isGptImage2I2IReady([
        { id: "gpt-image-2-kie", readiness: "ready", metadata: { supports: ["text_to_image", "edit"] } },
      ]),
    ).toBe(true);
    expect(generatorBlockReason("gpt-image-2", true, true, true, false)).toBe(
      GPT_I2I_NOT_READY_MESSAGE,
    );
    expect(generatorBlockReason("qwen2512", true, true, false)).toBe(QWEN_I2I_NOT_READY_MESSAGE);
  });

  it("blocks ERS when the Spatial Map has no authoritative source image", () => {
    expect(hasAuthoritativeEnvironmentSource({})).toBe(false);
    expect(
      hasAuthoritativeEnvironmentSource({ originalEnvironmentReferenceAssetId: "src-1" }),
    ).toBe(true);
    expect(generatorBlockReason("qwen2512", true, true, true, true, false)).toBe(
      ERS_NO_SOURCE_MESSAGE,
    );
  });

  it("disables a generator at selection time when its I2I path is unavailable", () => {
    // Qwen cannot be selected when local Qwen I2I is not ready (pixel-verified unavailable).
    expect(ersGeneratorOptionDisabled("qwen2512", false, true)).toBe(true);
    expect(ersGeneratorOptionDisabled("qwen2512", null, true)).toBe(false);
    expect(ersGeneratorOptionDisabled("qwen2512", true, true)).toBe(false);
    // GPT Image 2 is disabled only when its own I2I path is unavailable.
    expect(ersGeneratorOptionDisabled("gpt-image-2", true, false)).toBe(true);
    expect(ersGeneratorOptionDisabled("gpt-image-2", true, true)).toBe(false);
    // Unknown readiness never disables (honest unknown -> keep selectable, block reason shows).
    expect(ersGeneratorOptionDisabled("qwen2512", undefined, undefined)).toBe(false);
  });
});
