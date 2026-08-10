import { api } from "../api";
import type { Asset, Project } from "../types";

const IMAGE_KINDS = new Set(["image", "imagegen_edit"]);
const VIDEO_KINDS = new Set(["video", "video_upscale"]);
const IMAGE_EXTS = /\.(png|jpe?g|webp|gif|bmp)$/i;
const VIDEO_EXTS = /\.(mp4|webm|mov|mkv|m4v)$/i;

export type ProjectCover = {
  url: string | null;
  kind: "image" | "video" | null;
};

function mediaKind(asset: Asset): "image" | "video" | null {
  const kind = (asset.kind || "").toLowerCase();
  const name = asset.filename || asset.path || "";
  if (IMAGE_KINDS.has(kind) || IMAGE_EXTS.test(name)) return "image";
  if (VIDEO_KINDS.has(kind) || VIDEO_EXTS.test(name)) return "video";
  return null;
}

function newest(assets: Asset[]): Asset | null {
  if (!assets.length) return null;
  return assets.reduce((best, a) => {
    const bt = best.created_at ? Date.parse(best.created_at) : 0;
    const at = a.created_at ? Date.parse(a.created_at) : 0;
    return at >= bt ? a : best;
  });
}

/** Resolve library card media: API cover first, else newest image/video asset. */
export function resolveProjectCover(project: Project): ProjectCover {
  if (project.cover_asset_id) {
    const kind =
      project.cover_kind === "video" || project.cover_kind === "image"
        ? project.cover_kind
        : mediaKind(project.assets?.find((a) => a.id === project.cover_asset_id) || ({ kind: "image" } as Asset)) ||
          "image";
    return { url: api.assetUrl(project.cover_asset_id), kind };
  }
  const assets = project.assets || [];
  const image = newest(assets.filter((a) => mediaKind(a) === "image"));
  if (image) return { url: api.assetUrl(image.id), kind: "image" };
  const video = newest(assets.filter((a) => mediaKind(a) === "video"));
  if (video) return { url: api.assetUrl(video.id), kind: "video" };
  return { url: null, kind: null };
}
