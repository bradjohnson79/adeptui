import { describe, expect, it } from "vitest";
import { selectableCloudModels } from "./cloudModels";

describe("Cloud Generators dropdown offering (CDX-080)", () => {
  it("drops adapter-unavailable / non-executable rows from the dropdown", () => {
    const rows = [
      {
        id: "flux-fal",
        label: "FLUX Kontext — fal.ai",
        adapterAvailable: true,
        executable: true,
        selectable: true,
      },
      {
        id: "flux-kontext-fal",
        label: "FLUX Kontext Pro — fal.ai",
        adapterAvailable: false,
        executable: false,
        selectable: false,
      },
      {
        id: "legacy-row",
        label: "Legacy Row",
        adapterAvailable: true,
      },
    ];
    const kept = selectableCloudModels(rows);
    expect(kept.map((m) => m.id)).toEqual(["flux-fal", "legacy-row"]);
    expect(kept.some((m) => m.id === "flux-kontext-fal")).toBe(false);
  });

  it("returns [] for null / undefined / empty lists", () => {
    expect(selectableCloudModels(null)).toEqual([]);
    expect(selectableCloudModels(undefined)).toEqual([]);
    expect(selectableCloudModels([])).toEqual([]);
  });
});
