import { describe, expect, it, vi } from "vitest";

// The panel is a DOM component; this repo ships no jsdom/RTL. These node-env
// tests cover the pure reuse-or-create decision the panel uses so the atlas
// flow never orphans placements (CDX-021).
vi.mock("../../../api", () => ({ api: {} }));

import { readFileSync } from "node:fs";
import { atlasReuseDecision, isAtlasAssignExecution, isAtlasGenerateExecution } from "./SpatialMapPanel";
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

  it("rejects atlas.assign so a direct import is never treated as generation", () => {
    expect(isAtlasGenerateExecution({ capability: "atlas.assign", surface_type: "atlas_assign" })).toBe(false);
    expect(isAtlasAssignExecution({ capability: "atlas.assign", surface_type: "atlas_assign" })).toBe(true);
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

describe("Spatial Map empty-state cutover lock", () => {
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");

  it("mounts Express form and Standard chooser instead of the retired Atlas Shot intake", () => {
    expect(panel).toContain("SpatialMapExpressForm");
    expect(panel).toContain("SpatialMapStartChooser");
    expect(panel).toContain('generationMethod: "api"');
    expect(panel).toContain("gpt-image-2-kie");
    expect(panel).not.toContain("Create Atlas Shot with Co-Director");
    expect(panel).not.toContain("Start with an environment reference.");
  });
});

describe("ERS generator contract", () => {
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");

  it("pins GPT Image 2 as a fixed ERS provider, not a Qwen dropdown", () => {
    expect(panel).toContain("data-testid=\"ers-generator-fixed\"");
    expect(panel).toContain("GPT Image 2 — API");
    expect(panel).toContain("GPT Image 2 — Requires Setup");
    expect(panel).not.toContain("data-testid=\"ers-generator-select\"");
    expect(panel).not.toContain("ERS_GENERATOR_OPTIONS");
  });
});

describe("Spatial Map movement autosave toast lock", () => {
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");

  it("shows a visible auto-save notification after a successful place/move persist", () => {
    expect(panel).toContain('data-testid="spatial-map-autosave-toast"');
    expect(panel).toContain("Spatial Map auto-saved");
    expect(panel).toContain("showAutosaveToast(placementMode.kind)");
    expect(panel).toContain("movementSegmentId: liveDoc.activeMovementSegmentId");
  });
});

describe("CDX-021 applyAtlasToMap server reuse lock (overlay law)", () => {
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");

  it("consults getMostRecentMap before createMap so null React state cannot orphan overlays", () => {
    expect(panel).toContain("spatialMapApi.getMostRecentMap(projectId)");
    expect(panel).toContain("Never createMap when a map already exists");
    const reuseIdx = panel.indexOf("getMostRecentMap(projectId)");
    const createIdx = panel.indexOf("spatialMapApi.createMap(projectId");
    // First getMostRecentMap inside applyAtlasToMap must precede createMap.
    expect(reuseIdx).toBeGreaterThan(-1);
    expect(createIdx).toBeGreaterThan(reuseIdx);
  });

  it("still creates only when no in-memory and no server map exist", () => {
    expect(panel).toContain('atlasReuseDecision(document) === "reuse"');
    expect(panel).toContain("targetId");
  });
});
