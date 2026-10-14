import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * One shared Setup Wizard. These checks fail if an obsolete wizard is wired
 * back into active routing, or if the approved inline key section disappears.
 */
const src = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(relative: string): string {
  return readFileSync(join(src, relative), "utf8");
}

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === "node_modules") continue;
      walk(full, out);
    } else if (/\.(tsx|ts)$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

describe("legacy wizard cannot become the first-run authority", () => {
  it("routes every platform through the same Setup page", () => {
    const app = read("App.tsx");
    expect(app).toContain('<Route path="/setup" element={<SetupPage />} />');
    expect(app).not.toMatch(/SetupWizard\.(win|mac|linux|windows|darwin)/);
    const page = read("pages/SetupPage.tsx");
    expect(page).toContain("SetupWizardPanel");
  });

  it("keeps the approved three-option wizard and the inline key section", () => {
    const wizard = read("components/SetupWizard.tsx");
    const modal = read("setup/FirstRunSetupModal.tsx");
    expect(wizard).toContain("FirstRunSetupModal");
    expect(wizard).toContain('data-testid="setup-wizard-permanent"');
    expect(wizard).toContain("ProviderKeysPanel");
    expect(wizard).toContain('data-testid="setup-api-keys-section"');
    expect(modal).toContain('title: "Full Local Installation"');
    expect(modal).toContain('title: "Hybrid Installation — Local + API"');
    expect(modal).toContain('title: "Full API Installation"');
  });

  it("does not mount the duplicate API key panel", () => {
    for (const file of ["components/SetupWizard.tsx", "App.tsx", "pages/SetupPage.tsx", "setup/lifecycle/AiGuidedSetupPanel.tsx"]) {
      expect(read(file)).not.toContain("HostedProvidersSetupPanel");
    }
  });

  it("has no platform-specific wizard component", () => {
    const names = walk(src).map((file) => file.replace(/\\/g, "/"));
    const forks = names.filter((file) => /setupwizard\.(win|mac|linux|windows|darwin)/i.test(file));
    expect(forks).toEqual([]);
  });
});
