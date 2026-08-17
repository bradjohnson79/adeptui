import assert from "node:assert/strict";
import test from "node:test";
import {
  CENTER_PANE_MIN,
  DEFAULT_LEFT_WIDTH,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_TIMELINE_WORKSPACE,
  DEFAULT_VIEWER_HEIGHT,
  DRAWER_HANDLE_WIDTH,
  DRAWER_SPLITTER_WIDTH,
  LEFT_PANE_MAX,
  LEFT_PANE_MIN,
  MIN_MONITOR_HEIGHT,
  RIGHT_PANE_MAX,
  RIGHT_PANE_MIN,
  TIMELINE_REGION_MIN_PX,
  TIMELINE_WORKSPACE_KEY,
  clampPushedDrawerWidth,
  clampSidebarWidths,
  clampViewerHeight,
  loadTimelineWorkspaceLayout,
  previewHeightStorageKey,
  resolveDrawerChrome,
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

test("sidebar widths clamp to pane limits without shrinking stored widths for center", () => {
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

test("pushed drawer drag keeps center usable without rewriting the other width", () => {
  const roomy = clampPushedDrawerWidth({
    side: "left",
    proposed: 440,
    otherWidth: 320,
    otherPushing: true,
    containerWidth: 1600,
  });
  assert.equal(roomy, 440);
  const squeezed = clampPushedDrawerWidth({
    side: "left",
    proposed: 440,
    otherWidth: 320,
    otherPushing: true,
    containerWidth: 1200,
  });
  assert.equal(squeezed, 1200 - DRAWER_HANDLE_WIDTH * 2 - (320 + DRAWER_SPLITTER_WIDTH) - CENTER_PANE_MIN - DRAWER_SPLITTER_WIDTH);
  assert.ok(squeezed < 440);
  assert.ok(squeezed >= LEFT_PANE_MIN);
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

test("missing drawer open flags default to both open", () => {
  fakeLayoutStorage(JSON.stringify({ leftWidth: 300, rightWidth: 340 }));
  const loaded = loadTimelineWorkspaceLayout();
  assert.equal(loaded.leftDrawerOpen, true);
  assert.equal(loaded.rightDrawerOpen, true);
  assert.equal(loaded.leftWidth, 300);
  assert.equal(loaded.rightWidth, 340);
  assert.equal(DEFAULT_TIMELINE_WORKSPACE.leftDrawerOpen, true);
  assert.equal(DEFAULT_TIMELINE_WORKSPACE.rightDrawerOpen, true);
});

test("explicit closed drawer flags survive load", () => {
  fakeLayoutStorage(JSON.stringify({ leftDrawerOpen: false, rightDrawerOpen: true, leftWidth: 280, rightWidth: 390 }));
  const loaded = loadTimelineWorkspaceLayout();
  assert.equal(loaded.leftDrawerOpen, false);
  assert.equal(loaded.rightDrawerOpen, true);
  assert.equal(loaded.rightWidth, 390);
});

test("resolveDrawerChrome pushes both drawers when the center still fits", () => {
  const chrome = resolveDrawerChrome({
    containerWidth: 1600,
    leftOpen: true,
    rightOpen: true,
    leftWidth: 280,
    rightWidth: 320,
    lastActivatedSide: "right",
  });
  assert.equal(chrome.leftPlacement, "push");
  assert.equal(chrome.rightPlacement, "push");
  assert.equal(chrome.leftColumnPx, 280);
  assert.equal(chrome.rightColumnPx, 320);
  assert.ok(chrome.gridTemplateColumns.includes(`minmax(${CENTER_PANE_MIN}px, 1fr)`));
});

test("resolveDrawerChrome prefers the last-activated drawer in push when both cannot coexist", () => {
  const containerWidth = DRAWER_HANDLE_WIDTH * 2 + CENTER_PANE_MIN + 280 + DRAWER_SPLITTER_WIDTH + 40;
  const chrome = resolveDrawerChrome({
    containerWidth,
    leftOpen: true,
    rightOpen: true,
    leftWidth: 280,
    rightWidth: 320,
    lastActivatedSide: "left",
  });
  assert.equal(chrome.leftPlacement, "push");
  assert.equal(chrome.rightPlacement, "overlay");
  assert.equal(chrome.leftColumnPx, 280);
  assert.equal(chrome.rightColumnPx, 0);
});

test("resolveDrawerChrome overlays both when neither side can push", () => {
  const chrome = resolveDrawerChrome({
    containerWidth: CENTER_PANE_MIN + DRAWER_HANDLE_WIDTH * 2 + 40,
    leftOpen: true,
    rightOpen: true,
    leftWidth: 280,
    rightWidth: 320,
    lastActivatedSide: "right",
  });
  assert.equal(chrome.leftPlacement, "overlay");
  assert.equal(chrome.rightPlacement, "overlay");
  assert.equal(chrome.leftColumnPx, 0);
  assert.equal(chrome.rightColumnPx, 0);
});

test("resolveDrawerChrome keeps overlay until the hysteresis band clears", () => {
  const leftCost = 280 + DRAWER_SPLITTER_WIDTH;
  const budgetExact = leftCost;
  const containerWidth = budgetExact + DRAWER_HANDLE_WIDTH * 2 + CENTER_PANE_MIN;
  const previous = { leftPlacement: "overlay" as const, rightPlacement: "closed" as const };
  const stillOverlay = resolveDrawerChrome({
    containerWidth,
    leftOpen: true,
    rightOpen: false,
    leftWidth: 280,
    rightWidth: 320,
    previous,
  });
  assert.equal(stillOverlay.leftPlacement, "overlay");
  const wide = resolveDrawerChrome({
    containerWidth: containerWidth + 80,
    leftOpen: true,
    rightOpen: false,
    leftWidth: 280,
    rightWidth: 320,
    previous,
  });
  assert.equal(wide.leftPlacement, "push");
});

test("resolveDrawerChrome does not change persisted widths", () => {
  const chrome = resolveDrawerChrome({
    containerWidth: 900,
    leftOpen: true,
    rightOpen: true,
    leftWidth: 400,
    rightWidth: 420,
    lastActivatedSide: "right",
  });
  assert.ok(chrome.leftPlacement === "overlay" || chrome.rightPlacement === "overlay");
  assert.ok(chrome.leftColumnPx === 0 || chrome.leftColumnPx === 400);
  assert.ok(chrome.rightColumnPx === 0 || chrome.rightColumnPx === 420);
});
