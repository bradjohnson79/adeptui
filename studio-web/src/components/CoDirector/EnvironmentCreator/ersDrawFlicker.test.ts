import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const drawing = readFileSync(new URL("./ErsDrawingLayer.tsx", import.meta.url), "utf8");
const mask = readFileSync(new URL("../../imageEdit/ImageMaskEditor.tsx", import.meta.url), "utf8");

function sliceBetween(source: string, start: string, end: string): string {
  const from = source.indexOf(start);
  const to = source.indexOf(end, from + start.length);
  return source.slice(from, to);
}

describe("ERS draw mode stays off the sheet repaint path", () => {
  it("keeps the in-progress stroke on the live canvas", () => {
    const move = sliceBetween(drawing, "const onPointerMove", "const onPointerUp");
    expect(drawing).toContain('data-testid="ers-drawing-live"');
    expect(drawing).toContain('data-testid="ers-drawing-committed"');
    expect(move).toContain("paintLive()");
    expect(move).not.toContain("commitDoc");
    expect(move).not.toContain("setDoc");
  });

  it("does not end a stroke when the pointer slips off the sheet", () => {
    expect(drawing).not.toContain("onPointerLeave={onPointerUp}");
    expect(drawing).toContain("onPointerCancel={onPointerUp}");
  });

  it("does not redraw the ERS image when the fitted size is unchanged", () => {
    const resize = sliceBetween(mask, "new ResizeObserver", "ro.observe");
    expect(resize).toContain("if (fit.changed) syncDisplayRef.current()");
    expect(mask).toContain("if (!changed) return");
  });
});
