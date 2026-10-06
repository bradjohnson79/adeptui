import { describe, expect, it } from "vitest";

import {
  environmentApiProvidersFromDiscovered,
  resolveEnvironmentApiSelection,
} from "./environmentCreatorProviders";

function row(providerId: string, id: string, label: string, extra: Record<string, unknown> = {}) {
  return {
    providerId,
    id,
    providerModelId: extra.providerModelId || id,
    label,
    modality: "image",
    capabilities: ["text_to_image"],
    executable: extra.executable !== false,
    accountAccessible: extra.accountAccessible !== false,
    selectable: true,
  };
}

function availability(providers: ReturnType<typeof environmentApiProvidersFromDiscovered>) {
  return Object.fromEntries(providers.map((provider) => [provider.id, provider.available]));
}

describe("Environment Creator API providers", () => {
  it("always lists fal.ai, kie.ai, and wavespeed.ai, with only fal.ai active", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("fal", "flux-fal", "FLUX — fal.ai", { providerModelId: "fal-ai/flux/dev" }),
      row("kie", "flux-kie", "FLUX — Kie.ai", { accountAccessible: false }),
    ]);
    expect(providers.map((provider) => provider.label)).toEqual(["kie.ai", "wavespeed.ai", "fal.ai"]);
    expect(availability(providers)).toEqual({ kie: false, wavespeed: false, fal: true });
  });

  it("keeps all three listed when only kie.ai is configured", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("kie", "gpt-image-2-kie", "GPT Image 2 — Kie.ai"),
    ]);
    expect(providers.map((provider) => provider.label)).toEqual(["kie.ai", "wavespeed.ai", "fal.ai"]);
    expect(availability(providers)).toEqual({ kie: true, wavespeed: false, fal: false });
    expect(providers[0].models.map((model) => model.label)).toEqual(["GPT Image 2"]);
  });

  it("keeps all three listed when only wavespeed.ai is configured", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("wavespeed", "flux-wavespeed", "FLUX — WaveSpeed.ai", { providerModelId: "wavespeed-ai/flux-dev" }),
    ]);
    expect(availability(providers)).toEqual({ kie: false, wavespeed: true, fal: false });
  });

  it("activates fal.ai and kie.ai and leaves wavespeed.ai inactive", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("fal", "flux-fal", "FLUX — fal.ai"),
      row("kie", "gpt-image-2-kie", "GPT Image 2 — Kie.ai"),
    ]);
    expect(availability(providers)).toEqual({ kie: true, wavespeed: false, fal: true });
  });

  it("activates all three in catalog order", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("fal", "flux-fal", "FLUX — fal.ai"),
      row("wavespeed", "flux-wavespeed", "FLUX — WaveSpeed.ai"),
      row("kie", "seedream-kie", "Seedream — Kie.ai"),
    ]);
    expect(providers.map((provider) => provider.label)).toEqual(["kie.ai", "wavespeed.ai", "fal.ai"]);
    expect(providers.every((provider) => provider.available)).toBe(true);
  });

  it("grays out an unconfigured provider and drops GPT Image 2.5", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("kie", "gpt-image-2-kie", "GPT Image 2 — Kie.ai"),
      row("kie", "gpt-image-2.5-kie", "GPT Image 2.5 — API", { executable: false }),
      row("wavespeed", "flux-wavespeed", "FLUX — WaveSpeed.ai", { accountAccessible: false }),
      row("elevenlabs", "voice", "Voice"),
    ]);
    expect(providers.map((provider) => provider.id)).toEqual(["kie", "wavespeed", "fal"]);
    expect(availability(providers)).toEqual({ kie: true, wavespeed: false, fal: false });
    expect(providers[0].models.map((model) => model.label).join(" ")).not.toMatch(/2\.5/);
  });

  it("changes the model list with the provider and clears a stale model", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("kie", "gpt-image-2-kie", "GPT Image 2 — Kie.ai"),
      row("fal", "flux-fal", "FLUX — fal.ai"),
      row("fal", "krea2-turbo-fal", "Krea 2 Turbo — fal.ai"),
    ]);
    const kie = resolveEnvironmentApiSelection(providers, "kie", "gpt-image-2-kie");
    expect(kie.modelLabel).toBe("GPT Image 2");
    const fal = resolveEnvironmentApiSelection(providers, "fal", "gpt-image-2-kie");
    expect(fal.providerId).toBe("fal");
    expect(fal.modelId).toBe("flux-fal");
    expect(providers.find((provider) => provider.id === "fal")?.models.map((model) => model.label)).toEqual([
      "FLUX",
      "Krea 2 Turbo",
    ]);
    expect(providers.find((provider) => provider.id === "wavespeed")?.available).toBe(false);
  });

  it("uses the first configured provider when nothing valid is saved", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("wavespeed", "flux-wavespeed", "FLUX — WaveSpeed.ai"),
      row("fal", "flux-fal", "FLUX — fal.ai"),
    ]);
    const picked = resolveEnvironmentApiSelection(providers, "", "");
    expect(picked.providerId).toBe("wavespeed");
    expect(picked.unavailable).toBe(false);
  });

  it("does not keep a saved provider that is grayed out", () => {
    const providers = environmentApiProvidersFromDiscovered([
      row("fal", "flux-fal", "FLUX — fal.ai"),
    ]);
    const picked = resolveEnvironmentApiSelection(providers, "wavespeed", "flux-wavespeed");
    expect(picked.unavailable).toBe(true);
    expect(picked.providerId).toBe("fal");
    expect(providers.find((provider) => provider.id === "wavespeed")?.available).toBe(false);
  });
});
