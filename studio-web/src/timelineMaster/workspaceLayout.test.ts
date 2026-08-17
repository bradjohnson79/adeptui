import assert from "node:assert/strict";
import test from "node:test";
import {
  CENTER_PANE_MIN,
  DEFAULT_LEFT_WIDTH,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_VIEWER_HEIGHT,
  LEFT_PANE_MAX,
  LEFT_PANE_MIN,
  MIN_MONITOR_HEIGHT,
  RIGHT_PANE_MAX,
  RIGHT_PANE_MIN,
  TIMELINE_REGION_MIN_PX,
  clampSidebarWidths,
  clampViewerHeight,
  previewHeightStorageKey,
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

test("sidebar widths clamp to pane limits", () => {
  assert.equal(clampSidebarWidths(10, 10).leftWidth, LEFT_PANE_MIN);
  assert.equal(clampSidebarWidths(10, 10).rightWidth, RIGHT_PANE_MIN);
  assert.equal(clampSidebarWidths(900, 900).leftWidth, LEFT_PANE_MAX);
  assert.equal(clampSidebarWidths(900, 900).rightWidth, RIGHT_PANE_MAX);
  assert.equal(clampSidebarWidths(DEFAULT_LEFT_WIDTH, DEFAULT_RIGHT_WIDTH).leftWidth, DEFAULT_LEFT_WIDTH);
  assert.equal(clampSidebarWidths(DEFAULT_LEFT_WIDTH, DEFAULT_RIGHT_WIDTH).rightWidth, DEFAULT_RIGHT_WIDTH);
});

test("sidebar widths keep a usable center column", () => {
  const next = clampSidebarWidths(440, 500, 1200);
  assert.ok(next.leftWidth + next.rightWidth <= 1200 - CENTER_PANE_MIN);
  assert.ok(next.leftWidth >= LEFT_PANE_MIN);
  assert.ok(next.rightWidth >= RIGHT_PANE_MIN);
});
