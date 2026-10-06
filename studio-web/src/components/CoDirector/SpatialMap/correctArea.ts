/** Spatial Map Correct Area helpers — Certified zimage.inpaint (Brad 2026-09-11). */

import {
  containRect,
  pixelsFromAlignment,
  sourceAspect,
  transformedImageBounds,
  transformPoint,
  type BackgroundAlignment,
} from "./backgroundAlignment";

export const GPT_MASK_BLOCKED = "GPT_MASK_BLOCKED_NEED_BRAD";
export const ENGINE_HOLD = "ENGINE_HOLD_PENDING_BRAD";
export const ZIMAGE_INPAINT_CERTIFIED = "ZIMAGE_INPAINT_CERTIFIED";
/** Creator-facing certified engine id — must stay exported (CorrectAreaPanel boots App). */
export const CERTIFIED_CORRECT_AREA_ENGINE = "zimage.inpaint";

export const CORRECT_AREA_PRESERVATION_HINT =
  "Outside the mask stays pixel-exact. Dimensions unchanged. Characters, cameras, and movement overlays stay on the map.";

export type CorrectAreaEngineState = {
  engineStatus: string;
  executable: boolean;
  engineHold?: string | null;
  preferredModel?: string;
  zimageWired?: boolean;
  reason?: string;
  activeSession?: CorrectAreaSession | null;
  acceptedChain?: Array<Record<string, unknown>>;
  canUndo?: boolean;
  originalBackgroundAssetId?: string | null;
  currentBackgroundAssetId?: string | null;
  workflowKey?: string;
  atlasGenerationUnchanged?: boolean;
};

export type CorrectAreaSession = {
  sessionId: string;
  sourceAssetId: string;
  maskAssetId: string;
  creatorPrompt: string;
  composedPrompt?: string;
  frozen?: boolean;
  coDirectorRewrite?: boolean;
  engineStatus: string;
  executable?: boolean;
  outputAssetId?: string | null;
  resultAssetId?: string | null;
  status?: string;
  reason?: string;
  versionId?: string;
  preferredModel?: string;
  zimageWired?: boolean;
  acceptToken?: string | null;
  preserveStyle?: boolean;
  preservePerspective?: boolean;
  preserveLighting?: boolean;
  providerJobId?: string | null;
  previewUrl?: string | null;
  engineHold?: string | null;
};

export type MaskAlignment = {
  /** Display canvas size used while painting (CSS/layout scaled). */
  displayWidth: number;
  displayHeight: number;
  /** Source Spatial Map natural pixel size (master). */
  sourceWidth: number;
  sourceHeight: number;
  /** CSS bounding-box size of the display canvas (may differ under DPR/zoom). */
  cssWidth: number;
  cssHeight: number;
  devicePixelRatio: number;
};

/**
 * CRITICAL: mask must map 1:1 to source Spatial Map pixels.
 * ImageMaskEditor paints at display size; we upscale to natural WxH with
 * nearest-neighbor (no blur) so white=edit / black=preserve edges stay hard.
 *
 * Pointer mapping already uses getBoundingClientRect → canvas.width/height
 * (ImageMaskEditor.canvasPoint), so CSS scale and aspect letterboxing are
 * cancelled at paint time. This helper only reconciles display→source.
 */
export function computeMaskScale(align: Pick<MaskAlignment, "displayWidth" | "displayHeight" | "sourceWidth" | "sourceHeight">): {
  scaleX: number;
  scaleY: number;
  needsUpscale: boolean;
} {
  const dw = Math.max(1, align.displayWidth || 0);
  const dh = Math.max(1, align.displayHeight || 0);
  const sw = Math.max(1, align.sourceWidth || 0);
  const sh = Math.max(1, align.sourceHeight || 0);
  const scaleX = sw / dw;
  const scaleY = sh / dh;
  const needsUpscale = Math.abs(scaleX - 1) > 0.001 || Math.abs(scaleY - 1) > 0.001;
  return { scaleX, scaleY, needsUpscale };
}

export function stripPngDataUrl(png: string): string {
  const raw = (png || "").trim();
  if (!raw) return "";
  return raw.replace(/^data:image\/png;base64,/i, "");
}

export function asPngDataUrl(png: string): string {
  const raw = (png || "").trim();
  if (!raw) return "";
  return raw.startsWith("data:") ? raw : `data:image/png;base64,${raw}`;
}

