import { describe, expect, it } from "vitest";
import {
  completeRowsMaxHeight,
  HOME_LIBRARY_VISIBLE_ROWS,
  measureFirstRowHeight,
  threeRowLibraryMaxHeight,
} from "./libraryRowBounds";

describe("libraryRowBounds", () => {
  it("derives three complete rows from card height plus gap", () => {
    expect(HOME_LIBRARY_VISIBLE_ROWS).toBe(3);
    expect(threeRowLibraryMaxHeight(200, 16)).toBe(200 * 3 + 16 * 2);
  });

  it("does not invent a height when the first row has not measured", () => {
    expect(threeRowLibraryMaxHeight(0, 16)).toBe(0);
    expect(threeRowLibraryMaxHeight(-4, 16)).toBe(0);
  });

  it("uses the tallest card in the first row as the uniform row height", () => {
    expect(
      measureFirstRowHeight([
        { top: 100, height: 461 },
        { top: 100, height: 453 },
        { top: 100, height: 453 },
        { top: 577, height: 430 },
      ]),
    ).toBe(461);
  });

  it("fits complete list rows into the grid footprint without clipping", () => {
    const gridFootprint = threeRowLibraryMaxHeight(280, 16);
    const listHeight = completeRowsMaxHeight(88, 12, gridFootprint);
    expect(listHeight).toBeLessThanOrEqual(gridFootprint);
    const stride = 88 + 12;
    expect((listHeight + 12) % stride).toBe(0);
  });
});
