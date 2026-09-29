/** Frontend mirror of backend MiniMax H3 legal-canvas (D1 ResolutionSelector).
 *
 * Width/height are never stored on BatchBlock; they are always derived from
 * megapixels x aspect via ResolutionSelector(multiple=32). See
 * studio-api/app/video_runtime/legal_canvas.py for the source of truth.
 */

export type H3ResolutionMode = "auto" | "manual";

export interface H3ResolutionState {
  mode: H3ResolutionMode;
  megapixels: number;
}

export interface H3ResolvedCanvas {
  mode: H3ResolutionMode;
  megapixels: number;
  label: string;
  width: number;
  height: number;
  auto: boolean;
}

/** Canonical MiniMax H3 megapixel → 16:9 /32 pixel grid. */
export const H3_MEGAPIXEL_GRID: readonly [number, readonly [number, number]][] = [
  [0.2, [608, 352]],
  [0.3, [736, 416]],
  [0.4, [864, 480]],
  [0.5, [960, 544]],
  [0.6, [1056, 608]],
  [0.7, [1152, 640]],
  [0.8, [1216, 672]],
  [0.9, [1280, 736]],
  [0.98, [1344, 768]],
  [1.0, [1376, 768]],
  [1.2, [1504, 832]],
  [1.5, [1664, 928]],
  [1.8, [1824, 1024]],
  [2.0, [1920, 1088]],
];

/** Auto Fast = 0.4 MP (864×480) — certified Scene5 release-gate H3 template canvas. */
export const H3_AUTO_MEGAPIXEL_FAST = 0.4;

/** Auto Quality = 0.7 MP (1152×640) — FM4/FM5 certified Timeline default. */
export const H3_AUTO_MEGAPIXEL_QUALITY = 0.7;

const H3_MEGAPIXEL_BY_VALUE: ReadonlyMap<number, readonly [number, number]> = new Map(
  H3_MEGAPIXEL_GRID.map(([mp, dims]) => [mp, dims]),
);


/** Adept production ∩ ResolutionSelector aspects — mirrors legal_canvas.H3_SUPPORTED_ASPECTS. */
export const H3_SUPPORTED_ASPECTS = ["1:1", "4:3", "16:9", "9:16", "21:9"] as const;
export type H3SupportedAspect = (typeof H3_SUPPORTED_ASPECTS)[number];

/** Comfy ResolutionSelector ratio per supported H3 picture shape.
 *
 * Keyed by H3SupportedAspect so the capability check and the math share ONE
 * source — there is no unknown-key fallback left to silently resolve 16:9.
 */
const H3_ASPECT_RATIO: Record<H3SupportedAspect, readonly [number, number]> = {
  "1:1": [1, 1],
  "4:3": [4, 3],
  "16:9": [16, 9],
  "9:16": [9, 16],
  "21:9": [21, 9],
};

/** Soft 16:9 display aliases — mirrors backend legal_canvas.H3_ASPECT_ALIASES. */
const H3_ASPECT_ALIASES: Record<string, H3SupportedAspect> = {
  "≈16:9": "16:9",
  "~16:9": "16:9",
};

/** Fail-closed capability error — mirrors backend legal_canvas.SpecFidelityError.
 *
 * The backend MiniMax H3 path refuses any shape outside H3_SUPPORTED_ASPECTS
 * (legal_canvas.require_h3_timeline_aspect → code "H3_ASPECT_UNSUPPORTED"). The FE
 * raises this instead of silently showing 16:9 dims the backend would refuse.
 */
export class H3UnsupportedAspectError extends Error {
  readonly code = "H3_ASPECT_UNSUPPORTED";
  readonly aspect: string;

  constructor(aspect: string) {
    super(
      `MiniMax H3 does not support picture shape ${aspect}. Supported: ${H3_SUPPORTED_ASPECTS.join(", ")}.`,
    );
    this.name = "H3UnsupportedAspectError";
    this.aspect = aspect;
  }
}

