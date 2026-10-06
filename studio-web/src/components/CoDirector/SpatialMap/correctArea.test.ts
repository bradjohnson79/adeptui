import { describe, expect, it } from "vitest";
import {
  GPT_MASK_BLOCKED,
  ENGINE_HOLD,
  ZIMAGE_INPAINT_CERTIFIED,
  CERTIFIED_CORRECT_AREA_ENGINE,
  buildSubmitPreview,
  computeMaskScale,
  correctAreaSummary,
  isEngineBlocked,
  isQueuedSession,
  normalizeCorrectAreaSubmitResult,
  stripPngDataUrl,
  asPngDataUrl,
  atlasContainBox,
  displayedAtlasRect,
  viewBoxToSourcePixel,
  sourcePixelToViewBox,
} from "./correctArea";
import { ZERO_ALIGNMENT, type BackgroundAlignment } from "./backgroundAlignment";

describe("spatial map correctArea helpers", () => {
  it("treats missing state as blocked", () => {
    expect(isEngineBlocked(null)).toBe(true);
    expect(isEngineBlocked(undefined)).toBe(true);
  });

  it("blocks Apply unless honestly executable (zimage + executable + no hold)", () => {
    expect(
      isEngineBlocked({ engineStatus: GPT_MASK_BLOCKED, executable: false }),
    ).toBe(true);
    expect(
      isEngineBlocked({
        engineStatus: CERTIFIED_CORRECT_AREA_ENGINE,
        executable: true,
        engineHold: null,
        zimageWired: true,
      }),
    ).toBe(false);
    expect(
      isEngineBlocked({ engineStatus: ZIMAGE_INPAINT_CERTIFIED, executable: true }),
    ).toBe(false);
    // blocked status wins even if executable flag is somehow true
    expect(
      isEngineBlocked({ engineStatus: GPT_MASK_BLOCKED, executable: true }),
    ).toBe(true);
    // hold keeps Apply disabled
    expect(
      isEngineBlocked({
        engineStatus: CERTIFIED_CORRECT_AREA_ENGINE,
        executable: true,
        engineHold: ENGINE_HOLD,
      }),
    ).toBe(true);
    // executable false keeps Apply disabled
    expect(
      isEngineBlocked({
        engineStatus: CERTIFIED_CORRECT_AREA_ENGINE,
        executable: false,
        engineHold: null,
      }),
    ).toBe(true);
  });

  it("summarizes chain, queued, and unlocked states", () => {
    expect(correctAreaSummary(null)).toContain("Correct Area");
    expect(
      correctAreaSummary({
        engineStatus: ZIMAGE_INPAINT_CERTIFIED,
        executable: true,
        acceptedChain: [{}, {}],
        canUndo: true,
      }),
    ).toContain("v2");
    expect(
      correctAreaSummary({
        engineStatus: ZIMAGE_INPAINT_CERTIFIED,
        executable: true,
        zimageWired: true,
      }),
    ).toContain("zimage.inpaint unlocked");
    expect(
      correctAreaSummary({
        engineStatus: ZIMAGE_INPAINT_CERTIFIED,
        executable: true,
        activeSession: { sessionId: "s1", sourceAssetId: "a", maskAssetId: "m", creatorPrompt: "x", engineStatus: ZIMAGE_INPAINT_CERTIFIED, status: "queued" },
      }),
    ).toContain("running");
    expect(
      correctAreaSummary({
        engineStatus: GPT_MASK_BLOCKED,
        executable: false,
      }),
    ).toContain("GPT mask blocked");
  });

  it("detects queued session statuses", () => {
    expect(isQueuedSession({ sessionId: "1", sourceAssetId: "a", maskAssetId: "m", creatorPrompt: "p", engineStatus: ZIMAGE_INPAINT_CERTIFIED, status: "queued" })).toBe(true);
    expect(isQueuedSession({ sessionId: "1", sourceAssetId: "a", maskAssetId: "m", creatorPrompt: "p", engineStatus: ZIMAGE_INPAINT_CERTIFIED, status: "preview_ready" })).toBe(false);
  });

  it("computes display-to-source mask scale for alignment", () => {
    const same = computeMaskScale({
      displayWidth: 1024,
      displayHeight: 512,
      sourceWidth: 1024,
      sourceHeight: 512,
    });
    expect(same.needsUpscale).toBe(false);
    expect(same.scaleX).toBe(1);
    expect(same.scaleY).toBe(1);

    const up = computeMaskScale({
      displayWidth: 512,
      displayHeight: 256,
      sourceWidth: 2048,
      sourceHeight: 1024,
    });
    expect(up.needsUpscale).toBe(true);
    expect(up.scaleX).toBe(4);
    expect(up.scaleY).toBe(4);
  });

  it("buildSubmitPreview gates Apply until mask+prompt+source dims", () => {
    const notReady = buildSubmitPreview({
      prompt: "",
      sourceAssetId: "src-1",
      maskPreviewUrl: null,
      preserveStyle: true,
      preservePerspective: true,
      preserveLighting: true,
      sourceWidth: 0,
      sourceHeight: 0,
    });
    expect(notReady.ready).toBe(false);

    const ready = buildSubmitPreview({
      prompt: "fix crate",
      sourceAssetId: "src-1",
      maskPreviewUrl: "data:image/png;base64,xx",
      preserveStyle: true,
      preservePerspective: true,
      preserveLighting: true,
      sourceWidth: 2048,
      sourceHeight: 1024,
    });
    expect(ready.ready).toBe(true);
    expect(ready.lines.some((l) => l.includes("style=true"))).toBe(true);
    expect(ready.lines.some((l) => l.includes("perspective=true"))).toBe(true);
    expect(ready.lines.some((l) => l.includes("lighting=true"))).toBe(true);
    expect(ENGINE_HOLD).toContain("ENGINE_HOLD");
    expect(ZIMAGE_INPAINT_CERTIFIED).toBe("ZIMAGE_INPAINT_CERTIFIED");
    expect(CERTIFIED_CORRECT_AREA_ENGINE).toBe("zimage.inpaint");
  });

  it("normalizes startCorrectArea payloads without inventing pixels", () => {
    const held = normalizeCorrectAreaSubmitResult({
      engineStatus: GPT_MASK_BLOCKED,
      executable: false,
      engineHold: ENGINE_HOLD,
      message: "held",
    });
    expect(held.blocked).toBe(true);
    expect(held.resultAssetId).toBeNull();

    const preview = normalizeCorrectAreaSubmitResult({
      engineStatus: CERTIFIED_CORRECT_AREA_ENGINE,
      executable: true,
      zimageWired: true,
      resultAssetId: "asset-1",
      previewUrl: "/media/preview.png",
      acceptToken: "tok",
      jobId: "job-1",
      parentAssetId: "src-1",
      session: {
        sessionId: "job-1",
        sourceAssetId: "src-1",
        maskAssetId: "mask-1",
        creatorPrompt: "fix crate",
        engineStatus: CERTIFIED_CORRECT_AREA_ENGINE,
        executable: true,
        outputAssetId: "asset-1",
        status: "preview_ready",
      },
    });
    expect(preview.blocked).toBe(false);
    expect(preview.resultAssetId).toBe("asset-1");
    expect(preview.session?.acceptToken).toBe("tok");
    expect(preview.previewUrl).toBe("/media/preview.png");
  });

  it("normalizes png data urls", () => {
    expect(stripPngDataUrl("data:image/png;base64,abc")).toBe("abc");
    expect(asPngDataUrl("abc")).toBe("data:image/png;base64,abc");
    expect(asPngDataUrl("data:image/png;base64,abc")).toBe("data:image/png;base64,abc");
  });
});

