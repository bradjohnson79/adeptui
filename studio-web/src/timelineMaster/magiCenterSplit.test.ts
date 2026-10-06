import { describe, expect, it } from "vitest";
import {
  MAGI_CENTER_SPLIT_KEY,
  MAGI_DEFAULT_VIEWER_RATIO,
  MAGI_REGION_MIN_PX,
  MAGI_VIEWER_MIN_PX,
  TIMELINE_WORKSPACE_KEY,
  clampMagiViewerHeight,
  loadMagiCenterSplit,
  loadMagiProjectPreviewHeightRatio,
  magiPreviewHeightStorageKey,
  magiViewerHeightBounds,
  previewHeightStorageKey,
  resetMagiCenterSplit,
  resolveMagiViewerHeight,
} from "./workspaceLayout";

function fakeStorage() {
  const map = new Map<string, string>();
  (globalThis as { localStorage?: Storage }).localStorage = {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
    clear: () => map.clear(),
    key: () => null,
    length: 0,
  } as Storage;
}

describe("MAGI center split isolation", () => {
  it("does not share Timeline Large Viewer keys", () => {
    expect(magiPreviewHeightStorageKey("proj-1")).toBe("adept-ui.magi.preview-height.proj-1");
    expect(magiPreviewHeightStorageKey("proj-1")).not.toBe(previewHeightStorageKey("proj-1"));
    expect(MAGI_CENTER_SPLIT_KEY).not.toBe(TIMELINE_WORKSPACE_KEY);
  });

  it("keeps the MAGI viewer floor and four-track floor when the center is tall enough", () => {
    const bounds = magiViewerHeightBounds(800);
    expect(bounds.min).toBe(MAGI_VIEWER_MIN_PX);
    expect(bounds.max).toBe(800 - MAGI_REGION_MIN_PX);
    expect(clampMagiViewerHeight(10, 800)).toBe(MAGI_VIEWER_MIN_PX);
  });

  it("reset restores the balanced MAGI ratio", () => {
    fakeStorage();
    expect(resetMagiCenterSplit("proj-1").viewerHeight).toBe(MAGI_DEFAULT_VIEWER_RATIO);
    expect(MAGI_DEFAULT_VIEWER_RATIO).toBe(0.62);
  });

  it("rests the preview in the 60–70% band and adopts a legacy split once", () => {
    fakeStorage();
    localStorage.setItem(MAGI_CENTER_SPLIT_KEY, JSON.stringify({ viewerHeight: 0.5958 }));
    localStorage.setItem(magiPreviewHeightStorageKey("proj-1"), "0.5958");
    expect(loadMagiCenterSplit().viewerHeight).toBe(0.62);
    expect(loadMagiProjectPreviewHeightRatio("proj-1")).toBe(0.62);
    localStorage.setItem(magiPreviewHeightStorageKey("proj-1"), "0.6");
    expect(loadMagiProjectPreviewHeightRatio("proj-1")).toBe(0.6);
    expect(resolveMagiViewerHeight(0.62, 1100)).toBe(682);
    expect(resolveMagiViewerHeight(0.7, 663)).toBe(663 - MAGI_REGION_MIN_PX);
  });
});
