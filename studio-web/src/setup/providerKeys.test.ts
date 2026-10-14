import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * The permanent Setup Wizard panel: one shared API Providers & Keys manager
 * rendered inline on the Setup page for Windows, macOS, and Linux.
 */
const here = dirname(fileURLToPath(import.meta.url));
const panel = readFileSync(join(here, "ProviderKeysPanel.tsx"), "utf8");
const wizard = readFileSync(join(here, "..", "components", "SetupWizard.tsx"), "utf8");
const styles = readFileSync(join(here, "..", "styles.css"), "utf8");

describe("API Providers & Keys panel", () => {
  it("lists every supported provider", () => {
    for (const id of ["fal", "kie", "wavespeed", "elevenlabs"]) {
      expect(panel).toContain(`id: "${id}"`);
    }
  });

  it("offers masked input, show/hide, test, save, and remove controls", () => {
    expect(panel).toContain('type={showKey[provider.id] ? "text" : "password"}');
    expect(panel).toContain("Show key");
    expect(panel).toContain("Hide key");
    expect(panel).toContain("Test Connection");
    expect(panel).toContain("Save Key");
    expect(panel).toContain("Update Key");
    expect(panel).toContain("Remove Key");
  });

  it("confirms before removing a credential", () => {
    expect(panel).toContain("window.confirm");
  });

  it("reports honest result states", () => {
    for (const label of ["Connected", "Authentication failed", "Provider unavailable", "Timeout", "Configuration error"]) {
      expect(panel).toContain(label);
    }
  });

  it("validates through the transactional backend without a duplicate endpoint", () => {
    expect(panel).toContain("api.hostedProvidersConnect");
    expect(panel).toContain("api.hostedProvidersTest");
    expect(panel).toContain("api.hostedProvidersClear");
    expect(panel).not.toContain("fetch(");
  });

  it("never renders a stored secret into the input", () => {
    expect(panel).toContain("Key saved — enter a new key to replace");
    expect(panel).not.toContain("defaultValue");
  });
});

describe("Setup Wizard page integration", () => {
  it("renders the three required sections inline on the page", () => {
    expect(wizard).toContain('data-testid="setup-wizard-permanent"');
    expect(wizard).toContain('data-testid="setup-profile-section"');
    expect(wizard).toContain('data-testid="setup-api-keys-section"');
    expect(wizard).toContain('data-testid="setup-system-config-section"');
    expect(wizard).toContain("API Providers &amp; Keys");
  });

  it("keeps the approved three profile radios in the approved order", () => {
    expect(wizard).toContain('(["local", "hybrid", "api"] as const)');
    expect(wizard).toContain("PROFILE_COPY[id].title");
    expect(wizard).toContain('name="installation-profile-page"');
  });

  it("does not link to a separate API manager", () => {
    expect(wizard).not.toContain("manage-api-connections");
    expect(wizard).not.toContain("HostedProvidersSetupPanel");
  });

  it("states that Full API Installation skips local generation requirements", () => {
    expect(wizard).toContain("ComfyUI and local generation models are not required for Full API Installation.");
  });
});

describe("Provider keys styling", () => {
  it("uses Adept tokens instead of browser defaults", () => {
    for (const selector of [
      ".setup-provider-keys",
      ".setup-provider-row",
      ".setup-provider-status",
      ".setup-provider-status.is-success",
      ".setup-provider-status.is-auth_failed",
      ".setup-provider-controls",
      ".setup-provider-message",
    ]) {
      expect(styles).toContain(selector);
    }
    expect(styles).toMatch(/\.setup-provider-status\.is-success\s*\{[^}]*border-color:\s*var\(--accent\)/);
  });
});
