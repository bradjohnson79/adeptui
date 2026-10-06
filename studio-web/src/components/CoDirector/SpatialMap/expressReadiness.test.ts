import { describe, expect, it } from "vitest";
import {
  API_NEEDS_GPT,
  API_NEEDS_SOURCE,
  DIRECT_USE_NEEDS_IMAGE,
  ENV_DESCRIPTION_HELP,
  GPT_REQUIRED_MESSAGE,
  expressGenerateReadiness,
  expressProgressMessage,
} from "./expressReadiness";

describe("Express Generate readiness contract", () => {
  it("requires GPT Image 2 and a description or reference", () => {
    expect(
      expressGenerateReadiness({
        gptConfigured: false,
        description: "a silver underground research corridor",
        referenceAssetId: "",
      }),
    ).toEqual({ ok: false, reason: API_NEEDS_GPT });
    expect(
      expressGenerateReadiness({
        gptConfigured: null,
        description: "a silver underground research corridor",
        referenceAssetId: "",
      }),
    ).toEqual({ ok: false, reason: API_NEEDS_GPT });
    expect(
      expressGenerateReadiness({
        gptConfigured: true,
        description: "",
        referenceAssetId: "",
      }),
    ).toEqual({ ok: false, reason: API_NEEDS_SOURCE });
    expect(
      expressGenerateReadiness({
        gptConfigured: true,
        description: "a silver underground research corridor",
        referenceAssetId: "",
      }),
    ).toEqual({ ok: true, reason: null });
    expect(
      expressGenerateReadiness({
        gptConfigured: true,
        description: "",
        referenceAssetId: "asset-1",
      }),
    ).toEqual({ ok: true, reason: null });
  });

  it("direct-use needs only a reference and does not require GPT", () => {
    expect(
      expressGenerateReadiness({
        gptConfigured: false,
        description: "",
        referenceAssetId: "",
        useAsAtlas: true,
      }),
    ).toEqual({ ok: false, reason: DIRECT_USE_NEEDS_IMAGE });
    expect(
      expressGenerateReadiness({
        gptConfigured: false,
        description: "",
        referenceAssetId: "asset-1",
        useAsAtlas: true,
      }),
    ).toEqual({ ok: true, reason: null });
  });

  it("does not offer a Local fallback when GPT is missing", () => {
    expect(API_NEEDS_GPT).toBe(GPT_REQUIRED_MESSAGE);
    expect(API_NEEDS_GPT.toLowerCase()).not.toMatch(/local|free reconstruction|fallback/);
    expect(ENV_DESCRIPTION_HELP.toLowerCase()).not.toMatch(/moge|vggt|packet|provider|conditioning|flux|qwen/);
  });

  it("maps API-only creator-facing progress stages", () => {
    expect(expressProgressMessage("queued", "Preparing")).toBe("Preparing Spatial Map");
    expect(expressProgressMessage("design", "layout")).toBe("Designing Environment");
    expect(expressProgressMessage("generating", "Generating Atlas")).toBe(
      "Generating Atlas with GPT Image 2",
    );
    expect(expressProgressMessage("gpt", "atlas")).toBe("Generating Atlas with GPT Image 2");
    expect(expressProgressMessage("validating", "gate")).toBe("Validating Atlas");
    expect(expressProgressMessage("saving", "persist")).toBe("Saving Spatial Map");
    expect(expressProgressMessage("completed", "done")).toBe("Complete");
  });
});
