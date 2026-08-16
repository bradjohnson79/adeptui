import { describe, expect, it } from "vitest";
import {
  ERS_GPT_OFFICIAL_ID,
  ERS_QWEN_WORKFLOW_KEY,
  generatorBlockReason,
  isGptImage2I2IReady,
  isQwenI2IReady,
  isQwenT2IReady,
  type ErsProviderRow,
} from "./ersGenerator";

const qwenT2I: ErsProviderRow = {
  id: "qwen-image-2512-local",
  family: "qwen2512",
  readiness: "ready",
  source: "local",
  metadata: { supports: ["text_to_image"] },
};
const qwenI2I: ErsProviderRow = {
  id: "qwen-image-2512-local",
  family: "qwen2512",
  readiness: "ready",
  source: "local",
  metadata: { supports: ["text_to_image", "reference_conditioning"] },
};
const gptT2I: ErsProviderRow = {
  id: "gpt-image-2-kie",
  readiness: "ready",
  source: "api",
  metadata: { supports: ["text_to_image"] },
};
const gptI2I: ErsProviderRow = {
  id: "gpt-image-2-kie",
  readiness: "ready",
  source: "api",
  metadata: { supports: ["text_to_image", "edit"] },
};

describe("Phase 2 — ERS Qwen I2I eligibility truth", () => {
  it("distinguishes Qwen T2I readiness from I2I readiness", () => {
    expect(isQwenT2IReady([qwenT2I])).toBe(true);
    expect(isQwenI2IReady([qwenT2I])).toBe(false); // T2I-only is NOT ERS-eligible
    expect(isQwenI2IReady([qwenI2I])).toBe(true);
    expect(isQwenI2IReady([gptT2I])).toBe(false);
  });

  it("uses the image-to-image workflow key for ERS", () => {
    expect(ERS_QWEN_WORKFLOW_KEY).toBe("qwen2512.ref");
  });

  it("blocks Qwen for ERS when I2I is unavailable even if T2I is ready", () => {
    const reason = generatorBlockReason("qwen2512", true, true, false);
    expect(reason).toBeTruthy();
    expect(reason).toContain("image-to-image");
    expect(generatorBlockReason("qwen2512", true, true, true)).toBeNull();
  });

  it("keeps GPT Image 2 eligibility independent and requires I2I", () => {
    expect(generatorBlockReason("gpt-image-2", true, false, false)).toBeTruthy();
    expect(generatorBlockReason("gpt-image-2", true, true, false, true)).toBeNull();
    expect(isGptImage2I2IReady([gptT2I])).toBe(false);
    expect(isGptImage2I2IReady([gptI2I])).toBe(true);
    expect(generatorBlockReason("gpt-image-2", true, true, true, false)).toBeTruthy();
    expect(ERS_GPT_OFFICIAL_ID).toBe("gpt-image-2-image-to-image");
    expect(ERS_GPT_OFFICIAL_ID).not.toContain("text-to-image");
  });
});
