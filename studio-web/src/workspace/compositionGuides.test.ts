import { describe, expect, it } from "vitest";
import {
  aspectFromDimensions,
  fitAspectRect,
  getCenterLineSegments,
  getCompositionRect,
  getSafeAreaRects,
  insetRect,
  ACTION_SAFE_INSET,
  TITLE_SAFE_INSET,
} from "./compositionGuides";

const VIEW = { w: 1600, h: 900 };

describe("fitAspectRect / getCompositionRect", () => {
  it("16:9 fills a 1600×900 viewport", () => {
    const rect = getCompositionRect(VIEW.w, VIEW.h, "16:9");
    expect(rect.x).toBeCloseTo(0);
    expect(rect.y).toBeCloseTo(0);
    expect(rect.width).toBeCloseTo(1600);
    expect(rect.height).toBeCloseTo(900);
  });

  it("21:9 letterboxes inside 1600×900", () => {
    const rect = getCompositionRect(VIEW.w, VIEW.h, "21:9");
    expect(rect.width).toBeCloseTo(1600);
    expect(rect.height).toBeCloseTo(1600 / (21 / 9), 1);
    expect(rect.x).toBeCloseTo(0);
    expect(rect.y).toBeCloseTo((900 - rect.height) / 2, 1);
    expect(rect.height).toBeLessThan(900);
  });

  it("9:16 pillarboxes inside 1600×900", () => {
    const rect = getCompositionRect(VIEW.w, VIEW.h, "9:16");
    expect(rect.height).toBeCloseTo(900);
    expect(rect.width).toBeCloseTo(900 * (9 / 16), 1);
    expect(rect.x).toBeCloseTo((1600 - rect.width) / 2, 1);
    expect(rect.y).toBeCloseTo(0);
  });

  it("1:1 pillarboxes inside 1600×900", () => {
    const rect = getCompositionRect(VIEW.w, VIEW.h, "1:1");
    expect(rect.width).toBeCloseTo(900);
    expect(rect.height).toBeCloseTo(900);
    expect(rect.x).toBeCloseTo(350);
    expect(rect.y).toBeCloseTo(0);
  });

  it("fitAspectRect matches getCompositionRect for 21:9", () => {
    const a = fitAspectRect(1600, 900, 21, 9);
    const b = getCompositionRect(1600, 900, "21:9");
    expect(a.width).toBeCloseTo(b.width);
    expect(a.height).toBeCloseTo(b.height);
    expect(a.x).toBeCloseTo(b.x);
    expect(a.y).toBeCloseTo(b.y);
  });

  it("returns empty for a zero-size viewport", () => {
    const rect = getCompositionRect(0, 0, "16:9");
    expect(rect.width).toBe(0);
    expect(rect.height).toBe(0);
  });

  it("unknown aspect defaults to 16:9", () => {
    const rect = getCompositionRect(1600, 900, "unknown");
    expect(rect.width).toBeCloseTo(1600);
    expect(rect.height).toBeCloseTo(900);
  });
});

describe("safe areas and center lines derive only from the master rect", () => {
  it("insets action safe by 5% and title safe by 10%", () => {
    const comp = getCompositionRect(1600, 900, "21:9");
    const safe = getSafeAreaRects(comp);
    const action = insetRect(comp, ACTION_SAFE_INSET);
    const title = insetRect(comp, TITLE_SAFE_INSET);
    expect(safe.actionSafe.x).toBeCloseTo(action.x);
    expect(safe.actionSafe.width).toBeCloseTo(action.width);
    expect(safe.titleSafe.x).toBeCloseTo(title.x);
    expect(safe.titleSafe.width).toBeCloseTo(title.width);
    expect(safe.actionSafe.x).toBeGreaterThan(comp.x);
    expect(safe.titleSafe.x).toBeGreaterThan(safe.actionSafe.x);
    expect(safe.titleSafe.x + safe.titleSafe.width).toBeLessThan(safe.actionSafe.x + safe.actionSafe.width);
  });

  it("clips center lines to the composition boundary", () => {
    const comp = getCompositionRect(1600, 900, "21:9");
    const lines = getCenterLineSegments(comp);
    expect(lines.horizontal.x1).toBeCloseTo(comp.x);
    expect(lines.horizontal.x2).toBeCloseTo(comp.x + comp.width);
    expect(lines.vertical.y1).toBeCloseTo(comp.y);
    expect(lines.vertical.y2).toBeCloseTo(comp.y + comp.height);
    expect(lines.horizontal.y).toBeCloseTo(comp.y + comp.height / 2);
    expect(lines.vertical.x).toBeCloseTo(comp.x + comp.width / 2);
  });
});

describe("aspectFromDimensions", () => {
  it("classifies published-master pixels onto the production catalog", () => {
    expect(aspectFromDimensions(1920, 1080)).toBe("16:9");
    expect(aspectFromDimensions(1920, 1088)).toBe("16:9");
    expect(aspectFromDimensions(720, 1280)).toBe("9:16");
    expect(aspectFromDimensions(1024, 1024)).toBe("1:1");
    expect(aspectFromDimensions(1344, 576)).toBe("21:9");
  });
});
