import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isSetupModel } from "./SetupLocalModels";

const src = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(relative: string): string {
  return readFileSync(join(src, relative), "utf8");
}

describe("unified setup manager", () => {
  it("keeps the approved wizard and does not render the legacy section dashboard", () => {
    const wizard = read("components/SetupWizard.tsx");
    const app = read("App.tsx");
    const chrome = read("components/dashboard/AppChrome.tsx");
    expect(wizard).toContain('data-testid="setup-wizard-permanent"');
    expect(wizard).toContain("ProviderKeysPanel");
    expect(wizard).toContain("SetupLocalModels");
    expect(wizard).toContain("SetupComfyStep");
    expect(wizard).not.toContain("adept-setup-sections");
    expect(wizard).not.toContain("LoRASetupSection");
    expect(wizard).not.toContain("<ComfyManager");
    expect(wizard).not.toContain("AdeptSetupUpdates");
    expect(app).not.toContain("<ComfyManagerPage />");
    expect(chrome).not.toContain('label: "Comfy Manager"');
  });

  it("treats video and still-image catalog rows as local models", () => {
    expect(isSetupModel({ category: "Video Models" })).toBe(true);
    expect(isSetupModel({ category: "Still Image Models" })).toBe(true);
    expect(isSetupModel({ category: "API Providers" })).toBe(false);
    expect(isSetupModel({ category: "Core" })).toBe(false);
  });
});
