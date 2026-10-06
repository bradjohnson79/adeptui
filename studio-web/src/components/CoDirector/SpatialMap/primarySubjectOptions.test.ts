import { describe, expect, it } from "vitest";
import {
  camerasNeedingSubjectFallback,
  primarySubjectOptions,
  resolvePrimarySubjectValue,
} from "./primarySubjectOptions";
import type { SpatialCharacterPlacement } from "./types";

function char(partial: Partial<SpatialCharacterPlacement>): SpatialCharacterPlacement {
  return {
    id: partial.id || "p1",
    characterId: partial.characterId || "ent-1",
    label: partial.label || "Hero",
    tag: partial.tag || "Hero",
    colorKey: "red",
    gridRow: partial.gridRow ?? -1,
    gridColumn: partial.gridColumn ?? -1,
    slotIndex: partial.slotIndex ?? 0,
    visible: partial.visible,
    normalizedX: partial.normalizedX,
    normalizedY: partial.normalizedY,
  } as SpatialCharacterPlacement;
}

describe("primarySubjectOptions", () => {
  it("lists Auto + Environment + enabled characters from Characters panel source", () => {
    const opts = primarySubjectOptions([
      char({ characterId: "ent-a", label: "Ada", visible: true }),
      char({ characterId: "ent-b", label: "Ben", visible: false }),
      char({ id: "p3", characterId: "ent-c", label: "Cy", visible: undefined, gridRow: -1 }),
    ]);
    expect(opts.map((o) => o.value)).toEqual(["auto", "environment", "ent-a", "ent-c"]);
    expect(opts.find((o) => o.value === "ent-a")?.label).toBe("Ada");
    expect(opts.some((o) => /korri|anadriya/i.test(o.label))).toBe(false);
  });

  it("excludes disabled characters and dedupes entity ids", () => {
    const opts = primarySubjectOptions([
      char({ id: "p1", characterId: "ent-a", label: "Ada", visible: false }),
      char({ id: "p2", characterId: "ent-a", label: "Ada Dup", visible: true }),
    ]);
    expect(opts.filter((o) => o.value === "ent-a")).toHaveLength(1);
  });

  it("falls back to Auto when selected subject is disabled or unknown", () => {
    const chars = [char({ characterId: "ent-a", label: "Ada", visible: false })];
    expect(resolvePrimarySubjectValue("ent-a", chars)).toBe("auto");
    expect(resolvePrimarySubjectValue("environment", chars)).toBe("environment");
    expect(resolvePrimarySubjectValue("auto", chars)).toBe("auto");
  });

  it("identifies cameras that must fall back when a character is disabled", () => {
    expect(
      camerasNeedingSubjectFallback(
        [
          { id: "cam1", primarySubject: "ent-a" },
          { id: "cam2", primarySubject: "auto" },
          { id: "cam3", primarySubject: "ent-a" },
        ],
        "ent-a",
      ),
    ).toEqual(["cam1", "cam3"]);
  });
});
