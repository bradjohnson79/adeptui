/** Typed Timeline reference tokens. Prefix is UI-only; compile uses binding IDs. */

export type ReferenceMediaKind = "entity" | "image" | "video";

export type ReferenceBindingView = {
  id: string;
  asset_id: string;
  identity_id?: string | null;
  alias?: string | null;
  media_kind?: ReferenceMediaKind | null;
  reference_type: string;
  display_token?: string | null;
  asset_name?: string | null;
  broken?: boolean;
  broken_reason?: string | null;
  duration_sec?: number | null;
  scope_type?: string | null;
};

export function stripReferencePrefix(raw: string): string {
  const token = (raw || "").trim();
  if (token.startsWith("@") || token.startsWith("#") || token.startsWith("*")) {
    return token.slice(1).trim();
  }
  return token;
}

export function sanitizeAlias(raw: string): string {
  return stripReferencePrefix(raw).replace(/\s+/g, "").replace(/[^A-Za-z0-9_]/g, "");
}

export function prefixForMediaKind(kind: ReferenceMediaKind | string | null | undefined): "@" | "#" | "*" {
  if (kind === "entity") return "@";
  if (kind === "video") return "*";
  return "#";
}

export function mediaKindForAssetKind(kind: string): ReferenceMediaKind | null {
  if (kind === "video") return "video";
  if (kind === "image") return "image";
  return null;
}

export function referenceTypeForAssetKind(kind: string): "image" | "video" | null {
  if (kind === "video") return "video";
  if (kind === "image") return "image";
  return null;
}

