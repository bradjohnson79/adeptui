import { describe, expect, it } from "vitest";
import {
  resolutionProductLabel,
  resolutionPixels,
  type ResolutionLabel,
} from "./cinematicImageStudio";

describe("CIS resolution contracts", () => {
  it("maps ResolutionLabel to the runtime product label (1K=1080p, 8K caps at 4K)", () => {
    expect(resolutionProductLabel("1K")).toBe("1080p");
    expect(resolutionProductLabel("2K")).toBe("2K");
    expect(resolutionProductLabel("4K")).toBe("4K");
    expect(resolutionProductLabel("8K")).toBe("4K");
  });

  it("computes 16:9 pixels matching image_product/compile.py _size (snap to 8)", () => {
    expect(resolutionPixels("1K", "16:9")).toEqual([1920, 1080]);
    // 1080 * 1.25 = 1350 -> snap to multiple of 8 = 1352
    expect(resolutionPixels("2K", "16:9")).toEqual([2400, 1352]);
    expect(resolutionPixels("4K", "16:9")).toEqual([3840, 2160]);
    // 8K caps at 4K scale (2.0)
    expect(resolutionPixels("8K", "16:9")).toEqual([3840, 2160]);
  });

  it("computes 9:16 pixels (portrait)", () => {
    expect(resolutionPixels("1K", "9:16")).toEqual([1080, 1920]);
  });

  it("computes 1:1 pixels", () => {
    expect(resolutionPixels("1K", "1:1")).toEqual([1024, 1024]);
  });

  it("falls back to 1:1 base for unknown aspect", () => {
    expect(resolutionPixels("1K", "bogus" as string)).toEqual([1024, 1024]);
  });

  it("1K 16:9 is 1920x1080 — UI and runtime agree (no 1080p-while-generating-another-size lie)", () => {
    const [w, h] = resolutionPixels("1K" as ResolutionLabel, "16:9");
    expect(`${w}x${h}`).toBe("1920x1080");
  });
});
