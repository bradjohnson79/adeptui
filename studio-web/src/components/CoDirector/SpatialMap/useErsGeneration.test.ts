import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The hook needs a DOM render harness, which this repo does not ship
// (no jsdom/RTL). These node-env tests cover the failure-honesty contract of
// the "Use Anyway" override that the hook's catch path actually uses.
vi.mock("../../../api", () => ({ api: {} }));

import {
  ERS_MAP_SCOPED_STATE_KEYS,
  buildErsGenerateStartPayload,
  countsForErsSurface,
  emptyErsMapScopedState,
  ersGeneratorStorageKey,
  readStoredGenerator,
  useAnywayFailure,
  writeStoredGenerator,
} from "./useErsGeneration";

describe("FE-010 Use Anyway failure honesty", () => {
  it("maps an Error rejection to a creator-facing message plus raw detail", () => {
    const failure = useAnywayFailure(new Error("override rejected"));
    expect(failure.error).toBe("Use Anyway failed � override rejected");
    expect(failure.errorDetail).toBe("override rejected");
  });

  it("maps a non-Error rejection (string) without crashing", () => {
    const failure = useAnywayFailure("network reset");
    expect(failure.error).toContain("Use Anyway failed");
    expect(failure.errorDetail).toBe("network reset");
  });

  it("peels backend error prefixes through the shared ERS strip logic", () => {
    const failure = useAnywayFailure(new Error("HANDLER_ERROR: boom"));
    expect(failure.error).toBe("Use Anyway failed � boom");
    expect(failure.errorDetail).toBe("HANDLER_ERROR: boom");
  });
});

describe("CDX-022 ERS state scoped to the active Spatial Map", () => {
  it("declares composite, sheet, and phase as map-scoped keys", () => {
    expect(ERS_MAP_SCOPED_STATE_KEYS).toEqual(
      expect.arrayContaining(["compositeAssetId", "sheetId", "phase"]),
    );
  });

  it("clears every map-scoped key to its idle default so the previous map's ERS never shows as current", () => {
    const reset = emptyErsMapScopedState();
    expect(reset.phase).toBe("idle");
    expect(reset.busy).toBe(false);
    expect(reset.compositeAssetId).toBeNull();
    expect(reset.sheetId).toBeNull();
    expect(reset.executionId).toBeNull();
    expect(reset.jobId).toBeNull();
    expect(reset.error).toBeNull();
    expect(reset.errorDetail).toBeNull();
    expect(reset.zombie).toBe(false);
    expect(reset.elapsedSec).toBe(0);
    expect(reset.semanticGate).toBeNull();
    expect(reset.gateOverride).toBe(false);
    expect(reset.model).toEqual({ model: "", sourceKind: null });
    expect(reset.progress).toMatchObject({ status: "idle", finalAssetId: null });
  });

  it("keeps every key in the returned state covered by the reset slice", () => {
    const reset = emptyErsMapScopedState();
    for (const key of ERS_MAP_SCOPED_STATE_KEYS) {
      expect(reset).toHaveProperty(key);
    }
    // Generator choice is deliberately NOT map-scoped (survives remounts
    // within the same project via per-project storage, CDX-072).
    expect(ERS_MAP_SCOPED_STATE_KEYS).not.toContain("selectedGenerator");
  });
});

describe("CDX-072 per-project generator persistence", () => {
  const store = new Map<string, string>();
  const originalWindow = (globalThis as { window?: unknown }).window;

  function installFakeWindow() {
    (globalThis as { window?: unknown }).window = {
      localStorage: {
        getItem: (k: string) => store.get(k) ?? null,
        setItem: (k: string, v: string) => void store.set(k, v),
        removeItem: (k: string) => void store.delete(k),
      },
    } as unknown as Window & typeof globalThis;
  }

  function removeWindow() {
    if (originalWindow === undefined) {
      delete (globalThis as { window?: unknown }).window;
    } else {
      (globalThis as { window?: unknown }).window = originalWindow;
    }
  }

  beforeEach(() => {
    store.clear();
    installFakeWindow();
  });

  afterEach(() => {
    removeWindow();
  });

  it("falls back to the default when nothing is stored for the project", () => {
    expect(readStoredGenerator("proj-a")).toBe("gpt-image-2");
  });

  it("round-trips a choice per project and never leaks across projects", () => {
    writeStoredGenerator("proj-a", "gpt-image-2");
    expect(readStoredGenerator("proj-a")).toBe("gpt-image-2");
    // Project B must NOT inherit project A's generator (CDX-072).
    expect(readStoredGenerator("proj-b")).toBe("gpt-image-2");
    expect(ersGeneratorStorageKey("proj-a")).toBe("adept.spatial-map.ers-generator.proj-a");
  });

  it("ignores corrupted stored values and falls back", () => {
    store.set("adept.spatial-map.ers-generator.proj-c", "flux-xyz");
    expect(readStoredGenerator("proj-c")).toBe("gpt-image-2");
  });

  it("remaps a stored Qwen ERS choice to GPT Image 2", () => {
    writeStoredGenerator("proj-qwen", "qwen2512");
    expect(readStoredGenerator("proj-qwen")).toBe("gpt-image-2");
  });

  it("returns the default when storage is unavailable (no window)", () => {
    removeWindow();
    expect(readStoredGenerator("proj-d")).toBe("gpt-image-2");
    // Writing without storage must not throw.
    expect(() => writeStoredGenerator("proj-d", "gpt-image-2")).not.toThrow();
  });
});

