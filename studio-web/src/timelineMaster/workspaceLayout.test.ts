import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_LEFT_WIDTH,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_TIMELINE_WORKSPACE,
  DEFAULT_VIEWER_HEIGHT,
  LEFT_PANE_MAX,
  LEFT_PANE_MIN,
  MIN_MONITOR_HEIGHT,
  RIGHT_PANE_MAX,
  RIGHT_PANE_MIN,
  TIMELINE_REGION_MIN_PX,
  TIMELINE_WORKSPACE_KEY,
  clampDrawerWidth,
  clampSidebarWidths,
  clampViewerHeight,
  loadTimelineWorkspaceLayout,
  previewHeightStorageKey,
  resetTimelineWorkspaceLayout,
  viewerHeightBounds,
} from "./workspaceLayout.ts";

test("preview height storage key is project-scoped", () => {
  assert.equal(previewHeightStorageKey("proj-1"), "adept-ui.timeline.preview-height.proj-1");
  assert.equal(previewHeightStorageKey(""), "adept-ui.timeline.preview-height.global");
  assert.equal(previewHeightStorageKey(null), "adept-ui.timeline.preview-height.global");
});

test("viewerHeightBounds leave room for toolbar + compact timeline", () => {
  const { min, max } = viewerHeightBounds(1000, 1920);
  assert.ok(min >= MIN_MONITOR_HEIGHT);
  assert.ok(max <= 1000 - TIMELINE_REGION_MIN_PX);
  assert.ok(max > min);
  assert.ok(DEFAULT_VIEWER_HEIGHT >= 0.4 && DEFAULT_VIEWER_HEIGHT <= 0.5);
});

test("clampViewerHeight clamps below min and above max", () => {
  const { min, max } = viewerHeightBounds(900, 1440);
  assert.equal(clampViewerHeight(10, 900, 1440), min);
  assert.equal(clampViewerHeight(10_000, 900, 1440), max);
  assert.equal(clampViewerHeight((min + max) / 2, 900, 1440), Math.round((min + max) / 2));
});

test("out-of-range persisted heights clamp to current viewport", () => {
  const containerHeight = 800;
  const viewportWidth = 1366;
  const { max } = viewerHeightBounds(containerHeight, viewportWidth);
  const restored = clampViewerHeight(containerHeight * 0.95, containerHeight, viewportWidth);
  assert.equal(restored, max);
  assert.ok(restored <= containerHeight - TIMELINE_REGION_MIN_PX);
});

test("sidebar widths clamp to pane limits without rewriting the other side", () => {
  assert.equal(clampSidebarWidths(10, 10).leftWidth, LEFT_PANE_MIN);
  assert.equal(clampSidebarWidths(10, 10).rightWidth, RIGHT_PANE_MIN);
  assert.equal(clampSidebarWidths(900, 900).leftWidth, LEFT_PANE_MAX);
  assert.equal(clampSidebarWidths(900, 900).rightWidth, RIGHT_PANE_MAX);
  assert.equal(clampSidebarWidths(DEFAULT_LEFT_WIDTH, DEFAULT_RIGHT_WIDTH).leftWidth, DEFAULT_LEFT_WIDTH);
  assert.equal(clampSidebarWidths(DEFAULT_LEFT_WIDTH, DEFAULT_RIGHT_WIDTH).rightWidth, DEFAULT_RIGHT_WIDTH);
  const tight = clampSidebarWidths(440, 500, 900);
  assert.equal(tight.leftWidth, 440);
  assert.equal(tight.rightWidth, 500);
});

test("clampDrawerWidth clamps only that side to pane min/max", () => {
  assert.equal(clampDrawerWidth("left", 10), LEFT_PANE_MIN);
  assert.equal(clampDrawerWidth("left", 900), LEFT_PANE_MAX);
  assert.equal(clampDrawerWidth("left", 400), 400);
  assert.equal(clampDrawerWidth("right", 10), RIGHT_PANE_MIN);
  assert.equal(clampDrawerWidth("right", 900), RIGHT_PANE_MAX);
  assert.equal(clampDrawerWidth("right", 390), 390);
});

function fakeLayoutStorage(json?: string) {
  const map = new Map<string, string>();
  if (json) map.set(TIMELINE_WORKSPACE_KEY, json);
  globalThis.localStorage = {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => {
      map.set(k, v);
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
    clear: () => map.clear(),
    key: () => null,
    length: 0,
  } as Storage;
}

test("missing drawer open flags default to both closed", () => {
  fakeLayoutStorage(JSON.stringify({ leftWidth: 300, rightWidth: 340 }));
  const loaded = loadTimelineWorkspaceLayout();
  assert.equal(loaded.leftDrawerOpen, false);
  assert.equal(loaded.rightDrawerOpen, false);
  assert.equal(loaded.leftWidth, 300);
  assert.equal(loaded.rightWidth, 340);
  assert.equal(DEFAULT_TIMELINE_WORKSPACE.leftDrawerOpen, false);
  assert.equal(DEFAULT_TIMELINE_WORKSPACE.rightDrawerOpen, false);
});

test("explicit open drawer flags survive load", () => {
  fakeLayoutStorage(JSON.stringify({ leftDrawerOpen: true, rightDrawerOpen: false, leftWidth: 280, rightWidth: 390 }));
  const loaded = loadTimelineWorkspaceLayout();
  assert.equal(loaded.leftDrawerOpen, true);
  assert.equal(loaded.rightDrawerOpen, false);
  assert.equal(loaded.rightWidth, 390);
});

test("reset layout closes both drawers and restores default widths", () => {
  fakeLayoutStorage(JSON.stringify({ leftDrawerOpen: true, rightDrawerOpen: true, leftWidth: 400, rightWidth: 420 }));
  const reset = resetTimelineWorkspaceLayout();
  assert.equal(reset.leftDrawerOpen, false);
  assert.equal(reset.rightDrawerOpen, false);
  assert.equal(reset.leftWidth, DEFAULT_LEFT_WIDTH);
  assert.equal(reset.rightWidth, DEFAULT_RIGHT_WIDTH);
});
