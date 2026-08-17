import { describe, expect, it } from "vitest";
import { toApiGeneratorOption, toLocalGeneratorOption } from "./types";

describe("toLocalGeneratorOption (CDX-081 fail closed)", () => {
  it("missing executable/status fields fail closed - never available, never Certified", () => {
    const opt = toLocalGeneratorOption({ id: "qwen2512", label: "Qwen Image 2512" });
    expect(opt.executable).toBe(false);
    expect(opt.status).toBe("Unknown");
  });

  it("backend executable:true with status makes the option executable", () => {
    const opt = toLocalGeneratorOption({
      id: "zimage",
      label: "Z-Image Turbo",
      status: "Certified",
      executable: true,
    });
    expect(opt.executable).toBe(true);
    expect(opt.status).toBe("Certified");
  });

  it("propagates capability flags", () => {
    const opt = toLocalGeneratorOption({
      id: "flux",
      label: "FLUX",
      supportsEditing: true,
      supportsReferences: true,
    });
    expect(opt.supportsEditing).toBe(true);
    expect(opt.supportsReferences).toBe(true);
  });
});

describe("toApiGeneratorOption (CDX-081)", () => {
  it("missing executable is disabled - never defaulted to available", () => {
    const opt = toApiGeneratorOption({ id: "flux-fal", label: "FLUX", providerId: "fal" }, null);
    expect(opt.executable).toBe(false);
    expect(opt.availability).toBe("Balance unavailable");
  });

  it("backend executable:true is available - availability only when asserted", () => {
    const opt = toApiGeneratorOption(
      { id: "flux-fal", label: "FLUX", providerId: "fal", executable: true },
      null,
    );
    expect(opt.executable).toBe(true);
    expect(opt.availability).toBe("Connected");
  });

  it("credits only when a fal balance is exposed", () => {
    const fal = toApiGeneratorOption({ id: "flux-fal", providerId: "fal", executable: true }, 42);
    expect(fal.credits).toBe(42);
    expect(fal.availability).toBeUndefined();
    const nonFal = toApiGeneratorOption(
      { id: "nano-banana-kie", providerId: "kie", executable: true },
      42,
    );
    expect(nonFal.credits).toBeNull();
  });

  it("reads providerId (discovery rows) and falls back to legacy provider field", () => {
    const viaProviderId = toApiGeneratorOption({ id: "x", providerId: "fal", executable: true }, 7);
    expect(viaProviderId.credits).toBe(7);
    const viaProvider = toApiGeneratorOption({ id: "y", provider: "FAL", executable: true }, 9);
    expect(viaProvider.credits).toBe(9);
  });
});

