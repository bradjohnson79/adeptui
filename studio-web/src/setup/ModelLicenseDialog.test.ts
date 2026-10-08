import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const dialog = readFileSync(new URL("./ModelLicenseDialog.tsx", import.meta.url), "utf8");
const wizard = readFileSync(new URL("../components/SetupWizard.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../api.ts", import.meta.url), "utf8");

describe("MiniMax H3 license dialog", () => {
  it("states that Adept UI does not grant the MiniMax license", () => {
    expect(dialog).toContain("Adept UI does not grant you a license to use MiniMax H3.");
    expect(dialog).toContain("MiniMax H3 is provided by MiniMax and is governed by MiniMax's own license.");
    expect(dialog).not.toContain("legally permitted");
    expect(dialog).not.toContain("geolocation");
    expect(dialog).not.toContain("navigator.geolocation");
  });

  it("requires a user-selected region and a confirmation before enable", () => {
    expect(dialog).toContain("Select country / region");
    expect(dialog).toContain("I have read and agree to the applicable MiniMax H3 license.");
    expect(dialog).toContain("I confirm that I have obtained the required MiniMax authorization.");
    expect(dialog).toContain("Separate MiniMax authorization is required for your region.");
    expect(dialog).toContain("Apply / Request Authorization");
    expect(dialog).toContain("Read Official License");
    expect(dialog).toContain("disabled={!selected || !agreed || busy}");
    expect(dialog).toContain("Enable MiniMax H3");
  });

  it("cancels without acknowledging and locks when the license cannot be verified", () => {
    expect(dialog).toContain('onClick={onClose}');
    expect(dialog).toContain("MiniMax H3 licensing information could not be verified.");
    expect(dialog).toContain("View Official MiniMax Source");
    const enable = dialog.slice(dialog.indexOf("async function enable"));
    expect(enable).toContain("setupAcknowledgeModelLicense");
    expect(dialog.slice(0, dialog.indexOf("async function enable"))).not.toContain("setupAcknowledgeModelLicense");
  });

  it("wires the review button to the existing setup card and hides install while locked", () => {
    expect(wizard).toContain("Review License &amp; Enable");
    expect(wizard).toContain("onReviewLicense={setLicenseFor}");
    expect(wizard).toContain("modelLicenseStatusLabel");
    expect(wizard).toContain("!installBlocked");
    expect(wizard).toContain("Provider: {component.model_license.provider}");
    expect(wizard).toContain("License: {component.model_license.licenseName");
    expect(api).toContain("/api/setup/model-licenses/");
    expect(api).not.toContain("geolocation");
  });
});
