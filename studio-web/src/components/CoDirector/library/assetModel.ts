/**
 * Shared Library asset model + helpers.
 *
 * Lifted from CoDirectorAssetPicker.tsx so the inline Library tab and the
 * attachment picker import from one source of truth. Extended with the real
 * backend fields (created_at, characterId, sceneId, classification).
 */
import { api } from "../../../api";
import { apiUrl } from "../../../runtime/apiBase";

/**
 * Resolve an asset URL string against the configured API_BASE.
 *
 * - Absolute URLs (http://, https://, protocol-relative //) and data: URIs are
 *   returned unchanged.
 * - Relative paths starting with "/" are routed through apiUrl() so they pick
 *   up API_BASE on hosted (Vercel) builds and stay relative in local dev (where
 *   Vite proxies /api → Studio API).
 * - Other strings (e.g. already-resolved absolute URLs without a leading slash)
 *   are returned as-is.
 */
export function resolveAssetUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  if (/^(https?:)?\/\//i.test(url) || /^data:/i.test(url)) return url;
  if (url.startsWith("/")) return apiUrl(url);
  return url;
}

export type LibraryAsset = {
  id: string;
  tag?: string;
  title?: string;
  filename?: string;
  kind?: string;
  mime_type?: string;
  url?: string;
  file_url?: string;
  previewUrl?: string;
  preview_url?: string;
  thumb_url?: string;
  libraryPath?: string;
  created_at?: string | null;
  characterId?: string | null;
  sceneId?: string | null;
  propId?: string | null;
  classification?: Record<string, unknown> | null;
};

export type AssetFilterId = "all" | "images" | "video" | "audio" | "documents";

export type AssetFilter = {
  id: AssetFilterId;
  label: string;
};

export const FILTERS: AssetFilter[] = [
  { id: "all", label: "All" },
  { id: "images", label: "Images" },
  { id: "video", label: "Video" },
  { id: "audio", label: "Audio" },
  { id: "documents", label: "Documents" },
];

export function getAssetName(asset: LibraryAsset): string {
  return asset.tag || asset.title || asset.filename || "Untitled";
}

export function getAssetKindText(asset: LibraryAsset): string {
  const haystack = `${asset.kind || ""} ${asset.mime_type || ""} ${asset.filename || ""}`.toLowerCase();
  if (haystack.includes("image")) return "Image";
  if (haystack.includes("video")) return "Video";
  if (haystack.includes("audio")) return "Audio";
  if (
    haystack.includes("document") ||
    haystack.includes("application/") ||
    haystack.includes("text/") ||
    haystack.includes("pdf") ||
    haystack.includes(".docx") ||
    haystack.includes(".fountain") ||
    haystack.includes("json")
  ) {
    return "Document";
  }
  return "Library item";
}

export function isImageAsset(asset: LibraryAsset): boolean {
  const haystack = `${asset.kind || ""} ${asset.mime_type || ""}`.toLowerCase();
  return haystack.includes("image");
}

export function isVideoAsset(asset: LibraryAsset): boolean {
  const haystack = `${asset.kind || ""} ${asset.mime_type || ""}`.toLowerCase();
  return haystack.includes("video");
}

export function isAudioAsset(asset: LibraryAsset): boolean {
  const haystack = `${asset.kind || ""} ${asset.mime_type || ""}`.toLowerCase();
  return haystack.includes("audio");
}

export function isDocumentAsset(asset: LibraryAsset): boolean {
  const haystack = `${asset.kind || ""} ${asset.mime_type || ""} ${asset.filename || ""}`.toLowerCase();
  return (
    haystack.includes("document") ||
    haystack.includes("application/") ||
    haystack.includes("text/") ||
    haystack.includes("pdf") ||
    haystack.includes(".docx") ||
    haystack.includes(".fountain") ||
    haystack.includes(".txt") ||
    haystack.includes("json")
  );
}

export function matchesFilter(asset: LibraryAsset, filter: AssetFilterId): boolean {
  if (filter === "all") return true;
  if (filter === "images") return isImageAsset(asset);
  if (filter === "video") return isVideoAsset(asset);
  if (filter === "audio") return isAudioAsset(asset);
  if (filter === "documents") return isDocumentAsset(asset);
  return true;
}

export function getCardPreviewUrl(asset: LibraryAsset): string | undefined {
  if (asset.thumb_url) return resolveAssetUrl(asset.thumb_url);
  const preview = asset.preview_url || asset.previewUrl;
  if (preview) return resolveAssetUrl(preview);
  if (isImageAsset(asset)) return api.assetUrl(asset.id);
  return undefined;
}

export function getDisplayDate(asset: LibraryAsset): string {
  if (!asset.created_at) return "";
  try {
    const d = new Date(asset.created_at);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function getDocumentKind(filename?: string): string {
  if (!filename) return "DOC";
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "PDF";
  if (lower.endsWith(".docx") || lower.endsWith(".doc")) return "DOCX";
  if (lower.endsWith(".fountain")) return "Fountain";
  if (lower.endsWith(".txt")) return "TXT";
  if (lower.endsWith(".json")) return "JSON";
  return "DOC";
}

export function getAssetIcon(asset: LibraryAsset): string {
  if (isVideoAsset(asset)) return "Vid";
  if (isAudioAsset(asset)) return "Aud";
  if (isDocumentAsset(asset)) return "Doc";
  return "Lib";
}
