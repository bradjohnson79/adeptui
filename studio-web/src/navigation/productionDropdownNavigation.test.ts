import { describe, expect, it } from "vitest";
import { buildProjectWorkspaceLocation } from "./projectWorkspaceNavigation";
import { isTimelineShellWorkspace } from "../sceneSelection";
import { resolveWorkspace } from "../core/workspaces";

/** Mirrors ProjectEditor timeline-url-sync stale-tab guard. */
function shouldRewriteTimelineSearch(tab: string, locationSearch: string): boolean {
  if (!isTimelineShellWorkspace(tab)) return false;
  const urlWorkspace = resolveWorkspace(
    new URLSearchParams(locationSearch).get("workspace") ??
      new URLSearchParams(locationSearch).get("tab"),
  );
  if (urlWorkspace && !isTimelineShellWorkspace(urlWorkspace)) return false;
  return true;
}

describe("Production dropdown navigation query-param law", () => {
  const projectId = "proj-1";

  it("Library destination URL uses workspace=library and does not retain workspace=timeline", () => {
    const loc = buildProjectWorkspaceLocation({
      projectId,
      tab: "library",
      sceneId: undefined,
    });
    expect(loc?.search).toBe("?workspace=library");
    expect(loc?.search).not.toContain("workspace=timeline");
    expect(loc?.search).not.toContain("sceneId=");
  });

  it("Character Creator destination is not Timeline", () => {
    const loc = buildProjectWorkspaceLocation({
      projectId,
      tab: "characters",
      sceneId: undefined,
    });
    expect(loc?.search).toBe("?workspace=characters");
    expect(loc?.search).not.toContain("workspace=timeline");
  });

  it("Timeline destination may keep sceneId", () => {
    const loc = buildProjectWorkspaceLocation({
      projectId,
      tab: "timeline",
      sceneId: "scene-9",
    });
    expect(loc?.search).toContain("workspace=timeline");
    expect(loc?.search).toContain("sceneId=scene-9");
  });

  it("stale tab=timeline must not rewrite an explicit library URL", () => {
    expect(
      shouldRewriteTimelineSearch("timeline", "?workspace=library&sceneId=scene-9"),
    ).toBe(false);
  });

  it("timeline tab may sync when URL is still timeline", () => {
    expect(
      shouldRewriteTimelineSearch("timeline", "?workspace=timeline&sceneId=scene-9"),
    ).toBe(true);
  });

  it("non-timeline tab never syncs timeline search", () => {
    expect(shouldRewriteTimelineSearch("library", "?workspace=library")).toBe(false);
  });
});
