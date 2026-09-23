/** Typed Timeline reference tokens. Prefix IS the sheet type. Compile uses binding IDs.

  @ CRS  Character Reference Sheet
  # ERS  Environment Reference Sheet
  % PRS  Prop Reference Sheet
  * video / motion
  ~ Generic Image (Image Generator "Other Image References" authority;
    any project image that is not a CRS/ERS/PRS/video binding)
*/

export type ReferenceMediaKind = "entity" | "image" | "video";
export type SheetPrefix = "@" | "#" | "%" | "*" | "~";

/** Canonical sigil for generic image references (Image Generator authority). */
export const GENERIC_IMAGE_PREFIX = "~" as const;
/** Reference type carrying the generic-image sigil. */
export const GENERIC_IMAGE_REFERENCE_TYPE = "generic_image";

/** Semantic sheet types used by Timeline Refs / Timed Prompt (not media kinds). */
export type SemanticSheetType = "character" | "environment" | "prop";

export type ReferenceBindingView = {
  id: string;
  asset_id: string;
  identity_id?: string | null;
  alias?: string | null;
  media_kind?: ReferenceMediaKind | null;
  reference_type: string;
  display_token?: string | null;
  asset_name?: string | null;
  /** Creator sheet role. Wins over a mis-stamped environment type for prop sheets. */
  reference_roles?: string[] | null;
  broken?: boolean;
  broken_reason?: string | null;
  duration_sec?: number | null;
};

export type TimelineSemanticType = "character" | "prop" | "environment" | "video" | "image" | "other";
export type TimedPromptSemanticType = "character" | "prop" | "environment";

export type NormalizedTimelineReference = {
  /** Adept sheet semantics after normalization. */
  semanticType: TimelineSemanticType;
  /** Timed Prompt Character/Prop/Environment only; null for video/generic image/other. */
  timedPromptType: TimedPromptSemanticType | null;
  prefix: SheetPrefix;
  alias: string;
  /** Canonical tag with a single enforced prefix (never ##). */
  tag: string;
  mediaKind: ReferenceMediaKind;
};

function leadingSheetPrefix(raw: string | null | undefined): SheetPrefix | null {
  const token = String(raw || "").trim();
  if (!token) return null;
  const ch = token[0];
  if (ch === "@" || ch === "#" || ch === "%" || ch === "*" || ch === "~") return ch;
  return null;
}

function semanticTypeFromReferenceType(referenceType: string | null | undefined): TimelineSemanticType | null {
  const type = String(referenceType || "").trim().toLowerCase();
  if (type === "character" || type === "wardrobe" || type === "creature") return "character";
  if (type === "environment" || type === "location") return "environment";
  if (type === "prop" || type === "vehicle") return "prop";
  if (type === "video" || type === "motion") return "video";
  if (type === GENERIC_IMAGE_REFERENCE_TYPE) return "image";
  // mediaType / reference_type "image" is NOT semantic by itself — never overrides #/@/%.
  return null;
}

function semanticTypeFromLeadingPrefix(prefix: SheetPrefix | null | undefined): TimelineSemanticType | null {
  if (prefix === "@") return "character";
  if (prefix === "#") return "environment";
  if (prefix === "%") return "prop";
  if (prefix === "*") return "video";
  if (prefix === "~") return "image";
  return null;
}

function prefixForSemanticType(semanticType: TimelineSemanticType): SheetPrefix {
  if (semanticType === "character") return "@";
  if (semanticType === "environment") return "#";
  if (semanticType === "prop") return "%";
  if (semanticType === "video") return "*";
  if (semanticType === "image") return "~";
  return "#";
}

function propSheetIdentity(
  ref:
    | Pick<ReferenceBindingView, "alias" | "asset_name" | "reference_roles">
    | null
    | undefined,
): boolean {
  const roles = ref?.reference_roles || [];
  if (roles.some((role) => String(role || "").trim().toLowerCase() === "prop")) return true;
  const tag = String(ref?.asset_name || "").trim().toLowerCase();
  return tag.startsWith("prop_") || tag.startsWith("prop-") || tag.includes("approved_prop");
}

function mediaKindForSemanticType(
  semanticType: TimelineSemanticType,
  fallback: ReferenceMediaKind | string | null | undefined,
): ReferenceMediaKind {
  if (semanticType === "video") return "video";
  if (semanticType === "character" || semanticType === "prop") return "entity";
  if (semanticType === "environment" || semanticType === "image") return "image";
  const kind = String(fallback || "").toLowerCase();
  if (kind === "video" || kind === "entity" || kind === "image") return kind;
  return "image";
}

