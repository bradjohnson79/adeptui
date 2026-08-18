import { describe, expect, it } from "vitest";
import { PRODUCTION_MENU_CATALOG } from "./productionMenu";

function catalogEntries() {
  return PRODUCTION_MENU_CATALOG.flatMap((cat) => [...cat.entries]);
}

describe("PRODUCTION_MENU_CATALOG routing", () => {
  it("routes Avatar Studio to the avatar workspace without a character gate", () => {
    const avatar = catalogEntries().find((entry) => entry.id === "avatar");
    expect(avatar?.workspace).toBe("avatar");
    expect(avatar?.requiresCharacter).toBeFalsy();
  });

  it("keeps Character Creator on the characters workspace", () => {
    const characters = catalogEntries().find((entry) => entry.id === "characters");
    expect(characters?.workspace).toBe("characters");
  });

  it("does not list Production Bible as a user destination", () => {
    expect(catalogEntries().some((entry) => entry.id === "bible")).toBe(false);
  });
});
