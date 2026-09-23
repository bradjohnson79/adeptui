import { describe, expect, it } from "vitest";
import {
  formatH3Megapixels,
  H3_AUTO_MEGAPIXEL_FAST,
  H3_AUTO_MEGAPIXEL_QUALITY,
  H3_MEGAPIXEL_GRID,
  LTX_DEFAULT_QUALITY,
  LTX_TIMELINE_QUALITY_TIERS,
  normalizeLtxTimelineQuality,
  resolveH3MegapixelCanvas,
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

  it("marks native 4K as UNAVAILABLE", () => {
    const canvas = resolveLtxTimelineCanvas("4K");
    expect(canvas.available).toBe(false);
    expect(canvas.honestyLabel).toMatch(/UNAVAILABLE/i);
  });
});
