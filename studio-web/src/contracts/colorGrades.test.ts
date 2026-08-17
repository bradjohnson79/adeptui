import { describe, expect, it } from "vitest";
import { CREATOR_IMAGE_CATEGORIES, DEFAULT_IMAGE_CATEGORY } from "./cinematicImageStudio";
import { COLOR_GRADE_OPTIONS, DEFAULT_COLOR_GRADE, resolveColorGradeId } from "./colorGrades";

describe("creator image categories", () => {
  it("excludes Storyboard and defaults to General", () => {
    expect(DEFAULT_IMAGE_CATEGORY).toBe("general");
    expect(CREATOR_IMAGE_CATEGORIES.map((c) => c.value)).not.toContain("storyboard");
    expect(CREATOR_IMAGE_CATEGORIES[0]?.value).toBe("general");
  });
});

describe("color grade presets", () => {
  it("defaults to natural and maps legacy labels", () => {
    expect(DEFAULT_COLOR_GRADE).toBe("natural");
    expect(resolveColorGradeId("Teal & orange")).toBe("teal_orange");
    expect(resolveColorGradeId("Neutral cinematic")).toBe("cinematic_neutral");
    expect(COLOR_GRADE_OPTIONS.some((g) => g.id === "teal_orange")).toBe(true);
  });
});
