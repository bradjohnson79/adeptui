export const HOME_LIBRARY_VISIBLE_ROWS = 3;

export function measureFirstRowHeight(cards: ReadonlyArray<{ top: number; height: number }>): number {
  if (!cards.length) return 0;
  const firstTop = cards[0].top;
  const row = cards.filter((card) => Number.isFinite(card.height) && Math.abs(card.top - firstTop) <= 1.5);
  const heights = row.map((card) => card.height).filter((height) => height > 0);
  return heights.length ? Math.max(...heights) : 0;
}

export function threeRowLibraryMaxHeight(
  rowHeight: number,
  gap: number,
  rows = HOME_LIBRARY_VISIBLE_ROWS,
): number {
  if (!(rowHeight > 0) || !Number.isFinite(rowHeight)) return 0;
  const safeGap = Number.isFinite(gap) && gap >= 0 ? gap : 0;
  const safeRows = Number.isFinite(rows) && rows > 0 ? Math.floor(rows) : HOME_LIBRARY_VISIBLE_ROWS;
  return rowHeight * safeRows + safeGap * Math.max(0, safeRows - 1);
}

/** Fit as many complete rows as possible into a target footprint without clipping a row. */
export function completeRowsMaxHeight(rowHeight: number, gap: number, targetFootprint: number): number {
  if (!(rowHeight > 0) || !Number.isFinite(rowHeight)) return 0;
  const safeGap = Number.isFinite(gap) && gap >= 0 ? gap : 0;
  if (!(targetFootprint > 0) || !Number.isFinite(targetFootprint)) {
    return threeRowLibraryMaxHeight(rowHeight, safeGap);
  }
  const stride = rowHeight + safeGap;
  const rows = Math.max(1, Math.floor((targetFootprint + safeGap) / stride));
  return threeRowLibraryMaxHeight(rowHeight, safeGap, rows);
}
