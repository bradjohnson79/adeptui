import { describe, expect, it } from "vitest";
import {
  ATTACHED_CHARACTER_SLOTS,
  ATTACHMENT_POINTS,
  CAMERA_SLOTS,
  CHARACTER_SLOTS,
  PLACEMENT_MODES,
  PROP_RELATIONSHIPS,
  PROP_SLOTS,
  SLOT_COLORS,
  attachedSlotFromSlotIndex,
  characterTag,
  normalizePropAttachment,
  normalizePropTag,
  propPlacementIdentity,
  slotIndexFromAttachedSlot,
  validatePropAttachment,
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

describe("Spatial Map character-prop attachment contract", () => {
  it("freezes field names and enums identically to the Python contract", () => {
    expect(PLACEMENT_MODES).toEqual(["independent", "attached"]);
    expect(PROP_RELATIONSHIPS).toEqual([
      "held",
      "carried",
      "worn",
      "using",
      "interacting",
      "associated",
    ]);
    expect(ATTACHMENT_POINTS).toEqual([
      "left_hand",
      "right_hand",
      "both_hands",
      "head",
      "upper_body",
      "lower_body",
      "back",
      "waist",
      "wrist",
      "shoulder",
      "unspecified",
    ]);
    expect(ATTACHED_CHARACTER_SLOTS).toEqual([1, 2, 3, 4]);
  });

  it("defaults missing fields to independent on read", () => {
    const incoming = { propId: "coffee-1" };
    const prop = Object.assign(incoming, normalizePropAttachment({}));
    expect(prop.placementMode).toBe("independent");
    expect(prop.attachedCharacterSlot).toBeNull();
    expect(prop.attachedCharacterId).toBeNull();
    expect(prop.relationship).toBeNull();
    expect(prop.attachmentPoint).toBeNull();
    expect(prop.propId).toBe("coffee-1");
  });

  it("attaches Korri coffee held right_hand without a fake grid marker", () => {
    const prop = validatePropAttachment({
      propId: "coffee-1",
      placementMode: "attached",
      attachedCharacterId: "korri",
      attachedCharacterSlot: 1,
      relationship: "held",
      attachmentPoint: "right_hand",
    });
    expect(prop.propId).toBe("coffee-1");
    expect(prop.placementMode).toBe("attached");
    expect(prop.attachedCharacterId).toBe("korri");
    expect(prop.attachedCharacterSlot).toBe(1);
    expect(prop.relationship).toBe("held");
    expect(prop.attachmentPoint).toBe("right_hand");
    expect("normalizedX" in prop ? (prop as { normalizedX?: number }).normalizedX : undefined).toBeUndefined();
  });

  it("XOR: independent clears attachment fields; attached without character+relationship rejects", () => {
    const cleared = validatePropAttachment({
      placementMode: "independent",
      attachedCharacterId: "korri",
      attachedCharacterSlot: 1,
      relationship: "held",
      attachmentPoint: "right_hand",
    });
    expect(cleared.placementMode).toBe("independent");
    expect(cleared.attachedCharacterId).toBeNull();
    expect(cleared.attachedCharacterSlot).toBeNull();
    expect(cleared.relationship).toBeNull();
    expect(cleared.attachmentPoint).toBeNull();

    expect(() => validatePropAttachment({ placementMode: "attached" })).toThrow(/attachedCharacterId or attachedCharacterSlot/);
    expect(() =>
      validatePropAttachment({ placementMode: "attached", relationship: "held" }),
    ).toThrow(/attachedCharacterId or attachedCharacterSlot/);
    expect(() =>
      validatePropAttachment({ placementMode: "attached", attachedCharacterId: "korri" }),
    ).toThrow(/relationship/);
    expect(() =>
      validatePropAttachment({
        placementMode: "attached",
        attachedCharacterSlot: 0,
        relationship: "held",
      }),
    ).toThrow(/1-4/);
  });

  it("backward compat: legacy props keep physical positions and become independent", () => {
    const legacy = {
      propId: "coffee-1",
      label: "Coffee",
      x: 1.5,
      z: -2.0,
      normalizedX: 0.25,
      normalizedY: -0.4,
      gridRow: 3,
      gridColumn: 6,
      slotIndex: 0,
    };
    const prop = normalizePropAttachment({ ...legacy });
    expect(prop.placementMode).toBe("independent");
    expect(prop.x).toBe(1.5);
    expect(prop.z).toBe(-2.0);
    expect(prop.normalizedX).toBe(0.25);
    expect(prop.normalizedY).toBe(-0.4);
    expect(prop.gridRow).toBe(3);
    expect(prop.gridColumn).toBe(6);
    expect(prop.slotIndex).toBe(0);
  });

  it("maps slotIndex 0-3 to attachedCharacterSlot 1-4 and never the reverse mix", () => {
    expect(CHARACTER_SLOTS.map((s) => s.index)).toEqual([0, 1, 2, 3]);
    expect(attachedSlotFromSlotIndex(0)).toBe(1);
    expect(attachedSlotFromSlotIndex(3)).toBe(4);
    expect(attachedSlotFromSlotIndex(4)).toBeNull();
    expect(slotIndexFromAttachedSlot(1)).toBe(0);
    expect(slotIndexFromAttachedSlot(4)).toBe(3);
    expect(CHARACTER_SLOTS[0].label).toMatch(/Character 1/);
  });
});

describe("Spatial Map project vs character prop identity", () => {
  it("writes PropEntity.id into propId and tags category=project", () => {
    const placed = propPlacementIdentity({ id: "prop-entity-1", source: "project" });
    expect(placed.propId).toBe("prop-entity-1");
    expect(placed.category).toBe("project");
  });

  it("does not write CharacterPropRow.id into propId", () => {
    const placed = propPlacementIdentity({ id: "character-prop-row-9", source: "character" });
    expect(placed.propId).toBeNull();
    expect(placed.category).toBe("character_prop");
    expect(placed.propId).not.toBe("character-prop-row-9");
  });

  it("keeps library items as propId-null category=prop", () => {
    const placed = propPlacementIdentity({ id: "asset-77", source: "library" });
    expect(placed.propId).toBeNull();
    expect(placed.category).toBe("prop");
  });
});
