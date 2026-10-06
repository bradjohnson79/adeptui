import { describe, expect, it } from "vitest";

import {
  ERS_ANNOTATION_COLORS,
  ERS_LEGEND_CHARACTER_COLORS,
  ERS_LEGEND_PROP_COLORS,
} from "./ersAnnotationPalette";
import {
  ERS_EDIT_ZOOM_MAX,
  ERS_LEGEND_FOOTNOTE,
  ERS_LEGEND_SLOT_COUNT,
  ERS_MIDDLE_ROW,
  ERS_SHEET_MASTER,
  clampErsLegendBox,
  defaultErsLegendBox,
  ersMiddleColumnBox,
  moveErsLegendBoxByPointerDelta,
} from "./ersSheetLayout";

describe("ERS sheet legend layout", () => {
  it("uses a 4:3 2048x1536 master", () => {
    expect(ERS_SHEET_MASTER).toEqual({ width: 2048, height: 1536 });
    expect(ERS_SHEET_MASTER.width / ERS_SHEET_MASTER.height).toBeCloseTo(4 / 3, 5);
  });

  it("places Legend between Spatial Map and Structuring / 3D", () => {
    expect(ERS_MIDDLE_ROW.columns.map((column) => column.label)).toEqual([
      "Spatial Map",
      "Legend",
      "Structuring / 3D",
    ]);
    expect(ERS_MIDDLE_ROW.columns.map((column) => column.width)).toEqual([0.42, 0.16, 0.42]);
    const spatial = ersMiddleColumnBox("spatial");
    const legend = ersMiddleColumnBox("legend");
    const structuring = ersMiddleColumnBox("structuring");
    expect(legend.left).toBeCloseTo(spatial.left + spatial.width);
    expect(structuring.left).toBeCloseTo(legend.left + legend.width);
    expect(spatial.left + spatial.width + legend.width + structuring.width).toBeCloseTo(1);
  });

  it("defines four character slots, four prop slots, and the footnote", () => {
    expect(ERS_LEGEND_SLOT_COUNT).toBe(4);
    expect(ERS_LEGEND_FOOTNOTE).toBe("Use a color for each character or prop in scene.");
  });

  it("lists the ten annotation colors in order", () => {
    expect(ERS_ANNOTATION_COLORS.map((swatch) => swatch.name)).toEqual([
      "White",
      "Red",
      "Orange",
      "Yellow",
      "Green",
      "Aqua",
      "Blue",
      "Purple",
      "Gray",
      "Black",
    ]);
  });

  it("caps Edit zoom at 12x", () => {
    expect(ERS_EDIT_ZOOM_MAX).toBe(12);
  });

  it("seeds legend slots red through green, then aqua through gray", () => {
    expect(ERS_LEGEND_CHARACTER_COLORS).toEqual(["#ef4444", "#f97316", "#eab308", "#22c55e"]);
    expect(ERS_LEGEND_PROP_COLORS).toEqual(["#22d3ee", "#3b82f6", "#a855f7", "#9ca3af"]);
  });

  it("defaults Legend to the center column box", () => {
    expect(defaultErsLegendBox()).toEqual(ersMiddleColumnBox("legend"));
  });

  it("clamps Legend position inside sheet bounds with margin", () => {
    const clamped = clampErsLegendBox({ left: -0.5, top: 2, width: 0.16, height: 0.3 });
    expect(clamped.left).toBeGreaterThanOrEqual(0.01);
    expect(clamped.top + clamped.height).toBeLessThanOrEqual(0.99 + 1e-9);
    expect(clamped.left + clamped.width).toBeLessThanOrEqual(0.99 + 1e-9);
  });

  it("maps pointer deltas in sheet CSS pixels to normalized coords", () => {
    const start = defaultErsLegendBox();
    const moved = moveErsLegendBoxByPointerDelta(start, 100, -50, 1000, 750);
    expect(moved.left).toBeCloseTo(start.left + 0.1, 5);
    expect(moved.top).toBeCloseTo(start.top - 50 / 750, 5);
  });

  it("keeps free drag from re-locking to the center column", () => {
    const start = defaultErsLegendBox();
    const moved = moveErsLegendBoxByPointerDelta(start, -200, 0, 1000, 750);
    expect(moved.left).toBeLessThan(start.left);
    expect(moved.left).not.toBeCloseTo(ersMiddleColumnBox("legend").left, 3);
  });

  it("stores source-sheet fractions so zoom/pan CSS size does not resize Legend W/H", () => {
    const start = defaultErsLegendBox();
    // Same pointer delta at 1x vs 4x frame CSS size => different normalized delta,
    // but W/H stay identical (no independent resize during zoom).
    const at1x = moveErsLegendBoxByPointerDelta(start, 40, 20, 1000, 750);
    const at4x = moveErsLegendBoxByPointerDelta(start, 160, 80, 4000, 3000);
    expect(at1x.width).toBeCloseTo(start.width, 8);
    expect(at1x.height).toBeCloseTo(start.height, 8);
    expect(at4x.width).toBeCloseTo(start.width, 8);
    expect(at4x.height).toBeCloseTo(start.height, 8);
    expect(at1x.left).toBeCloseTo(at4x.left, 8);
    expect(at1x.top).toBeCloseTo(at4x.top, 8);
  });
});
