import { describe, expect, it } from "vitest";
import {
  formatH3Megapixels,
  H3_AUTO_MEGAPIXEL_FAST,
  H3_AUTO_MEGAPIXEL_QUALITY,
  H3_MEGAPIXEL_GRID,
  H3_SUPPORTED_ASPECTS,
  H3UnsupportedAspectError,
  LTX_DEFAULT_QUALITY,
  LTX_TIMELINE_QUALITY_TIERS,
  normalizeH3Aspect,
  normalizeLtxTimelineQuality,
  resolveH3MegapixelCanvas,
  resolveH3ResolutionSelector,
  resolveH3TimelineCanvas,
  resolveLtxTimelineCanvas,
} from "./legalCanvas";

describe("H3_MEGAPIXEL_GRID", () => {
  it("has exactly 14 canonical tiers", () => {
    expect(H3_MEGAPIXEL_GRID).toHaveLength(14);
  });

  it("matches the backend canonical 16:9 /32 grid", () => {
    const rows = H3_MEGAPIXEL_GRID.map(([mp, dims]) => [mp, dims[0], dims[1]]);
    expect(rows).toEqual([
      [0.2, 608, 352],
      [0.3, 736, 416],
      [0.4, 864, 480],
      [0.5, 960, 544],
      [0.6, 1056, 608],
      [0.7, 1152, 640],
      [0.8, 1216, 672],
      [0.9, 1280, 736],
      [0.98, 1344, 768],
      [1.0, 1376, 768],
      [1.2, 1504, 832],
      [1.5, 1664, 928],
      [1.8, 1824, 1024],
      [2.0, 1920, 1088],
    ]);
  });
});

describe("formatH3Megapixels", () => {
  it("formats whole numbers as x.0 MP", () => {
    expect(formatH3Megapixels(1.0)).toBe("1.0 MP");
    expect(formatH3Megapixels(2.0)).toBe("2.0 MP");
  });

  it("keeps decimal values as-is", () => {
    expect(formatH3Megapixels(0.4)).toBe("0.4 MP");
    expect(formatH3Megapixels(0.98)).toBe("0.98 MP");
  });
});

describe("resolveH3MegapixelCanvas", () => {
  it("resolves every grid tier", () => {
    for (const [mp, dims] of H3_MEGAPIXEL_GRID) {
      const result = resolveH3MegapixelCanvas(mp);
      expect(result.width).toBe(dims[0]);
      expect(result.height).toBe(dims[1]);
      expect(result.label).toBe(formatH3Megapixels(mp));
    }
  });

  it("resolves aspect-aware canvases (21:9 @1.2 → 1728x736, 16:9 @1.2 → 1504x832, 21:9 @0.7 → 1312x576)", () => {
    expect(resolveH3MegapixelCanvas(1.2, "21:9")).toMatchObject({ width: 1728, height: 736 });
    expect(resolveH3MegapixelCanvas(1.2, "16:9")).toMatchObject({ width: 1504, height: 832 });
    expect(resolveH3MegapixelCanvas(0.7, "21:9")).toMatchObject({ width: 1312, height: 576 });
  });

  it("throws for unsupported megapixel values", () => {
    expect(() => resolveH3MegapixelCanvas(0.45)).toThrow(/not a supported/);
    expect(() => resolveH3MegapixelCanvas(3.0)).toThrow(/not a supported/);
    expect(() => resolveH3MegapixelCanvas(Number.NaN)).toThrow(/not a supported/);
  });
});

