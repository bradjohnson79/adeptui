import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { isSpatialMapEnabled } from "../core/featureFlags";

describe("EssentialAgreementPanel", () => {
  const src = readFileSync(new URL("./EssentialAgreementPanel.tsx", import.meta.url), "utf8");
  const wizard = readFileSync(new URL("./SetupWizard.tsx", import.meta.url), "utf8");

  it("wires View, Open Full, AGREE, and Decline without auto-accept", () => {
    expect(src).toContain("essential-agreement-view");
    expect(src).toContain("essential-agreement-open-full");
    expect(src).toContain("essential-agreement-agree");
    expect(src).toContain("essential-agreement-decline");
    expect(src).toContain("document unavailable");
    expect(src).not.toContain("documentAvailableConfirmed: true,\n      });\n      // auto");
    expect(src).toContain("documentAvailableConfirmed: true");
    expect(src).toContain("Open the full notice before you agree");
  });

  it("keeps independent readiness badges and both Spatial Essentials", () => {
    expect(src).toContain("moge2_geometry");
    expect(src).toContain("vggt_1b_commercial");
    expect(src).toContain("Agreement Accepted");
    expect(src).toContain("Commercial Model Access");
    expect(src).toContain("Production Certified");
  });

  it("gates Spatial Essentials when Spatial Map is shelved for v1.1", () => {
    expect(isSpatialMapEnabled()).toBe(false);
    expect(src).toContain("isSpatialMapEnabled");
    expect(src).toContain("if (!isSpatialMapEnabled()) return null");
  });
});
