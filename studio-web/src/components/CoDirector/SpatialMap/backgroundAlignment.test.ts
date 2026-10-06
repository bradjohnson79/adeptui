import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  ALIGNMENT_MAX,
  ALIGNMENT_SCALE_MAX,
  ALIGNMENT_SCALE_MIN,
  alignmentFromOppositeAnchorResize,
  alignmentFromPixelPair,
  clampOffset,
  clampScale,
  containRect,
  displayPixels,
  hydrateAlignment,
  parseAlignmentInput,
  pixelsFromAlignment,
  transformPoint,
  transformedImageBounds,
  ZERO_ALIGNMENT,
} from "./backgroundAlignment";

describe("backgroundAlignment helpers", () => {
  it("hydrates missing and invalid values to zero", () => {
    expect(hydrateAlignment(undefined)).toEqual(ZERO_ALIGNMENT);
    expect(hydrateAlignment(null)).toEqual(ZERO_ALIGNMENT);
    expect(hydrateAlignment({})).toEqual(ZERO_ALIGNMENT);
    expect(hydrateAlignment({ offsetX: "nope", offsetY: Infinity })).toEqual(ZERO_ALIGNMENT);
  });

  it("hydrates missing scale to 1", () => {
    expect(hydrateAlignment({ offsetX: 0.2, offsetY: -0.1 })).toEqual({
      offsetX: 0.2,
      offsetY: -0.1,
      scale: 1,
      sourceWidth: 0,
      sourceHeight: 0,
      sourceAspectRatio: 1,
    });
    expect(ZERO_ALIGNMENT.scale).toBe(1);
  });

  it("containRect keeps 16:9 and 4:3 without stretching", () => {
    const wide = containRect(1000, 16 / 9);
    expect(wide.w / wide.h).toBeCloseTo(16 / 9);
    expect(wide.w).toBe(1000);
    expect(wide.y).toBeGreaterThan(0);
    const four = containRect(1000, 4 / 3);
    expect(four.w / four.h).toBeCloseTo(4 / 3);
    const portrait = containRect(1000, 9 / 16);
    expect(portrait.w / portrait.h).toBeCloseTo(9 / 16);
    expect(portrait.x).toBeGreaterThan(0);
  });

  it("clamps extreme offsets so the Atlas stays reachable", () => {
    expect(clampOffset(99999999)).toBe(ALIGNMENT_MAX);
    expect(clampOffset(-99999999)).toBe(-ALIGNMENT_MAX);
    expect(clampOffset(Number.NaN)).toBe(0);
  });

  it("clamps scale to 0.1..8", () => {
    expect(clampScale(999)).toBe(ALIGNMENT_SCALE_MAX);
    expect(clampScale(0.01)).toBe(ALIGNMENT_SCALE_MIN);
    expect(clampScale(Number.NaN)).toBe(1);
    expect(hydrateAlignment({ scale: 99 }).scale).toBe(8);
    expect(hydrateAlignment({ scale: 0 }).scale).toBe(0.1);
  });

  it("ZERO_ALIGNMENT includes scale 1", () => {
    expect(ZERO_ALIGNMENT).toEqual({
      offsetX: 0,
      offsetY: 0,
      scale: 1,
      sourceWidth: 0,
      sourceHeight: 0,
      sourceAspectRatio: 1,
    });
  });

  it("converts fraction to pixels stably at two canvas sizes", () => {
    const alignment = alignmentFromPixelPair(-24, 12, 480);
    expect(displayPixels(alignment, 480)).toEqual({ x: -24, y: 12 });
    const at600 = displayPixels(alignment, 600);
    expect(at600.x).toBe(Math.round((-24 / 480) * 600));
    expect(at600.y).toBe(Math.round((12 / 480) * 600));
    expect(pixelsFromAlignment(alignment.offsetX, 480)).toBeCloseTo(-24);
  });

  it("opposite-anchor SE resize pins NW and keeps contain aspect", () => {
    const box = containRect(1000, 16 / 9);
    const start = hydrateAlignment({ scale: 1, sourceAspectRatio: 16 / 9, sourceWidth: 1280, sourceHeight: 720 });
    const nw0 = transformPoint(box.x, box.y, 1000, start);
    const se0 = transformPoint(box.x + box.w, box.y + box.h, 1000, start);
    const next = alignmentFromOppositeAnchorResize(start, box, 1000, "se", {
      x: se0.x + 80,
      y: se0.y + 45,
    });
    expect(next.scale).toBeGreaterThan(start.scale);
    expect(next.sourceAspectRatio).toBeCloseTo(16 / 9);
    const nw1 = transformPoint(box.x, box.y, 1000, next);
    expect(nw1.x).toBeCloseTo(nw0.x, 2);
    expect(nw1.y).toBeCloseTo(nw0.y, 2);
    const bounds = transformedImageBounds(box, 1000, next);
    expect(bounds.w / bounds.h).toBeCloseTo(16 / 9, 4);
  });

  it("opposite-anchor NW resize inward shrinks without stretching 4:3", () => {
    const box = containRect(800, 4 / 3);
    const start = hydrateAlignment({ scale: 1.4, sourceAspectRatio: 4 / 3, sourceWidth: 800, sourceHeight: 600 });
    const se0 = transformPoint(box.x + box.w, box.y + box.h, 800, start);
    const nw0 = transformPoint(box.x, box.y, 800, start);
    const mid = { x: (nw0.x + se0.x) / 2, y: (nw0.y + se0.y) / 2 };
    const next = alignmentFromOppositeAnchorResize(start, box, 800, "nw", mid);
    expect(next.scale).toBeLessThan(start.scale);
    const se1 = transformPoint(box.x + box.w, box.y + box.h, 800, next);
    expect(se1.x).toBeCloseTo(se0.x, 2);
    expect(se1.y).toBeCloseTo(se0.y, 2);
    const bounds = transformedImageBounds(box, 800, next);
    expect(bounds.w / bounds.h).toBeCloseTo(4 / 3, 4);
  });

  it("parseAlignmentInput rejects blank and NaN", () => {
    expect(parseAlignmentInput("", 7)).toBe(7);
    expect(parseAlignmentInput("   ", 7)).toBe(7);
    expect(parseAlignmentInput("abc", 7)).toBe(7);
    expect(parseAlignmentInput("-18", 7)).toBe(-18);
  });
});

