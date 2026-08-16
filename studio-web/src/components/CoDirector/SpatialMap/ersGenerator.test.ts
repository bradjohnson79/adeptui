import { describe, expect, it } from "vitest";
import {
  ERS_GENERATOR_DEFAULT,
  ERS_GENERATOR_OPTIONS,
  ERS_GPT_HOSTED_ID,
  ERS_GPT_OFFICIAL_ID,
  ERS_QWEN_OFFICIAL_ID,
  ERS_QWEN_PROVIDER_ID,
  GPT_NOT_READY_MESSAGE,
  QWEN_NOT_READY_MESSAGE,
  buildErsStartContext,
  formatErsProvenance,
  generatorBlockReason,
  isGptImage2Ready,
  isQwenReady,
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

  it("builds startExecution context with catalog official ids only", () => {
    const qwen = buildErsStartContext("qwen2512");
    expect(qwen.model).toBe("qwen2512");
    expect(qwen.modelFamilyPreference).toBe("qwen2512");
    expect(qwen.source).toBe("local");
    expect(qwen.hostedModelId).toBeUndefined();
    expect(qwen.kieImageModelId).toBeUndefined();

    const gpt = buildErsStartContext("gpt-image-2");
    expect(gpt.hostedModelId).toBe(ERS_GPT_HOSTED_ID);
    expect(gpt.hosted_model_id).toBe("gpt-image-2-kie");
    expect(gpt.kieImageModelId).toBe(ERS_GPT_OFFICIAL_ID);
    expect(gpt.kie_image_model_id).toBe("gpt-image-2-text-to-image");
    expect(gpt.source).toBe("api");
    expect(gpt.modelFamilyPreference).toBeUndefined();
  });

  it("changing the dropdown only changes the selected context — it is not a generate POST", () => {
    const after = buildErsStartContext("gpt-image-2");
    expect(after.hostedModelId).toBe("gpt-image-2-kie");
    expect(after.kieImageModelId).toBe("gpt-image-2-text-to-image");
  });

  it("formats provenance from resolved official ids, not dropdown labels", () => {
    expect(formatErsProvenance({ model: "qwen2512", sourceKind: "Local" })).toBe(
      "Generating with Qwen Image · Local",
    );
    expect(formatErsProvenance({ model: "qwen2512.txt2img", sourceKind: "Local" })).toBe(
      "Generating with Qwen Image · Local",
    );
    expect(formatErsProvenance({ model: "gpt-image-2-text-to-image", sourceKind: "API" })).toBe(
      "Generating with GPT Image 2 · API",
    );
    expect(formatErsProvenance({ model: "gpt-image-2-kie", sourceKind: "API" })).toBe(
      "Generating with GPT Image 2 · API",
    );
    expect(formatErsProvenance({ model: "qwen2512", sourceKind: "Local" })).not.toContain(
      "Qwen Image — Local",
    );
  });

  it("reconnects selection from a live execution model", () => {
    expect(resolveErsGeneratorFromModel({ model: "qwen2512.txt2img" })).toBe("qwen2512");
    expect(resolveErsGeneratorFromModel({ model: "gpt-image-2-text-to-image" })).toBe("gpt-image-2");
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
    expect(generatorBlockReason("qwen2512", true, false)).toBeNull();
    expect(generatorBlockReason("gpt-image-2", false, true)).toBeNull();
  });
});
