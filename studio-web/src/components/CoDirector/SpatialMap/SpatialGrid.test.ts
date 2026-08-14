import { describe, expect, it } from "vitest";
import { toGridPlacements } from "./SpatialGrid";
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
