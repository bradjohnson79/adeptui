import { describe, expect, it } from "vitest";
import {
  CREATOR_SCOPE_HELP,
  characterOwnedByProject,
  propEditableInProject,
  isStalePropHomeOnlyEditMessage,
  PROP_GLOBAL_SCOPE_HELP,
  findVisibleNameCollision,
  groupScopeItems,
  normalizeProfileName,
  pickOwnedCharacterId,
  readIsGlobal,
  scopeLabel,
} from "./creatorScope";

describe("creatorScope", () => {
  it("keeps owned global assets in PROJECT and other-owner globals in GLOBAL", () => {
    const grouped = groupScopeItems(
      [
        { id: "1", project_id: "a", isGlobal: true, name: "Mine" },
        { id: "2", project_id: "b", isGlobal: true, name: "Other" },
        { id: "3", project_id: "a", isGlobal: false, name: "Local" },
      ],
      "a",
    );
    expect(grouped.project.map((i) => i.id)).toEqual(["1", "3"]);
    expect(grouped.global.map((i) => i.id)).toEqual(["2"]);
  });

  it("does not change tags — scope is a label only", () => {
    expect(scopeLabel("@Korri", { project_id: "a", isGlobal: true }, "a")).toBe("@Korri");
    expect(scopeLabel("@Renkoka", { project_id: "b", isGlobal: true }, "a")).toBe("@Renkoka  Global");
  });

  it("reads both isGlobal and is_global", () => {
    expect(readIsGlobal({ is_global: true })).toBe(true);
    expect(readIsGlobal({ isGlobal: false })).toBe(false);
    expect(CREATOR_SCOPE_HELP).toContain("every project");
  });

  it("does not auto-select a foreign Global when a project has no local characters", () => {
    const items = [
      { id: "foreign-global", project_id: "other", is_global: true, name: "TestGlobalCharacter" },
    ];
    expect(pickOwnedCharacterId(items, "cade-scenes")).toBe("");
    expect(characterOwnedByProject(items[0], "cade-scenes")).toBe(false);
  });

  it("auto-selects the first project-owned character and keeps an explicit selection", () => {
    const items = [
      { id: "foreign-global", project_id: "other", is_global: true, name: "Global" },
      { id: "cade", project_id: "cade-scenes", is_global: false, name: "Cade O'Connor" },
    ];
    expect(pickOwnedCharacterId(items, "cade-scenes")).toBe("cade");
    expect(pickOwnedCharacterId(items, "cade-scenes", "foreign-global")).toBe("foreign-global");
    expect(characterOwnedByProject(items[1], "cade-scenes")).toBe(true);
  });

  it("normalizes profile names for uniqueness comparison only", () => {
    expect(normalizeProfileName("  Cade's Starfighter ")).toBe("cade's starfighter");
    expect(normalizeProfileName("CADE'S   STARFIGHTER")).toBe("cade's starfighter");
    const hit = findVisibleNameCollision(
      [
        { id: "a", display_label: "Cade's Starfighter" },
        { id: "b", display_label: "Other" },
      ],
      " cade's starfighter ",
    );
    expect(hit?.id).toBe("a");
    expect(findVisibleNameCollision([{ id: "a", display_label: "Cade's Starfighter" }], "Cade's Starfighter", "a")).toBeUndefined();
  });
});

describe("ORDER 18 prop Global edit law", () => {
  it("allows Global prop edit from a foreign project", () => {
    const globalProp = { id: "p1", project_id: "home", isGlobal: true };
    expect(propEditableInProject(globalProp, "foreign")).toBe(true);
    expect(propEditableInProject(globalProp, "home")).toBe(true);
  });

  it("keeps non-global props home-only", () => {
    const local = { id: "p2", project_id: "home", isGlobal: false };
    expect(propEditableInProject(local, "home")).toBe(true);
    expect(propEditableInProject(local, "foreign")).toBe(false);
  });

  it("filters stale home-only edit messages but keeps delete copy", () => {
    expect(
      isStalePropHomeOnlyEditMessage(
        "Global props can only be edited from the project that created them.",
      ),
    ).toBe(true);
    expect(
      isStalePropHomeOnlyEditMessage("This prop can only be edited from the project that created it."),
    ).toBe(true);
    expect(
      isStalePropHomeOnlyEditMessage(
        "Global props can only be deleted from the project that created them.",
      ),
    ).toBe(false);
    expect(PROP_GLOBAL_SCOPE_HELP.toLowerCase()).toContain("edited from any project");
  });
});
