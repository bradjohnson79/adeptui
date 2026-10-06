/** Creator-facing video tiers. Pixel sizes come from the backend legal-canvas authority. */

// Timeline canonical H3 legal-canvas (mirror of backend D1). Imported and
// re-exported here so existing Video UI consumers keep working without a
// second copy of the H3 grid/selector/aspect logic (Slice C consolidation).
import {
  H3_MEGAPIXEL_GRID,
  H3_SUPPORTED_ASPECTS,
  formatH3Megapixels,
  normalizeH3Aspect,
  resolveH3ResolutionSelector,
} from "../timelineMaster/legalCanvas";

export { H3_SUPPORTED_ASPECTS, resolveH3ResolutionSelector };

/**
 * Creator-video aspect for H3 resolution display (B5 scope guard).
 *
 * The Video Picture Shape list (AspectRatioSelect) offers shapes outside the
 * MiniMax H3 capability set — 3:2 / 16:10 / 18:9 / 2.39:1 / custom. The Timeline
 * H3 path now fails closed on those (timelineMaster/legalCanvas
 * H3UnsupportedAspectError); these creator-video consumers must keep their
 * published contract, so the 16:9-class dims they have always shown stay
 * explicit here instead of hidden inside the shared selector.
 */
function h3VideoDisplayAspect(aspect?: string | null): string {
  return normalizeH3Aspect(aspect) || "16:9";
}

export const VIDEO_TIERS = ["480p", "720p", "1080p", "2K", "4K"] as const;
export type VideoTier = (typeof VIDEO_TIERS)[number];

/** Published /32 16:9 class — must match studio-api legal_canvas.py */
const ALIGN32_16_9: Record<VideoTier, { width: number; height: number } | null> = {
  "480p": { width: 832, height: 480 },
  "720p": { width: 1280, height: 704 },
  "1080p": { width: 1920, height: 1088 },
  "2K": { width: 2560, height: 1440 },
  "4K": null,
};

const SEEDANCE_16_9: Record<VideoTier, { width: number; height: number } | null> = {
  "480p": { width: 854, height: 480 },
  "720p": { width: 1280, height: 720 },
  "1080p": null,
  "2K": null,
  "4K": null,
};

/**
 * MiniMax H3 native resolution grid — megapixel-labeled, 16:9, dimensions are
 * multiples of 32. This is the creator-facing Resolution list for the MiniMax
 * generator only (other generators keep the 480p/720p/1080p/2K/4K tiers).
 *
 * Source: MiniMax "Size Settings Reference" (megapixels → Output, multiple=32).
 */
export const MINIMAX_MEGAPIXEL_TIERS = [
  "0.2 MP", "0.3 MP", "0.4 MP", "0.5 MP", "0.6 MP", "0.7 MP",
  "0.8 MP", "0.9 MP", "0.98 MP", "1.0 MP", "1.2 MP", "1.5 MP",
  "1.8 MP", "2.0 MP",
] as const;
export type MinimaxMegapixelTier = (typeof MINIMAX_MEGAPIXEL_TIERS)[number];

const MINIMAX_MEGAPIXEL_SET = new Set<string>(MINIMAX_MEGAPIXEL_TIERS);

/** 16:9 /32 dims keyed by megapixel label, from the canonical Timeline grid. */
const MINIMAX_MEGAPIXEL_16_9: Record<MinimaxMegapixelTier, { width: number; height: number }> =
  Object.fromEntries(
    H3_MEGAPIXEL_GRID.map(([mp, [width, height]]) => [formatH3Megapixels(mp), { width, height }]),
  ) as Record<MinimaxMegapixelTier, { width: number; height: number }>;

function megapixelsFromLabel(label: string): number {
  return Number(String(label).replace(/\s*MP$/i, "").trim());
}


/** MiniMax H3 uses the megapixel-labeled Resolution dropdown (not 480p/720p/…). */
export function isMinimaxMegapixelEngine(engine: string): boolean {
  return String(engine || "").toLowerCase() === "minimax-h3";
}

export function isMinimaxMegapixelTier(tier: string): boolean {
  return MINIMAX_MEGAPIXEL_SET.has(String(tier || ""));
}

/** Megapixel Resolution options for the MiniMax dropdown (any aspect). */
export function minimaxMegapixelOptions(
  aspect = "16:9",
): { label: MinimaxMegapixelTier; width: number; height: number; available: boolean }[] {
  return MINIMAX_MEGAPIXEL_TIERS.map((label) => {
    const mp = megapixelsFromLabel(label);
    const dims = resolveH3ResolutionSelector(h3VideoDisplayAspect(aspect), mp, 32);
    return { label, ...dims, available: true };
  });
}

