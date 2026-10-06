import { describe, expect, it } from "vitest";
import { createImageElement, createTextElement, overlayVisibleAtFrame } from "./types";

describe("MAGI overlay timing", () => {
  it("hides overlays outside start/end frames", () => {
    const el = createTextElement({ startFrame: 48, endFrame: 168 });
    expect(overlayVisibleAtFrame(el, 47)).toBe(false);
    expect(overlayVisibleAtFrame(el, 48)).toBe(true);
    expect(overlayVisibleAtFrame(el, 167)).toBe(true);
    expect(overlayVisibleAtFrame(el, 168)).toBe(false);
  });

  it("creates image overlays with an asset id and contain fit", () => {
    const el = createImageElement("asset-logo", { startFrame: 0, endFrame: 72 });
    expect(el.type).toBe("image");
    expect(el.assetId).toBe("asset-logo");
    expect(el.fit).toBe("contain");
    expect(overlayVisibleAtFrame(el, 10)).toBe(true);
  });
});
