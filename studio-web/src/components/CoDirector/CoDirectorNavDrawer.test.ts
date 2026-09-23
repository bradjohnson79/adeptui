import { describe, expect, it } from "vitest";
import { CONTENT_NAV, OPEN_CONTENT_TAB_EVENT } from "./navEntries";
import { isSpatialMapEnabled } from "../../core/featureFlags";

describe("Co-Director viewport navigation", () => {
  it("keeps production tabs and does not expose a More overflow", () => {
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    const more = CONTENT_NAV.find((item) => item.kind === "group" && item.id === "more");
    const expected = [
      "wiki",
      "notes",
      "story",
      "scriptwriter",
      "characters",
      "voice_creator",
      "prop_creator",
      ...(isSpatialMapEnabled() ? (["spatial_map"] as const) : []),
      "scene_creator",
      "timeline",
      "library",
    ];
    expect(tabs).toEqual([...expected]);
    expect(more).toBeUndefined();
    expect(CONTENT_NAV.some((item) => item.label === "More")).toBe(false);
    expect(OPEN_CONTENT_TAB_EVENT).toBe("adept:open-codirector-content-tab");
    expect(tabs).not.toContain("storyboards");
    expect(tabs).not.toContain("casting");
    expect(tabs).not.toContain("jobs");
  });

  it("shelves Spatial Map from Express tabs when the v1.1 gate is off", () => {
    expect(isSpatialMapEnabled()).toBe(false);
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(tabs).not.toContain("spatial_map");
  });
});