/**
 * Normalize an active Timeline / Scene reference binding to Adept sheet semantics.
 *
 * Contract:
 * - One collection only (no parallel registry).
 * - mediaType / reference_type "image" never overrides # / @ / % tag semantics.
 * - Tag-prefix fallback: @=character #=environment %=prop *=video ~=generic image.
 * - Output tag always has exactly one prefix (no ##).
 */
export function normalizeTimelineReference(
  ref:
    | Pick<
        ReferenceBindingView,
        "reference_type" | "media_kind" | "alias" | "asset_name" | "display_token" | "reference_roles"
      >
    | null
    | undefined,
): NormalizedTimelineReference {
  const referenceType = String(ref?.reference_type || "");
  const mediaKindRaw = ref?.media_kind || null;
  const alias = sanitizeAlias(ref?.alias || ref?.asset_name || ref?.display_token || "") || "";
  const tagPrefix =
    leadingSheetPrefix(ref?.display_token) ||
    leadingSheetPrefix(ref?.alias) ||
    leadingSheetPrefix(ref?.asset_name);

  const fromType = semanticTypeFromReferenceType(referenceType);
  const fromPrefix = semanticTypeFromLeadingPrefix(tagPrefix);
  const fromPattern =
    semanticTypeFromSheetPattern(ref?.alias) ||
    semanticTypeFromSheetPattern(ref?.display_token) ||
    semanticTypeFromSheetPattern(ref?.asset_name);

  let semanticType: TimelineSemanticType;
  if (fromType) {
    semanticType = fromType;
  } else if (fromPrefix) {
    // image mediaType must not win over explicit @/#/% on the active tag.
    semanticType = fromPrefix;
  } else if (fromPattern) {
    semanticType = fromPattern;
  } else if (String(mediaKindRaw || "").toLowerCase() === "video" || referenceType.toLowerCase() === "video") {
    semanticType = "video";
  } else if (String(mediaKindRaw || "").toLowerCase() === "entity") {
    semanticType = "character";
  } else if (referenceType.toLowerCase() === "image" || String(mediaKindRaw || "").toLowerCase() === "image") {
    semanticType = "image";
  } else if (referenceType) {
    semanticType = "other";
  } else {
    semanticType = "image";
  }

  // A prop sheet tagged prop_ / approved as a prop stays a prop even when
  // prompt prose ("no environment scene") stamped reference_type environment.
  if (propSheetIdentity(ref) && semanticType !== "character" && semanticType !== "video") {
    semanticType = "prop";
  }

  const prefix = prefixForSemanticType(semanticType);
  const tag = alias ? `${prefix}${alias}` : "";
  const timedPromptType: TimedPromptSemanticType | null =
    semanticType === "character" || semanticType === "prop" || semanticType === "environment"
      ? semanticType
      : null;

  return {
    semanticType,
    timedPromptType,
    prefix,
    alias,
    tag,
    mediaKind: mediaKindForSemanticType(semanticType, mediaKindRaw),
  };
}

/** Enforce a single sheet prefix for rename input; strips stacked ## / @@. */
export function enforceReferenceTagPrefix(
  raw: string,
  semanticType: TimelineSemanticType | TimedPromptSemanticType | string,
): string {
  const alias = sanitizeAlias(raw);
  if (!alias) return "";
  const normalized = normalizeTimelineReference({
    alias,
    reference_type:
      semanticType === "character" || semanticType === "prop" || semanticType === "environment"
        ? semanticType
        : semanticType === "video"
          ? "video"
          : semanticType === "image"
            ? GENERIC_IMAGE_REFERENCE_TYPE
            : "other",
    media_kind: mediaKindForSemanticType(
      (semanticType as TimelineSemanticType) || "other",
      null,
    ),
  });
  return normalized.tag;
}

export function stripReferencePrefix(raw: string): string {
  const token = (raw || "").trim();
  if (
    token.startsWith("@") ||
    token.startsWith("#") ||
    token.startsWith("*") ||
    token.startsWith("%") ||
    token.startsWith("~")
  ) {
    return token.slice(1).trim();
  }
  return token;
}

export function sanitizeAlias(raw: string): string {
  const stripped = stripReferencePrefix(raw).replace(/[^A-Za-z0-9]+/g, " ").trim();
  if (!stripped) return "";
  return stripped
    .split(/\s+/)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join("")
    .replace(/[^A-Za-z0-9]/g, "");
}