/** Canonical H3 picture shape for a UI token, or null when H3 cannot resolve it.
 *
 * An absent/empty token and the soft 16:9 aliases normalize to "16:9" (backend
 * `str(aspect or "").strip() or "16:9"`); every other unknown shape returns null so
 * callers fail closed rather than falling back to 16:9.
 */
export function normalizeH3Aspect(aspect?: string | null): H3SupportedAspect | null {
  const key = String(aspect || "16:9").trim() || "16:9";
  const alias = H3_ASPECT_ALIASES[key];
  if (alias) return alias;
  return key in H3_ASPECT_RATIO ? (key as H3SupportedAspect) : null;
}

/** Comfy ResolutionSelector(aspect, megapixels, multiple=32) — FE mirror of D1.
 *
 * Fail-closed: an aspect outside H3_SUPPORTED_ASPECTS (+ soft 16:9 aliases)
 * throws H3UnsupportedAspectError and never resolves 16:9 dims.
 */
export function resolveH3ResolutionSelector(
  aspect: string,
  megapixels: number,
  multiple = 32,
): { width: number; height: number } {
  const key = String(aspect || "16:9").trim() || "16:9";
  const supported = normalizeH3Aspect(key);
  if (!supported) throw new H3UnsupportedAspectError(key);
  const [a, b] = H3_ASPECT_RATIO[supported];
  const total = Number(megapixels) * 1024 * 1024;
  const mult = Math.max(1, Math.trunc(multiple));
  const width = Math.max(mult, Math.round(Math.sqrt((total * a) / b) / mult) * mult);
  const height = Math.max(mult, Math.round(Math.sqrt((total * b) / a) / mult) * mult);
  return { width, height };
}

export function formatH3Megapixels(value: number): string {
  if (value === Math.trunc(value)) {
    return `${Math.trunc(value)}.0 MP`;
  }
  return `${value} MP`;
}

/** Canonical H3 canvas for a megapixel × picture shape.
 *
 * Fails closed: an unsupported MP value throws, and an aspect outside
 * H3_SUPPORTED_ASPECTS propagates H3UnsupportedAspectError from the selector.
 */
export function resolveH3MegapixelCanvas(
  mp: number,
  aspect: string = "16:9",
): { label: string; width: number; height: number } {
  if (!H3_MEGAPIXEL_BY_VALUE.has(mp)) {
    throw new Error(`${mp} MP is not a supported MiniMax H3 canvas.`);
  }
  const { width, height } = resolveH3ResolutionSelector(aspect, mp, 32);
  return { label: formatH3Megapixels(mp), width, height };
}

/** Resolve a BatchBlock's H3 resolution intent to a canonical canvas.
 *
 * Manual mode always uses the stored megapixel value. Auto or absent uses
 * the policy constant by draftMode. Returns a provenance dict carrying the
 * resolved mode, megapixels, label, width, height, and whether the choice was
 * auto-derived. Aspect is fail-closed: an unsupported picture shape
 * propagates H3UnsupportedAspectError (never a silent 16:9 canvas).
 */
export function resolveH3TimelineCanvas(
  h3Resolution: H3ResolutionState | null | undefined,
  draftMode: boolean,
  aspect: string = "16:9",
): H3ResolvedCanvas {
  let mode: H3ResolutionMode = "auto";
  let auto = true;
  let mp = draftMode ? H3_AUTO_MEGAPIXEL_FAST : H3_AUTO_MEGAPIXEL_QUALITY;

  if (h3Resolution && typeof h3Resolution === "object") {
    const storedMode = String(h3Resolution.mode || "auto").trim().toLowerCase() as H3ResolutionMode;
    if (storedMode === "manual") {
      mode = "manual";
      if (h3Resolution.megapixels === undefined || h3Resolution.megapixels === null) {
        throw new Error("Manual MiniMax H3 resolution requires a megapixel value.");
      }
      mp = Number(h3Resolution.megapixels);
      auto = false;
    }
  }

  const { label, width, height } = resolveH3MegapixelCanvas(mp, aspect);
  return { mode, megapixels: mp, label, width, height, auto };
}

