import { describe, expect, it, vi } from "vitest";

// The panel is a DOM component; this repo ships no jsdom/RTL. These node-env
// tests cover the pure reuse-or-create decision the panel uses so the atlas
// flow never orphans placements (CDX-021).
vi.mock("../../../api", () => ({ api: {} }));

import { atlasReuseDecision, isAtlasGenerateExecution } from "./SpatialMapPanel";
import type { SpatialMapDocument } from "./types";

function doc(id: string, backgroundAssetId: string | null): SpatialMapDocument {
  return {
    id,
    projectId: "p1",
    title: "Map",
    backgroundAssetId,
  } as unknown as SpatialMapDocument;
}

describe("CDX-021 atlas reuse decision", () => {
  it("reuses the existing map document when one exists (post-Remove empty state)", () => {
    // After Remove Atlas the document still exists with backgroundAssetId null.
    expect(atlasReuseDecision(doc("m1", null))).toBe("reuse");
    expect(atlasReuseDecision(doc("m1", "atlas-1"))).toBe("reuse");
  });

  it("creates a brand-new document only when no map exists yet", () => {
    expect(atlasReuseDecision(null)).toBe("create");
  });
});

describe("CDX-029 atlas adoption capability guard", () => {
  it("accepts an atlas.generate execution by capability", () => {
    expect(isAtlasGenerateExecution({ capability: "atlas.generate", surface_type: "" })).toBe(true);
  });

  it("accepts an atlas_shot_generation surface by surface type", () => {
    expect(isAtlasGenerateExecution({ capability: "", surface_type: "atlas_shot_generation" })).toBe(true);
  });

  it("rejects foreign executions so their assets can never become the map background", () => {
    expect(isAtlasGenerateExecution({ capability: "image.generate", surface_type: "image_generation" })).toBe(false);
    expect(isAtlasGenerateExecution({ capability: "ers.generate", surface_type: "ers_generation" })).toBe(false);
    expect(isAtlasGenerateExecution({ capability: "chat.reply", surface_type: "" })).toBe(false);
  });

  it("rejects null/undefined executions", () => {
    expect(isAtlasGenerateExecution(null)).toBe(false);
    expect(isAtlasGenerateExecution(undefined)).toBe(false);
  });
});
