import { describe, expect, it } from "vitest";
import { characterSheetProvenanceLabel } from "./types";

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
});