export function typeLabel(referenceType: string, mediaKind?: string | null): string {
  if (referenceType === "character" || (mediaKind === "entity" && referenceType !== "prop")) {
    if (referenceType === "prop") return "Prop";
    if (referenceType === "character") return "Character";
  }
  if (referenceType === "prop") return "Prop";
  if (mediaKind === "video" || referenceType === "video") return "Video";
  if (mediaKind === "image" || referenceType === "image") return "Image";
  if (referenceType === "character") return "Character";
  return referenceType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function displayToken(alias: string | null | undefined, mediaKind: string | null | undefined): string {
  const token = sanitizeAlias(alias || "");
  if (!token) return "";
  return `${prefixForMediaKind(mediaKind)}${token}`;
}

export function chipLabel(binding: ReferenceBindingView): string {
  const alias = sanitizeAlias(binding.alias || binding.asset_name || "") || "Reference";
  const prefix = prefixForMediaKind(binding.media_kind || mediaKindForType(binding.reference_type));
  return `${prefix} ${alias} ${typeLabel(binding.reference_type, binding.media_kind)}`;
}

export function mediaKindForType(referenceType: string): ReferenceMediaKind {
  if (referenceType === "video" || referenceType === "motion") return "video";
  if (referenceType === "image") return "image";
  return "entity";
}

export function parseTokenQuery(raw: string): { prefix: "@" | "#" | "*" | null; query: string } {
  const text = (raw || "").trim();
  if (text.startsWith("@")) return { prefix: "@", query: text.slice(1) };
  if (text.startsWith("#")) return { prefix: "#", query: text.slice(1) };
  if (text.startsWith("*")) return { prefix: "*", query: text.slice(1) };
  return { prefix: null, query: text };
}

export function formatAutocompleteRow(
  binding: ReferenceBindingView,
  durationSec?: number | null,
): string {
  const token = binding.display_token || displayToken(binding.alias || binding.asset_name, binding.media_kind);
  const type = typeLabel(binding.reference_type, binding.media_kind);
  const duration = durationSec ?? binding.duration_sec;
  if (typeof duration === "number" && duration > 0 && (binding.media_kind === "video" || binding.reference_type === "video")) {
    return `${token} · ${type} · ${duration.toFixed(1)}s`;
  }
  return `${token} · ${type}`;
}

export type ReferenceTrack = "imageReference" | "videoReference" | "prompt" | "lipsyncSpeaker" | "camera";

export function bindingAcceptedOnTrack(
  binding: ReferenceBindingView,
  track: ReferenceTrack,
): boolean {
  const kind = binding.media_kind || mediaKindForType(binding.reference_type);
  if (track === "videoReference") return kind === "video";
  if (track === "lipsyncSpeaker") {
    return kind === "entity" && binding.reference_type !== "prop";
  }
  if (track === "camera") {
    return kind === "video" || kind === "entity";
  }
  if (track === "prompt") return Boolean(binding.id) && !String(binding.id).startsWith("character:");
  return kind === "image" || kind === "entity";
}

export function sortBindingsForTrack(
  bindings: ReferenceBindingView[],
  track: ReferenceTrack,
): ReferenceBindingView[] {
  if (track !== "camera") return bindings;
  const rank = (binding: ReferenceBindingView) => {
    if (binding.reference_type === "character") return 0;
    const kind = binding.media_kind || mediaKindForType(binding.reference_type);
    if (kind === "entity") return 1;
    if (kind === "video") return 2;
    return 3;
  };
  return [...bindings].sort((a, b) => rank(a) - rank(b));
}

export function isRealBindingId(id: string | null | undefined): boolean {
  const token = (id || "").trim();
  return Boolean(token) && !token.startsWith("character:");
}

export function tokenAtCaret(
  text: string,
  caret: number,
): { prefix: "@" | "#" | "*" | null; query: string; start: number; end: number } | null {
  const pos = Math.max(0, Math.min(caret, (text || "").length));
  const before = (text || "").slice(0, pos);
  const match = before.match(/([@#*])([A-Za-z0-9_]*)$/);
  if (!match || match.index == null) return null;
  return {
    prefix: match[1] as "@" | "#" | "*",
    query: match[2] || "",
    start: match.index,
    end: pos,
  };
}

function isListedGenerateBinding(item: ReferenceBindingView): boolean {
  return isRealBindingId(item.id) && !String(item.id).startsWith("character:");
}

/** Prefer scene-scope / listed rows. Sibling (project-scope) ids resolve via asset_id. */
export function resolveBinding(
  id: string | null | undefined,
  bindings: ReferenceBindingView[],
  siblingBindings: ReferenceBindingView[] = [],
): ReferenceBindingView | undefined {
  const token = String(id || "").trim();
  if (!token) return undefined;
  const listedById = bindings.find((item) => item.id === token);
  if (listedById) return listedById;
  const listedByAsset = bindings.find((item) => item.asset_id === token && isListedGenerateBinding(item));
  if (listedByAsset) return listedByAsset;
  const sibling =
    siblingBindings.find((item) => item.id === token) ||
    siblingBindings.find((item) => item.asset_id === token);
  if (sibling?.asset_id) {
    const sceneRow =
      bindings.find((item) => item.asset_id === sibling.asset_id && item.scope_type === "scene" && isListedGenerateBinding(item)) ||
      bindings.find((item) => item.asset_id === sibling.asset_id && isListedGenerateBinding(item));
    if (sceneRow) return sceneRow;
  }
  return undefined;
}

export function remapBindingIdsToSceneScope(
  ids: string[] | null | undefined,
  bindings: ReferenceBindingView[],
  siblingBindings: ReferenceBindingView[] = [],
): string[] {
  const next: string[] = [];
  for (const id of ids || []) {
    const resolved = resolveBinding(id, bindings, siblingBindings);
    const keep = resolved && isListedGenerateBinding(resolved) ? resolved.id : "";
    if (keep && !next.includes(keep)) next.push(keep);
  }
  return next;
}

export function tokenSummary(
  ids: string[] | null | undefined,
  bindings: ReferenceBindingView[],
  limit = 3,
  siblingBindings: ReferenceBindingView[] = [],
): string {
  const tokens = (ids || []).map((id) => {
    const binding = resolveBinding(id, bindings, siblingBindings);
    if (!binding) return "Broken Reference";
    return displayToken(binding.alias || binding.asset_name, binding.media_kind);
  });
  const shown = tokens.slice(0, limit);
  const extra = tokens.length - shown.length;
  if (!shown.length) return "";
  return extra > 0 ? `${shown.join(" ")} +${extra}` : shown.join(" ");
}

export function countBindingsByKind(
  ids: string[] | null | undefined,
  bindings: ReferenceBindingView[],
): { image: number; video: number; entity: number } {
  const counts = { image: 0, video: 0, entity: 0 };
  for (const id of ids || []) {
    const binding = resolveBinding(id, bindings);
    const kind = binding?.media_kind || mediaKindForType(binding?.reference_type || "image");
    if (kind === "video") counts.video += 1;
    else if (kind === "entity") counts.entity += 1;
    else counts.image += 1;
  }
  return counts;
}

export function assetDurationSec(asset: { duration_sec?: number | null; prompt_meta_json?: string | null } | undefined): number | null {
  if (!asset) return null;
  if (typeof asset.duration_sec === "number" && asset.duration_sec > 0) return asset.duration_sec;
  try {
    const meta = JSON.parse(asset.prompt_meta_json || "{}") as { duration_sec?: number; duration?: number };
    const value = Number(meta.duration_sec ?? meta.duration);
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}
