/**
 * Shared Library asset model + helpers.
 *
 * Lifted from CoDirectorAssetPicker.tsx so the inline Library tab and the
 * attachment picker import from one source of truth. Extended with the real
 * backend fields (created_at, characterId, sceneId, classification) plus the
 * library taxonomy payload types (tree.folders / folderMap) and approval /
 * entity-name resolution helpers surfaced in the Library UI.
 */
import { api } from "../../../api";
import type { LibraryFolderNode } from "../../../api";
import { apiUrl } from "../../../runtime/apiBase";

/** Re-export the backend library taxonomy shapes for grid/panel consumers. */
export type { LibraryFolderMapEntry, LibraryFolderNode } from "../../../api";

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
  /** Raw JSON-string label array (e.g. `["approved_prop", "scene_shot"]`). */
  labels_json?: string | null;
  /** Raw JSON-string prompt metadata (e.g. ImageProvenance block). */
  prompt_meta_json?: string | null;
  /** Asset scope: project | shared | global. */
  scope?: string | null;
  /** Production approval status: none | approved | rejected (Asset DB column). */
  production_approval?: string | null;
  /** camelCase production approval (vision comparison payload serialization). */
  productionApproval?: string | null;
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

/**
 * Parse `labels_json` (a JSON-string array) into a clean string array.
 * Never throws — malformed or non-array payloads yield [].
 */
export function parseAssetLabels(asset: LibraryAsset): string[] {
  if (!asset.labels_json) return [];
  try {
    const parsed: unknown = JSON.parse(asset.labels_json);
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
}

export type AssetApprovalBadge = { label: string };

/**
 * Approval badge for a library asset, or null when the payload carries no
 * approval marker (CDX-017).
 *
 * Signals, in precedence order:
 *  - `labels_json` containing "approved_prop" → "Approved Prop"
 *  - `labels_json` containing "approved_take" → "Approved Take"
 *  - `production_approval` / `productionApproval` === "approved" → "Approved"
 */
export function getApprovalBadge(asset: LibraryAsset): AssetApprovalBadge | null {
  const labels = parseAssetLabels(asset);
  if (labels.includes("approved_prop")) return { label: "Approved Prop" };
  if (labels.includes("approved_take")) return { label: "Approved Take" };
  const approval = String(asset.productionApproval ?? asset.production_approval ?? "")
    .trim()
    .toLowerCase();
  if (approval === "approved") return { label: "Approved" };
  return null;
}

/** Flatten a nested library folder tree into a single list (pre-order). */
export function flattenTreeFolders(
  folders: LibraryFolderNode[] | undefined | null,
): LibraryFolderNode[] {
  if (!folders) return [];
  const out: LibraryFolderNode[] = [];
  const walk = (nodes: LibraryFolderNode[]): void => {
    for (const node of nodes) {
      out.push(node);
      if (node.children?.length) walk(node.children);
    }
  };
  walk(folders);
  return out;
}

/**
 * Build entityId → entityName lookup from the folder tree. Entity folders
 * (e.g. Characters/Anadriya, Props/Sword, Scenes/Castle) carry entityId +
 * entityName, so an asset's characterId / propId / sceneId can be resolved to
 * a human name for UI display.
 */
export function buildEntityNameMap(
  folders: LibraryFolderNode[] | undefined | null,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const folder of flattenTreeFolders(folders)) {
    if (folder.entityId && folder.entityName) {
      map.set(folder.entityId, folder.entityName);
    }
  }
  return map;
}

const ENTITY_ROOT_SEGMENT: Record<string, string> = {
  character: "Characters",
  prop: "Props",
  scene: "Scenes",
};

/** Best-effort entity name from a libraryPath like "Characters/Anadriya/…". */
function entityNameFromLibraryPath(
  path: string | undefined | null,
  entityType: string,
): string | null {
  if (!path) return null;
  const root = ENTITY_ROOT_SEGMENT[entityType];
  const segs = path.split("/").filter(Boolean);
  const idx = root ? segs.indexOf(root) : -1;
  if (idx >= 0 && segs[idx + 1]) {
    const name = segs[idx + 1].replace(/[-_]/g, " ").trim();
    if (name) return name;
  }
  return null;
}

/**
 * Resolve a linked entity (character / prop / scene) to a display name for
 * normal UI (CDX-071). Never returns a raw entity UUID: prefers the entity
 * name from the folder tree, falls back to the entity name embedded in the
 * asset's libraryPath, and returns null when nothing resolves.
 */
export function resolveLinkedEntityName(
  asset: LibraryAsset,
  folders: LibraryFolderNode[] | undefined | null,
  entityType: "character" | "prop" | "scene",
): string | null {
  const entityId =
    entityType === "character"
      ? asset.characterId
      : entityType === "prop"
        ? asset.propId
        : asset.sceneId;
  if (!entityId) return null;
  const fromTree = buildEntityNameMap(folders).get(entityId);
  if (fromTree) return fromTree;
  return entityNameFromLibraryPath(asset.libraryPath, entityType);
}

/**
 * Human label for an asset's entity associations (CDX-071). Shows resolved
 * names when available (e.g. "Character · Anadriya"); bare entity kind when
 * the id is present but no name resolves; the last libraryPath segment as a
 * final fallback. Never emits raw entity UUIDs.
 */
export function getAssetAssociationLabel(
  asset: LibraryAsset,
  folders: LibraryFolderNode[] | undefined | null,
): string {
  const parts: string[] = [];
  if (asset.characterId) {
    const name = resolveLinkedEntityName(asset, folders, "character");
    parts.push(name ? `Character · ${name}` : "Character");
  }
  if (asset.propId) {
    const name = resolveLinkedEntityName(asset, folders, "prop");
    parts.push(name ? `Prop · ${name}` : "Prop");
  }
  if (asset.sceneId) {
    const name = resolveLinkedEntityName(asset, folders, "scene");
    parts.push(name ? `Scene · ${name}` : "Scene");
  }
  if (parts.length === 0 && asset.libraryPath) {
    const seg = asset.libraryPath.split("/").filter(Boolean).pop();
    return seg ? seg.replace(/[-_]/g, " ") : "";
  }
  return parts.join(" · ");
}
