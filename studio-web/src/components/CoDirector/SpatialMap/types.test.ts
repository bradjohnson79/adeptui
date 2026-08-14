import { describe, expect, it } from "vitest";
import {
  CAMERA_SLOTS,
  CHARACTER_SLOTS,
  PROP_SLOTS,
  SLOT_COLORS,
  characterTag,
  normalizePropTag,
  type ActivePlacement,
  type SlotKind,
} from "./types";

describe("Spatial Map slot contract (Work Order E)", () => {
  it("binds four saved-character slots with unique color keys and indexes 0-3", () => {
    expect(CHARACTER_SLOTS).toHaveLength(4);
    expect(CHARACTER_SLOTS.map((s) => s.index)).toEqual([0, 1, 2, 3]);
    expect(CHARACTER_SLOTS.every((s) => s.kind === "character")).toBe(true);
    const colors = CHARACTER_SLOTS.map((s) => s.colorKey);
    expect(new Set(colors).size).toBe(4);
    for (const key of colors) expect(SLOT_COLORS[key]).toMatch(/^#/);
  });

  it("gives props four parallel slots with a disjoint color set", () => {
    expect(PROP_SLOTS).toHaveLength(4);
    expect(PROP_SLOTS.map((s) => s.index)).toEqual([0, 1, 2, 3]);
    expect(PROP_SLOTS.every((s) => s.kind === "prop")).toBe(true);
    const charColors = new Set(CHARACTER_SLOTS.map((s) => s.colorKey));
    for (const slot of PROP_SLOTS) {
      expect(charColors.has(slot.colorKey)).toBe(false);
      expect(SLOT_COLORS[slot.colorKey]).toBeDefined();
    }
  });

  it("exposes four camera slots C1-C4", () => {
    expect(CAMERA_SLOTS).toHaveLength(4);
    expect(CAMERA_SLOTS.map((s) => s.index)).toEqual([0, 1, 2, 3]);
    expect(CAMERA_SLOTS.every((s) => s.kind === "camera")).toBe(true);
    expect(CAMERA_SLOTS.map((s) => s.label)).toEqual(["C1", "C2", "C3", "C4"]);
  });

  it("ActivePlacement names the active object by type, slot, and entityId", () => {
    const kinds: SlotKind[] = ["character", "prop", "camera"];
    const active: ActivePlacement[] = kinds.map((type, slot) => ({
      type,
      slot,
      entityId: `entity-${type}`,
    }));
    expect(active[0]).toEqual({ type: "character", slot: 0, entityId: "entity-character" });
    expect(active[1]).toEqual({ type: "prop", slot: 1, entityId: "entity-prop" });
    expect(active[2]).toEqual({ type: "camera", slot: 2, entityId: "entity-camera" });
  });

  it("normalizePropTag and characterTag match the Amendment #5 helpers", () => {
    expect(normalizePropTag("Coffee Cup")).toBe("coffee-cup");
    expect(normalizePropTag("  ##Hello!!  ")).toBe("hello");
    expect(normalizePropTag("   ")).toBe("prop");
    expect(characterTag("Ada")).toBe("@Ada");
    expect(characterTag("  ")).toBe("");
  });
});