/**
 * Upscale a display-sized mask PNG to exact source natural dimensions.
 * Uses nearest-neighbor so mask binary edges stay crisp.
 * Returns base64 (no data: prefix) + dims for API width/height.
 */
export async function alignMaskToSourcePixels(
  displayPngBase64: string,
  sourceWidth: number,
  sourceHeight: number,
): Promise<{ pngBase64: string; width: number; height: number; upscaled: boolean }> {
  const sw = Math.max(1, Math.round(sourceWidth));
  const sh = Math.max(1, Math.round(sourceHeight));
  const dataUrl = asPngDataUrl(displayPngBase64);
  if (!dataUrl) {
    throw new Error("Mask PNG is empty — paint a region first.");
  }

  const img = await loadImageElement(dataUrl);
  const dw = img.naturalWidth || img.width;
  const dh = img.naturalHeight || img.height;
  if (dw === sw && dh === sh) {
    return { pngBase64: stripPngDataUrl(dataUrl), width: sw, height: sh, upscaled: false };
  }

  const canvas = document.createElement("canvas");
  canvas.width = sw;
  canvas.height = sh;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Could not create mask alignment canvas.");
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, sw, sh);
  ctx.drawImage(img, 0, 0, dw, dh, 0, 0, sw, sh);
  const out = canvas.toDataURL("image/png");
  return { pngBase64: stripPngDataUrl(out), width: sw, height: sh, upscaled: true };
}

function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to decode mask PNG for alignment."));
    img.src = src;
  });
}

export function probeSourceNaturalSize(imageUrl: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    if (!imageUrl) {
      reject(new Error("Source image URL required for mask alignment."));
      return;
    }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () =>
      resolve({
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
      });
    img.onerror = () => reject(new Error("Failed to load source Spatial Map for mask alignment."));
    img.src = imageUrl;
  });
}

export function isEngineBlocked(
  state: Pick<CorrectAreaEngineState, "engineStatus" | "executable" | "engineHold" | "preferredModel" | "zimageWired"> | null | undefined,
): boolean {
  // Apply stays disabled unless honestly executable:
  // engine=zimage.inpaint (or certified status), executable=true, engineHold=null.
  if (!state) return true;
  if (state.executable !== true) return true;
  const hold = (state.engineHold ?? "").toString().trim();
  if (hold) return true;
  const status = (state.engineStatus || "").trim();
  if (
    status === GPT_MASK_BLOCKED ||
    status === ENGINE_HOLD ||
    status.includes("GPT_MASK_BLOCKED") ||
    status.includes("ENGINE_HOLD")
  ) {
    return true;
  }
  const engineOk =
    status === CERTIFIED_CORRECT_AREA_ENGINE ||
    status === ZIMAGE_INPAINT_CERTIFIED ||
    (state.preferredModel || "") === CERTIFIED_CORRECT_AREA_ENGINE ||
    state.zimageWired === true;
  return !engineOk;
}

export function isQueuedSession(session: CorrectAreaSession | null | undefined): boolean {
  const st = (session?.status || "").toLowerCase();
  return st === "queued" || st === "running" || st === "generating" || st === "processing";
}

export function correctAreaSummary(state: CorrectAreaEngineState | null | undefined): string {
  if (!state) return "Correct Area / Inpaint Re-prompt";
  const chain = state.acceptedChain?.length || 0;
  if (chain > 0) return `Correct Area · v${chain} · Undo available`;
  if (state.activeSession?.status === "preview_ready") return "Correct Area · preview ready";
  if (isQueuedSession(state.activeSession)) return "Correct Area · zimage.inpaint running";
  if (isEngineBlocked(state)) return "Correct Area · GPT mask blocked";
  if (state.zimageWired || state.engineStatus === ZIMAGE_INPAINT_CERTIFIED) {
    return "Correct Area · zimage.inpaint unlocked";
  }
  return "Correct Area / Inpaint Re-prompt";
}

export function buildSubmitPreview(args: {
  prompt: string;
  sourceAssetId: string;
  maskPreviewUrl: string | null;
  preserveStyle: boolean;
  preservePerspective: boolean;
  preserveLighting: boolean;
  sourceWidth: number;
  sourceHeight: number;
}): {
  ready: boolean;
  lines: string[];
} {
  const prompt = (args.prompt || "").trim();
  const hasMask = Boolean(args.maskPreviewUrl);
  const ready = Boolean(prompt && hasMask && args.sourceAssetId && args.sourceWidth > 0 && args.sourceHeight > 0);
  const lines = [
    `Source asset: ${args.sourceAssetId || "(missing)"}`,
    `Source pixels: ${args.sourceWidth || "?"}×${args.sourceHeight || "?"}`,
    `Mask: ${hasMask ? "ready (aligned to source)" : "not painted"}`,
    `Prompt: ${prompt || "(empty)"}`,
    `Preserve: style=${args.preserveStyle} · perspective=${args.preservePerspective} · lighting=${args.preserveLighting}`,
  ];
  return { ready, lines };
}

