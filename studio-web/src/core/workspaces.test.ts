import { describe, expect, it } from "vitest";
import { resolveWorkspace, commandPaletteWorkspaces, WORKSPACES } from "./workspaces";

describe("workspace registry — Project Profile retirement", () => {
  it("retires the profiles workspace from the registry", () => {
    expect("profiles" in WORKSPACES).toBe(false);
  });

  it("resolves stale ?workspace=profiles deep links to project home (no blank page)", () => {
    expect(resolveWorkspace("profiles")).toBe("home");
    expect(resolveWorkspace("PROFILES")).toBe("home");
    expect(resolveWorkspace(" profiles ")).toBe("home");
  });

  it("does not surface Project Profile in the command palette", () => {
    expect(commandPaletteWorkspaces().some((tab) => tab === "profiles")).toBe(false);
  });

  it("keeps Character Creator registered (relocated, not removed)", () => {
    expect(resolveWorkspace("characters")).toBe("characters");
    expect(WORKSPACES.characters.label).toBe("Character Creator");
  });

  it("keeps existing canonical mappings intact", () => {
    expect(resolveWorkspace("director")).toBe("timeline");
    expect(resolveWorkspace("editor")).toBe("magi");
    expect(resolveWorkspace("script-writer")).toBe("scriptwriter");
  });

  it("folds retired video destinations onto Timeline", () => {
    expect(resolveWorkspace("txt2vid")).toBe("timeline");
    expect(resolveWorkspace("text-to-video")).toBe("timeline");
    expect(resolveWorkspace("one")).toBe("timeline");
    expect(resolveWorkspace("one-frame")).toBe("timeline");
    expect(resolveWorkspace("three")).toBe("timeline");
    expect(resolveWorkspace("three-frame")).toBe("timeline");
    expect(commandPaletteWorkspaces()).not.toContain("txt2vid");
    expect(commandPaletteWorkspaces()).not.toContain("one");
    expect(commandPaletteWorkspaces()).not.toContain("three");
    expect(WORKSPACES.txt2vid.menuHidden).toBe(true);
    expect(WORKSPACES.one.menuHidden).toBe(true);
    expect(WORKSPACES.three.menuHidden).toBe(true);
  });
});
