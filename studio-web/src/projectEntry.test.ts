import assert from "node:assert/strict";
import test from "node:test";

import {
  buildPendingProjectCancelDestination,
  buildHomeCreateProjectPath,
  buildPendingProjectDestination,
  buildSetupPendingEntry,
  getEligibleProjectId,
  readPendingProjectEntry,
} from "./projectEntry.ts";

function installStorage(initial: Record<string, string> = {}) {
  const store = new Map(Object.entries(initial));
  const localStorage = {
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: localStorage,
  });
  return store;
}

test("getEligibleProjectId skips archived projects and clears stale recent ids", () => {
  const recentKey = "adept_ui_recent_projects";
  const store = installStorage({
    [recentKey]: JSON.stringify([
      { id: "missing-project", name: "Missing" },
      { id: "archived-project", name: "Archived" },
      { id: "live-project", name: "Live" },
    ]),
  });

  const projectId = getEligibleProjectId([
    { id: "archived-project", archived: 1 },
    { id: "live-project", archived: 0 },
    { id: "backup-project", archived: 0 },
  ]);

  assert.equal(projectId, "live-project");
  assert.deepEqual(JSON.parse(store.get(recentKey) || "[]"), [{ id: "live-project", name: "Live" }]);
});

test("getEligibleProjectId does not wipe recent projects while the list is still loading", () => {
  const recentKey = "adept_ui_recent_projects";
  const store = installStorage({
    [recentKey]: JSON.stringify([{ id: "live-project", name: "Live" }]),
  });

  const projectId = getEligibleProjectId([]);

  assert.equal(projectId, "live-project");
  assert.deepEqual(JSON.parse(store.get(recentKey) || "[]"), [{ id: "live-project", name: "Live" }]);
});

test("buildHomeCreateProjectPath round-trips a co-director pending entry", () => {
  const path = buildHomeCreateProjectPath({
    suggestedName: "Dreamweaver",
    pendingEntry: { kind: "co-director", returnTo: "/co-director?projectId=demo" },
  });

  const params = new URL(path, "http://localhost").searchParams;
  assert.equal(params.get("create"), "1");
  assert.equal(params.get("createName"), "Dreamweaver");
  assert.deepEqual(readPendingProjectEntry(params), {
    kind: "co-director",
    returnTo: "/co-director?projectId=demo",
  });
});

test("buildSetupPendingEntry converts setup query params into a pending entry", () => {
  const params = new URLSearchParams({
    setupMode: "ai_guided",
    setupComponent: "flux1_dev_local",
    setupSource: "workspace_launch",
    pendingReturnTo: "/project/source?workspace=home",
  });

  assert.deepEqual(buildSetupPendingEntry(params), {
    kind: "setup",
    setupMode: "ai_guided",
    setupComponent: "flux1_dev_local",
    setupSource: "workspace_launch",
    returnTo: "/project/source?workspace=home",
  });
});

test("buildPendingProjectDestination resumes setup and workspace destinations", () => {
  assert.equal(
    buildPendingProjectDestination("proj-123", {
      kind: "setup",
      setupMode: "ai_guided",
      setupComponent: "hunyuan_video_13b",
      setupSource: "workspace_launch",
    }),
    "/project/proj-123?setupMode=ai_guided&setupComponent=hunyuan_video_13b&setupSource=workspace_launch&workspace=setup#ai-guided-setup-heading",
  );

  assert.equal(
    buildPendingProjectDestination("proj-123", { kind: "project", workspace: "timeline" }),
    "/project/proj-123?workspace=timeline",
  );
});

test("buildPendingProjectCancelDestination prefers sanitized in-app return paths", () => {
  assert.equal(
    buildPendingProjectCancelDestination({
      kind: "project",
      returnTo: "/project/source?workspace=timeline",
    }),
    "/project/source?workspace=timeline",
  );
  assert.equal(
    buildPendingProjectCancelDestination({ kind: "project", returnTo: "https://example.com" }),
    "/",
  );
});