/** Timeline LTX QUALITY tiers — no 480p. Native 4K is UNAVAILABLE. */
export const LTX_TIMELINE_QUALITY_TIERS = ["720p", "1080p", "2K", "4K"] as const;
export type LtxTimelineQuality = (typeof LTX_TIMELINE_QUALITY_TIERS)[number];

/** Default Timeline LTX QUALITY (= adapter finalResolution 1280x704). */
export const LTX_DEFAULT_QUALITY: LtxTimelineQuality = "720p";

/** Legal /32 16:9 canvases for Timeline LTX QUALITY. 4K = null (UNAVAILABLE). */
export const LTX_QUALITY_CANVAS_16_9: Record<
  LtxTimelineQuality,
  { width: number; height: number } | null
> = {
  "720p": { width: 1280, height: 704 },
  "1080p": { width: 1920, height: 1088 },
  "2K": { width: 2560, height: 1440 },
  "4K": null,
};

export function normalizeLtxTimelineQuality(
  value: string | null | undefined,
): LtxTimelineQuality {
  const token = String(value || "").trim();
  const aliases: Record<string, LtxTimelineQuality> = {
    "720p": "720p",
    "1080p": "1080p",
    "2k": "2K",
    "2K": "2K",
    "4k": "4K",
    "4K": "4K",
  };
  return aliases[token] || aliases[token.toLowerCase()] || LTX_DEFAULT_QUALITY;
}

export function resolveLtxTimelineCanvas(
  ltxQuality: string | null | undefined,
  aspect?: string | null,
): {
  tier: LtxTimelineQuality;
  width: number;
  height: number;
  available: boolean;
  honestyLabel: string;
} {
  const tier = normalizeLtxTimelineQuality(ltxQuality);
  const dims16 = LTX_QUALITY_CANVAS_16_9[tier];
  if (!dims16) {
    return {
      tier,
      width: 0,
      height: 0,
      available: false,
      honestyLabel: "Native 4K is UNAVAILABLE",
    };
  }
  const aspectKey = String(aspect || "16:9").trim() || "16:9";
  if (aspectKey === "16:9" || aspectKey === "≈16:9" || aspectKey === "~16:9") {
    return {
      tier,
      width: dims16.width,
      height: dims16.height,
      available: true,
      honestyLabel: `Native ${tier} · ${dims16.width}x${dims16.height}`,
    };
  }
  // Non-16:9: align to BE /32 short-edge class (legal_canvas._ALIGN32_SHORT).
  const shortByTier: Record<LtxTimelineQuality, number | null> = {
    "720p": 704,
    "1080p": 1088,
    "2K": 1440,
    "4K": null,
  };
  const short = shortByTier[tier];
  if (short == null) {
    return {
      tier,
      width: 0,
      height: 0,
      available: false,
      honestyLabel: "Native 4K is UNAVAILABLE",
    };
  }
  const pair = ltxDimsForAspectShort(aspectKey, short);
  if (!pair) {
    // Honest: do not show landscape WxH for a different aspect.
    return {
      tier,
      width: 0,
      height: 0,
      available: true,
      honestyLabel: `Native ${tier} · ${aspectKey} (WxH at generate)`,
    };
  }
  return {
    tier,
    width: pair.width,
    height: pair.height,
    available: true,
    honestyLabel: `Native ${tier} · ${pair.width}x${pair.height}`,
  };
}

/** BE-aligned /32 short-edge dims for Timeline LTX honesty labels. */
function ltxDimsForAspectShort(
  aspect: string,
  short: number,
): { width: number; height: number } | null {
  const map: Record<string, [number, number]> = {
    "1:1": [1, 1],
    "4:3": [4, 3],
    "16:9": [16, 9],
    "21:9": [21, 9],
    "9:16": [9, 16],
  };
  const ab = map[aspect];
  if (!ab) return null;
  const [a, b] = ab;
  const align = (n: number) => Math.max(32, Math.round(n / 32) * 32);
  if (a >= b) {
    const height = align(short);
    return { width: align(Math.round((height * a) / b)), height };
  }
  const width = align(short);
  return { width, height: align(Math.round((width * b) / a)) };
}