export type CorrectAreaSubmitNormalized = {
  session: CorrectAreaSession | null;
  engineStatus: string;
  executable: boolean;
  reason?: string;
  message?: string;
  engineHold?: string | null;
  preferredModel?: string;
  zimageWired?: boolean;
  previewUrl?: string | null;
  resultAssetId?: string | null;
  blocked: boolean;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

/**
 * Flatten startCorrectArea payloads so Accept ungates only on real pixels.
 * Missing/hold results stay honest — no fake resultAssetId.
 */
export function normalizeCorrectAreaSubmitResult(raw: Record<string, unknown> | null | undefined): CorrectAreaSubmitNormalized {
  const payload = asRecord(raw) || {};
  const nested = asRecord(payload.session);
  const resultAssetId =
    asString(payload.resultAssetId) ||
    asString(payload.outputAssetId) ||
    asString(nested?.resultAssetId) ||
    asString(nested?.outputAssetId) ||
    null;
  const previewUrl =
    asString(payload.previewUrl) || asString(nested?.previewUrl) || null;
  const engineStatus =
    asString(payload.engineStatus) ||
    asString(nested?.engineStatus) ||
    asString(payload.engine) ||
    CERTIFIED_CORRECT_AREA_ENGINE;
  const executable = payload.executable === true || nested?.executable === true;
  const engineHold = asString(payload.engineHold) || asString(nested?.engineHold) || null;
  const session: CorrectAreaSession | null = nested
    ? {
        sessionId: asString(nested.sessionId) || asString(payload.jobId) || asString(payload.queueJobId) || "",
        sourceAssetId: asString(nested.sourceAssetId) || asString(payload.parentAssetId) || "",
        maskAssetId: asString(nested.maskAssetId) || "",
        creatorPrompt: asString(nested.creatorPrompt) || "",
        composedPrompt: asString(nested.composedPrompt),
        frozen: nested.frozen === true,
        coDirectorRewrite: nested.coDirectorRewrite === true,
        engineStatus: asString(nested.engineStatus) || engineStatus,
        executable: nested.executable === true || executable,
        outputAssetId: asString(nested.outputAssetId) || resultAssetId,
        resultAssetId: asString(nested.resultAssetId) || resultAssetId,
        status: asString(nested.status) || asString(payload.status),
        reason: asString(nested.reason) || asString(payload.reason),
        versionId: asString(nested.versionId),
        preferredModel: asString(nested.preferredModel) || asString(payload.preferredModel),
        zimageWired: nested.zimageWired === true || payload.zimageWired === true,
        acceptToken: asString(nested.acceptToken) || asString(payload.acceptToken) || null,
        previewUrl,
        engineHold,
      }
    : resultAssetId || asString(payload.jobId)
      ? {
          sessionId: asString(payload.jobId) || asString(payload.queueJobId) || "",
          sourceAssetId: asString(payload.parentAssetId) || "",
          maskAssetId: "",
          creatorPrompt: "",
          engineStatus,
          executable,
          outputAssetId: resultAssetId,
          resultAssetId,
          status: asString(payload.status),
          reason: asString(payload.reason),
          preferredModel: asString(payload.preferredModel),
          zimageWired: payload.zimageWired === true,
          acceptToken: asString(payload.acceptToken) || null,
          previewUrl,
          engineHold,
        }
      : null;
  const blocked = isEngineBlocked({ engineStatus, executable }) || Boolean(engineHold && !resultAssetId);
  return {
    session,
    engineStatus,
    executable,
    reason: asString(payload.reason),
    message: asString(payload.message),
    engineHold,
    preferredModel: asString(payload.preferredModel) || CERTIFIED_CORRECT_AREA_ENGINE,
    zimageWired: payload.zimageWired === true || nested?.zimageWired === true,
    previewUrl,
    resultAssetId,
    blocked,
  };
}

/* -------------------------------------------------------------------------
 * Viewport Parity Contract (Spatial Map ↔ Correct Area)
 *
 * Correct Area does NOT re-render the map. It overlays the SAME atlas <image>
 * rectangle inside SpatialGrid, using the IDENTICAL contain-fit + alignment
 * transform as the normal Map view. These pure helpers are the single source
 * of truth for:
 *   viewBox point → atlas-image local point → source-image pixel (and back)
 * so a mask painted on the shared viewport maps 1:1 to source Atlas pixels
 * under any zoom / alignment / browser size / devicePixelRatio.
 * ---------------------------------------------------------------------- */

export type SourceRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/**
 * The untransformed atlas-image rectangle (contain-fit) inside the square
 * viewBox — identical to SpatialGrid's `imageBox`. x/y are viewBox coords.
 */
export function atlasContainBox(
  size: number,
  sourceWidth: number,
  sourceHeight: number,
): SourceRect {
  const aspect = sourceAspect(sourceWidth, sourceHeight);
  const box = containRect(size, aspect);
  return { x: box.x, y: box.y, width: box.w, height: box.h };
}

/**
 * The displayed atlas rectangle AFTER the shared BackgroundAlignment
 * (freehand offset + uniform scale) — identical to SpatialGrid's
 * `transformedImageBounds(imageBox, size, alignment)`. This is the exact
 * rectangle the mask canvas must overlay for pixel-parity.
 */
export function displayedAtlasRect(
  size: number,
  sourceWidth: number,
  sourceHeight: number,
  alignment: BackgroundAlignment,
): SourceRect {
  const box = atlasContainBox(size, sourceWidth, sourceHeight);
  const b = transformedImageBounds(
    { x: box.x, y: box.y, w: box.width, h: box.height },
    size,
    alignment,
  );
  return { x: b.x, y: b.y, width: b.w, height: b.h };
}

/**
 * Map a viewBox-space point to a source-image pixel coordinate.
 * Inverts the shared atlas transform, then normalizes inside the contain box
 * and scales to the natural source size. Returns null when the point falls
 * outside the displayed atlas (so callers never paint off-image).
 */
export function viewBoxToSourcePixel(
  viewBoxX: number,
  viewBoxY: number,
  size: number,
  sourceWidth: number,
  sourceHeight: number,
  alignment: BackgroundAlignment,
): { x: number; y: number } | null {
  if (!(size > 0) || !(sourceWidth > 0) || !(sourceHeight > 0)) return null;
  // Invert translate(offset) → scale-about-center.
  const cx = size / 2;
  const cy = size / 2;
  const scale = alignment.scale > 0 ? alignment.scale : 1;
  const offX = pixelsFromAlignment(alignment.offsetX, size);
  const offY = pixelsFromAlignment(alignment.offsetY, size);
  const localX = (viewBoxX - offX - cx) / scale + cx;
  const localY = (viewBoxY - offY - cy) / scale + cy;
  const box = atlasContainBox(size, sourceWidth, sourceHeight);
  if (!(box.width > 0) || !(box.height > 0)) return null;
  const u = (localX - box.x) / box.width;
  const v = (localY - box.y) / box.height;
  // Boundary epsilon: floating-point round-trips through the shared scale
  // transform can push the exact displayed corner a hair past the box. Clamp
  // within a small tolerance so the bottom/rightmost source row+col stay
  // paintable; genuinely off-image points still return null.
  const EPS = 1e-6;
  if (u < -EPS || u > 1 + EPS || v < -EPS || v > 1 + EPS) return null;
  const cu = Math.min(1, Math.max(0, u));
  const cv = Math.min(1, Math.max(0, v));
  return { x: cu * sourceWidth, y: cv * sourceHeight };
}

/**
 * Forward map: source-image pixel → viewBox point (for overlay / verify).
 * Round-trips with viewBoxToSourcePixel.
 */
export function sourcePixelToViewBox(
  srcX: number,
  srcY: number,
  size: number,
  sourceWidth: number,
  sourceHeight: number,
  alignment: BackgroundAlignment,
): { x: number; y: number } {
  const box = atlasContainBox(size, sourceWidth, sourceHeight);
  const u = sourceWidth > 0 ? srcX / sourceWidth : 0;
  const v = sourceHeight > 0 ? srcY / sourceHeight : 0;
  const localX = box.x + u * box.width;
  const localY = box.y + v * box.height;
  return transformPoint(localX, localY, size, alignment);
}