describe("resolveH3TimelineCanvas", () => {
  it("Auto Fast = 0.4 MP (864×480)", () => {
    const canvas = resolveH3TimelineCanvas(null, true);
    expect(canvas.mode).toBe("auto");
    expect(canvas.megapixels).toBe(H3_AUTO_MEGAPIXEL_FAST);
    expect(canvas.megapixels).toBe(0.4);
    expect(canvas.width).toBe(864);
    expect(canvas.height).toBe(480);
    expect(canvas.auto).toBe(true);
    expect(canvas.label).toBe("0.4 MP");
  });

  it("Auto Quality = 0.7 MP (1152×640)", () => {
    const canvas = resolveH3TimelineCanvas(null, false);
    expect(canvas.mode).toBe("auto");
    expect(canvas.megapixels).toBe(H3_AUTO_MEGAPIXEL_QUALITY);
    expect(canvas.megapixels).toBe(0.7);
    expect(canvas.width).toBe(1152);
    expect(canvas.height).toBe(640);
    expect(canvas.auto).toBe(true);
  });

  it("manual mode uses the stored megapixel value", () => {
    const canvas = resolveH3TimelineCanvas({ mode: "manual", megapixels: 1.0 }, true);
    expect(canvas.mode).toBe("manual");
    expect(canvas.megapixels).toBe(1.0);
    expect(canvas.width).toBe(1376);
    expect(canvas.height).toBe(768);
    expect(canvas.auto).toBe(false);
  });

  it("manual mode is authoritative over draftMode", () => {
    const canvas = resolveH3TimelineCanvas({ mode: "manual", megapixels: 2.0 }, true);
    expect(canvas.megapixels).toBe(2.0);
    expect(canvas.width).toBe(1920);
    expect(canvas.height).toBe(1088);
  });

  it("treats an explicit auto state like absent auto", () => {
    const canvas = resolveH3TimelineCanvas({ mode: "auto", megapixels: 1.5 }, true);
    expect(canvas.mode).toBe("auto");
    expect(canvas.megapixels).toBe(0.4);
    expect(canvas.auto).toBe(true);
  });

  it("throws when manual mode is missing megapixels", () => {
    expect(() =>
      resolveH3TimelineCanvas({ mode: "manual", megapixels: undefined as unknown as number }, false),
    ).toThrow(/requires a megapixel value/);
  });
});

/** Backend D1 authority (studio-api legal_canvas.resolve_h3_resolution_selector),
 * measured for the five production picture shapes. */
const H3_D1_DIMS: Record<string, Record<string, [number, number]>> = {
  "0.7": {
    "1:1": [864, 864],
    "4:3": [992, 736],
    "16:9": [1152, 640],
    "9:16": [640, 1152],
    "21:9": [1312, 576],
  },
  "1.2": {
    "1:1": [1120, 1120],
    "4:3": [1280, 960],
    "16:9": [1504, 832],
    "9:16": [832, 1504],
    "21:9": [1728, 736],
  },
};

