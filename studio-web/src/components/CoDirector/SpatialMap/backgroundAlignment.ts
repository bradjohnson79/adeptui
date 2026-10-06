/**
 * Spatial Map Atlas background alignment — translation + uniform scale.
 *
 * Canonical persisted unit: fraction of the Spatial Map square (viewBox).
 * Creator X/Y fields show integers in the current viewBox pixels.
 * Render: offsetPx = offsetX * size. Scale is a unitless multiplier on contain-fit.
 * The atlas keeps its native aspect (object-fit: contain). The grid stays square.
 * Missing / invalid offsets → 0. Missing / invalid scale → 1. No rotation.
 * sourceWidth/Height 0 = unknown until the image loads; aspect 1 until measured.
 */

export const ALIGNMENT_MAX = 0.45;
export const ALIGNMENT_SCALE_MIN = 0.1;
export const ALIGNMENT_SCALE_MAX = 8;
/** Creator X/Y fields use this viewBox pixel unit. Render still uses live SVG size. */
export const ALIGNMENT_DISPLAY_SIZE = 480;

export type BackgroundAlignment = {
  offsetX: number;
  offsetY: number;
  scale: number;
  sourceWidth: number;
  sourceHeight: number;
  sourceAspectRatio: number;
};

export const ZERO_ALIGNMENT: BackgroundAlignment = {
  offsetX: 0,
  offsetY: 0,
  scale: 1,
  sourceWidth: 0,
  sourceHeight: 0,
  sourceAspectRatio: 1,
};

export function clampOffset(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(-ALIGNMENT_MAX, Math.min(ALIGNMENT_MAX, number));
}

export function clampScale(value: unknown): number {
  if (value === undefined || value === null || value === "") return 1;
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return 1;
  return Math.max(ALIGNMENT_SCALE_MIN, Math.min(ALIGNMENT_SCALE_MAX, number));
}

export function clampSourceSize(value: unknown): number {
  if (value === undefined || value === null || value === "") return 0;
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number) || number <= 0) return 0;
  return Math.min(number, 65535);
}

export function sourceAspect(width: number, height: number): number {
  if (!(width > 0) || !(height > 0)) return 1;
  return width / height;
}

/** Contain-fit rectangle inside a size×size square. Does not crop or stretch. */
export function containRect(
  size: number,
  aspect: number,
): { x: number; y: number; w: number; h: number } {
  const a = Number.isFinite(aspect) && aspect > 0 ? aspect : 1;
  if (a >= 1) {
    const h = size / a;
    return { x: 0, y: (size - h) / 2, w: size, h };
  }
  const w = size * a;
  return { x: (size - w) / 2, y: 0, w, h: size };
}

export function withSource(
  alignment: BackgroundAlignment,
  width: number,
  height: number,
): BackgroundAlignment {
  const sourceWidth = clampSourceSize(width);
  const sourceHeight = clampSourceSize(height);
  return {
    ...hydrateAlignment(alignment),
    sourceWidth,
    sourceHeight,
    sourceAspectRatio: sourceAspect(sourceWidth, sourceHeight),
  };
}

export function hydrateAlignment(raw: unknown): BackgroundAlignment {
  if (!raw || typeof raw !== "object") return { ...ZERO_ALIGNMENT };
  const rec = raw as {
    offsetX?: unknown;
    offsetY?: unknown;
    scale?: unknown;
    sourceWidth?: unknown;
    sourceHeight?: unknown;
    sourceAspectRatio?: unknown;
  };
  const sourceWidth = clampSourceSize(rec.sourceWidth);
  const sourceHeight = clampSourceSize(rec.sourceHeight);
  const rawAspect = typeof rec.sourceAspectRatio === "number" ? rec.sourceAspectRatio : Number(rec.sourceAspectRatio);
  const sourceAspectRatio =
    Number.isFinite(rawAspect) && rawAspect > 0 ? rawAspect : sourceAspect(sourceWidth, sourceHeight);
  return {
    offsetX: clampOffset(rec.offsetX),
    offsetY: clampOffset(rec.offsetY),
    scale: rec.scale === undefined ? 1 : clampScale(rec.scale),
    sourceWidth,
    sourceHeight,
    sourceAspectRatio,
  };
}

export function pixelsFromAlignment(offset: number, size: number): number {
  if (!Number.isFinite(size) || size <= 0) return 0;
  return clampOffset(offset) * size;
}

export function alignmentFromPixels(pixels: number, size: number): number {
  if (!Number.isFinite(size) || size <= 0) return 0;
  return clampOffset(pixels / size);
}

