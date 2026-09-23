import { describe, expect, it } from "vitest";
import { PRODUCTION_MENU_CATALOG, PRODUCTION_CATEGORY_ORDER } from "./productionMenu";

function catalogEntries() {
  return PRODUCTION_MENU_CATALOG.flatMap((cat) => [...cat.entries]);
}

describe("PRODUCTION_MENU_CATALOG routing", () => {
  it("does not list Avatar Studio after temporary retirement from current Adept UI", () => {
    expect(catalogEntries().some((entry) => entry.id === "avatar")).toBe(false);
  });

  it("keeps Character Creator on the characters workspace", () => {
    const characters = catalogEntries().find((entry) => entry.id === "characters");
    expect(characters?.workspace).toBe("characters");
  });

  it("does not list Production Bible as a user destination", () => {
    expect(catalogEntries().some((entry) => entry.id === "bible")).toBe(false);
  });

  it("does not list Brand Studio after Adept UI v1.1 retirement", () => {
    expect(catalogEntries().some((entry) => entry.id === "brandstudio")).toBe(false);
  });
});

describe("PRODUCTION_MENU_CATALOG reorganization (Project Profile retirement)", () => {
  it("has no Profiles category and no Project Profile entry", () => {
    expect(PRODUCTION_MENU_CATALOG.some((cat) => cat.id === "profiles")).toBe(false);
    expect(catalogEntries().some((entry) => entry.id === "profiles")).toBe(false);
  });

  it("places Character Creator FIRST inside Creative Studios", () => {
    const studios = PRODUCTION_MENU_CATALOG.find((cat) => cat.id === "creative-studios");
    expect(studios?.entries[0]?.id).toBe("characters");
    expect(studios?.entries.map((e) => e.id)).toEqual([
      "characters",
      "voicestudio",
      "audiostudio",
      "library",
    ]);
  });

  it("keeps Pre-Production: scriptwriter, environment, prop (PoseCraft shelved for v1.2)", () => {
    const pre = PRODUCTION_MENU_CATALOG.find((cat) => cat.id === "pre-production");
    expect(pre?.entries.map((e) => e.id)).toEqual([
      "scriptwriter",
      "environmentcreator",
      "propcreator",
    ]);
    expect(pre?.entries.some((e) => e.id === "posecraft")).toBe(false);
  });

  it("orders categories create → pre-production → creative-studios → post", () => {
    expect(PRODUCTION_CATEGORY_ORDER.slice(0, 4)).toEqual([
      "create",
      "pre-production",
      "creative-studios",
      "post-production",
    ]);
  });
});
