import { describe, expect, it } from "vitest";
import {
  ALL_TABS,
  RETIRED_WORKSPACE_IDS,
  WORKSPACES,
  isRetiredWorkspace,
  resolveWorkspace,
  workspacesForMenu,
  commandPaletteWorkspaces,
} from "./workspaces";

/**
 * Journey 2 — Scene Creator Standard retirement contract.
 * The Image Generator is the production-still successor: every Scene Creator
 * deep link must land there (never a removed workspace, never a blank page),
 * and no menu / palette / label surface may list Scene Creator anymore.
 */
describe("Scene Creator retirement (Image Generator v1.1 triad)", () => {
  it("routes every stale Scene Creator id/alias to the Image Generator", () => {
    for (const stale of ["scenecreator", "mastersheet", "scene-creator", "scene_creator"]) {
      expect(resolveWorkspace(stale)).toBe("imagegen");
    }
    // Deep-link query shape: ?workspace=scenecreator
    expect(resolveWorkspace(" scenecreator ")).toBe("imagegen");
  });

  it("keeps Scene Creator out of the workspace registry", () => {
    expect((ALL_TABS as readonly string[]).includes("scenecreator")).toBe(false);
    expect((ALL_TABS as readonly string[]).includes("mastersheet")).toBe(false);
    expect(WORKSPACES).not.toHaveProperty("scenecreator");
    expect(WORKSPACES).not.toHaveProperty("mastersheet");
  });

  it("tombstones Scene Creator so it never remounts", () => {
    expect(isRetiredWorkspace("scenecreator")).toBe(true);
    expect(isRetiredWorkspace("mastersheet")).toBe(true);
    expect(RETIRED_WORKSPACE_IDS).toContain("scenecreator");
    expect(RETIRED_WORKSPACE_IDS).toContain("mastersheet");
  });

  it("lists no Scene Creator entry in any menu group or the command palette", () => {
    for (const group of ["project", "generate", "characters", "production", "tools", "window"] as const) {
      expect(workspacesForMenu(group).includes("scenecreator" as never)).toBe(false);
    }
    expect(commandPaletteWorkspaces().includes("scenecreator" as never)).toBe(false);
  });

  it("keeps the Image Generator and Environment Creator live", () => {
    expect(resolveWorkspace("imagegen")).toBe("imagegen");
    expect(resolveWorkspace("environmentcreator")).toBe("environmentcreator");
    expect(WORKSPACES.imagegen.label).toBe("Cinematic Image Generator");
  });
});
