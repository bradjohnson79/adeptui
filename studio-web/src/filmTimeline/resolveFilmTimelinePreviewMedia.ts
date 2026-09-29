export type FilmPreviewMedia = {
  assetId: string;
  kind: "video" | "image" | "empty";
  source: "segment" | "stitch" | "latest" | "reference" | "none";
};

type SegmentMedia = { assetId?: string | null; status?: string; order?: number };

const EMPTY: FilmPreviewMedia = { assetId: "", kind: "empty", source: "none" };

/** Stitch states that must never be presented as the current shot composition. */
const STALE_STITCH_STATUSES = new Set(["stale", "failed"]);

/** One resolver for the monitor and every Preview action. */
export function resolveFilmTimelinePreviewMedia(input: {
  selectedSegment?: SegmentMedia | null;
  stitchAssetId?: string | null;
  stitchStatus?: string | null;
  segments?: SegmentMedia[];
}): FilmPreviewMedia {
  const selected = input.selectedSegment?.assetId || "";
  if (selected && input.selectedSegment?.status !== "cancelled") {
    return { assetId: selected, kind: "video", source: "segment" };
  }
  const stitch = input.stitchAssetId || "";
  const stitchStatus = String(input.stitchStatus || "").trim().toLowerCase();
  // A stale stitch no longer covers every completed segment (Continue Shot adds
  // picture without rebuilding it), so fall through to the latest segment.
  // An absent status keeps the previous behaviour for legacy payloads.
  if (stitch && !STALE_STITCH_STATUSES.has(stitchStatus)) {
    return { assetId: stitch, kind: "video", source: "stitch" };
  }
  const completed = [...(input.segments || [])]
    .filter((item) => item.status === "completed" && item.assetId)
    .sort((a, b) => (a.order || 0) - (b.order || 0));
  const latest = completed[completed.length - 1]?.assetId || "";
  if (latest) return { assetId: latest, kind: "video", source: "latest" };
  return EMPTY;
}

export function previewActionsEnabled(media: FilmPreviewMedia): boolean {
  return media.kind === "video" && Boolean(media.assetId);
}
