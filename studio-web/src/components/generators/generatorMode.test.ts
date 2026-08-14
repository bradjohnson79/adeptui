import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import {
  generationModeWireValue,
  identityDisabledReason,
  isIdentityEligible,
  resolveCharacterGenerationMode,
  type GeneratorOption,
} from "./types";

function opt(partial: Partial<GeneratorOption> & Pick<GeneratorOption, "id" | "label">): GeneratorOption {
  return { executable: true, ...partial };
}

describe("resolveCharacterGenerationMode", () => {
  const illustrious = opt({
    id: "illustrious",
    label: "Illustrious XL 1.0 (Anime)",
    supportsReferences: false,
  });
  const qwen = opt({
    id: "qwen2512",
    label: "Qwen Image 2512",
    supportsReferences: false,
  });
  const zimage = opt({
    id: "zimage",
    label: "Z-Image Turbo",
    supportsReferences: true,
  });
  const down = opt({
    id: "illustrious",
    label: "Illustrious XL 1.0 (Anime)",
    executable: false,
    supportsReferences: false,
  });

  it("keeps Illustrious and Qwen Profile Guided when a reference is attached", () => {
    expect(resolveCharacterGenerationMode(illustrious, true)).toBe("PROFILE_GUIDED");
    expect(resolveCharacterGenerationMode(qwen, true)).toBe("PROFILE_GUIDED");
    expect(isIdentityEligible(illustrious)).toBe(true);
    expect(isIdentityEligible(qwen)).toBe(true);
    expect(identityDisabledReason(illustrious)).toBeNull();
    expect(generationModeWireValue("PROFILE_GUIDED")).toBe("profile_guided");
  });

  it("keeps Z-Image Reference Conditioned when a reference is attached", () => {
    expect(resolveCharacterGenerationMode(zimage, true)).toBe("REFERENCE_CONDITIONED");
    expect(generationModeWireValue("REFERENCE_CONDITIONED")).toBe("reference_conditioned");
  });

  it("uses Profile Guided with no reference for txt2img families", () => {
    expect(resolveCharacterGenerationMode(illustrious, false)).toBe("PROFILE_GUIDED");
    expect(resolveCharacterGenerationMode(zimage, false)).toBe("PROFILE_GUIDED");
  });

  it("blocks only UNSUPPORTED (not-ready) generators", () => {
    expect(resolveCharacterGenerationMode(down, true)).toBe("UNSUPPORTED");
    expect(resolveCharacterGenerationMode(null, true)).toBe("UNSUPPORTED");
    expect(generationModeWireValue("UNSUPPORTED")).toBeNull();
  });

  it("does not contain the legacy Illustrious blocking helper", () => {
    const src = readFileSync(new URL("./GeneratorSourceSelector.tsx", import.meta.url), "utf8");
    expect(src).not.toContain("illustrious requires text-to-image generation and cannot use the attached Character Reference.");
    expect(src).toContain("The attached Character Reference is not used by this generator.");
    expect(src).toContain("Uses the attached Character Reference as the primary visual guide.");
    expect(src).toContain("referenceLocked: false");
  });
});
