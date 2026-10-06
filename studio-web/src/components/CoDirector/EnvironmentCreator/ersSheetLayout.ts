/**
 * ERS sheet master used by Edit/Inpaint.
 * Middle row is Spatial Map, Legend, Structuring / 3D.
 * Fractions are of the full sheet so they track any zoomed raster.
 */

export const ERS_SHEET_MASTER = { width: 2048, height: 1536 } as const;

/** Edit/Inpaint zoom-in stops here. Fit returns to 1. */
export const ERS_EDIT_ZOOM_MAX = 12;

export const ERS_LEGEND_FOOTNOTE = "Use a color for each character or prop in scene.";

export const ERS_LEGEND_SLOT_COUNT = 4;

/** Usable margin when clamping the Legend overlay inside the sheet (normalized). */
export const ERS_LEGEND_SHEET_MARGIN = 0.01;

/** Middle band of the 4:3 master. Tall enough for eight legend slots. */
export const ERS_MIDDLE_ROW = {
  top: 0.28,
  height: 0.42,
  columns: [
    { id: "spatial", label: "Spatial Map", width: 0.42 },
    { id: "legend", label: "Legend", width: 0.16 },
    { id: "structuring", label: "Structuring / 3D", width: 0.42 },
  ],
} as const;

export type ErsMiddleColumnId = (typeof ERS_MIDDLE_ROW.columns)[number]["id"];

export type ErsNormalizedBox = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export function ersMiddleColumnBox(id: ErsMiddleColumnId): ErsNormalizedBox {
  let left = 0;
  for (const column of ERS_MIDDLE_ROW.columns) {
    if (column.id === id) {
      return {
        left,
        top: ERS_MIDDLE_ROW.top,
        width: column.width,
        height: ERS_MIDDLE_ROW.height,
      };
    }
    left += column.width;
  }
  return { left: 0, top: ERS_MIDDLE_ROW.top, width: 0, height: ERS_MIDDLE_ROW.height };
}

/** Default Legend insert box: center column between Spatial Map and Structuring / 3D. */
export function defaultErsLegendBox(): ErsNormalizedBox {
  return ersMiddleColumnBox("legend");
}

/**
 * Clamp a Legend overlay box to the ERS sheet in normalized (0..1) source-canvas coords.
 * Survives zoom/pan because callers store fractions of the sheet, not screen pixels.
 */
export function clampErsLegendBox(
  box: ErsNormalizedBox,
  margin: number = ERS_LEGEND_SHEET_MARGIN,
): ErsNormalizedBox {
  const m = Math.max(0, Math.min(0.2, margin));
  const width = Math.min(Math.max(box.width, 0.05), 1 - 2 * m);
  const height = Math.min(Math.max(box.height, 0.05), 1 - 2 * m);
  const maxLeft = Math.max(m, 1 - m - width);
  const maxTop = Math.max(m, 1 - m - height);
  const left = Math.min(Math.max(box.left, m), maxLeft);
  const top = Math.min(Math.max(box.top, m), maxTop);
  return { left, top, width, height };
}

/**
 * Apply a pointer delta (screen px) against the sheet element size to a normalized box.
 * sheetClientWidth/Height must be the ERS frame's CSS size (already zoomed).
 */
export function moveErsLegendBoxByPointerDelta(
  start: ErsNormalizedBox,
  deltaClientX: number,
  deltaClientY: number,
  sheetClientWidth: number,
  sheetClientHeight: number,
  margin: number = ERS_LEGEND_SHEET_MARGIN,
): ErsNormalizedBox {
  const w = Math.max(1, sheetClientWidth);
  const h = Math.max(1, sheetClientHeight);
  return clampErsLegendBox(
    {
      ...start,
      left: start.left + deltaClientX / w,
      top: start.top + deltaClientY / h,
    },
    margin,
  );
}
