// Image-Frame Visual helpers — A|imgclip_|B still until rtclip_.

export type ImageFrameClipLike = {
  id?: string | null;
  asset_id?: string | null;
  start?: number;
  length?: number;
  mediaType?: string | null;
  media_type?: string | null;
  metadata?: {
    role?: string | null;
    referenceImageAssetId?: string | null;
    [key: string]: unknown;
  } | null;
};

export function isImageFrameClip(clip: ImageFrameClipLike | null | undefined): boolean {
  if (!clip) return false;
  const id = String(clip.id || "");
  if (id.startsWith("imgclip_")) return true;
  const media = String(clip.media_type || clip.mediaType || "").toLowerCase();
  if (media === "image") return true;
  const role = String(clip.metadata?.role || "").toLowerCase();
  return role === "image_frame";
}

function rangesOverlap(a0: number, a1: number, b0: number, b1: number): boolean {
  return a0 < b1 && b0 < a1;
}

/** Prefer metadata.referenceImageAssetId, else the clip's own image asset_id. */
export function imageFrameReferenceAssetId(clip: ImageFrameClipLike): string | null {
  const fromMeta = String(clip.metadata?.referenceImageAssetId || "").trim();
  if (fromMeta) return fromMeta;
  const asset = String(clip.asset_id || "").trim();
  return asset || null;
}

/** Find the Visual image-frame overlapping [markIn, markOut). */
export function findImageFrameInRange(
  clips: ImageFrameClipLike[] | null | undefined,
  markIn: number,
  markOut: number,
): ImageFrameClipLike | null {
  const start = Math.min(markIn, markOut);
  const end = Math.max(markIn, markOut);
  for (const clip of clips || []) {
    if (!isImageFrameClip(clip)) continue;
    const c0 = Number(clip.start || 0);
    const c1 = c0 + Math.max(0, Number(clip.length || 0));
    if (rangesOverlap(start, end, c0, c1)) return clip;
  }
  return null;
}

export function findImageFrameReferenceAssetId(
  clips: ImageFrameClipLike[] | null | undefined,
  markIn: number,
  markOut: number,
): string | null {
  const hit = findImageFrameInRange(clips, markIn, markOut);
  return hit ? imageFrameReferenceAssetId(hit) : null;
}
