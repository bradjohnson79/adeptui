export type MagiUpscaleTarget = {
  id: string;
  label: string;
  width: number;
  height: number;
};

export const MAGI_TARGET_PRESETS_LANDSCAPE: MagiUpscaleTarget[] = [
  { id: "1080p", label: "1080p", width: 1920, height: 1080 },
  { id: "1440p", label: "1440p", width: 2560, height: 1440 },
  { id: "4K", label: "4K", width: 3840, height: 2160 },
  { id: "8K", label: "8K", width: 7680, height: 4320 },
];

export const MAGI_TARGET_PRESETS_PORTRAIT: MagiUpscaleTarget[] = [
  { id: "1080p", label: "1080p", width: 1080, height: 1920 },
  { id: "1440p", label: "1440p", width: 1440, height: 2560 },
  { id: "4K", label: "4K", width: 2160, height: 3840 },
  { id: "8K", label: "8K", width: 4320, height: 7680 },
];

/** @deprecated Use orientedPresets(srcW, srcH) — landscape-only alias for older imports. */
export const MAGI_TARGET_PRESETS = MAGI_TARGET_PRESETS_LANDSCAPE;

export const MAGI_SPATIAL_ONLY =
  "Spatial frame enhancement only. Not temporal AI restoration.";

export function isPortrait(srcW: number, srcH: number): boolean {
  return Number(srcH || 0) > Number(srcW || 0);
}

export function orientedPresets(srcW: number, srcH: number): MagiUpscaleTarget[] {
  return isPortrait(srcW, srcH) ? MAGI_TARGET_PRESETS_PORTRAIT : MAGI_TARGET_PRESETS_LANDSCAPE;
}

export function isAboveSource(
  srcW: number,
  srcH: number,
  targetW: number,
  targetH: number,
): boolean {
  if (srcW <= 0 || srcH <= 0 || targetW <= 0 || targetH <= 0) return false;
  if (targetW < srcW || targetH < srcH) return false;
  return targetW * targetH > srcW * srcH;
}

export function meaningfulTargets(srcW: number, srcH: number): MagiUpscaleTarget[] {
  return orientedPresets(srcW, srcH).filter((row) => isAboveSource(srcW, srcH, row.width, row.height));
}

export function defaultTargetId(srcW: number, srcH: number): string {
  return meaningfulTargets(srcW, srcH)[0]?.id || "";
}

export function preferredPublishSource(upscaledAssetId?: string | null): "stitch" | "upscaled" {
  return String(upscaledAssetId || "").trim() ? "upscaled" : "stitch";
}
