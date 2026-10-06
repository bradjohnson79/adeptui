import { describe, expect, it } from "vitest";
import {
  composeLiveGrade,
  hasLiveGrade,
  liveGradeCssFilter,
  liveGradeHasNonLiveChannels,
} from "./liveGrade";

describe("composeLiveGrade", () => {
  it("uses preset as the base and lets sliders override", () => {
    expect(composeLiveGrade("anime_vibrant", {})).toMatchObject({
      contrast: 0.1,
      saturation: 1.3,
      brightness: 0.02,
    });
    expect(composeLiveGrade("anime_vibrant", { saturation: 0.2 }).saturation).toBe(0.2);
  });
});

describe("liveGradeCssFilter", () => {
  it("returns empty for identity", () => {
    expect(liveGradeCssFilter({})).toBe("");
    expect(liveGradeCssFilter({ brightness: 0, contrast: 0, saturation: 0 })).toBe("");
  });

  it("maps stored slider units to CSS filter", () => {
    expect(liveGradeCssFilter({ brightness: 0.2, contrast: -0.1, saturation: 0.3 })).toBe(
      "brightness(1.2) contrast(0.9) saturate(1.3)",
    );
  });

  it("applies Anime Vibrant immediately without slider values", () => {
    const css = liveGradeCssFilter({}, "anime_vibrant");
    expect(css).toContain("saturate(2.3)");
    expect(css).toContain("contrast(1.1)");
    expect(css).toContain("brightness(1.02)");
  });
});

describe("hasLiveGrade / non-live honesty", () => {
  it("treats named presets as live previewable", () => {
    expect(hasLiveGrade("anime_vibrant", {})).toBe(true);
    expect(hasLiveGrade("", { brightness: 0.1 })).toBe(true);
    expect(hasLiveGrade("", {})).toBe(false);
  });

  it("is honest about bake-only channels still stored on the clip", () => {
    expect(liveGradeHasNonLiveChannels({ brightness: 0.1 })).toBe(false);
    expect(liveGradeHasNonLiveChannels({ gamma: 0.2 })).toBe(true);
    expect(liveGradeHasNonLiveChannels({}, "cinematic_warm")).toBe(true);
    expect(liveGradeHasNonLiveChannels({}, "anime_vibrant")).toBe(true);
  });
});
