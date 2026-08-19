import { describe, expect, it } from "vitest";
import { characterSheetBatchLabel, characterSheetProvenanceLabel } from "./types";

describe("characterSheetProvenanceLabel", () => {
  it("renders Illustrious Profile Guided from family id + mode", () => {
    expect(
      characterSheetProvenanceLabel({
        selectedSource: "illustrious",
        model: "illustrious",
        providerKind: "local",
        provider: "comfyui",
        conditioningMode: "PROFILE_GUIDED",
        workflowKey: "illustrious.txt2img",
      }),
    ).toBe("LOCAL — Illustrious XL — Profile Guided");
  });

  it("renders Qwen Image 2512 Reference Conditioned", () => {
    expect(
      characterSheetProvenanceLabel({
        selectedSource: "qwen2512",
        model: "qwen2512",
        providerKind: "local",
        provider: "comfyui",
        conditioningMode: "REFERENCE_CONDITIONED",
        workflowKey: "qwen2512.ref",
      }),
    ).toBe("LOCAL — Qwen Image 2512 — Reference Conditioned");
  });

  it("renders Z-Image Reference Conditioned", () => {
    expect(
      characterSheetProvenanceLabel({
        selectedSource: "zimage",
        model: "zimage",
        providerKind: "local",
        conditioningMode: "REFERENCE_CONDITIONED",
        workflowKey: "zimage.ref_edit",
      }),
    ).toBe("LOCAL — Z-Image Turbo — Reference Conditioned");
  });

  it("prefers persisted provenance when present", () => {
    expect(
      characterSheetProvenanceLabel({
        provenance: "LOCAL — Illustrious XL — Profile Guided",
        model: "illustrious",
      }),
    ).toBe("LOCAL — Illustrious XL — Profile Guided");
  });


  it("does not split workflowKey on . as family", () => {
    expect(
      characterSheetProvenanceLabel({
        providerKind: "local",
        provider: "comfyui",
        workflowKey: "illustrious.txt2img",
      }),
    ).toBe("LOCAL");
  });

  it("uses 1-based Batch N of M indexing", () => {
    expect(characterSheetBatchLabel({ batchIndex: 2, batchOf: 3 })).toBe("Batch 2 of 3");
    expect(characterSheetBatchLabel({ batchIndex: 0, batchOf: 2 })).toBe("Batch 0 of 2");
    expect(characterSheetBatchLabel({})).toBeNull();
  });
});
