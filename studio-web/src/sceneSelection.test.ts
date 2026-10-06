import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  SELECTED_SCENE_STORAGE_KEY,
  buildCoDirectorSearch,
  buildTimelineSearch,
  clearLastSelectedScene,
  loadLastSelectedScene,
  parseSceneIdFromSearch,
  persistWorkspaceKey,
  pruneSelectedScenes,
  resolveSelectedScene,
  saveLastSelectedScene,
} from "./sceneSelection";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => {
        store.set(k, String(v));
      },
      removeItem: (k: string) => {
        store.delete(k);
      },
      clear: () => store.clear(),
    },
  });
});

afterEach(() => {
  store.clear();
});

const SCENES = ["scene-1", "walk", "dialogue"];

describe("resolveSelectedScene precedence", () => {
  it("uses an explicit URL scene over remembered and session state", () => {
    expect(
      resolveSelectedScene({
        sceneIds: SCENES,
        urlSceneId: "walk",
        persistedSceneId: "scene-1",
        sessionSceneId: "dialogue",
      }),
    ).toBe("walk");
  });

  it("uses persisted project/workspace selection when the URL has no scene", () => {
    expect(
      resolveSelectedScene({
        sceneIds: SCENES,
        urlSceneId: null,
        persistedSceneId: "walk",
        sessionSceneId: "scene-1",
      }),
    ).toBe("walk");
  });

  it("uses the current session selection before the first-scene fallback", () => {
    expect(
      resolveSelectedScene({
        sceneIds: SCENES,
        urlSceneId: "",
        persistedSceneId: null,
        sessionSceneId: "dialogue",
      }),
    ).toBe("dialogue");
  });

  it("falls back to the first valid scene only when nothing else is valid", () => {
    expect(
      resolveSelectedScene({
        sceneIds: SCENES,
        urlSceneId: "deleted",
        persistedSceneId: "gone",
        sessionSceneId: "missing",
      }),
    ).toBe("scene-1");
  });

  it("discards an invalid URL id without looping", () => {
    expect(
      resolveSelectedScene({
        sceneIds: SCENES,
        urlSceneId: "other-project-scene",
        persistedSceneId: "walk",
        sessionSceneId: "scene-1",
      }),
    ).toBe("walk");
  });

  it("returns undefined when the project has no scenes", () => {
    expect(
      resolveSelectedScene({
        sceneIds: [],
        urlSceneId: "walk",
        persistedSceneId: "walk",
        sessionSceneId: "walk",
      }),
    ).toBeUndefined();
  });
});

describe("URL scene id parsing", () => {
  it("reads sceneId, then scene_id, then scene", () => {
    expect(parseSceneIdFromSearch("?workspace=timeline&sceneId=walk")).toBe("walk");
    expect(parseSceneIdFromSearch("workspace=timeline&scene_id=walk")).toBe("walk");
    expect(parseSceneIdFromSearch("?workspace=timeline&scene=walk")).toBe("walk");
  });

  it("prefers sceneId when aliases are all present", () => {
    expect(parseSceneIdFromSearch("?scene=old&scene_id=mid&sceneId=walk")).toBe("walk");
  });
});

describe("selected-scene persistence isolation", () => {
  it("does not persist landing/setup selections over Timeline memory", () => {
    saveLastSelectedScene("proj-a", "timeline", "walk");
    saveLastSelectedScene("proj-a", "home", "scene-1");
    saveLastSelectedScene("proj-a", "setup", "scene-1");
    expect(loadLastSelectedScene("proj-a", "timeline")).toBe("walk");
  });

  it("scopes remembered scenes to the project and workspace", () => {
    saveLastSelectedScene("proj-a", "timeline", "walk");
    saveLastSelectedScene("proj-b", "timeline", "other");
    expect(loadLastSelectedScene("proj-a", "timeline")).toBe("walk");
    expect(loadLastSelectedScene("proj-b", "timeline")).toBe("other");
    expect(loadLastSelectedScene("proj-a", "audiostudio")).toBeNull();
  });

  it("shares Timeline aliases under one persist key", () => {
    saveLastSelectedScene("proj-a", "director", "walk");
    expect(persistWorkspaceKey("director")).toBe("timeline");
    expect(loadLastSelectedScene("proj-a", "timeline")).toBe("walk");
    expect(loadLastSelectedScene("proj-a", "one")).toBe("walk");
  });

  it("clears an invalid remembered scene without affecting another project", () => {
    saveLastSelectedScene("proj-a", "timeline", "walk");
    saveLastSelectedScene("proj-b", "timeline", "keep");
    clearLastSelectedScene("proj-a", "timeline");
    expect(loadLastSelectedScene("proj-a", "timeline")).toBeNull();
    expect(loadLastSelectedScene("proj-b", "timeline")).toBe("keep");
  });

  it("prunes deleted projects from the scene map", () => {
    saveLastSelectedScene("proj-a", "timeline", "walk");
    saveLastSelectedScene("proj-b", "timeline", "gone");
    expect(pruneSelectedScenes(new Set(["proj-a"]))).toBe(1);
    expect(loadLastSelectedScene("proj-a", "timeline")).toBe("walk");
    expect(loadLastSelectedScene("proj-b", "timeline")).toBeNull();
    expect(store.get(SELECTED_SCENE_STORAGE_KEY)).toContain("proj-a");
  });
});

describe("shareable Timeline search", () => {
  it("writes workspace + sceneId and drops alias keys", () => {
    expect(
      buildTimelineSearch({
        workspace: "timeline",
        sceneId: "walk",
        currentSearch: "?workspace=timeline&scene=old",
      }),
    ).toBe("?workspace=timeline&sceneId=walk");
  });

  it("omits sceneId on the project landing page", () => {
    expect(buildTimelineSearch({ workspace: "home", sceneId: "walk" })).toBe("");
  });

  it("clears a deleted scene id when the replacement is empty", () => {
    expect(
      buildTimelineSearch({
        workspace: "timeline",
        sceneId: "",
        currentSearch: "",
      }),
    ).toBe("?workspace=timeline");
  });

  it("writes the workspace argument it is given", () => {
    expect(
      buildTimelineSearch({
        workspace: "one",
        sceneId: "walk",
        currentSearch: "?workspace=one&scene=old",
      }),
    ).toBe("?workspace=one&sceneId=walk");
  });

  it("preserves workspace=three identity (not rewritten to timeline)", () => {
    expect(
      buildTimelineSearch({
        workspace: "three",
        sceneId: "walk",
        currentSearch: "?workspace=three&scene=old",
      }),
    ).toBe("?workspace=three&sceneId=walk");
  });
});

describe("Co-Director search", () => {
  it("carries project, timeline workspace, and scene", () => {
    expect(
      buildCoDirectorSearch({
        projectId: "proj-1",
        workspace: "director",
        sceneId: "walk",
      }),
    ).toBe("?projectId=proj-1&workspace=timeline&sceneId=walk");
  });

  it("stays unbound without a project id", () => {
    expect(buildCoDirectorSearch({ sceneId: "walk", workspace: "timeline" })).toBe("?workspace=timeline&sceneId=walk");
  });
});
