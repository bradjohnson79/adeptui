import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  loadLastWorkspace,
  loadRecentProjects,
  pruneDeletedProjects,
  pushRecentProject,
  saveLastWorkspace,
} from "./workspacePrefs";

const KEY = "adept_ui_last_workspace";
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

describe("workspace resume prefs", () => {
  it("saves and loads a creative workspace", () => {
    saveLastWorkspace("proj-a", "timeline");
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
  });

  it("does not persist Setup Wizard as the resume destination", () => {
    saveLastWorkspace("proj-a", "scriptwriter");
    saveLastWorkspace("proj-a", "setup");
    expect(loadLastWorkspace("proj-a")).toBe("scriptwriter");
  });

  it("does not persist the project landing page as the resume destination", () => {
    saveLastWorkspace("proj-a", "timeline");
    saveLastWorkspace("proj-a", "home");
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
  });

  it("ignores a previously stored setup tab on load", () => {
    localStorage.setItem(KEY, JSON.stringify({ projectId: "proj-a", tab: "setup" }));
    expect(loadLastWorkspace("proj-a")).toBeNull();
  });

  it("migrates the legacy single-record shape into the per-project map", () => {
    localStorage.setItem(KEY, JSON.stringify({ projectId: "proj-a", tab: "timeline" }));
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
    expect(loadLastWorkspace("proj-b")).toBeNull();
  });

  it("scopes resume prefs to the project id", () => {
    saveLastWorkspace("proj-a", "timeline");
    expect(loadLastWorkspace("proj-b")).toBeNull();
  });

  it("keeps per-project workspace memory isolated (no cross-project contamination)", () => {
    saveLastWorkspace("proj-a", "timeline");
    saveLastWorkspace("proj-b", "scriptwriter");
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
    expect(loadLastWorkspace("proj-b")).toBe("scriptwriter");
    saveLastWorkspace("proj-a", "characters");
    expect(loadLastWorkspace("proj-a")).toBe("characters");
    expect(loadLastWorkspace("proj-b")).toBe("scriptwriter");
  });
});

describe("pruneDeletedProjects", () => {
  it("removes deleted project IDs from the workspace map", () => {
    saveLastWorkspace("proj-a", "timeline");
    saveLastWorkspace("proj-b", "characters");
    saveLastWorkspace("proj-c", "scriptwriter");
    const removed = pruneDeletedProjects(new Set(["proj-a"]));
    expect(removed).toBe(2);
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
    expect(loadLastWorkspace("proj-b")).toBeNull();
    expect(loadLastWorkspace("proj-c")).toBeNull();
  });

  it("removes deleted project IDs from the recent-projects list", () => {
    pushRecentProject("proj-a", "A");
    pushRecentProject("proj-b", "B");
    pushRecentProject("proj-c", "C");
    const removed = pruneDeletedProjects(new Set(["proj-a", "proj-c"]));
    expect(removed).toBe(1);
    const recent = loadRecentProjects();
    // pushRecentProject prepends, so the surviving order is [proj-c, proj-a].
    expect(recent.map((p) => p.id).sort()).toEqual(["proj-a", "proj-c"]);
  });

  it("returns 0 and makes no changes when all IDs are still valid", () => {
    saveLastWorkspace("proj-a", "timeline");
    pushRecentProject("proj-a", "A");
    const removed = pruneDeletedProjects(new Set(["proj-a"]));
    expect(removed).toBe(0);
    expect(loadLastWorkspace("proj-a")).toBe("timeline");
    expect(loadRecentProjects().map((p) => p.id)).toEqual(["proj-a"]);
  });

  it("handles an empty valid set (everything deleted)", () => {
    saveLastWorkspace("proj-a", "timeline");
    pushRecentProject("proj-a", "A");
    pushRecentProject("proj-b", "B");
    const removed = pruneDeletedProjects(new Set());
    expect(removed).toBe(3);
    expect(loadLastWorkspace("proj-a")).toBeNull();
    expect(loadRecentProjects()).toEqual([]);
  });
});