/** Infer the closest MiniMax megapixel tier for given pixel dimensions. */
export function inferMinimaxMegapixelTier(width: number, height: number): MinimaxMegapixelTier {
  const px = Number(width || 0) * Number(height || 0);
  if (px <= 0) return "0.9 MP"; // sensible default (~720p-class) when unknown
  let best: MinimaxMegapixelTier = "0.9 MP";
  let bestDelta = Infinity;
  for (const label of MINIMAX_MEGAPIXEL_TIERS) {
    const d = MINIMAX_MEGAPIXEL_16_9[label];
    const delta = Math.abs(d.width * d.height - px);
    if (delta < bestDelta) {
      bestDelta = delta;
      best = label;
    }
  }
  return best;
}

export function inferVideoTier(width: number, height: number): VideoTier {
  const short = Math.min(Number(width) || 0, Number(height) || 0);
  if (short <= 0) return "720p";
  if (short <= 560) return "480p";
  if (short <= 896) return "720p";
  if (short <= 1264) return "1080p";
  if (short <= 1800) return "2K";
  return "4K";
}

export function normalizeVideoTier(label: string): VideoTier {
  if (label === "1440p") return "2K";
  if ((VIDEO_TIERS as readonly string[]).includes(label)) return label as VideoTier;
  return "720p";
}

export function isAlign32Engine(engine: string): boolean {
  const id = String(engine || "").toLowerCase();
  return id.includes("minimax-h3") || id.includes("ltx-2.5") || id === "auto" || id === "ltx-2.5";
}

export function legalCanvasSize(
  engine: string,
  tier: string,
  aspect = "16:9",
): { width: number; height: number; available: boolean; honestyLabel: string } {
  // MiniMax H3 megapixel-labeled resolutions (16:9, /32). These are distinct
  // from the 480p/720p/1080p/2K/4K tiers and must be resolved before the
  // normalizeVideoTier fallback (which would map "0.9 MP" → "720p").
  if (isMinimaxMegapixelEngine(engine) && isMinimaxMegapixelTier(tier)) {
    const label = tier as MinimaxMegapixelTier;
    const mp = megapixelsFromLabel(label);
    const dims = resolveH3ResolutionSelector(h3VideoDisplayAspect(aspect), mp, 32);
    return {
      ...dims,
      available: true,
      honestyLabel: `Native ${label} · ${dims.width}×${dims.height}`,
    };
  }
  const key = normalizeVideoTier(tier);
  const hosted = String(engine || "").startsWith("seedance") || String(engine || "").startsWith("fal_");
  const table = hosted ? SEEDANCE_16_9 : ALIGN32_16_9;
  if (aspect === "16:9") {
    const dims = table[key];
    if (!dims) {
      return {
        width: 0,
        height: 0,
        available: false,
        honestyLabel:
          key === "4K"
            ? "Native 4K is not legal for this generator"
            : `${key} is not available for this generator`,
      };
    }
    const honesty =
      key === "720p" && !hosted
        ? "Native 720p · 1280×704"
        : key === "1080p" && !hosted
          ? "Native 1080p · 1920×1088"
          : `Native ${key}`;
    return { ...dims, available: true, honestyLabel: honesty };
  }
  if (hosted) {
    const short = key === "480p" ? 480 : key === "720p" ? 720 : 0;
    if (!short) {
      return { width: 0, height: 0, available: false, honestyLabel: `${key} is not available` };
    }
    return { ...sizeFromAspectShort(aspect, short, 2), available: true, honestyLabel: `Native ${key}` };
  }
  const short = key === "480p" ? 480 : key === "720p" ? 704 : key === "1080p" ? 1088 : key === "2K" ? 1440 : 0;
  if (!short) {
    return { width: 0, height: 0, available: false, honestyLabel: "Native 4K is not legal for this generator" };
  }
  return { ...sizeFromAspectShort(aspect, short, 32), available: true, honestyLabel: `Native ${key}` };
}

export function resolveSubmitCanvas(
  engine: string,
  width: number,
  height: number,
  aspect = "16:9",
) {
  const tier = inferVideoTier(width, height);
  return { tier, ...legalCanvasSize(engine, tier, aspect) };
}

export function exactFrameCount(seconds: number, fps: number): number {
  return Math.max(1, Math.round(Number(seconds) * Number(fps)));
}

