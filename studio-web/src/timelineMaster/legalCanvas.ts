/** Frontend mirror of the backend MiniMax H3 legal-canvas grid.
 *
 * Width/height are never stored on BatchBlock; they are always derived from
 * the canonical megapixel grid. See studio-api/app/video_runtime/legal_canvas.py
 * for the source of truth.
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

export function formatH3Megapixels(value: number): string {
  if (value === Math.trunc(value)) {
    return `${Math.trunc(value)}.0 MP`;
  }
  return `${value} MP`;
}

export function resolveH3MegapixelCanvas(mp: number): { label: string; width: number; height: number } {
  const dims = H3_MEGAPIXEL_BY_VALUE.get(mp);
  if (!dims) {
    throw new Error(
      `${mp} MP is not a supported MiniMax H3 canvas.`,
    );
  }
  return { label: formatH3Megapixels(mp), width: dims[0], height: dims[1] };
}

/** Resolve a BatchBlock's H3 resolution intent to a canonical canvas.
 *
 * Manual mode always uses the stored megapixel value. Auto or absent uses
 * the policy constant by draftMode. Returns a provenance dict carrying the
 * resolved mode, megapixels, label, width, height, and whether the choice was
 * auto-derived.
 */
export function resolveH3TimelineCanvas(
  h3Resolution: H3ResolutionState | null | undefined,
  draftMode: boolean,
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

  const { label, width, height } = resolveH3MegapixelCanvas(mp);
  return { mode, megapixels: mp, label, width, height, auto };
}
