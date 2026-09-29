import { describe, expect, it } from "vitest";
import {
  VIDEO_TIERS,
  durationFidelityMessage,
  h3DurationDisclosure,
  h3LegalDurationSeconds,
  h3LegalFrameCount,
  inferMinimaxMegapixelTier,
  inferVideoTier,
  isH3DurationLegal,
  isMinimaxMegapixelEngine,
  legalCanvasSize,
  minimaxMegapixelOptions,
  normalizeVideoTier,
  resolveH3ResolutionSelector,
} from "./legalCanvas";

describe("legalCanvas", () => {
  it("keeps standard tiers at 480p and above", () => {
    expect(VIDEO_TIERS).toEqual(["480p", "720p", "1080p", "2K", "4K"]);
    expect(normalizeVideoTier("1440p")).toBe("2K");
  });

  it("maps stale 1280x720 onto the 720p class, then resolves 1280x704", () => {
    expect(inferVideoTier(1280, 720)).toBe("720p");
    expect(inferVideoTier(1280, 704)).toBe("720p");
    expect(legalCanvasSize("minimax-h3", inferVideoTier(1280, 720), "16:9")).toMatchObject({
      width: 1280,
      height: 704,
      available: true,
    });
  });

  it("publishes 720p as 1280x704 for local /32 families", () => {
    const size = legalCanvasSize("ltx-2.5", "720p", "16:9");
    expect(size).toMatchObject({ width: 1280, height: 704, available: true });
    expect(legalCanvasSize("minimax-h3", "720p", "16:9").height).toBe(704);
  });

  it("does not advertise native 4K for local /32 families", () => {
    expect(legalCanvasSize("ltx-2.5", "4K", "16:9").available).toBe(false);
  });

  it("keeps Seedance 2.0 and 2.5 on hosted 480p/720p only", () => {
    expect(legalCanvasSize("seedance-2.5", "720p", "16:9")).toMatchObject({
      width: 1280,
      height: 720,
      available: true,
    });
    expect(legalCanvasSize("seedance-2.0", "4K", "16:9").available).toBe(false);
  });

  it("blocks illegal LTX duration instead of padding", () => {
    expect(durationFidelityMessage("ltx-2.5", 5, 24)).toMatch(/8n\+1/);
    expect(durationFidelityMessage("ltx-2.5", 121 / 24, 24)).toBe("");
    expect(durationFidelityMessage("minimax-h3", 5, 24)).toBe("");
  });

  it("exposes the MiniMax megapixel Resolution grid (16:9, /32)", () => {
    const opts = minimaxMegapixelOptions("16:9");
    expect(opts.length).toBe(14);
    expect(opts[0]).toMatchObject({ label: "0.2 MP", width: 608, height: 352, available: true });
    expect(opts[13]).toMatchObject({ label: "2.0 MP", width: 1920, height: 1088, available: true });
    // every dimension must be a multiple of 32
    for (const o of opts) {
      expect(o.width % 32).toBe(0);
      expect(o.height % 32).toBe(0);
    }
  });

  it("resolves MiniMax megapixel tiers through legalCanvasSize", () => {
    expect(legalCanvasSize("minimax-h3", "0.9 MP", "16:9")).toMatchObject({
      width: 1280,
      height: 736,
      available: true,
    });
    expect(legalCanvasSize("minimax-h3", "1.0 MP", "16:9")).toMatchObject({
      width: 1376,
      height: 768,
      available: true,
    });
    // honesty label carries the megapixel label + dims
    expect(legalCanvasSize("minimax-h3", "0.9 MP", "16:9").honestyLabel).toContain("0.9 MP");
  });

  it("keeps non-MiniMax engines on the 480p/720p/1080p tier model", () => {
    // LTX 2.5 must NOT resolve a megapixel label — it falls back to 720p.
    expect(legalCanvasSize("ltx-2.5", "0.9 MP", "16:9")).toMatchObject({
      width: 1280,
      height: 704,
      available: true,
    });
    // MiniMax with a legacy 720p label still resolves (no megapixel label given).
    expect(legalCanvasSize("minimax-h3", "720p", "16:9").height).toBe(704);
  });

  it("infers the closest MiniMax megapixel tier from pixel dimensions", () => {
    // exact 16:9 /32 match
    expect(inferMinimaxMegapixelTier(1280, 736)).toBe("0.9 MP");
    expect(inferMinimaxMegapixelTier(1920, 1088)).toBe("2.0 MP");
    // legacy 1280x704 (~0.90 MP) snaps to the closest megapixel tier (0.9 MP)
    expect(inferMinimaxMegapixelTier(1280, 704)).toBe("0.9 MP");
    // unknown / zero dims → sensible default
    expect(inferMinimaxMegapixelTier(0, 0)).toBe("0.9 MP");
  });

  it("scopes the MiniMax megapixel dropdown to minimax-h3 only", () => {
    expect(isMinimaxMegapixelEngine("minimax-h3")).toBe(true);
    expect(isMinimaxMegapixelEngine("ltx-2.5")).toBe(false);
    expect(isMinimaxMegapixelEngine("auto")).toBe(false);
    expect(isMinimaxMegapixelEngine("seedance-2.5")).toBe(false);
  });

  it("keeps the creator-video H3 display contract for shapes outside the H3 capability set", () => {
    // Video Picture Shape (AspectRatioSelect) offers 3:2 / 16:10 / 18:9 / 2.39:1 /
    // custom. B5 makes the Timeline H3 path fail closed; these creator-video
    // consumers must keep resolving instead of throwing behind the new guard.
    for (const aspect of ["3:2", "16:10", "18:9", "2.39:1", "custom"]) {
      const opts = minimaxMegapixelOptions(aspect);
      expect(opts).toHaveLength(14);
      for (const o of opts) {
        expect(Number.isFinite(o.width) && o.width > 0).toBe(true);
        expect(Number.isFinite(o.height) && o.height > 0).toBe(true);
      }
      // Behaviour unchanged: the 16:9-class dims this surface always published.
      expect(opts[9]).toMatchObject({ label: "1.0 MP", width: 1376, height: 768 });
      expect(legalCanvasSize("minimax-h3", "0.9 MP", aspect)).toMatchObject({
        width: 1280,
        height: 736,
        available: true,
      });
    }
  });

  it("keeps the B5 refusal boundary: the shared selector refuses, the video wrapper does not", () => {
    expect(() => resolveH3ResolutionSelector("2.39:1", 0.9, 32)).toThrow(/MiniMax H3/);
    expect(() => resolveH3ResolutionSelector("3:2", 0.9, 32)).toThrow(/MiniMax H3/);
    // Supported shapes keep resolving through the re-export.
    expect(resolveH3ResolutionSelector("21:9", 1.2, 32)).toEqual({ width: 1728, height: 736 });
  });

  it("snaps MiniMax H3 1F durations up to the 17k+5 grid (never shortens)", () => {
    // 13.0s @24fps = 312 frames (off-grid) → snap up to 328 (17*19+5) = 13.67s
    expect(h3LegalFrameCount(13, 24)).toBe(328);
    expect(h3LegalDurationSeconds(13, 24)).toBeCloseTo(13.6667, 4);
    // already on-grid: 124 frames (17*7+5) = 5.167s passes through
    expect(h3LegalFrameCount(124 / 24, 24)).toBe(124);
    // 5s @24fps = 120 frames → snap up to 124 (17*7+5)
    expect(h3LegalFrameCount(5, 24)).toBe(124);
    expect(isH3DurationLegal(13, 24)).toBe(false);
    expect(isH3DurationLegal(124 / 24, 24)).toBe(true);
  });

  it("discloses MiniMax H3 snap-and-disclose only for minimax off-grid durations", () => {
    expect(h3DurationDisclosure("minimax-h3", 13, 24)).toContain("328 frames");
    expect(h3DurationDisclosure("minimax-h3", 13, 24)).toContain("off-grid");
    // on-grid → no disclosure
    expect(h3DurationDisclosure("minimax-h3", 124 / 24, 24)).toBe("");
    // non-MiniMax → never discloses (LTX has its own durationFidelityMessage)
    expect(h3DurationDisclosure("ltx-2.5", 13, 24)).toBe("");
    expect(h3DurationDisclosure("auto", 13, 24)).toBe("");
  });
});