/** Nearest legal LTX 8n+1 count for a Timeline whole-second request. Ties take the longer count. */
export function ltxTimelineFrameCount(seconds: number, fps = 24): number {
  const frames = exactFrameCount(seconds, fps);
  if (frames >= 9 && (frames - 1) % 8 === 0) return frames;
  const lo = Math.floor((Math.max(1, frames) - 1) / 8) * 8 + 1;
  const hi = lo + 8;
  const near = [lo, hi].filter((count) => count >= 9);
  near.sort((a, b) => Math.abs(a - frames) - Math.abs(b - frames) || b - a);
  return near[0] || frames;
}

export function durationFidelityMessage(engine: string, seconds: number, fps: number): string {
  const id = String(engine || "").toLowerCase();
  if (!id.includes("ltx-2.5")) return "";
  const frames = exactFrameCount(seconds, fps);
  if (frames >= 9 && (frames - 1) % 8 === 0) return "";
  const lo = Math.floor((Math.max(1, frames) - 1) / 8) * 8 + 1;
  const hi = lo + 8;
  const suggest = [lo, hi].filter((n) => n >= 9).map((n) => `${(n / fps).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}s (${n} frames)`);
  return `LTX 2.5 needs a frame count of 8n+1. ${seconds}s at ${fps} fps is ${frames} frames. Adept will not pad or shorten the clip. Try ${suggest.join(" or ")}.`;
}

/**
 * MiniMax H3 1F requires frames = 17k + 5 (k >= 0, max 3600) at the project fps.
 * Mirrors the backend `_h3_frame_count` / `_h3_legal_duration` so the UI can
 * snap-and-disclose BEFORE submit (the backend 1F path is fail-closed and will
 * reject off-grid durations). Snap UP so we never silently shorten the clip.
 */
export function h3LegalFrameCount(seconds: number, fps: number): number {
  const fpsVal = Number(fps) || 24;
  const raw = Math.max(5, Math.round(Number(seconds || 0) * fpsVal));
  const snapped = ((raw - 5 + 16) / 17 | 0) * 17 + 5; // snap up to next 17k+5
  return Math.max(5, Math.min(snapped, 3600));
}

export function h3LegalDurationSeconds(seconds: number, fps: number): number {
  const fpsVal = Number(fps) || 24;
  return h3LegalFrameCount(seconds, fps) / fpsVal;
}

/** True if the requested duration already lands on the 17k+5 grid. */
export function isH3DurationLegal(seconds: number, fps: number): boolean {
  const fpsVal = Number(fps) || 24;
  const raw = Math.max(5, Math.round(Number(seconds || 0) * fpsVal));
  return (raw - 5) % 17 === 0 && raw <= 3600;
}

/**
 * Disclosure message for the 1F surface when MiniMax H3 snaps an off-grid
 * duration up to the next valid 17k+5 point. Empty string when nothing to
 * disclose (non-MiniMax, or already on-grid). This is snap-and-disclose, not a
 * block: Generate stays enabled and submits the snapped duration.
 */
export function h3DurationDisclosure(engine: string, seconds: number, fps: number): string {
  if (!isMinimaxMegapixelEngine(engine)) return "";
  if (isH3DurationLegal(seconds, fps)) return "";
  const fpsVal = Number(fps) || 24;
  const raw = Math.max(5, Math.round(Number(seconds || 0) * fpsVal));
  const snapped = h3LegalDurationSeconds(seconds, fps);
  return `MiniMax H3 needs a 17k+5 frame grid at ${fpsVal} fps. ${Number(seconds)}s → ${raw} frames is off-grid, so Adept will render ${snapped}s (${h3LegalFrameCount(seconds, fps)} frames).`;
}

function sizeFromAspectShort(aspect: string, short: number, multiple: number): { width: number; height: number } {
  const map: Record<string, [number, number]> = {
    "1:1": [1, 1],
    "4:3": [4, 3],
    "3:4": [3, 4],
    "16:9": [16, 9],
    "9:16": [9, 16],
    "21:9": [21, 9],
    "16:10": [16, 10],
    "18:9": [18, 9],
    "3:2": [3, 2],
    "2.39:1": [239, 100],
  };
  const [a, b] = map[aspect] || [16, 9];
  const align = (n: number) => Math.max(multiple, Math.floor(n / multiple) * multiple);
  if (a >= b) {
    const height = align(short);
    return { width: align(Math.round((height * a) / b)), height };
  }
  const width = align(short);
  return { width, height: align(Math.round((width * b) / a)) };
}