describe("H3 picture shapes fail closed (B5)", () => {
  it.each(["0.7", "1.2"])(
    "resolves the five production shapes at %s MP to exact D1 dims",
    (mpKey) => {
      const mp = Number(mpKey);
      const expectedByShape = H3_D1_DIMS[mpKey];
      for (const shape of H3_SUPPORTED_ASPECTS) {
        const [width, height] = expectedByShape[shape];
        expect(resolveH3ResolutionSelector(shape, mp, 32)).toEqual({ width, height });
        expect(resolveH3MegapixelCanvas(mp, shape)).toMatchObject({ width, height });
        expect(
          resolveH3TimelineCanvas({ mode: "manual", megapixels: mp }, false, shape),
        ).toMatchObject({ width, height });
      }
    },
  );

  it.each(["0.7", "1.2"])("keeps the soft 16:9 aliases at %s MP", (mpKey) => {
    const mp = Number(mpKey);
    const [width, height] = H3_D1_DIMS[mpKey]["16:9"];
    expect(resolveH3ResolutionSelector("≈16:9", mp, 32)).toEqual({ width, height });
    expect(resolveH3ResolutionSelector("~16:9", mp, 32)).toEqual({ width, height });
  });

  it("never silently resolves an unsupported shape to 16:9 dims", () => {
    const sixteenNine = resolveH3ResolutionSelector("16:9", 0.7, 32);
    expect(sixteenNine).toEqual({ width: 1152, height: 640 });
    for (const bad of ["2.39:1", "3:2", "2:3", "3:4", "16:10", "18:9", "4:5", "custom", "garbage"]) {
      expect(() => resolveH3ResolutionSelector(bad, 0.7, 32)).toThrow(H3UnsupportedAspectError);
      let resolved: { width: number; height: number } | null = null;
      try {
        resolved = resolveH3ResolutionSelector(bad, 0.7, 32);
      } catch {
        resolved = null;
      }
      expect(resolved).toBeNull();
      expect(resolved).not.toEqual(sixteenNine);
    }
  });

  it("fails closed through resolveH3MegapixelCanvas and resolveH3TimelineCanvas", () => {
    expect(() => resolveH3MegapixelCanvas(0.7, "2.39:1")).toThrow(H3UnsupportedAspectError);
    expect(() => resolveH3MegapixelCanvas(1.2, "3:2")).toThrow(H3UnsupportedAspectError);
    expect(() => resolveH3TimelineCanvas(null, true, "2.39:1")).toThrow(H3UnsupportedAspectError);
    expect(() =>
      resolveH3TimelineCanvas({ mode: "manual", megapixels: 1.2 }, false, "3:2"),
    ).toThrow(H3UnsupportedAspectError);
    // Supported shapes still resolve through both entry points.
    expect(resolveH3MegapixelCanvas(0.7, "9:16")).toMatchObject({ width: 640, height: 1152 });
    expect(
      resolveH3TimelineCanvas({ mode: "manual", megapixels: 0.7 }, false, "21:9"),
    ).toMatchObject({ width: 1312, height: 576 });
  });

  it("carries the backend refusal code and offending shape on the error", () => {
    try {
      resolveH3ResolutionSelector("2.39:1", 0.7, 32);
      throw new Error("expected H3UnsupportedAspectError");
    } catch (error) {
      expect(error).toBeInstanceOf(H3UnsupportedAspectError);
      expect((error as H3UnsupportedAspectError).code).toBe("H3_ASPECT_UNSUPPORTED");
      expect((error as H3UnsupportedAspectError).aspect).toBe("2.39:1");
      expect((error as Error).message).toMatch(/does not support picture shape 2\.39:1/);
    }
  });

  it("normalizes only the capability set plus the soft 16:9 aliases", () => {
    for (const shape of H3_SUPPORTED_ASPECTS) expect(normalizeH3Aspect(shape)).toBe(shape);
    expect(normalizeH3Aspect("≈16:9")).toBe("16:9");
    expect(normalizeH3Aspect("~16:9")).toBe("16:9");
    expect(normalizeH3Aspect("")).toBe("16:9");
    expect(normalizeH3Aspect(null)).toBe("16:9");
    expect(normalizeH3Aspect(undefined)).toBe("16:9");
    for (const bad of ["2.39:1", "3:2", "custom", "garbage"]) {
      expect(normalizeH3Aspect(bad)).toBeNull();
    }
  });
});

describe("LTX Timeline QUALITY", () => {
  it("exposes 720p/1080p/2K/4K only (no 480p)", () => {
    expect([...LTX_TIMELINE_QUALITY_TIERS]).toEqual(["720p", "1080p", "2K", "4K"]);
    expect(LTX_TIMELINE_QUALITY_TIERS).not.toContain("480p");
  });

  it("defaults to 720p", () => {
    expect(LTX_DEFAULT_QUALITY).toBe("720p");
    expect(normalizeLtxTimelineQuality(null)).toBe("720p");
    expect(normalizeLtxTimelineQuality(undefined)).toBe("720p");
  });

  it("resolves legal /32 canvases", () => {
    expect(resolveLtxTimelineCanvas("720p")).toMatchObject({
      width: 1280,
      height: 704,
      available: true,
    });
    expect(resolveLtxTimelineCanvas("1080p")).toMatchObject({
      width: 1920,
      height: 1088,
      available: true,
    });
    expect(resolveLtxTimelineCanvas("2K")).toMatchObject({
      width: 2560,
      height: 1440,
      available: true,
    });
  });

  it("resolves LTX 9:16 @720p to 704x1248", () => {
    const canvas = resolveLtxTimelineCanvas("720p", "9:16");
    expect(canvas).toMatchObject({ width: 704, height: 1248, available: true });
  });

  it("marks native 4K as UNAVAILABLE", () => {
    const canvas = resolveLtxTimelineCanvas("4K");
    expect(canvas.available).toBe(false);
    expect(canvas.honestyLabel).toMatch(/UNAVAILABLE/i);
  });
});
