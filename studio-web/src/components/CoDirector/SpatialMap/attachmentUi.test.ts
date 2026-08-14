import { describe, expect, it } from "vitest";
import {
  ATTACHMENT_POINTS_BY_RELATIONSHIP,
  assignedSpatialMapCharacters,
  attachedBadgeFor,
  attachedPropsForCharacter,
  attachmentPointsFor,
  characterSlotTag,
  formatAttachmentPointLabel,
  formatCharacterAttachmentTooltip,
  formatRelationshipLabel,
  independentAssignedProps,
  isAttachedProp,
  propSlotLabel,
  visibleAttachedPropsForCharacter,
} from "./attachmentUi";
import type { SpatialCharacterPlacement, SpatialPropPlacement } from "./types";

const korri = {
  id: "char-1",
  characterId: "korri",
  label: "Korri",
  tag: "Korri",
  slotIndex: 0,
  colorKey: "red",
  gridRow: 4,
  gridColumn: 4,
  visible: true,
} as SpatialCharacterPlacement;

const coffee = {
  id: "prop-1",
  propId: "coffee-1",
  label: "Coffee Cup",
  tag: "Coffee Cup",
  slotIndex: 0,
  colorKey: "purple",
  gridRow: 5,
  gridColumn: 5,
  placementMode: "attached",
  attachedCharacterSlot: 1,
  attachedCharacterId: "korri",
  relationship: "held",
  attachmentPoint: "right_hand",
  visible: true,
} as SpatialPropPlacement;

const book = {
  id: "prop-2",
  label: "Book",
  tag: "Book",
  slotIndex: 1,
  colorKey: "brown",
  gridRow: -1,
  gridColumn: -1,
  placementMode: "attached",
  attachedCharacterSlot: 1,
  attachedCharacterId: "korri",
  relationship: "carried",
  attachmentPoint: "back",
  visible: true,
} as SpatialPropPlacement;

const lamp = {
  id: "prop-3",
  label: "Lamp",
  tag: "Lamp",
  slotIndex: 2,
  colorKey: "aqua",
  gridRow: 2,
  gridColumn: 2,
  placementMode: "independent",
  attachedCharacterSlot: null,
  attachedCharacterId: null,
  relationship: null,
  attachmentPoint: null,
  visible: true,
} as SpatialPropPlacement;

describe("attachment UI helpers", () => {
  it("treats missing placementMode as independent", () => {
    expect(isAttachedProp({})).toBe(false);
    expect(isAttachedProp({ placementMode: "independent" })).toBe(false);
    expect(isAttachedProp({ placementMode: "attached" })).toBe(true);
  });

  it("filters attachment points by relationship", () => {
    expect(attachmentPointsFor("held")).toEqual(["left_hand", "right_hand", "both_hands"]);
    expect(attachmentPointsFor("worn")).toEqual(ATTACHMENT_POINTS_BY_RELATIONSHIP.worn);
    expect(attachmentPointsFor("held")).not.toContain("head");
  });

  it("formats compact tags and the Korri coffee tooltip", () => {
    expect(formatRelationshipLabel("held")).toBe("Held");
    expect(formatAttachmentPointLabel("right_hand")).toBe("Right Hand");
    expect(characterSlotTag(1)).toBe("C1");
    expect(propSlotLabel(0)).toBe("P1");
    expect(formatCharacterAttachmentTooltip(korri, [coffee])).toBe(
      "Korri / Attached: Coffee Cup — Held — Right Hand",
    );
  });

  it("lists only assigned Spatial Map characters as Character N — Name", () => {
    const assigned = assignedSpatialMapCharacters([korri]);
    expect(assigned).toEqual([{ slot: 1, id: "korri", name: "Korri" }]);
  });

  it("badge is P1 for one visible attached prop and +N for multiple", () => {
    expect(attachedBadgeFor([coffee])).toEqual({ type: "single", slotLabel: "P1" });
    expect(attachedBadgeFor([coffee, book])).toEqual({ type: "count", count: 2 });
    expect(attachedBadgeFor([{ ...coffee, visible: false }])).toBeNull();
  });

  it("hidden attached prop stays related but is omitted from badge/tooltip", () => {
    const hidden = { ...coffee, visible: false };
    expect(attachedPropsForCharacter(korri, [hidden, lamp])).toEqual([hidden]);
    expect(visibleAttachedPropsForCharacter(korri, [hidden, book])).toEqual([book]);
    expect(formatCharacterAttachmentTooltip(korri, [hidden])).toBe("Korri");
  });

  it("independentAssignedProps excludes attached props", () => {
    expect(independentAssignedProps([coffee, lamp]).map((p) => p.id)).toEqual(["prop-3"]);
  });
});
