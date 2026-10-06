/**
 * Creator-facing identity for Timeline Library rows.
 *
 * Reuses existing asset tag / filename / labels / prompt_meta and character
 * profile names. Does not invent a second naming system or mutate assets.
 */
import { prefixForBinding, sanitizeAlias, typeLabel } from "../../sceneReferences/referenceTokens";

export type TimelineLibraryAsset = {
  id?: string;
  tag?: string | null;
  filename?: string | null;
  kind?: string | null;
  labels_json?: string | null;
  prompt_meta_json?: string | null;
  parent_asset_id?: string | null;
};

export type TimelineLibraryIdentity = {
  title: string;
  context: string;
  filename: string;
  tooltip: string;
  searchText: string;
  sheetKind: "crs" | "ers" | "prs" | "video" | "audio" | "image";
};

const GENERIC_TAGS = new Set([
  "character_sheet",
  "character_reference",
  "reference_sheet",
  "reference_sheet_video",
  "continuity_last_frame",
  "ingredients_render",
  "scene_stitch",
  "untagged",
]);

const GENERIC_TAG_PREFIXES = [
  "codirector_image_generate_",
  "new-character_v3_",
  "batch_bb_",
  "timeline-",
];

const MACHINE_FILENAME =
  /^(imagegen_|character_sheet_|scene_0_|scene_1_|scene_stitch_|cbr_|retake_|reference_sheet|keyframe_repair_)/i;

const HUMAN_VIEW_SUFFIX = /\s+(front|side|back|three[-\s]?quarter|identity|reference)$/i;

const SHEET_ID_IN_FILENAME = /character_sheet_([0-9a-f]{8})/i;

