/**
 * Timeline Library purity (TIMELINE_LIBRARY_MEDIA_ONLY).
 *
 * The Timeline Library only accepts media that can live on a track:
 * image, video, and audio. Documents, archives, models, and other non-media
 * kinds are excluded. "All" in the library filter means "all compatible
 * media", never "every asset kind".
 */

export const TIMELINE_MEDIA_TYPES = ["image", "video", "audio"] as const;
export type TimelineMediaType = (typeof TIMELINE_MEDIA_TYPES)[number];

const MEDIA_KIND_SET = new Set<string>(TIMELINE_MEDIA_TYPES);

/** MIME / extension fallbacks used when asset.kind is missing or ambiguous. */
const EXT_TO_KIND: Record<string, TimelineMediaType> = {
  png: "image",
  jpg: "image",
  jpeg: "image",
  webp: "image",
  gif: "image",
  bmp: "image",
  tiff: "image",
  tif: "image",
  mp4: "video",
  webm: "video",
  mov: "video",
  avi: "video",
  mkv: "video",
  m4v: "video",
  mp3: "audio",
  wav: "audio",
  ogg: "audio",
  oga: "audio",
  m4a: "audio",
  aac: "audio",
  flac: "audio",
};

/**
 * Normalize an asset kind to a TimelineMediaType. Returns null for non-media
 * (documents, archives, unknown). Uses the explicit kind first, then falls
 * back to the filename extension.
 */
export function normalizeTimelineMediaKind(
  kind: string | null | undefined,
  filename: string | null | undefined,
): TimelineMediaType | null {
  const k = (kind || "").trim().toLowerCase();
  if (MEDIA_KIND_SET.has(k)) return k as TimelineMediaType;
  // Some uploads arrive as "application/pdf" or similar in `kind`; reject.
  if (k && !MEDIA_KIND_SET.has(k)) {
    // try extension fallback before rejecting
  }
  const ext = (filename || "").split(".").pop()?.toLowerCase() || "";
  return EXT_TO_KIND[ext] ?? null;
}

/** True if an asset is placeable on the Timeline (image/video/audio only). */
export function isTimelineMediaAsset(asset: {
  kind?: string | null;
  filename?: string | null;
}): boolean {
  return normalizeTimelineMediaKind(asset.kind, asset.filename) !== null;
}