export function alignmentFromPixelPair(
  x: number,
  y: number,
  size: number,
  scale: number = 1,
  source?: Pick<BackgroundAlignment, "sourceWidth" | "sourceHeight" | "sourceAspectRatio">,
): BackgroundAlignment {
  return {
    offsetX: alignmentFromPixels(x, size),
    offsetY: alignmentFromPixels(y, size),
    scale: clampScale(scale),
    sourceWidth: clampSourceSize(source?.sourceWidth),
    sourceHeight: clampSourceSize(source?.sourceHeight),
    sourceAspectRatio: source?.sourceAspectRatio && source.sourceAspectRatio > 0
      ? source.sourceAspectRatio
      : sourceAspect(clampSourceSize(source?.sourceWidth), clampSourceSize(source?.sourceHeight)),
  };
}

export function displayPixels(alignment: BackgroundAlignment, size: number): { x: number; y: number } {
  return {
    x: Math.round(pixelsFromAlignment(alignment.offsetX, size)),
    y: Math.round(pixelsFromAlignment(alignment.offsetY, size)),
  };
}

export type ResizeCorner = "nw" | "ne" | "sw" | "se";

export function oppositeCorner(corner: ResizeCorner): ResizeCorner {
  if (corner === "nw") return "se";
  if (corner === "ne") return "sw";
  if (corner === "sw") return "ne";
  return "nw";
}

export function imageCorners(box: { x: number; y: number; w: number; h: number }): Record<
  ResizeCorner,
  { x: number; y: number }
> {
  return {
    nw: { x: box.x, y: box.y },
    ne: { x: box.x + box.w, y: box.y },
    sw: { x: box.x, y: box.y + box.h },
    se: { x: box.x + box.w, y: box.y + box.h },
  };
}

/** Map an unscaled image-space point through the canonical Atlas transform. */
export function transformPoint(
  x: number,
  y: number,
  size: number,
  alignment: BackgroundAlignment,
): { x: number; y: number } {
  const scale = clampScale(alignment.scale);
  const cx = size / 2;
  const cy = size / 2;
  return {
    x: (x - cx) * scale + cx + pixelsFromAlignment(alignment.offsetX, size),
    y: (y - cy) * scale + cy + pixelsFromAlignment(alignment.offsetY, size),
  };
}

export function transformedImageBounds(
  box: { x: number; y: number; w: number; h: number },
  size: number,
  alignment: BackgroundAlignment,
): { x: number; y: number; w: number; h: number } {
  const pts = Object.values(imageCorners(box)).map((pt) => transformPoint(pt.x, pt.y, size, alignment));
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const left = Math.min(...xs);
  const top = Math.min(...ys);
  return { x: left, y: top, w: Math.max(...xs) - left, h: Math.max(...ys) - top };
}

/**
 * Uniform scale from a corner handle. The opposite corner stays put
 * (offset compensation). Aspect stays locked because scale is uniform.
 */
export function alignmentFromOppositeAnchorResize(
  origin: BackgroundAlignment,
  imageBox: { x: number; y: number; w: number; h: number },
  size: number,
  corner: ResizeCorner,
  pointer: { x: number; y: number },
): BackgroundAlignment {
  const current = hydrateAlignment(origin);
  if (!(size > 0)) return current;
  const corners = imageCorners(imageBox);
  const anchor = corners[oppositeCorner(corner)];
  const handle = corners[corner];
  const anchorWorld = transformPoint(anchor.x, anchor.y, size, current);
  const handleWorld = transformPoint(handle.x, handle.y, size, current);
  const startDist = Math.hypot(handleWorld.x - anchorWorld.x, handleWorld.y - anchorWorld.y);
  const currentDist = Math.hypot(pointer.x - anchorWorld.x, pointer.y - anchorWorld.y);
  if (startDist < 1e-6) return current;
  const nextScale = clampScale(current.scale * (currentDist / startDist));
  const cx = size / 2;
  const cy = size / 2;
  return {
    ...current,
    scale: nextScale,
    offsetX: clampOffset(current.offsetX + ((anchor.x - cx) * (current.scale - nextScale)) / size),
    offsetY: clampOffset(current.offsetY + ((anchor.y - cy) * (current.scale - nextScale)) / size),
  };
}

export function parseAlignmentInput(raw: string, fallback: number): number {
  const trimmed = raw.trim();
  if (!trimmed) return fallback;
  const number = Number(trimmed);
  if (!Number.isFinite(number)) return fallback;
  return number;
}