describe("Env Creator ERS � spatialMapId optional on start", () => {
  it("posts ers.generate without spatial_map_id when spatialMapId is null", () => {
    const payload = buildErsGenerateStartPayload(null);
    expect(payload.capability).toBe("ers.generate");
    expect(payload.context).not.toHaveProperty("spatial_map_id");
    expect(payload.context.forceFull).toBe(true);
    expect(payload.context.ers_pipeline).toBe("full_sheet");
    expect(payload.context.generationMode).toBe("full_sheet_api");
    expect(payload.context.templateId).toBe("ers.original.v1");
  });

  it("posts ers.generate without spatial_map_id when spatialMapId is undefined/empty", () => {
    expect(buildErsGenerateStartPayload(undefined).context).not.toHaveProperty("spatial_map_id");
    expect(buildErsGenerateStartPayload("").context).not.toHaveProperty("spatial_map_id");
  });

  it("includes spatial_map_id only when a real map id is provided", () => {
    const payload = buildErsGenerateStartPayload("map-abc");
    expect(payload.context.spatial_map_id).toBe("map-abc");
    expect(payload.context.forceFull).toBe(true);
    expect(payload.context.generationMode).toBe("full_sheet_api");
  });

  it("merges source_asset_id and reference_image when a source image is provided", () => {
    const payload = buildErsGenerateStartPayload(null, "env-1");
    expect(payload.context).not.toHaveProperty("spatial_map_id");
    expect(payload.context.source_asset_id).toBe("env-1");
    expect(payload.context.reference_image).toBe("env-1");
    expect(payload.context.forceFull).toBe(true);
  });

  it("omits source fields when no source image is provided", () => {
    const payload = buildErsGenerateStartPayload(null, null);
    expect(payload.context).not.toHaveProperty("source_asset_id");
    expect(payload.context).not.toHaveProperty("reference_image");
  });
});

describe("Env Creator Express � prompt-only vs source planning payload", () => {
  it("null map + prompt-only includes environmentPrompt and omits source_asset_id", () => {
    const payload = buildErsGenerateStartPayload(null, null, {
      environmentPrompt: "foggy neon alley at night",
      aspectRatio: "16:9",
      storyTheme: "neo-noir",
    });
    expect(payload.capability).toBe("ers.generate");
    expect(payload.context.environmentPrompt).toBe("foggy neon alley at night");
    expect(payload.context.prompt).toBe("foggy neon alley at night");
    expect(payload.context.aspectRatio).toBe("16:9");
    expect(payload.context.storyTheme).toBe("neo-noir");
    expect(payload.context).not.toHaveProperty("source_asset_id");
    expect(payload.context).not.toHaveProperty("reference_image");
    expect(payload.context.kieImageModelId).toBe("gpt-image-2-text-to-image");
  });

  it("with source includes source_asset_id; prompt optional", () => {
    const withPrompt = buildErsGenerateStartPayload(null, "env-9", {
      environmentPrompt: "keep the same courtyard",
    });
    expect(withPrompt.context.source_asset_id).toBe("env-9");
    expect(withPrompt.context.reference_image).toBe("env-9");
    expect(withPrompt.context.environmentPrompt).toBe("keep the same courtyard");
    expect(withPrompt.context.kieImageModelId).toBe("gpt-image-2-image-to-image");

    const sourceOnly = buildErsGenerateStartPayload(null, "env-9");
    expect(sourceOnly.context.source_asset_id).toBe("env-9");
    expect(sourceOnly.context).not.toHaveProperty("environmentPrompt");
    expect(sourceOnly.context.kieImageModelId).toBe("gpt-image-2-image-to-image");
  });
});

describe("Environment Creator plan counts", () => {
  it("counts the plan when no Spatial Map document is attached", () => {
    expect(
      countsForErsSurface(null, {
        environmentPrompt: "coffee house",
        characters: [{ characterId: "a" }, { characterId: "b" }],
        props: [{ propId: "p" }],
      }),
    ).toEqual({ environment: 1, characters: 2, props: 1, cameras: 0 });
  });

  it("keeps Spatial Map document counts when a document is present", () => {
    expect(
      countsForErsSurface(
        {
          backgroundAssetId: "atlas",
          characters: [{}],
          props: [],
          cameras: [{}, {}],
        } as never,
        { environmentPrompt: "ignored", characters: [{}, {}, {}], props: [{}, {}] },
      ),
    ).toEqual({ environment: 1, characters: 1, props: 0, cameras: 2 });
  });
});
