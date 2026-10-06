export type MagiUpscaleTarget = {
  id: string;
  label: string;
  width: number;
  height: number;
  aspect?: string;
};

/** Shorter-edge classes. Order is the MAGI target selector. Not aspect canvases. */
export const MAGI_UPSCALE_CLASSES: { id: string; shortEdge: number }[] = [
  { id: "1080p", shortEdge: 1080 },
  { id: "1440p", shortEdge: 1440 },
  { id: "2K", shortEdge: 2048 },
  { id: "4K", shortEdge: 2160 },
  { id: "8K", shortEdge: 4320 },
];

const EXTRA_SHORT_EDGE: Record<string, number> = {
  "720P": 720,
  "480P": 480,
};

const ASPECT_TOLERANCE = 0.005;

const KNOWN_ASPECTS: { ratio: number; label: string }[] = [
  { ratio: 1, label: "1:1" },
  { ratio: 4 / 3, label: "4:3" },
  { ratio: 3 / 4, label: "3:4" },
  { ratio: 16 / 9, label: "16:9" },
  { ratio: 9 / 16, label: "9:16" },
  { ratio: 21 / 9, label: "21:9" },
  { ratio: 2.39, label: "2.39:1" },
];

const LEGACY_CANVAS_TO_CLASS: Record<string, string> = {
  "1920x1080": "1080p",
  "1080x1920": "1080p",
  "2560x1440": "1440p",
  "1440x2560": "1440p",
  "3840x2160": "4K",
  "2160x3840": "4K",
  "7680x4320": "8K",
  "4320x7680": "8K",
  "1280x720": "720p",
  "720x1280": "720p",
};

export const MAGI_SPATIAL_ONLY =
  "Spatial frame enhancement only. Not temporal AI restoration.";

export function evenDim(value: number): number {
  return Math.max(2, Math.round(value / 2) * 2);
}

export function aspectsMatch(srcW: number, srcH: number, dstW: number, dstH: number): boolean {
  if (Math.min(srcW, srcH, dstW, dstH) <= 0) return false;
  const source = srcW / srcH;
  const output = dstW / dstH;
  return Math.abs(source - output) / source <= ASPECT_TOLERANCE;
}

export function aspectLabel(width: number, height: number): string {
  if (width <= 0 || height <= 0) return "";
  const ratio = width / height;
  for (const known of KNOWN_ASPECTS) {
    if (Math.abs(ratio - known.ratio) / known.ratio <= 0.004) return known.label;
  }
  const divisor = gcd(width, height);
  return `${Math.round(width / divisor)}:${Math.round(height / divisor)}`;
}

function gcd(a: number, b: number): number {
  let x = Math.abs(Math.round(a));
  let y = Math.abs(Math.round(b));
  while (y) {
    const next = x % y;
    x = y;
    y = next;
  }
  return x || 1;
}

function bestEven(raw: number, fixed: number, aspect: number, freeIsWidth: boolean): number {
  const base = evenDim(raw);
  let best = base;
  let bestErr = Number.POSITIVE_INFINITY;
  for (const candidate of [base - 2, base, base + 2]) {
    if (candidate < 2) continue;
    const ratio = freeIsWidth ? candidate / fixed : fixed / candidate;
    const err = Math.abs(ratio - aspect);
    if (err < bestErr) {
      bestErr = err;
      best = candidate;
    }
  }
  return best;
}

export function dimensionsForShortEdge(srcW: number, srcH: number, shortEdge: number): { width: number; height: number } {
  const short = evenDim(shortEdge);
  const aspect = srcW / srcH;
  if (srcW >= srcH) {
    const height = short;
    return { width: bestEven(height * aspect, height, aspect, true), height };
  }
  const width = short;
  return { width, height: bestEven(width / aspect, width, aspect, false) };
}

export function isAboveSource(srcW: number, srcH: number, targetW: number, targetH: number): boolean {
  if (srcW <= 0 || srcH <= 0 || targetW <= 0 || targetH <= 0) return false;
  if (targetW < srcW || targetH < srcH) return false;
  return targetW * targetH > srcW * srcH;
}

function classForId(id: string): { id: string; shortEdge: number } | null {
  const key = id.trim().toUpperCase();
  const known = MAGI_UPSCALE_CLASSES.find((row) => row.id.toUpperCase() === key);
  if (known) return known;
  if (EXTRA_SHORT_EDGE[key]) return { id: key === "720P" ? "720p" : "480p", shortEdge: EXTRA_SHORT_EDGE[key] };
  return null;
}

export function normalizeUpscaleTargetId(raw: string): string {
  const text = String(raw || "").trim();
  if (!text) return "";
  const known = classForId(text);
  if (known && MAGI_UPSCALE_CLASSES.some((row) => row.id === known.id)) return known.id;
  if (known) return known.id;
  const canvas = text.toLowerCase().replace("×", "x").replace(/\s/g, "");
  return LEGACY_CANVAS_TO_CLASS[canvas] || text;
}

export function resolveUpscaleTarget(srcW: number, srcH: number, requested: string): MagiUpscaleTarget {
  const normalized = normalizeUpscaleTargetId(requested);
  const known = classForId(normalized) || classForId(requested);
  if (!known) {
    throw new Error("Choose an upscale target such as 1080p, 1440p, 2K, or 4K.");
  }
  const size = dimensionsForShortEdge(srcW, srcH, known.shortEdge);
  return {
    id: known.id,
    label: known.id,
    width: size.width,
    height: size.height,
    aspect: aspectLabel(size.width, size.height),
  };
}

export function meaningfulTargets(srcW: number, srcH: number): MagiUpscaleTarget[] {
  return MAGI_UPSCALE_CLASSES.map((row) => resolveUpscaleTarget(srcW, srcH, row.id)).filter((row) =>
    isAboveSource(srcW, srcH, row.width, row.height),
  );
}

export function defaultTargetId(srcW: number, srcH: number): string {
  return meaningfulTargets(srcW, srcH)[0]?.id || "";
}

export function preferredPublishSource(upscaledAssetId?: string | null): "stitch" | "upscaled" {
  return String(upscaledAssetId || "").trim() ? "upscaled" : "stitch";
}

/** @deprecated Aspect-correct sizes for this source. Landscape presets are no longer a 16:9 table. */
export function orientedPresets(srcW: number, srcH: number): MagiUpscaleTarget[] {
  return MAGI_UPSCALE_CLASSES.map((row) => resolveUpscaleTarget(srcW, srcH, row.id));
}

export const MAGI_TARGET_PRESETS = MAGI_UPSCALE_CLASSES.map((row) =>
  resolveUpscaleTarget(1920, 1080, row.id),
);
export const MAGI_TARGET_PRESETS_LANDSCAPE = MAGI_TARGET_PRESETS;
export const MAGI_TARGET_PRESETS_PORTRAIT = MAGI_UPSCALE_CLASSES.map((row) =>
  resolveUpscaleTarget(1080, 1920, row.id),
);
