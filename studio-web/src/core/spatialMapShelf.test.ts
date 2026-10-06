import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { featureFlags, isSpatialMapEnabled } from "./featureFlags";
import { getExploreWorkspaceCards } from "./exploreWorkspaces";
import { PRODUCTION_MENU_CATALOG } from "./productionMenu";
import { commandPaletteWorkspaces, WORKSPACES, workspacesForMenu } from "./workspaces";
import { CONTENT_NAV } from "../components/CoDirector/navEntries";

describe("Spatial Map v1.1 shelf gate", () => {
  it("keeps a single featureFlags authority with shelved_v1_1 / v1_2_cloud", () => {
    expect(isSpatialMapEnabled()).toBe(false);
    expect(featureFlags.spatialMap.enabled).toBe(false);
    expect(featureFlags.spatialMap.status).toBe("shelved_v1_1");
    expect(featureFlags.spatialMap.targetReturn).toBe("v1_2_cloud");
  });

  it("hides Spatial Map from Express tabs, Production menu, Explore, and command palette", () => {
    const express = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(express).not.toContain("spatial_map");

    const menuIds = PRODUCTION_MENU_CATALOG.flatMap((cat) => cat.entries.map((e) => e.id));
    expect(menuIds).not.toContain("spatial");
    expect(workspacesForMenu("production")).not.toContain("spatial");

    expect(getExploreWorkspaceCards().some((c) => c.id === "spatial")).toBe(false);
    expect(commandPaletteWorkspaces()).not.toContain("spatial");
    expect(WORKSPACES.spatial.menuHidden).toBe(true);
  });


  it("CoDirectorProjectContent does not mount Spatial Map or name it when shelved", () => {
    const src = readFileSync(
      join(__dirname, "../components/CoDirector/CoDirectorProjectContent.tsx"),
      "utf8",
    );
    expect(src).toContain("isSpatialMapEnabled()");
    expect(src).not.toContain("Spatial Map unavailable");
    expect(src.toLowerCase()).not.toContain("continue scene production");
  });

  it("AgentWorkSurface gates Continue to Spatial Map behind isSpatialMapEnabled", () => {
    const src = readFileSync(
      join(__dirname, "../components/CoDirector/AgentWorkSurface/AgentWorkSurface.tsx"),
      "utf8",
    );
    expect(src).toContain("showSpatialWorkflowContinueCta");
    expect(src).toContain("isSpatialMapEnabled");
    expect(src).toMatch(/atlas_shot_generation[\s\S]*isSpatialMapEnabled\(\)/);
  });

  it("preserves Spatial Map workspace registry + aliases for stale route resolve", () => {
    expect(WORKSPACES.spatial.label).toBe("Spatial Map");
    expect(WORKSPACES.spatial.compatibilityAliases).toEqual(
      expect.arrayContaining(["blocking", "spatial-map", "spatialmap", "spatial_map"]),
    );
  });
});
