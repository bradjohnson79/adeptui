import { describe, expect, it } from "vitest";
import {
  DEFAULT_LAYOUT,
  validateMagiLayout,
  loadMagiLayout,
  applyPreset,
} from "./MagiLayoutPersistence";

describe("MagiLayoutPersistence", () => {
  it("DEFAULT_LAYOUT ships Clip Properties and Export accordions instead of Metadata", () => {
    const state = DEFAULT_LAYOUT.accordionState;
    expect(state.clipProperties).toBe(false);
    expect(state.export).toBe(false);
    expect(state).not.toHaveProperty("metadata");
  });

  it("migrates legacy Metadata accordion state into Clip Properties", () => {
    const legacy = {
      schemaVersion: 1,
      leftPaneOrder: ["project", "media", "actions"],
      rightPaneOrder: ["inspector"],
      leftDockWidth: 280,
      rightDockWidth: 300,
      timelineHeight: 280,
      accordionState: { metadata: true, transform: true },
    };
    const layout = validateMagiLayout(legacy);
    expect(layout).not.toBeNull();
    expect(layout!.accordionState.clipProperties).toBe(true);
    expect(layout!.accordionState.transform).toBe(true);
  });

  it("rejects invalid layouts", () => {
    expect(validateMagiLayout(null)).toBeNull();
    expect(validateMagiLayout({ schemaVersion: 99 })).toBeNull();
    expect(validateMagiLayout({ schemaVersion: 1 })).toBeNull();
    expect(validateMagiLayout("not-an-object")).toBeNull();
  });

  it("falls back to defaults when persisted state is unavailable", () => {
    const layout = loadMagiLayout();
    expect(layout.schemaVersion).toBe(1);
    expect(layout.accordionState.clipProperties).toBe(false);
    expect(layout.accordionState.export).toBe(false);
    expect(layout.accordionState.transform).toBe(true);
  });

  it("compare-review preset keeps Clip Properties expanded", () => {
    const layout = applyPreset("compare-review", { ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } });
    expect(layout.accordionState.compare).toBe(true);
    expect(layout.accordionState.clipProperties).toBe(true);
  });
});
