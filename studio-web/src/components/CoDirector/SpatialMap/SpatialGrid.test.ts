import { describe, expect, it } from "vitest";
import { toGridPlacements } from "./SpatialGrid";
import { fovLayersForCameras } from "./placementArm";
import type { SpatialCharacterPlacement, SpatialPropPlacement } from "./types";

describe("toGridPlacements (Work Order E)", () => {
  it("keeps a hidden character in the placement list (hide is not delete)", () => {
    const hiddenChar = {
      id: "c1",
      tag: "Ada",
      label: "Ada",
      colorKey: "red",
      gridRow: 4,
      gridColumn: 4,
      normalizedX: -0.1,
      normalizedY: -0.1,
      slotIndex: 0,
      visible: false,
    } as SpatialCharacterPlacement;
    const shownProp = {
      id: "p1",
      tag: "cup",
      label: "Cup",
      colorKey: "purple",
      gridRow: 5,
      gridColumn: 5,
      normalizedX: 0.1,
      normalizedY: 0.1,
      slotIndex: 0,
      visible: true,
    } as SpatialPropPlacement;

    const mapped = toGridPlacements([hiddenChar], [shownProp]);
    expect(mapped).toHaveLength(2);
    expect(mapped.find((p) => p.id === "c1")).toMatchObject({
      kind: "character",
      slotIndex: 0,
      visible: false,
      gridColumn: 4,
      gridRow: 4,
    });
    expect(mapped.find((p) => p.id === "p1")).toMatchObject({
      kind: "prop",
      slotIndex: 0,
      visible: true,
      gridColumn: 5,
      gridRow: 5,
    });
  });

  it("preserves saved-character and prop slot indexes without merging identities", () => {
    const characters = [
      { id: "c-red", tag: "Ada", label: "Ada", colorKey: "red", gridRow: 4, gridColumn: 3, slotIndex: 0, normalizedX: -0.3, normalizedY: -0.1 },
      { id: "c-blue", tag: "Ben", label: "Ben", colorKey: "blue", gridRow: 4, gridColumn: 5, slotIndex: 1, normalizedX: 0.1, normalizedY: -0.1 },
    ] as SpatialCharacterPlacement[];
    const props = [
      { id: "p-purple", tag: "cup", label: "Cup", colorKey: "purple", gridRow: 6, gridColumn: 4, slotIndex: 0, normalizedX: -0.1, normalizedY: 0.3 },
    ] as SpatialPropPlacement[];

    const mapped = toGridPlacements(characters, props);
    expect(mapped.map((p) => p.id)).toEqual(["c-red", "c-blue", "p-purple"]);
    expect(mapped.map((p) => [p.kind, p.slotIndex])).toEqual([
      ["character", 0],
      ["character", 1],
      ["prop", 0],
    ]);
    expect(new Set(mapped.map((p) => p.id)).size).toBe(3);
  });
});

describe("toGridPlacements attachment XOR", () => {
  const korri = {
    id: "c1",
    characterId: "korri",
    tag: "Korri",
    label: "Korri",
    colorKey: "red",
    gridRow: 4,
    gridColumn: 4,
    normalizedX: -0.1,
    normalizedY: -0.1,
    slotIndex: 0,
    visible: true,
  } as SpatialCharacterPlacement;

  const coffee = {
    id: "p-coffee",
    tag: "Coffee Cup",
    label: "Coffee Cup",
    colorKey: "purple",
    gridRow: 5,
    gridColumn: 5,
    normalizedX: 0.1,
    normalizedY: 0.1,
    slotIndex: 0,
    visible: true,
    placementMode: "attached",
    attachedCharacterSlot: 1,
    attachedCharacterId: "korri",
    relationship: "held",
    attachmentPoint: "right_hand",
  } as SpatialPropPlacement;

  it("never renders an independent marker for an attached prop", () => {
    const mapped = toGridPlacements([korri], [coffee]);
    expect(mapped.find((p) => p.id === "p-coffee")).toBeUndefined();
    expect(mapped.filter((p) => p.kind === "prop")).toHaveLength(0);
    expect(mapped).toHaveLength(1);
  });

  it("puts a P1 badge and Korri coffee tooltip on the character", () => {
    const mapped = toGridPlacements([korri], [coffee]);
    expect(mapped[0].attachedBadge).toEqual({ type: "single", slotLabel: "P1" });
    expect(mapped[0].tooltip).toBe("Korri / Attached: Coffee Cup — Held — Right Hand");
  });

  it("collapses multiple visible attached props to +N and omits hidden props from the badge", () => {
    const book = {
      ...coffee,
      id: "p-book",
      label: "Book",
      tag: "Book",
      slotIndex: 1,
      relationship: "carried",
      attachmentPoint: "back",
    } as SpatialPropPlacement;
    const hidden = { ...coffee, id: "p-hidden", visible: false, slotIndex: 2 } as SpatialPropPlacement;
    const mapped = toGridPlacements([korri], [coffee, book, hidden]);
    expect(mapped[0].attachedBadge).toEqual({ type: "count", count: 2 });
    expect(mapped.find((p) => p.kind === "prop")).toBeUndefined();
  });

  it("keeps the relationship when the character is hidden (hide is not delete)", () => {
    const hiddenChar = { ...korri, visible: false };
    const mapped = toGridPlacements([hiddenChar], [coffee]);
    expect(mapped[0]).toMatchObject({ id: "c1", visible: false });
    expect(mapped[0].attachedBadge).toEqual({ type: "single", slotLabel: "P1" });
    expect(mapped.find((p) => p.id === "p-coffee")).toBeUndefined();
  });
});

describe("camera FOV layers are not selection-filtered", () => {
  it("keeps multiple visible camera FOVs when one camera is selected", () => {
    const cameras = [
      { id: "cam-1", visible: true, gridRow: 2, gridColumn: 2, normalizedX: -0.2, normalizedY: -0.2 },
      { id: "cam-2", visible: true, gridRow: 6, gridColumn: 6, normalizedX: 0.3, normalizedY: 0.3 },
    ];
    const layers = fovLayersForCameras(cameras, "cam-2");
    expect(layers).toHaveLength(2);
    expect(layers.every((layer) => layer.hidden === false)).toBe(true);
    expect(layers.map((layer) => layer.id)).toEqual(["cam-1", "cam-2"]);
  });
});
