import { describe, expect, it } from "vitest";
import { computeClientArrows, movementAlias, movementLabel, parseMovementAlias } from "./movementSegments";
import type { SpatialMapDocument } from "./types";

function doc(): SpatialMapDocument {
  return {
    id: "map-1",
    projectId: "p1",
    version: "2",
    activeMovementSegmentId: "m2",
    movementSegments: [
      {
        id: "m1",
        segmentNumber: 1,
        beatName: "Green Drink Reaction",
        characterStates: [
          { id: "c1", characterId: "korri", label: "Korri", normalizedX: -0.4, normalizedY: 0.2, gridRow: 3, gridColumn: 2 } as never,
        ],
        propStates: [],
      },
      {
        id: "m2",
        segmentNumber: 2,
        beatName: "Leaves Counter",
        characterStates: [
          { id: "c1", characterId: "korri", label: "Korri", normalizedX: 0.5, normalizedY: -0.1, gridRow: 6, gridColumn: 7 } as never,
        ],
        propStates: [],
      },
    ],
  } as unknown as SpatialMapDocument;
}

describe("movement helpers", () => {
  it("derives aliases and labels", () => {
    expect(movementAlias(2)).toBe("M2");
    expect(movementLabel({ segmentNumber: 2, beatName: "Leaves Counter" })).toBe("M2 — Leaves Counter");
    expect(parseMovementAlias("~M3")).toBe(3);
  });

  it("draws the active transition arrow from saved coordinates", () => {
    const arrows = computeClientArrows(doc());
    expect(arrows).toHaveLength(1);
    expect(arrows[0].fromAlias).toBe("M1");
    expect(arrows[0].toAlias).toBe("M2");
    expect(arrows[0].from.normalizedX).toBe(-0.4);
    expect(arrows[0].to.normalizedX).toBe(0.5);
  });
  it("multi-movement sequencing draws lower→higher consecutive arrows when fullSequence", () => {
    const three = {
      ...doc(),
      activeMovementSegmentId: "m3",
      movementSegments: [
        ...(doc().movementSegments || []),
        {
          id: "m3",
          segmentNumber: 3,
          beatName: "Doorway",
          characterStates: [
            { id: "c1", characterId: "korri", label: "Korri", normalizedX: 0.7, normalizedY: -0.4, gridRow: 8, gridColumn: 8 } as never,
          ],
          propStates: [],
        },
      ],
    } as unknown as SpatialMapDocument;
    const arrows = computeClientArrows(three, null, { fullSequence: true });
    expect(arrows.map((a) => `${a.fromAlias}->${a.toAlias}`)).toEqual(["M1->M2", "M2->M3"]);
  });

  it("isolates arrows to the focused character entity", () => {
    const multi = {
      id: "map-1",
      projectId: "p1",
      version: "2",
      activeMovementSegmentId: "m2",
      movementSegments: [
        {
          id: "m1",
          segmentNumber: 1,
          beatName: "Start",
          characterStates: [
            { id: "c1", characterId: "ent-a", label: "Ada", normalizedX: -0.4, normalizedY: 0.2, gridRow: 3, gridColumn: 2 } as never,
            { id: "c2", characterId: "ent-b", label: "Ben", normalizedX: 0.1, normalizedY: 0.1, gridRow: 4, gridColumn: 4 } as never,
          ],
          propStates: [],
        },
        {
          id: "m2",
          segmentNumber: 2,
          beatName: "End",
          characterStates: [
            { id: "c1", characterId: "ent-a", label: "Ada", normalizedX: 0.5, normalizedY: -0.1, gridRow: 6, gridColumn: 7 } as never,
            { id: "c2", characterId: "ent-b", label: "Ben", normalizedX: -0.2, normalizedY: 0.4, gridRow: 7, gridColumn: 3 } as never,
          ],
          propStates: [],
        },
      ],
    } as unknown as SpatialMapDocument;
    const all = computeClientArrows(multi, null, { fullSequence: true });
    expect(all).toHaveLength(2);
    expect(new Set(all.map((a) => a.characterId))).toEqual(new Set(["ent-a", "ent-b"]));
    const onlyA = computeClientArrows(multi, "ent-a", { fullSequence: true });
    expect(onlyA).toHaveLength(1);
    expect(onlyA[0].characterId).toBe("ent-a");
  });

});
