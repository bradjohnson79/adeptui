import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_PANE_WIDTHS,
  PANE_LIMITS,
  clampPaneWidths,
  readPaneWidths,
  resetPaneWidths,
  writePaneWidths,
} from "./sceneCreatorPanes";

describe("sceneCreatorPanes", () => {
  const store = new Map<string, string>();

  beforeEach(() => {
    store.clear();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clamps to min and max", () => {
    expect(clampPaneWidths({ left: 10, right: 10 })).toEqual({
      left: PANE_LIMITS.leftMin,
      right: PANE_LIMITS.rightMin,
    });
    expect(clampPaneWidths({ left: 999, right: 999 })).toEqual({
      left: PANE_LIMITS.leftMax,
      right: PANE_LIMITS.rightMax,
    });
  });

  it("persists and resets to default", () => {
    writePaneWidths({ left: 300, right: 320 });
    expect(readPaneWidths()).toEqual({ left: 300, right: 320 });
    expect(resetPaneWidths()).toEqual({ ...DEFAULT_PANE_WIDTHS });
    expect(readPaneWidths()).toEqual({ ...DEFAULT_PANE_WIDTHS });
  });
});
