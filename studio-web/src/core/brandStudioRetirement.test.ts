import { describe, expect, it } from "vitest";
import { getExploreWorkspaceCards } from "./exploreWorkspaces";
import { PRODUCTION_MENU_CATALOG } from "./productionMenu";
import {
  ALL_TABS,
  commandPaletteWorkspaces,
  isRetiredWorkspace,
  resolveWorkspace,
  WORKSPACES,
} from "./workspaces";

describe("Brand Studio retirement from Adept UI v1.1", () => {
  it("does not register brandstudio as a live workspace", () => {
    expect("brandstudio" in WORKSPACES).toBe(false);
    expect(ALL_TABS).not.toContain("brandstudio");
    expect(commandPaletteWorkspaces()).not.toContain("brandstudio");
  });

  it("treats stale Brand Studio aliases as retired, not remounted", () => {
    for (const alias of ["brandstudio", "brand", "branding", "promo"]) {
      expect(isRetiredWorkspace(alias)).toBe(true);
      expect(resolveWorkspace(alias)).toBeNull();
    }
  });

  it("keeps Brand Ad project-type language out of the workspace registry", () => {
    expect(resolveWorkspace("brand_ad")).toBeNull();
    expect(isRetiredWorkspace("brand_ad")).toBe(false);
  });

  it("removes Brand Studio from Explore and Production", () => {
    expect(getExploreWorkspaceCards().some((card) => card.id === "brandstudio")).toBe(false);
    const menuIds = PRODUCTION_MENU_CATALOG.flatMap((cat) => cat.entries.map((entry) => entry.id));
    expect(menuIds).not.toContain("brandstudio");
  });
});
