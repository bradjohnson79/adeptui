import { describe, expect, it, vi } from "vitest";

vi.mock("./spatialMapApi", () => ({
  spatialMapApi: {
    saveMap: vi.fn(),
  },
}));

import {
  spatialMapIsDirty,
  spatialMapIsSaved,
  spatialMapSaveDerivation,
} from "./useSpatialMapSave";
import { spatialMapSaveButtonLabel, spatialMapSaveStateLabel } from "./SpatialMapSaveControls";
import type { SpatialMapDocument } from "./types";

function doc(version: string, savedVersion?: string | null): SpatialMapDocument {
  return {
    id: "m1",
    version,
    savedVersion: savedVersion ?? null,
    projectId: "p1",
    title: "Map",
  } as unknown as SpatialMapDocument;
}

describe("Spatial Map Save Gate — dirty/saved derivation (Tests A, B, C, D)", () => {
  it("A: never-saved map (no savedVersion) is dirty => Use in Scene Creator must be disabled", () => {
    const d = doc("3");
    expect(spatialMapIsDirty(d)).toBe(true);
    expect(spatialMapIsSaved(d)).toBe(false);
  });

  it("B: after save, savedVersion === version => saved, not dirty", () => {
    const d = doc("4", "4");
    expect(spatialMapIsDirty(d)).toBe(false);
    expect(spatialMapIsSaved(d)).toBe(true);
  });

  it("C: any edit bumps version => dirty again immediately", () => {
    const d = doc("5", "4"); // edited after save at version 4
    expect(spatialMapIsDirty(d)).toBe(true);
    expect(spatialMapIsSaved(d)).toBe(false);
  });

  it("D: re-save updates savedVersion to the new version => saved again", () => {
    const d = doc("5", "5");
    expect(spatialMapIsDirty(d)).toBe(false);
    expect(spatialMapIsSaved(d)).toBe(true);
  });

  it("null document is dirty (fresh/unsaved state)", () => {
    expect(spatialMapSaveDerivation(null).isDirty).toBe(true);
  });

  it("savedVersion equal but map null-safe (no crash)", () => {
    expect(spatialMapSaveDerivation(undefined as unknown as SpatialMapDocument | null).isDirty).toBe(true);
  });

  it("top and bottom Save share the same status copy", () => {
    expect(spatialMapSaveButtonLabel("saving")).toBe("Saving…");
    expect(spatialMapSaveButtonLabel("idle")).toBe("Save Spatial Map");
    expect(spatialMapSaveStateLabel("error", true)).toBe("Save failed");
    expect(spatialMapSaveStateLabel("saving", true)).toBe("Saving…");
    expect(spatialMapSaveStateLabel("idle", true)).toBe("Unsaved changes");
    expect(spatialMapSaveStateLabel("saved", false)).toBe("Saved");
    expect(spatialMapSaveStateLabel("idle", false)).toBe("Saved");
  });
});
