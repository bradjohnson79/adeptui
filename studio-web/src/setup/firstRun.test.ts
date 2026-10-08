import { describe, expect, it } from "vitest";
import { bootHandoffTarget, requiredFirstRunReady, scanAllowsCompletion, setupWizardRequired } from "./firstRun";
import { buildAiGuidedSetupPath, buildSetupWizardPath, homeLaunchAction } from "./navigation";
import { buildHomeCreateProjectPath } from "../projectEntry";

const ready = [
  { id: "python", status: "ready" },
  { id: "ffmpeg", status: "ready" },
  { id: "comfyui", status: "ready" },
];

describe("first-run boot handoff", () => {
  it("opens the wizard when the flag is false", () => {
    expect(bootHandoffTarget(false, false)).toBe("/setup");
  });

  it("opens Home after the flag is true", () => {
    expect(bootHandoffTarget(true, false)).toBe("/");
  });

  it("keeps a returning launch on Home when an optional model is missing", () => {
    expect(requiredFirstRunReady([...ready, { id: "minimax-h3", status: "not_installed" }])).toBe(true);
    expect(bootHandoffTarget(true, false)).toBe("/");
  });

  it("does not treat a failed flag read as a new first run", () => {
    expect(bootHandoffTarget(undefined, true)).toBe("/");
  });

  it("opens the installer only while the essential baseline is incomplete", () => {
    expect(setupWizardRequired(null)).toBe(false);
    expect(setupWizardRequired({ firstRunSetupComplete: true })).toBe(false);
    expect(setupWizardRequired({ firstRunSetupComplete: false })).toBe(true);
    expect(setupWizardRequired({
      firstRunSetupComplete: true,
      firstRunScan: { essentialBlockerCount: 1, baselineImageWorkflow: "blocked", baselineVideoWorkflow: "ready" },
    })).toBe(true);
    expect(setupWizardRequired({
      firstRunSetupComplete: false,
      firstRunScan: { essentialBlockerCount: 0, baselineImageWorkflow: "ready", baselineVideoWorkflow: "ready" },
    })).toBe(false);
  });

  it("does not complete while the image or video baseline is blocked", () => {
    expect(scanAllowsCompletion({
      essentialBlockerCount: 1,
      baselineImageWorkflow: "blocked",
      baselineVideoWorkflow: "ready",
    })).toBe(false);
    expect(scanAllowsCompletion({
      essentialBlockerCount: 0,
      baselineImageWorkflow: "ready",
      baselineVideoWorkflow: "ready",
    })).toBe(true);
  });

  it("stays incomplete when a successful read is not explicitly complete", () => {
    expect(bootHandoffTarget(undefined, false)).toBe("/setup");
    expect(requiredFirstRunReady([{ id: "python", status: "ready" }, { id: "ffmpeg", status: "not_installed" }, { id: "comfyui", status: "ready" }])).toBe(false);
  });
});

describe("setup routing stays off create project", () => {
  it("opens the wizard without a project and without create=1", () => {
    const path = buildSetupWizardPath(null);
    expect(path.startsWith("/setup?")).toBe(true);
    expect(path).not.toContain("create=1");
    expect(buildAiGuidedSetupPath({ source: "workspace_launch" })).not.toContain("create=1");
  });

  it("keeps an open project on the existing setup workspace", () => {
    expect(buildSetupWizardPath("proj-1")).toContain("/project/proj-1?");
    expect(buildSetupWizardPath("proj-1")).toContain("workspace=setup");
  });

  it("opens Create Project only for a real project entry", () => {
    expect(homeLaunchAction({ forcedCreate: true, pendingKind: "project" })).toEqual({ type: "create-project" });
    expect(homeLaunchAction({ forcedCreate: true, pendingKind: "setup", projectId: null })).toEqual({
      type: "open-setup",
      projectId: null,
    });
    expect(homeLaunchAction({ forcedCreate: false, pendingKind: "setup", projectId: "proj-9" })).toEqual({
      type: "open-setup",
      projectId: "proj-9",
    });
    const createPath = buildHomeCreateProjectPath({ pendingEntry: { kind: "project", workspace: "timeline" } });
    expect(createPath).toContain("create=1");
    expect(createPath).not.toContain("workspace=setup");
  });
});