export function prefixForBinding(
  referenceType: string | null | undefined,
  mediaKind?: ReferenceMediaKind | string | null,
): SheetPrefix {
  const blob = `${referenceType || ""} ${mediaKind || ""}`.toLowerCase();
  if (blob.includes("video") || blob.trim() === "motion") return "*";
  if (["character", "wardrobe", "creature"].includes(String(referenceType || ""))) return "@";
  if (["environment", "location"].includes(String(referenceType || ""))) return "#";
  if (["prop", "vehicle"].includes(String(referenceType || ""))) return "%";
  if (referenceType === GENERIC_IMAGE_REFERENCE_TYPE) return "~";
  if (mediaKind === "entity") return "@";
  if (mediaKind === "video") return "*";
  return "#";
}

export function prefixForMediaKind(kind: ReferenceMediaKind | string | null | undefined): SheetPrefix {
  return prefixForBinding(null, kind);
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

/**
 * Human-readable role label for metadata display (autocomplete rows, Library
 * context subtitles). This is METADATA, never part of the visible @ token.
 *
 * Canonical law: Reference type is metadata. Character identity is the tag.
 * Never encode the reference type into the character's visible @ token.
 */

/**
 * Map an explicit @/#/% sigil (or leading char of a token) to a semantic sheet type.
 * Media-only sigils (* video, ~ generic image) return null.
 */
export function semanticTypeFromPrefix(raw: string | null | undefined): SemanticSheetType | null {
  const token = String(raw || "").trim();
  if (!token) return null;
  const ch = token[0];
  if (ch === "@") return "character";
  if (ch === "#") return "environment";
  if (ch === "%") return "prop";
  return null;
}

/**
 * Detect CRS / ERS / PRS (and common words) in Library tags / filenames.
 * Does not treat bare media_kind image/video as semantic sheet type.
 */
export function semanticTypeFromSheetPattern(raw: string | null | undefined): SemanticSheetType | null {
  const text = String(raw || "").trim();
  if (!text) return null;
  const compact = sanitizeAlias(text);
  const lower = text.toLowerCase();
  // Prop Creator tags and labels win over the word "environment" in a prop prompt.
  if (
    lower.startsWith("prop_") ||
    lower.startsWith("prop-") ||
    lower.includes("approved_prop") ||
    lower.includes("prop_view") ||
    lower.includes("prop_reference_sheet")
  ) {
    return "prop";
  }
  // Delimiter / camelCase / id-suffixed markers:
  // CodirectorErs, CodirectorErs3d90b410Sheet, foo_ers.png, hero-crs, mug.prs
  const hasErs =
    /(?:^|[^a-z])ers(?:$|[^a-z])/i.test(text) ||
    /Ers(?=[0-9A-Z_]|Sheet|$)/.test(text) ||
    /ERS(?=$|[0-9_]|Sheet)/i.test(compact) ||
    /ers$/i.test(compact) ||
    /environment(?:reference)?(?:sheet)?/i.test(lower);
  const hasCrs =
    /(?:^|[^a-z])crs(?:$|[^a-z])/i.test(text) ||
    /Crs(?=[0-9A-Z_]|Sheet|$)/.test(text) ||
    /CRS(?=$|[0-9_]|Sheet)/i.test(compact) ||
    /crs$/i.test(compact) ||
    /character(?:reference)?(?:sheet)?/i.test(lower);
  const hasPrs =
    /(?:^|[^a-z])prs(?:$|[^a-z])/i.test(text) ||
    /Prs(?=[0-9A-Z_]|Sheet|$)/.test(text) ||
    /PRS(?=$|[0-9_]|Sheet)/i.test(compact) ||
    /prs$/i.test(compact) ||
    /prop(?:reference)?(?:sheet)?/i.test(lower);
  if (hasErs) return "environment";
  if (hasCrs) return "character";
  if (hasPrs) return "prop";
  if (/\b(environment|location|place)\b/.test(lower)) return "environment";
  if (/\b(character|wardrobe|creature)\b/.test(lower)) return "character";
  if (/\b(prop|vehicle)\b/.test(lower)) return "prop";
  return null;
}

/**
 * Infer semantic reference_type when attaching a Library asset as a Timeline ref.
 * Keeps media_kind (image/video) separate — never leak media into sheet type when
 * a CRS/ERS/PRS or @/#/% signal is present.
 */
export function inferSemanticReferenceType(input: {
  tag?: string | null;
  filename?: string | null;
  alias?: string | null;
  label?: string | null;
  mediaKind?: string | null;
  referenceType?: string | null;
}): string {
  const explicit = String(input.referenceType || "").trim().toLowerCase();
  if (explicit === "character" || explicit === "wardrobe" || explicit === "creature") return explicit;
  if (explicit === "environment" || explicit === "location") {
    return explicit === "location" ? "environment" : explicit;
  }
  if (explicit === "prop" || explicit === "vehicle") return explicit === "vehicle" ? "prop" : explicit;
  if (explicit === GENERIC_IMAGE_REFERENCE_TYPE) return GENERIC_IMAGE_REFERENCE_TYPE;

  const fields = [input.tag, input.alias, input.filename, input.label];
  for (const field of fields) {
    const fromPrefix = semanticTypeFromPrefix(String(field || "").trim());
    if (fromPrefix) return fromPrefix;
  }
  for (const field of fields) {
    const fromPattern = semanticTypeFromSheetPattern(field);
    if (fromPattern) return fromPattern;
  }

  const mk = String(input.mediaKind || "").toLowerCase();
  if (mk === "video" || explicit === "video" || explicit === "motion") return "video";
  if (explicit === "image") return "image";
  if (mk === "image") return "image";
  if (mk === "entity") return "character";
  return referenceTypeForAssetKind(mk) || "image";
}


/** media_kind for an inferred Adept sheet type (CRS/ERS/PRS keep media separate from semantics). */
export function mediaKindForReferenceType(
  referenceType: string | null | undefined,
  assetKind?: string | null,
): ReferenceMediaKind {
  const type = String(referenceType || "").trim().toLowerCase();
  if (type === "video" || type === "motion") return "video";
  if (type === "character" || type === "wardrobe" || type === "creature" || type === "prop" || type === "vehicle") {
    return "entity";
  }
  if (
    type === "environment" ||
    type === "location" ||
    type === "image" ||
    type === GENERIC_IMAGE_REFERENCE_TYPE
  ) {
    return "image";
  }
  const kind = String(assetKind || "").toLowerCase();
  if (kind === "video") return "video";
  if (kind === "image") return "image";
  return "image";
}

/** Creator-facing role chip label from normalized Timeline reference semantics. */
export function roleLabelForBinding(
  binding: Pick<ReferenceBindingView, "reference_type" | "media_kind" | "alias" | "asset_name" | "display_token">,
): string {
  const normalized = normalizeTimelineReference(binding);
  if (normalized.semanticType === "character") return "Character";
  if (normalized.semanticType === "environment") return "Environment";
  if (normalized.semanticType === "prop") return "Prop";
  if (normalized.semanticType === "video") return "Video";
  if (normalized.semanticType === "image") return "Image";
  return typeLabel(binding.reference_type, binding.media_kind);
}

export function typeLabel(referenceType: string, mediaKind?: string | null): string {
  if (referenceType === "character") return "Character";
  if (referenceType === "wardrobe") return "Wardrobe";
  if (referenceType === "creature") return "Creature";
  if (referenceType === "environment" || referenceType === "location") return "Environment";
  if (referenceType === "prop") return "Prop";
  if (referenceType === "vehicle") return "Vehicle";
  if (referenceType === "scene_frame") return "Scene Frame";
  if (referenceType === GENERIC_IMAGE_REFERENCE_TYPE) return "Image Reference";
  if (mediaKind === "video" || referenceType === "video") return "Video";
  if (mediaKind === "entity") return "Character";
  if (mediaKind === "image" || referenceType === "image") return "Image";
  return referenceType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function displayToken(
  alias: string | null | undefined,
  mediaKind: string | null | undefined,
  referenceType?: string | null,
): string {
  const token = sanitizeAlias(alias || "");
  if (!token) return "";
  return `${prefixForBinding(referenceType, mediaKind)}${token}`;
}

/**
 * The canonical character @ tag shown on reference chips.
 *
 * Canonical law: Character identity IS the tag. Reference type (CRS/ERS/PRS)
 * is metadata and must never be encoded into the visible @ token.
 * Returns just the prefix + alias, e.g. "@Addex" — never "@AddexCRS".
 * The role label ("Character") is rendered separately by the chip consumer.
 */
export function chipLabel(binding: ReferenceBindingView): string {
  const alias = sanitizeAlias(binding.alias || binding.asset_name || "") || "Reference";
  const prefix = prefixForBinding(binding.reference_type, binding.media_kind);
  return `${prefix}${alias}`;
}

export function mediaKindForType(referenceType: string): ReferenceMediaKind {
  if (referenceType === "video" || referenceType === "motion") return "video";
  if (referenceType === "image") return "image";
  return "entity";
}

export function parseTokenQuery(raw: string): { prefix: SheetPrefix | null; query: string } {
  const text = (raw || "").trim();
  if (text.startsWith("@")) return { prefix: "@", query: text.slice(1) };
  if (text.startsWith("#")) return { prefix: "#", query: text.slice(1) };
  if (text.startsWith("%")) return { prefix: "%", query: text.slice(1) };
  if (text.startsWith("*")) return { prefix: "*", query: text.slice(1) };
  if (text.startsWith("~")) return { prefix: "~", query: text.slice(1) };
  return { prefix: null, query: text };
}

export function formatAutocompleteRow(
  binding: ReferenceBindingView,
  durationSec?: number | null,
): string {
  const token = binding.display_token || displayToken(binding.alias || binding.asset_name, binding.media_kind, binding.reference_type);
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
): { prefix: SheetPrefix | null; query: string; start: number; end: number } | null {
  const pos = Math.max(0, Math.min(caret, (text || "").length));
  const before = (text || "").slice(0, pos);
  const match = before.match(/([@#%*~])([A-Za-z0-9_]*)$/);
  if (!match || match.index == null) return null;
  return {
    prefix: match[1] as SheetPrefix,
    query: match[2] || "",
    start: match.index,
    end: pos,
  };
}

export function tokenSummary(
  ids: string[] | null | undefined,
  bindings: ReferenceBindingView[],
  limit = 3,
): string {
  const tokens = (ids || []).map((id) => {
    const binding = bindings.find((item) => item.id === id);
    if (!binding) return "Broken Reference";
    return displayToken(binding.alias || binding.asset_name, binding.media_kind, binding.reference_type);
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
    const binding = bindings.find((item) => item.id === id);
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

/**
 * Sheet suffixes that legacy prompts may have appended to character @-tags.
 * These are reference-type metadata (CRS/ERS/PRS), never part of the
 * character identity. Stripped for display normalization.
 */
const SHEET_SUFFIXES = ["CRS", "ERS", "PRS", "Sheet", "ReferenceSheet", "Reference"];

/**
 * Normalize legacy @-tags in prompt text for DISPLAY ONLY.
 *
 * Canonical law: Character identity is the tag. Reference type (CRS/ERS/PRS)
 * is metadata and must never be encoded into the visible @ token.
 *
 * Legacy prompts may contain @KorriCRS or @AddexCRS. This function strips
 * the sheet suffix so the display shows @Korri / @Addex — the canonical
 * character identity tag. The stored prompt text is NOT modified; the
 * entity resolver already handles legacy suffixes at resolve time.
 *
 * If a bindings list is provided, the stripped name is further mapped to
 * the binding's canonical display_token (e.g. @Korri → @Korri40YearsOld)
 * so the prompt display matches the Library and References tags exactly.
 */
export function normalizePromptTags(
  text: string,
  bindings?: ReferenceBindingView[],
): string {
  if (!text) return "";
  // Build a lookup from lowercase character name → display_token.
  // Also build a prefix lookup: if a stripped name is a prefix of a binding
  // alias (e.g. "Korri" is a prefix of "Korri40YearsOld"), map to that
  // binding's display_token so the prompt matches the Library/References tag.
  const tokenByCharName = new Map<string, string>();
  const prefixMatches: { prefix: string; token: string }[] = [];
  if (bindings) {
    for (const b of bindings) {
      const alias = sanitizeAlias(b.alias || b.asset_name || "");
      if (alias) {
        const token = b.display_token || displayToken(alias, b.media_kind, b.reference_type);
        tokenByCharName.set(alias.toLowerCase(), token);
        if (alias.length >= 4) {
          prefixMatches.push({ prefix: alias.toLowerCase(), token });
        }
      }
    }
  }
  return text.replace(/([@#%*~])([A-Za-z][A-Za-z0-9_\-]+)/g, (full, prefix, name) => {
    // Check if the name ends with a known sheet suffix
    for (const suffix of SHEET_SUFFIXES) {
      if (name.length > suffix.length && name.endsWith(suffix)) {
        const base = name.slice(0, -suffix.length);
        if (!base) continue;
        const baseLower = base.toLowerCase();
        // Direct match: stripped name == binding alias
        const direct = tokenByCharName.get(baseLower);
        if (direct) return direct;
        // Prefix match: stripped name is a prefix of a binding alias
        // (e.g. "korri" is a prefix of "korri40yearsold")
        if (baseLower.length >= 3) {
          const prefixHit = prefixMatches.find((m) => m.prefix.startsWith(baseLower));
          if (prefixHit) return prefixHit.token;
        }
        // Otherwise just strip the suffix
        return `${prefix}${base}`;
      }
    }
    return full;
  });
}
