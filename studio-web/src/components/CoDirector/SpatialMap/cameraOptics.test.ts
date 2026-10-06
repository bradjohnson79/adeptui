import { describe, expect, it } from "vitest";
import {
  applyFovChange,
  applyLensChange,
  fovDegreesFromLensMm,
  hydrateLens,
  hydrateLightingMood,
  isFisheyeLens,
  lensLabel,
  LENS_VALUES,
  LIGHTING_MOODS,
  LIGHTING_MOOD_LABELS,
  snapFovPreset,
} from "./cameraOptics";

describe("camera optics", () => {
  it("hydrates missing lens and mood to auto", () => {
    expect(hydrateLens(undefined)).toBe("auto");
    expect(hydrateLens("")).toBe("auto");
    expect(hydrateLens("35mm")).toBe("35");
    expect(hydrateLightingMood(undefined)).toBe("auto");
    expect(hydrateLightingMood("Sci-Fi")).toBe("sci_fi");
  });

  it("includes Sci-Fi and Fantasy production moods", () => {
    expect(LIGHTING_MOODS).toContain("sci_fi");
    expect(LIGHTING_MOODS).toContain("fantasy");
    expect(LIGHTING_MOOD_LABELS.sci_fi).toBe("Sci-Fi");
    expect(LIGHTING_MOOD_LABELS.fantasy).toBe("Fantasy");
  });

  it("derives FOV from a manual lens on a 36 mm full-frame sensor", () => {
    const fov18 = fovDegreesFromLensMm(18);
    const fov135 = fovDegreesFromLensMm(135);
    expect(fov18).toBeGreaterThan(80);
    expect(fov135).toBeLessThan(20);
    expect(snapFovPreset(fov18)).toBe("wide");
    expect(snapFovPreset(fov135)).toBe("narrow");
    expect(applyLensChange("18").fovPreset).toBe("wide");
    expect(applyLensChange("85").fovPreset).toBe("narrow");
  });

  it("returns lens to auto when FOV buttons win", () => {
    expect(applyFovChange("narrow")).toEqual({ lens: "auto", fovPreset: "narrow" });
  });

  it("treats fisheye as a special projection, not 18mm", () => {
    expect(LENS_VALUES).toContain("fisheye");
    expect(hydrateLens("fisheye")).toBe("fisheye");
    expect(hydrateLens("fish-eye")).toBe("fisheye");
    expect(isFisheyeLens("fisheye")).toBe(true);
    expect(lensLabel("fisheye")).toBe("Fisheye");
    const next = applyLensChange("fisheye", 35, "narrow");
    expect(next.lens).toBe("fisheye");
    expect(next.fovDegrees).toBeNull();
    expect(next.lensMm).toBe(35);
    expect(next.fovPreset).toBe("wide");
  });
});
