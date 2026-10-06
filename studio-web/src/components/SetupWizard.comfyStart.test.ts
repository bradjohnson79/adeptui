import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("SetupWizard start and catalog timeout", () => {
  const src = readFileSync(new URL("./SetupWizard.tsx", import.meta.url), "utf8");

  it("does not own runtime lifecycle from Setup", () => {
    expect(src).not.toContain("runtimeManagerStart");
    expect(src).not.toContain("runtimeManagerStop");
    expect(src).not.toContain("runtimeManagerRestartApi");
    expect(src).not.toContain("runtimeManagerRestartComfy");
    expect(src).not.toContain("start-background-services");
    expect(src).not.toContain("stop-background-services");
    expect(src).not.toContain("restart-studio-api");
    expect(src).not.toContain("restart-comfy");
    expect(src).toContain("Adept Runtime — Managed Automatically");
    expect(src).toContain("validate-runtime-configuration");
    expect(src).toContain("runtimeManagerValidateConfig");
    expect(src).toContain("runtimeManagerRepair");
    expect(src).not.toContain("if (!comfyuiReady) return null");
  });

  it("does not claim Ready after a background start", () => {
    expect(src).not.toContain('setActiveStatus("Ready")');
  });

  it("keeps Try Again and Open Runtime Manager", () => {
    expect(src).toContain("Try Again");
    expect(src).toContain("Open Runtime Manager");
  });
});
