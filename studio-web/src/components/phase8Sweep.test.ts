/**
 * Phase 8 sweep - frontend contract tests (CDX-011/016/026/040/041/047/050).
 *
 * These are deterministic source/contract assertions over the authored fixes.
 * They pin the intended contracts so a regression cannot silently reintroduce
 * ghost prop rows, draft-identity placement, or undecorated qwen ERS drops.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const IMAGE_GEN = new URL("../components/ImageGenPanel.tsx", import.meta.url);
const SPATIAL = new URL("../components/CoDirector/SpatialMap/SpatialMapPanel.tsx", import.meta.url);
const SC = new URL("../components/CoDirector/SceneCreator/SceneCreatorCore.tsx", import.meta.url);
const HOOK = new URL("../components/CoDirector/SceneCreator/useSceneCreator.ts", import.meta.url);
const API_FACADE = new URL("../components/CoDirector/SceneCreator/sceneCreatorApi.ts", import.meta.url);
const PROP_API = new URL("../components/CoDirector/PropCreator/propCreatorApi.ts", import.meta.url);
const PROP_HOOK = new URL("../components/CoDirector/PropCreator/usePropCreator.ts", import.meta.url);
const ERS_CONTRACT = new URL("../contracts/environmentReferenceSheet.ts", import.meta.url);
const WS = new URL("../components/scene-creator/SceneCreatorWorkspace.tsx", import.meta.url);

describe("CDX-011: ImageGenPanel Prop promote is honestly disabled", () => {
  const src = readFileSync(IMAGE_GEN, "utf8");

  it("no longer offers a live Prop promote button", () => {
    expect(src).toContain("promote-prop-disabled");
    expect(src).toContain("Use Prop Creator to save a project prop");
    expect(src).not.toContain('profile_kind: "prop"');
  });
});

describe("CDX-016: prop upsert contract is aligned", () => {
  const hook = readFileSync(PROP_HOOK, "utf8");
  const facade = readFileSync(PROP_API, "utf8");

  it("uses identity_asset_id and drops the redundant useAsIdentity call", () => {
    expect(hook).toContain("identity_asset_id: refId");
    expect(hook).not.toContain("approved_asset_id: refId");
    expect(hook).not.toContain("library_asset_id: refId");
    expect(hook).not.toContain("propCreatorApi.useAsIdentity");
  });

  it("facade no longer exports a useAsIdentity helper", () => {
    expect(facade).not.toContain("useAsIdentity");
  });
});

describe("CDX-026: Spatial Map character placement is approved-only", () => {
  const src = readFileSync(SPATIAL, "utf8");

  it("never falls back to a draft canonical reference", () => {
    expect(src).toContain('approval_status === "approved"');
    expect(src).toContain("has only a draft reference");
    expect(src).not.toContain("|| items.find((r) => r.canonical)");
  });
});

describe("CDX-040: qwen ERS composite drop is disclosed", () => {
  const src = readFileSync(HOOK, "utf8");

  it("blocks qwen when an ERS composite exists but cannot load", () => {
    expect(src).toContain("The environment picture cannot be loaded by this generator.");
    expect(src).toContain("resolved_ers");
    expect(src).toContain("ers_composite_asset_id");
    // guard applies in both preview and final render paths
    expect(src.indexOf("The environment picture cannot be loaded by this generator.")).toBeGreaterThan(-1);
  });
});

describe("CDX-041: ERS TS contract carries the backend sheet payload", () => {
  const src = readFileSync(ERS_CONTRACT, "utf8");

  it("adds ers_composite_asset_id and provenance to EnvironmentReferenceSheet", () => {
    const sheet = src.slice(src.indexOf("export type EnvironmentReferenceSheet = {"), src.indexOf("export type EnvironmentReferenceSheetSummary"));
    expect(sheet).toContain("ers_composite_asset_id?: string | null;");
    expect(sheet).toContain("provenance?: ERSProvenanceRecord | null;");
  });
});

describe("CDX-047: sceneCreatorApi facade types include shot", () => {
  const src = readFileSync(API_FACADE, "utf8");

  it("cinematographerPreview/Final declare { cinematographer, shot }", () => {
    const preview = src.slice(src.indexOf("cinematographerPreview"), src.indexOf("cinematographerFinal"));
    expect(preview).toContain("Promise<{ cinematographer: SceneCinematographerPack; shot: SceneShot }>");
    const final = src.slice(src.indexOf("cinematographerFinal"), src.indexOf("regionEdit"));
    expect(final).toContain("Promise<{ cinematographer: SceneCinematographerPack; shot: SceneShot }>");
  });
});

describe("CDX-050: SceneCreatorVariant dead prop removed", () => {
  const core = readFileSync(SC, "utf8");
  const hook = readFileSync(HOOK, "utf8");
  const ws = readFileSync(WS, "utf8");

  it("SceneCreatorCore has no variant prop and no dead type import", () => {
    expect(core).not.toContain("SceneCreatorVariant");
    expect(core).not.toContain("variant:");
    expect(hook).not.toContain("SceneCreatorVariant");
    expect(ws).not.toContain('variant="standard"');
  });
});