import { describe, expect, it } from "vitest";
import { resolveFilmTimelinePlanDims, visibleSegmentError } from "./filmTimelinePresentation";

describe("visibleSegmentError", () => {
  it("shows the raw sticky failure until settings change suppresses it", () => {
    expect(visibleSegmentError("H3_DIRECTOR_REFS_REQUIRED: needs a character picture", false)).toBe(
      "H3_DIRECTOR_REFS_REQUIRED: needs a character picture",
    );
    expect(visibleSegmentError("H3_DIRECTOR_REFS_REQUIRED: needs a character picture", true)).toBe("");
    expect(visibleSegmentError("", true)).toBe("");
  });

  it("hides legacy R2V duration sticky copy when Director path opts in", () => {
    const legacy =
      "MiniMax H3 Reference-to-Video needs a frame count where n ≡ 5 (mod 17). 14s at 24 fps is 336 frames. Adept will not pad the clip.";
    expect(visibleSegmentError(legacy, false)).toBe(legacy);
    expect(visibleSegmentError(legacy, false, { hideLegacyR2v: true })).toBe("");
  });
});

describe("resolveFilmTimelinePlanDims", () => {
  it("prefers stamped segment resolvedGeneration over Scene canvas", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      segments: [{ generationMetadata: { resolvedGeneration: { width: 1152, height: 640 } } }],
    });
    expect(dims).toEqual({ width: 1152, height: 640, source: "resolvedGeneration" });
  });

  it("falls back to H3 Auto Quality 0.7 → 1152×640 when nothing is stamped", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "auto", megapixels: 0.7 },
    });
    expect(dims).toEqual({ width: 1152, height: 640, source: "h3_auto_quality" });
  });

  it("is aspect-aware for H3 manual 1.2 MP (21:9 → 1728×736)", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "manual", megapixels: 1.2 },
      aspect: "21:9",
    });
    expect(dims).toEqual({ width: 1728, height: 736, source: "h3_auto_quality" });
  });

  it("defaults to 16:9 when no aspect is given (1.2 MP → 1504×832)", () => {
    const dims = resolveFilmTimelinePlanDims({
      generatorId: "minimax-h3-i2v-local",
      h3Resolution: { mode: "manual", megapixels: 1.2 },
    });
    expect(dims).toEqual({ width: 1504, height: 832, source: "h3_auto_quality" });
  });

  it("does not invent H3 dims for non-H3 generators", () => {
    expect(resolveFilmTimelinePlanDims({ generatorId: "ltx-25-local" })).toBeNull();
  });

  it("returns no plan dims for an H3 shape outside H3_SUPPORTED_ASPECTS (never 16:9)", () => {
    // The backend fail-closes on these shapes; showing 16:9-class dims would be
    // a display the backend refuses (legal_canvas.require_h3_timeline_aspect).
    for (const aspect of ["3:2", "16:10", "18:9", "2.39:1", "5:4"]) {
      expect(
        resolveFilmTimelinePlanDims({
          generatorId: "minimax-h3-i2v-local",
          h3Resolution: { mode: "auto", megapixels: 0.7 },
          aspect,
        }),
      ).toBeNull();
    }
  });

  it("keeps the certified Auto 0.7 fallback for supported H3 shapes and aliases", () => {
    const base = { generatorId: "minimax-h3-i2v-local", h3Resolution: { mode: "auto" as const, megapixels: 0.7 } };
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "16:9" })).toEqual({
      width: 1152,
      height: 640,
      source: "h3_auto_quality",
    });
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "≈16:9" })).toEqual({
      width: 1152,
      height: 640,
      source: "h3_auto_quality",
    });
    expect(resolveFilmTimelinePlanDims({ ...base, aspect: "1:1" })).toEqual({
      width: 864,
      height: 864,
      source: "h3_auto_quality",
    });
  });

  it("still prefers stamped dims over refusing an unsupported shape", () => {
    // Stamped resolvedGeneration is observed reality, not a guess.
    expect(
      resolveFilmTimelinePlanDims({
        generatorId: "minimax-h3-i2v-local",
        segments: [{ generationMetadata: { resolvedGeneration: { width: 1728, height: 736 } } }],
        aspect: "3:2",
      }),
    ).toEqual({ width: 1728, height: 736, source: "resolvedGeneration" });
  });
});
