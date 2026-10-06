import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  featureFlags,
  isFire3DEnabled,
  isPoseCraftEnabled,
  isSceneCraftEnabled,
  isSpatialMapEnabled,
} from "./featureFlags";
import { getExploreWorkspaceCards } from "./exploreWorkspaces";
import { PRODUCTION_MENU_CATALOG } from "./productionMenu";
import {
  commandPaletteWorkspaces,
  resolveShelvedCreatorWorkspace,
  WORKSPACES,
  workspacesForMenu,
} from "./workspaces";
import { CONTENT_NAV } from "../components/CoDirector/navEntries";

describe("v1.1 SceneCraft / spatial-3D shelf", () => {
  it("keeps Spatial Map, PoseCraft, Fire3D, and SceneCraft shelved_v1_1 / v1_2_cloud", () => {
    expect(isSpatialMapEnabled()).toBe(false);
    expect(isPoseCraftEnabled()).toBe(false);
    expect(isFire3DEnabled()).toBe(false);
    expect(isSceneCraftEnabled()).toBe(false);
    for (const flag of [featureFlags.spatialMap, featureFlags.poseCraft, featureFlags.fire3d, featureFlags.sceneCraft]) {
      expect(flag.enabled).toBe(false);
      expect(flag.status).toBe("shelved_v1_1");
      expect(flag.targetReturn).toBe("v1_2_cloud");
    }
  });

  it("hides PoseCraft and Spatial Map from menus, Explore, Express, and command palette", () => {
    const express = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(express).not.toContain("spatial_map");

    const menuIds = PRODUCTION_MENU_CATALOG.flatMap((cat) => cat.entries.map((e) => e.id));
    expect(menuIds).not.toContain("spatial");
    expect(menuIds).not.toContain("posecraft");
    expect(workspacesForMenu("production")).not.toContain("spatial");
    expect(workspacesForMenu("production")).not.toContain("posecraft");

    expect(getExploreWorkspaceCards().some((c) => c.id === "spatial")).toBe(false);
    expect(getExploreWorkspaceCards().some((c) => c.id === "posecraft")).toBe(false);
    expect(commandPaletteWorkspaces()).not.toContain("spatial");
    expect(commandPaletteWorkspaces()).not.toContain("posecraft");
    expect(WORKSPACES.spatial.menuHidden).toBe(true);
    expect(WORKSPACES.posecraft.menuHidden).toBe(true);
  });

  it("silently remaps stale Spatial Map and PoseCraft destinations", () => {
    expect(resolveShelvedCreatorWorkspace("spatial")).toBe("environmentcreator");
    expect(resolveShelvedCreatorWorkspace("posecraft")).toBe("imagegen");
    expect(resolveShelvedCreatorWorkspace("imagegen")).toBe("imagegen");
    expect(resolveShelvedCreatorWorkspace("environmentcreator")).toBe("environmentcreator");
  });

  it("does not mount unavailable / coming-soon chrome for shelved systems", () => {
    const editor = readFileSync(join(__dirname, "../pages/ProjectEditor.tsx"), "utf8");
    expect(editor).toContain("resolveShelvedCreatorWorkspace");
    expect(editor).not.toContain("Spatial Map unavailable");
    expect(editor).not.toContain("will return in a later release");
    expect(editor).toContain("isPoseCraftEnabled()");
    expect(editor).toContain("isSpatialMapEnabled()");

    const content = readFileSync(
      join(__dirname, "../components/CoDirector/CoDirectorProjectContent.tsx"),
      "utf8",
    );
    expect(content).not.toContain("Spatial Map unavailable");
    expect(content).not.toContain("codirector-spatial-map-unavailable");
  });

  it("does not advertise shelved names on active creator copy", () => {
    expect(WORKSPACES.propcreator.description).not.toMatch(/Spatial Map|PoseCraft|Fire3D|SceneCraft/);
    const deferred = readFileSync(join(__dirname, "../components/Version12DeferredPage.tsx"), "utf8");
    expect(deferred).not.toMatch(/Spatial Map|PoseCraft|Fire3D|SceneCraft/);
    const propRemove = readFileSync(
      join(__dirname, "../components/CoDirector/PropCreator/usePropCreator.ts"),
      "utf8",
    );
    expect(propRemove).not.toMatch(/Spatial Map|PoseCraft|Fire3D|SceneCraft/);
    const igHint = readFileSync(join(__dirname, "../i18n/locales/en/imageGenerator.json"), "utf8");
    expect(igHint).toContain("Library ~ image");
    expect(JSON.parse(igHint).referencesHint).not.toMatch(/PoseCraft|Spatial Map|Fire3D|SceneCraft/);
  });

  it("preserves workspace registry + aliases for stale route resolve", () => {
    expect(WORKSPACES.spatial.label).toBe("Spatial Map");
    expect(WORKSPACES.posecraft.label).toBe("PoseCraft");
    expect(WORKSPACES.spatial.compatibilityAliases).toEqual(
      expect.arrayContaining(["blocking", "spatial-map", "spatialmap", "spatial_map"]),
    );
    expect(WORKSPACES.posecraft.compatibilityAliases).toEqual(
      expect.arrayContaining(["pose-craft", "pose", "posing"]),
    );
  });
});