describe("viewport parity contract (Spatial Map ↔ Correct Area)", () => {
  const SIZE = 512;
  const SW = 1670; // Mess Hall source width
  const SH = 941;  // Mess Hall source height

  it("contain box matches source aspect and centers in the square viewBox", () => {
    const box = atlasContainBox(SIZE, SW, SH);
    // Wider than tall → full width, vertically letterboxed.
    expect(box.width).toBeCloseTo(SIZE, 6);
    expect(box.height).toBeCloseTo(SIZE / (SW / SH), 6);
    expect(box.x).toBeCloseTo(0, 6);
    expect(box.y).toBeCloseTo((SIZE - box.height) / 2, 6);
    // Aspect preserved.
    expect(box.width / box.height).toBeCloseTo(SW / SH, 6);
  });

  it("displayed rect equals contain box under zero alignment", () => {
    const contain = atlasContainBox(SIZE, SW, SH);
    const disp = displayedAtlasRect(SIZE, SW, SH, ZERO_ALIGNMENT);
    expect(disp.x).toBeCloseTo(contain.x, 6);
    expect(disp.y).toBeCloseTo(contain.y, 6);
    expect(disp.width).toBeCloseTo(contain.width, 6);
    expect(disp.height).toBeCloseTo(contain.height, 6);
  });

  it("displayed rect tracks freehand offset + uniform scale (shared transform)", () => {
    const aligned: BackgroundAlignment = {
      offsetX: 0.1,
      offsetY: -0.05,
      scale: 1.35,
      sourceWidth: SW,
      sourceHeight: SH,
      sourceAspectRatio: SW / SH,
    };
    const contain = atlasContainBox(SIZE, SW, SH);
    const disp = displayedAtlasRect(SIZE, SW, SH, aligned);
    // Scaled up about center.
    expect(disp.width).toBeCloseTo(contain.width * 1.35, 6);
    expect(disp.height).toBeCloseTo(contain.height * 1.35, 6);
    // Center shifted by offset*size.
    const containCx = contain.x + contain.width / 2;
    const containCy = contain.y + contain.height / 2;
    const dispCx = disp.x + disp.width / 2;
    const dispCy = disp.y + disp.height / 2;
    expect(dispCx).toBeCloseTo(containCx + 0.1 * SIZE, 6);
    expect(dispCy).toBeCloseTo(containCy - 0.05 * SIZE, 6);
  });

  it("center of the source maps to the atlas center under zero alignment", () => {
    const px = viewBoxToSourcePixel(SIZE / 2, SIZE / 2, SIZE, SW, SH, ZERO_ALIGNMENT);
    expect(px).not.toBeNull();
    expect(px!.x).toBeCloseTo(SW / 2, 4);
    expect(px!.y).toBeCloseTo(SH / 2, 4);
  });

  it("round-trips source pixel ↔ viewBox under pan + zoom (no drift)", () => {
    const aligned: BackgroundAlignment = {
      offsetX: 0.12,
      offsetY: 0.07,
      scale: 1.35,
      sourceWidth: SW,
      sourceHeight: SH,
      sourceAspectRatio: SW / SH,
    };
    const src = { x: 835, y: 470 }; // Mess Hall central table (approx)
    const vb = sourcePixelToViewBox(src.x, src.y, SIZE, SW, SH, aligned);
    const back = viewBoxToSourcePixel(vb.x, vb.y, SIZE, SW, SH, aligned);
    expect(back).not.toBeNull();
    expect(back!.x).toBeCloseTo(src.x, 3);
    expect(back!.y).toBeCloseTo(src.y, 3);
  });

  it("maps displayed corners to source corners (no offset / no scale drift)", () => {
    const aligned: BackgroundAlignment = {
      offsetX: -0.08,
      offsetY: 0.04,
      scale: 1.2,
      sourceWidth: SW,
      sourceHeight: SH,
      sourceAspectRatio: SW / SH,
    };
    const disp = displayedAtlasRect(SIZE, SW, SH, aligned);
    const tl = viewBoxToSourcePixel(disp.x, disp.y, SIZE, SW, SH, aligned);
    const br = viewBoxToSourcePixel(disp.x + disp.width, disp.y + disp.height, SIZE, SW, SH, aligned);
    expect(tl!.x).toBeCloseTo(0, 3);
    expect(tl!.y).toBeCloseTo(0, 3);
    expect(br!.x).toBeCloseTo(SW, 3);
    expect(br!.y).toBeCloseTo(SH, 3);
  });

  it("returns null for viewBox points outside the displayed atlas", () => {
    // Far corner of the square viewBox, off the letterboxed image.
    const px = viewBoxToSourcePixel(SIZE - 1, SIZE - 1, SIZE, SW, SH, ZERO_ALIGNMENT);
    expect(px).toBeNull();
  });

  it("is DPR/browser-size independent: same source pixel regardless of viewBox size", () => {
    const src = { x: 835, y: 470 };
    for (const s of [256, 480, 512, 920]) {
      const vb = sourcePixelToViewBox(src.x, src.y, s, SW, SH, ZERO_ALIGNMENT);
      const back = viewBoxToSourcePixel(vb.x, vb.y, s, SW, SH, ZERO_ALIGNMENT);
      expect(back!.x).toBeCloseTo(src.x, 3);
      expect(back!.y).toBeCloseTo(src.y, 3);
    }
  });
});