describe("Background Alignment chrome", () => {
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");
  const grid = readFileSync(new URL("./SpatialGrid.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("./spatialMap.css", import.meta.url), "utf8");

  it("places Background Alignment below Placement Precision and above Grid controls", () => {
    const precision = panel.indexOf('data-testid="placement-precision-control"');
    const alignment = panel.indexOf('data-testid="background-alignment"');
    const controls = panel.indexOf('data-testid="map-controls"');
    expect(precision).toBeGreaterThan(0);
    expect(alignment).toBeGreaterThan(precision);
    expect(controls).toBeGreaterThan(alignment);
    expect(panel).toContain("Background Alignment");
    expect(panel).toContain("Hand Tool");
    expect(panel).toContain("Resize");
    expect(panel).toContain("background-alignment-resize");
    expect(panel).toContain("background-alignment-x");
    expect(panel).toContain("background-alignment-y");
    expect(panel).toContain("background-alignment-reset");
    expect(panel).toContain("HelpTip");
    expect(panel).toContain("Click the Spatial Map picture to select it");
    expect(panel).toContain("Drag a corner to enlarge or shrink it");
    expect(panel).toContain("setHandActive(false)");
  });

  it("keeps Atlas translation on its own layer and does not move the grid", () => {
    expect(grid).toContain("spatial-map-atlas-layer");
    expect(grid).toContain("data-scale");
    expect(grid).toContain('data-fit="contain"');
    expect(grid).toContain('preserveAspectRatio="xMidYMid meet"');
    expect(grid).toContain('preserveAspectRatio="xMidYMid slice"');
    expect(grid).toContain('data-viewport="rect"');
    expect(grid).toContain('data-clip="none"');
    expect(grid).not.toContain("spatial-map-circle-clip");
    expect(grid).not.toContain("grid-wrap--circle");
    expect(grid).not.toContain("spatial-map__circle-stroke");
    expect(grid).not.toContain("clipPath");
    expect(grid).toContain("translate(${offsetPx} ${offsetPy}) translate(${cx} ${cy}) scale(${scale}) translate(${-cx} ${-cy})");
    expect(grid).toContain("spatial-map-grid-lines");
    expect(grid).toContain("handActive");
    expect(grid).toContain("setPointerCapture");
    expect(grid).toContain("spatial-map-transform-box");
    expect(grid).toContain("alignmentFromOppositeAnchorResize");
    expect(grid).toContain("bindWindowDrag");
    expect(grid.indexOf("spatial-map-atlas-layer")).toBeLessThan(grid.indexOf("spatial-map-grid-lines"));
    expect(grid).toContain("spatial-map-placement-grid-layer");
    expect(grid).toContain("spatial-map__cell-circle");
    expect(grid).toContain("validCells");
    expect(grid).toContain("showCircles");
    expect(grid).not.toContain("transform: `scale(${zoom})`");
    expect(grid).toContain("--spatial-map-zoom");
    expect(grid).toContain('data-zoom-domain="view"');
    expect(css).toContain("--spatial-map-zoom");
    expect(css).toContain(".spatial-map__cell-circle");
    expect(css).toContain(".spatial-map__grid-wrap--hide-circles .spatial-map__cell-circle");
    expect(css).not.toContain(".spatial-map__grid-wrap--circle");
    expect(css).not.toContain("spatial-map-circle-clip");
  });

  it("keeps Circles on the placement grid and never clips the Atlas picture", () => {
    expect(panel).toContain("map-toggle-circles");
    expect(panel).toContain("Show circles");
    expect(panel).toContain("showCircles");
    expect(panel).toContain("map-toggle-grid");
    expect(panel).toContain("map-toggle-labels");
    expect(panel).toContain("map-zoom-slider");
    expect(panel.indexOf("map-toggle-grid")).toBeLessThan(panel.indexOf("map-toggle-circles"));
    expect(panel.indexOf("map-toggle-circles")).toBeLessThan(panel.indexOf("map-toggle-labels"));
    const placeIdx = grid.indexOf("if (placementActive)");
    const swallow = grid.indexOf("if (onTransform) return");
    expect(placeIdx).toBeGreaterThan(0);
    expect(swallow).toBe(-1);
  });
});
