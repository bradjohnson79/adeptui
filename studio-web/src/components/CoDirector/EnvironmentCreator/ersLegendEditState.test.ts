import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  clearErsLegendEditState,
  clampDirectionMovementText,
  finalizeDirectionMovementText,
  createDefaultErsLegendSnapshot,
  dropLiveErsLegendEditState,
  ersLegendStateKey,
  loadErsLegendEditState,
  saveErsLegendEditState,
  ersLegendEditHasUnsavedChanges,
  updateErsLegendEditState,
} from "./ersLegendEditState";
import { defaultErsLegendBox } from "./ersSheetLayout";

const key = ersLegendStateKey({
  projectId: "proj-test",
  sheetId: "sheet-test",
  sourceAssetId: "asset-test",
});

afterEach(() => {
  clearErsLegendEditState(key);
});

describe("ERS legend edit state persistence", () => {
  it("builds a stable state key from project/sheet/asset", () => {
    expect(key).toBe("ers-legend:proj-test:sheet-test:asset-test");
  });

  it("defaults to the center-column Legend box", () => {
    const snap = loadErsLegendEditState(key);
    expect(snap.position).toEqual(defaultErsLegendBox());
    expect(snap.userMoved).toBe(false);
    expect(snap.characters).toHaveLength(4);
    expect(snap.props).toHaveLength(4);
    expect(snap.directionMovement).toBe("");
  });

  it("persists Direction/Movement and clamps to 50 words", () => {
    const words = Array.from({ length: 55 }, (_, i) => `w${i}`).join(" ");
    expect(clampDirectionMovementText(words).match(/\S+/g)).toHaveLength(50);
    updateErsLegendEditState(key, { directionMovement: "Hero crosses left to the bar" });
    const committed = saveErsLegendEditState(key);
    dropLiveErsLegendEditState(key);
    expect(loadErsLegendEditState(key).directionMovement).toBe("Hero crosses left to the bar");
    expect(committed.directionMovement).toBe("Hero crosses left to the bar");
  });

  it("preserves spaces and newlines while typing (no whitespace collapse)", () => {
    expect(clampDirectionMovementText("Hero  crosses ")).toBe("Hero  crosses ");
    expect(clampDirectionMovementText("Line one\n\nLine two")).toBe("Line one\n\nLine two");
    expect(clampDirectionMovementText("  leading")).toBe("  leading");
    // Paste with multi-space preserved under the word cap
    expect(clampDirectionMovementText("A    B    C")).toBe("A    B    C");
    // Finalize only trims ends
    expect(finalizeDirectionMovementText("  Hero  crosses  ")).toBe("Hero  crosses");
  });

  it("keeps live drag position across load without Save", () => {
    updateErsLegendEditState(key, (prev) => ({
      ...prev,
      position: { ...prev.position, left: 0.05, top: 0.1 },
      userMoved: true,
      characters: prev.characters.map((slot, i) => (i === 0 ? { ...slot, label: "Maya" } : slot)),
    }));
    const again = loadErsLegendEditState(key);
    expect(again.position.left).toBeCloseTo(0.05);
    expect(again.position.top).toBeCloseTo(0.1);
    expect(again.userMoved).toBe(true);
    expect(again.characters[0].label).toBe("Maya");
  });

  it("Save commits labels, colors, and position for reload", () => {
    const base = createDefaultErsLegendSnapshot();
    updateErsLegendEditState(key, {
      ...base,
      position: { left: 0.7, top: 0.55, width: 0.16, height: 0.3 },
      userMoved: true,
      characters: base.characters.map((slot, i) =>
        i === 1 ? { ...slot, label: "Rex", color: "#ef4444" } : slot,
      ),
      props: base.props.map((slot, i) =>
        i === 0 ? { ...slot, label: "Mug", color: "#22d3ee" } : slot,
      ),
    });
    const committed = saveErsLegendEditState(key);
    dropLiveErsLegendEditState(key);
    const reloaded = loadErsLegendEditState(key);
    expect(reloaded.position.left).toBeCloseTo(committed.position.left);
    expect(reloaded.position.top).toBeCloseTo(committed.position.top);
    expect(reloaded.characters[1].label).toBe("Rex");
    expect(reloaded.props[0].label).toBe("Mug");
    expect(reloaded.userMoved).toBe(true);
  });
});


describe("ersLegendEditHasUnsavedChanges", () => {
  const key = "ers-legend:p:s:a";
  beforeEach(() => clearErsLegendEditState(key));
  it("is false for defaults", () => {
    loadErsLegendEditState(key);
    expect(ersLegendEditHasUnsavedChanges(key)).toBe(false);
  });
  it("is true after move until Save", () => {
    updateErsLegendEditState(key, (prev) => ({
      ...prev,
      position: { ...prev.position, left: 0.1 },
      userMoved: true,
    }));
    expect(ersLegendEditHasUnsavedChanges(key)).toBe(true);
    saveErsLegendEditState(key);
    expect(ersLegendEditHasUnsavedChanges(key)).toBe(false);
  });
});

