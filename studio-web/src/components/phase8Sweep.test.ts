/**
 * Phase 8 sweep - frontend contract tests (CDX-011/016/026/041).
 *
 * These are deterministic source/contract assertions over the authored fixes.
 * They pin the intended contracts so a regression cannot silently reintroduce
 * ghost prop rows or draft-identity placement. CDX-040/047/050 asserted
 * Scene Creator Standard contracts, which was retired with the Image
 * Generator v1.1 triad (Image Generator now owns production stills).
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const SPATIAL = new URL("../components/CoDirector/SpatialMap/SpatialMapPanel.tsx", import.meta.url);
const PROP_API = new URL("../components/CoDirector/PropCreator/propCreatorApi.ts", import.meta.url);
const PROP_HOOK = new URL("../components/CoDirector/PropCreator/usePropCreator.ts", import.meta.url);
const ERS_CONTRACT = new URL("../contracts/environmentReferenceSheet.ts", import.meta.url);

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

describe("CDX-041: ERS TS contract carries the backend sheet payload", () => {
  const src = readFileSync(ERS_CONTRACT, "utf8");

  it("adds ers_composite_asset_id and provenance to EnvironmentReferenceSheet", () => {
    const sheet = src.slice(src.indexOf("export type EnvironmentReferenceSheet = {"), src.indexOf("export type EnvironmentReferenceSheetSummary"));
    expect(sheet).toContain("ers_composite_asset_id?: string | null;");
    expect(sheet).toContain("provenance?: ERSProvenanceRecord | null;");
  });
});