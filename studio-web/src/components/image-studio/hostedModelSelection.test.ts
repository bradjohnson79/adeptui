import { describe, expect, it } from "vitest";
import type { ImageProviderDescriptor } from "../../contracts/cinematicImageStudio";
import {
  HOSTED_AUTO_ID,
  hostedCostLabel,
  hostedExecutionFields,
  hostedIncompatibility,
  hostedModelOptions,
  hostedSelectionBlockReason,
  resolveHostedProvider,
  usingModelLabel,
} from "./hostedModelSelection";

function provider(partial: Partial<ImageProviderDescriptor> & Pick<ImageProviderDescriptor, "id" | "displayName">): ImageProviderDescriptor {
  return {
    family: partial.family || partial.id,
    source: partial.source || "local",
    readiness: partial.readiness || "ready",
    imageCapable: partial.imageCapable !== false,
    requiresPaidConfirmation: partial.requiresPaidConfirmation || false,
    nativeResolutions: partial.nativeResolutions || ["1K"],
    upscaleSupported: partial.upscaleSupported || false,
    ...partial,
  };
}

const qwen = provider({
  id: "qwen2512",
  displayName: "Qwen Image 2512",
  family: "qwen2512",
  source: "local",
  costHint: "Local GPU",
});

const gpt = provider({
  id: "gpt-image-2-kie",
  displayName: "GPT Image 2",
  family: "gptimage2",
  source: "hosted",
  providerPreference: "kie",
  modelId: "gpt-image-2-kie",
  requiresPaidConfirmation: true,
  costHint: "Paid hosted API",
});

const flux = provider({
  id: "flux-fal",
  displayName: "FLUX",
  family: "flux",
  source: "hosted",
  providerPreference: "fal",
  modelId: "flux-fal",
  requiresPaidConfirmation: true,
  readiness: "needs_auth",
  costHint: "$0.04 / image",
});

const noRefs = provider({
  id: "single-kie",
  displayName: "Single Shot",
  family: "single",
  source: "hosted",
  providerPreference: "kie",
  modelId: "single-kie",
  requiresPaidConfirmation: true,
  metadata: { capabilities: { supportsReferences: false } },
});

describe("hosted image generator selection", () => {
  const catalog = [qwen, gpt, flux, noRefs];

  it("hides hosted models from the local execution owner", () => {
    expect(usingModelLabel(qwen, { hosted: false, auto: false })).toBe("Qwen Image 2512 (Local)");
    expect(hostedCostLabel(false, qwen)).toBe("Local GPU");
    expect(hostedModelOptions(catalog, 0).some((option) => option.id === "qwen2512")).toBe(false);
  });

  it("lists registered hosted models and Auto when one is selectable", () => {
    const options = hostedModelOptions(catalog, 0);
    expect(options.map((option) => option.id)).toEqual([
      HOSTED_AUTO_ID,
      "gpt-image-2-kie",
      "flux-fal",
      "single-kie",
    ]);
    expect(options.find((option) => option.id === "flux-fal")?.disabled).toBe(true);
    expect(options.find((option) => option.id === "flux-fal")?.reason).toBe("Provider not configured");
  });

  it("propagates the selected hosted model into the execution fields", () => {
    const selected = resolveHostedProvider(catalog, "gpt-image-2-kie", 0);
    expect(selected?.id).toBe("gpt-image-2-kie");
    expect(hostedExecutionFields(selected!)).toMatchObject({
      hostedModelId: "gpt-image-2-kie",
      requested_provider: "kie",
      provider: "kie",
      source: "api",
      kieImageModelId: "gpt-image-2-kie",
    });
    expect(hostedExecutionFields(selected!).source).not.toBe("local");
  });

  it("does not treat an unconfigured hosted model as a local fallback", () => {
    const selected = resolveHostedProvider(catalog, "flux-fal", 0);
    expect(selected?.source).toBe("hosted");
    expect(hostedSelectionBlockReason(selected, 0)).toBe("Provider not configured");
  });

  it("marks hosted models the registry says cannot take references", () => {
    expect(hostedIncompatibility(noRefs, 2)).toBe("Does not support reference images");
    const options = hostedModelOptions(catalog, 2);
    expect(options.find((option) => option.id === "single-kie")?.disabled).toBe(true);
    expect(resolveHostedProvider(catalog, HOSTED_AUTO_ID, 2)?.id).toBe("gpt-image-2-kie");
  });

  it("names the selected hosted model and does not report Local GPU", () => {
    expect(usingModelLabel(gpt, { hosted: true, auto: false })).toBe("GPT Image 2 (kie)");
    expect(usingModelLabel(gpt, { hosted: true, auto: true })).toBe("Auto / Best Match");
    expect(hostedCostLabel(true, gpt)).toBe("Hosted API pricing applies");
    expect(hostedCostLabel(true, flux)).toBe("$0.04 / image");
  });
});