export function parseAssetJson(raw: string | null | undefined): unknown {
  if (!raw || !String(raw).trim()) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function parsePromptMeta(raw: string | null | undefined): Record<string, unknown> {
  const parsed = parseAssetJson(raw);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : {};
}

export function parseLabelList(raw: string | null | undefined): string[] {
  const parsed = parseAssetJson(raw);
  return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
}

export function buildCharacterNameMap(
  profiles: Array<{ id?: string; name?: string; character_name?: string; title?: string }>,
): Record<string, string> {
  const map: Record<string, string> = {};
  for (const profile of profiles) {
    const id = String(profile.id || "").trim();
    const name = String(profile.name || profile.character_name || profile.title || "").trim();
    if (!id || !name) continue;
    map[id] = name;
    map[id.slice(0, 8)] = name;
  }
  return map;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function filenameStem(filename: string): string {
  return filename.replace(/\.[^.]+$/, "").trim();
}

function isGenericTag(tag: string): boolean {
  const lower = tag.toLowerCase();
  if (!lower || GENERIC_TAGS.has(lower)) return true;
  return GENERIC_TAG_PREFIXES.some((prefix) => lower.startsWith(prefix));
}

function isHumanFilename(filename: string): boolean {
  const stem = filenameStem(filename);
  if (!stem || MACHINE_FILENAME.test(filename) || MACHINE_FILENAME.test(stem)) return false;
  if (/\s/.test(stem)) return true;
  if (/^[A-Z][A-Za-z]+(?:[A-Z][A-Za-z]+)+$/.test(stem)) return true;
  return /^[A-Za-z][A-Za-z-]{2,}$/.test(stem) && !/_/.test(stem);
}

function nameFromHumanFilename(filename: string): string {
  const stem = filenameStem(filename).replace(/[_-]+/g, " ").replace(HUMAN_VIEW_SUFFIX, "").trim();
  return stem;
}

function classifySheetKind(asset: TimelineLibraryAsset, blob: string, kind: string): TimelineLibraryIdentity["sheetKind"] {
  if (kind === "audio") return "audio";
  if (kind === "video") return "video";
  if (
    blob.includes("character_sheet") ||
    blob.includes("character_reference") ||
    blob.includes("composed_sheet") ||
    blob.includes("identity_references") ||
    blob.includes("hero_identity")
  ) {
    return "crs";
  }
  const tagKey = String(asset.tag || "").trim().toLowerCase();
  if (
    tagKey.startsWith("prop_") ||
    tagKey.startsWith("prop-") ||
    blob.includes("approved_prop") ||
    blob.includes("prop_view") ||
    blob.includes("prop_reference") ||
    blob.includes("project_prop") ||
    /\bprs\b/.test(blob)
  ) {
    return "prs";
  }
  if (
    blob.includes("environment") ||
    blob.includes("venture-corridor") ||
    blob.includes("venture_corridor") ||
    blob.includes("ers_sheet") ||
    blob.includes("codirectorers") ||
    (/ers(?:[0-9a-f]{4,})?sheet/i.test(blob)) ||
    blob.includes("location")
  ) {
    return "ers";
  }
  return kind === "image" ? "image" : "image";
}

function characterIdFromAsset(asset: TimelineLibraryAsset, meta: Record<string, unknown>): string {
  const direct = asString(meta.characterId) || asString(meta.character_id);
  if (direct) return direct;
  const creative = meta.creativeContext;
  if (creative && typeof creative === "object") {
    const nested = asString((creative as Record<string, unknown>).characterId);
    if (nested) return nested;
  }
  const fromFile = String(asset.filename || "").match(SHEET_ID_IN_FILENAME);
  return fromFile?.[1] || "";
}

function characterNameFromRelated(
  asset: TimelineLibraryAsset,
  meta: Record<string, unknown>,
  related: TimelineLibraryAsset[],
): string {
  const sourceIds = new Set<string>();
  const rawSources = meta.sourceAssetIds;
  if (Array.isArray(rawSources)) {
    for (const id of rawSources) {
      if (id) sourceIds.add(String(id));
    }
  }
  if (asset.parent_asset_id) sourceIds.add(asset.parent_asset_id);
  if (!sourceIds.size || !related.length) return "";
  for (const other of related) {
    if (!other.id || !sourceIds.has(other.id)) continue;
    if (!isHumanFilename(other.filename || "")) continue;
    const name = nameFromHumanFilename(other.filename || "");
    if (name) return name;
  }
  return "";
}

const PLACEHOLDER_CHARACTER_NAMES = new Set([
  "new character",
  "character",
  "untitled",
  "unnamed",
]);

function resolveCharacterName(
  asset: TimelineLibraryAsset,
  meta: Record<string, unknown>,
  characterNames: Record<string, string>,
  related: TimelineLibraryAsset[],
): string {
  const characterId = characterIdFromAsset(asset, meta);
  const mapped = characterId
    ? characterNames[characterId] || characterNames[characterId.slice(0, 8)] || ""
    : "";
  const fromMeta = asString(meta.characterName) || asString(meta.character_name);
  const placeholder = PLACEHOLDER_CHARACTER_NAMES.has(fromMeta.toLowerCase());
  if (fromMeta && !placeholder) return fromMeta;
  if (mapped) return mapped;
  const relatedName = characterNameFromRelated(asset, meta, related);
  if (relatedName) return relatedName;
  if (isHumanFilename(asset.filename || "")) {
    return nameFromHumanFilename(asset.filename || "");
  }
  return "";
}

function viewContext(blob: string, labels: string[]): string {
  if (labels.includes("composed") || blob.includes("character_sheet_composed") || blob.includes("character_sheet")) {
    return "Character sheet";
  }
  if (blob.includes("character_reference") || blob.includes("identity_references") || blob.includes("hero_identity")) {
    return "Identity";
  }
  if (blob.includes("three_quarter") || blob.includes("three-quarter")) return "Three-quarter";
  if (blob.includes("_side") || /\bside\b/.test(blob)) return "Side";
  if (blob.includes("_back") || /\bback\b/.test(blob)) return "Back";
  if (blob.includes("continuity_last_frame") || blob.includes("last_frame")) return "Last frame";
  if (blob.includes("scene_stitch")) return "Scene stitch";
  if (blob.includes("ingredients_render")) return "Ingredients";
  return "";
}

function kindContext(sheetKind: TimelineLibraryIdentity["sheetKind"], mediaKind: string): string {
  if (sheetKind === "crs") return typeLabel("character", "entity");
  if (sheetKind === "ers") return typeLabel("environment", "image");
  if (sheetKind === "prs") return typeLabel("prop", "entity");
  if (sheetKind === "video") return "Video";
  if (sheetKind === "audio") return "Audio";
  if (mediaKind === "image") return "Image";
  return mediaKind ? mediaKind.replace(/_/g, " ") : "Image";
}

function titleForAsset(args: {
  sheetKind: TimelineLibraryIdentity["sheetKind"];
  characterName: string;
  tag: string;
  filename: string;
}): string {
  const { sheetKind, characterName, tag, filename } = args;
  const aliasSource = characterName || (!isGenericTag(tag) ? tag : "") || (isHumanFilename(filename) ? nameFromHumanFilename(filename) : "");
  if (sheetKind === "crs" && aliasSource) {
    return `${prefixForBinding("character", "entity")}${sanitizeAlias(aliasSource)}`;
  }
  if (sheetKind === "ers" && aliasSource) {
    return `${prefixForBinding("environment", "image")}${sanitizeAlias(aliasSource)}`;
  }
  if (sheetKind === "prs" && aliasSource) {
    return `${prefixForBinding("prop", "entity")}${sanitizeAlias(aliasSource)}`;
  }
  if (sheetKind === "video" && aliasSource) {
    return `${prefixForBinding("video", "video")}${sanitizeAlias(aliasSource)}`;
  }
  if (aliasSource) {
    const token = sanitizeAlias(aliasSource);
    return token || aliasSource;
  }
  if (sheetKind === "video") return "Video";
  if (sheetKind === "audio") return "Audio";
  return "Image";
}

export function timelineLibraryIdentity(
  asset: TimelineLibraryAsset,
  options?: {
    characterNames?: Record<string, string>;
    relatedAssets?: TimelineLibraryAsset[];
  },
): TimelineLibraryIdentity {
  const tag = String(asset.tag || "").trim();
  const filename = String(asset.filename || "").trim();
  const kind = String(asset.kind || "").toLowerCase();
  const labels = parseLabelList(asset.labels_json);
  const meta = parsePromptMeta(asset.prompt_meta_json);
  const library = meta.library && typeof meta.library === "object" ? (meta.library as Record<string, unknown>) : {};
  const classification =
    library.classification && typeof library.classification === "object"
      ? (library.classification as Record<string, unknown>)
      : {};
  const blob = [
    tag,
    filename,
    kind,
    labels.join(" "),
    asString(meta.objective),
    asString(library.libraryPath),
    asString(classification.category),
    asString(classification.subtype),
  ]
    .join(" ")
    .toLowerCase();

  const sheetKind = classifySheetKind(asset, blob, kind);
  const characterName = resolveCharacterName(
    asset,
    meta,
    options?.characterNames || {},
    options?.relatedAssets || [],
  );
  const title = titleForAsset({ sheetKind, characterName, tag, filename });
  const view = viewContext(blob, labels);
  const type = kindContext(sheetKind, kind);
  const contextParts = [view, type].filter((part, index, all) => part && all.indexOf(part) === index);
  if (view && type && view.toLowerCase().includes(type.toLowerCase())) {
    contextParts.splice(contextParts.indexOf(type), 1);
  }
  const context = contextParts.join(" · ") || type;
  const tooltipParts = [title, context];
  if (filename && filename !== title) tooltipParts.push(filename);
  const tooltip = tooltipParts.filter(Boolean).join(" — ");
  const searchText = [title, context, characterName, tag, filename, kind, labels.join(" "), view, type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return { title, context, filename, tooltip, searchText, sheetKind };
}

export function assetMatchesLibrarySearch(
  asset: TimelineLibraryAsset,
  query: string,
  identity?: TimelineLibraryIdentity,
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const resolved = identity || timelineLibraryIdentity(asset);
  return resolved.searchText.includes(q);
}
