import assert from "node:assert/strict";
import test from "node:test";
import {
  DEFAULT_VIEWER_HEIGHT,
  MIN_MONITOR_HEIGHT,
  TIMELINE_REGION_MIN_PX,
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
