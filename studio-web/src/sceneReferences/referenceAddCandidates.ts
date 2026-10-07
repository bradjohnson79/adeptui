/**
 * Timeline References "Add Reference" candidate resolution.
 *
 * Sources:
 *  1) project.assets classified as character/prop/environment
 *  2) Character / Prop / Environment Creator registries (local + global) — authoritative names
 * No parallel registry. No free-text / phantom bindings (asset_id required).
 * Canonical display token = stored @/%/# tag or creator name; never CRS/ERS/PRS suffix.
 */

import type { Asset } from "../types";
import {
  inferSemanticReferenceType,
  mediaKindForAssetKind,
  parseTokenQuery,
  sanitizeAlias,
  type SemanticSheetType,
  type SheetPrefix,
} from "./referenceTokens";

export type ReferenceScopeLabel = "Local" | "Global";

export type AddReferenceCandidate = {
  assetId: string;
  displayToken: string;
  alias: string;
  semanticType: SemanticSheetType | "video" | "audio";
  referenceType: string;
  mediaKind: "image" | "video" | "audio";
  scopeLabel: ReferenceScopeLabel;
  thumbnailUrl?: string | null;
  assetName: string;
  searchBlob: string;
  /** Owning project id when known (creator registry). */
  owningProjectId?: string;
  source?: "asset" | "creator";
  /** Character / prop / environment profile id when the row belongs to one. */
  characterId?: string;
};

export type BoundIdentity = {
  assetId: string;
  alias: string;
};

type IdentityLike = {
  title?: string;
  sheetKind?: string | null;
};

/** Creator-registry row already resolved to a bindable asset id. */
export type CreatorRegistryRow = {
  entityId: string;
  name: string;
  semanticType: SemanticSheetType | "video" | "audio";
  assetId: string;
  isGlobal: boolean;
  owningProjectId: string;
  /** Prefer stored canonical tag when present (e.g. %Lantern, #VentureCorridorScene). */
  storedTag?: string | null;
  thumbnailUrl?: string | null;
  mediaKind?: "image" | "video" | "audio";
};

const PREFIX_FOR_SEMANTIC: Record<SemanticSheetType | "video" | "audio", SheetPrefix> = {
  character: "@",
  prop: "%",
  environment: "#",
  video: "*",
  audio: "&",
};

const SEMANTIC_FROM_SHEET: Record<string, SemanticSheetType> = {
  crs: "character",
  character: "character",
  prs: "prop",
  prop: "prop",
  ers: "environment",
  environment: "environment",
};

function characterIdOfAsset(asset: Asset): string {
  const raw = String(asset.prompt_meta_json || "").trim();
  if (!raw) return "";
  try {
    const meta = JSON.parse(raw) as { characterId?: string; character_id?: string };
    return String(meta.characterId || meta.character_id || "").trim();
  } catch {
    return "";
  }
}

function scopeLabelForAsset(asset: Pick<Asset, "scope" | "project_id">, projectId: string): ReferenceScopeLabel {
  const scope = String(asset.scope || "").toLowerCase();
  if (scope === "global" || scope === "shared") return "Global";
  if (asset.project_id && asset.project_id !== projectId) return "Global";
  return "Local";
}

/**
 * Prefer the asset's stored canonical tag when it already carries @/%/#.
 * Never append CRS/ERS/PRS.
 */
export function canonicalDisplayToken(opts: {
  storedTag?: string | null;
  aliasHint?: string | null;
  semanticType: SemanticSheetType | "video" | "audio";
}): { displayToken: string; alias: string; prefix: SheetPrefix } {
  const prefix = PREFIX_FOR_SEMANTIC[opts.semanticType];
  const raw = String(opts.storedTag || "").trim();
  const leading = raw[0];
  if (leading === "@" || leading === "%" || leading === "#") {
    const storedPrefix = leading as SheetPrefix;
    const body = sanitizeAlias(raw.slice(1)) || sanitizeAlias(opts.aliasHint || "") || "Reference";
    return { displayToken: `${storedPrefix}${body}`, alias: body, prefix: storedPrefix };
  }
  const alias =
    sanitizeAlias(opts.aliasHint || "") ||
    sanitizeAlias(raw) ||
    "Reference";
  return { displayToken: `${prefix}${alias}`, alias, prefix };
}

export function semanticTypeFromIdentity(
  identity: IdentityLike | null | undefined,
  inferred: string,
): SemanticSheetType | null {
  const sheet = String(identity?.sheetKind || "").toLowerCase();
  if (sheet && SEMANTIC_FROM_SHEET[sheet]) return SEMANTIC_FROM_SHEET[sheet];
  const type = String(inferred || "").toLowerCase();
  if (type === "character" || type === "wardrobe" || type === "creature") return "character";
  if (type === "prop" || type === "vehicle") return "prop";
  if (type === "environment" || type === "location") return "environment";
  return null;
}

/** Availability: home project OR Global flag. Selectable without requiring edit ownership. */
export function isCreatorRowAvailable(row: Pick<CreatorRegistryRow, "isGlobal" | "owningProjectId">, projectId: string): boolean {
  const home = String(row.owningProjectId || "").trim() === String(projectId || "").trim();
  return home || Boolean(row.isGlobal);
}

export function creatorRowToCandidate(row: CreatorRegistryRow, projectId: string): AddReferenceCandidate | null {
  if (!row.assetId) return null;
  if (!isCreatorRowAvailable(row, projectId)) return null;
  const { displayToken, alias } = canonicalDisplayToken({
    storedTag: row.storedTag,
    aliasHint: row.name,
    semanticType: row.semanticType,
  });
  if (!alias) return null;
  const scopeLabel: ReferenceScopeLabel = row.isGlobal ? "Global" : "Local";
  const assetName = String(row.name || alias);
  const searchBlob = `${displayToken} ${alias} ${assetName} ${row.semanticType} ${scopeLabel} ${row.entityId}`.toLowerCase();
  return {
    assetId: row.assetId,
    displayToken,
    alias,
    semanticType: row.semanticType,
    referenceType: row.semanticType,
    mediaKind: row.mediaKind || "image",
    scopeLabel,
    thumbnailUrl: row.thumbnailUrl ?? null,
    assetName,
    searchBlob,
    owningProjectId: row.owningProjectId,
    source: "creator",
    characterId: row.semanticType === "character" ? row.entityId : undefined,
  };
}

export function buildCreatorRegistryCandidates(opts: {
  rows: CreatorRegistryRow[];
  projectId: string;
}): AddReferenceCandidate[] {
  const out: AddReferenceCandidate[] = [];
  const seen = new Set<string>();
  for (const row of opts.rows || []) {
    const c = creatorRowToCandidate(row, opts.projectId);
    if (!c) continue;
    if (seen.has(c.assetId)) continue;
    seen.add(c.assetId);
    out.push(c);
  }
  return out.sort((a, b) => a.displayToken.localeCompare(b.displayToken));
}

/**
 * Build Add Reference candidates from existing project assets (local + global in the
 * same asset list). Caller may pass timelineLibraryIdentity(asset, …) via identityOf.
 */
export function buildAddReferenceCandidates(opts: {
  assets: Asset[];
  projectId: string;
  identityOf?: (asset: Asset) => IdentityLike;
  thumbnailUrlOf?: (asset: Asset) => string | null | undefined;
}): AddReferenceCandidate[] {
  const out: AddReferenceCandidate[] = [];
  const seenAsset = new Set<string>();

  for (const asset of opts.assets || []) {
    if (!asset?.id || seenAsset.has(asset.id)) continue;
    const mediaKind = mediaKindForAssetKind(asset.kind);
    if (mediaKind !== "image" && mediaKind !== "video" && mediaKind !== "audio") continue;

    const identity = opts.identityOf?.(asset) || { title: asset.tag || asset.filename };
    const inferred = inferSemanticReferenceType({
      tag: asset.tag,
      filename: asset.filename,
      alias: identity.title,
      mediaKind,
    });
    const semanticType = semanticTypeFromIdentity(identity, inferred);
    // First-class five types: CPE from identity/sheets; Video/Audio from media kind.
    let candidateType: AddReferenceCandidate["semanticType"] | null = semanticType;
    if (!candidateType && mediaKind === "video") candidateType = "video";
    if (!candidateType && mediaKind === "audio") candidateType = "audio";
    if (!candidateType) continue;

    let displayToken: string;
    let alias: string;
    if (candidateType === "video" || candidateType === "audio") {
      alias =
        sanitizeAlias(identity.title || "") ||
        sanitizeAlias(asset.tag || "") ||
        sanitizeAlias(asset.filename || "") ||
        (candidateType === "video" ? "Video" : "Audio");
      const prefix = candidateType === "video" ? "*" : "&";
      displayToken = `${prefix}${alias}`;
    } else {
      const canon = canonicalDisplayToken({
        storedTag: asset.tag,
        aliasHint: identity.title || asset.tag || asset.filename,
        semanticType: candidateType,
      });
      displayToken = canon.displayToken;
      alias = canon.alias;
    }
    if (!alias) continue;

    seenAsset.add(asset.id);
    const assetName = String(identity.title || asset.tag || asset.filename || alias);
    const scopeLabel = scopeLabelForAsset(asset, opts.projectId);
    const searchBlob = `${displayToken} ${alias} ${assetName} ${candidateType} ${scopeLabel} ${asset.filename || ""}`.toLowerCase();

    out.push({
      assetId: asset.id,
      displayToken,
      alias,
      semanticType: candidateType,
      referenceType: candidateType,
      mediaKind,
      scopeLabel,
      thumbnailUrl: opts.thumbnailUrlOf?.(asset) ?? null,
      assetName,
      searchBlob,
      owningProjectId: asset.project_id,
      source: "asset",
      characterId: characterIdOfAsset(asset),
    });
  }

  return out.sort((a, b) => a.displayToken.localeCompare(b.displayToken));
}

const SHEET_SUFFIX = /(CRS|ERS|PRS)$/i;

/**
 * Character / prop / environment identity, ignoring a trailing sheet suffix.
 * @Cade and @CadeCRS are the same character. @Korri40YearsOld stays distinct.
 */
export function identityAliasKey(alias: string): string {
  return sanitizeAlias(alias).replace(SHEET_SUFFIX, "").toLowerCase();
}

function prefersSheetToken(candidate: AddReferenceCandidate): boolean {
  if (SHEET_SUFFIX.test(sanitizeAlias(candidate.alias))) return true;
  const blob = `${candidate.assetName} ${candidate.displayToken} ${candidate.searchBlob}`.toLowerCase();
  return /\bcrs\b|\bers\b|\bprs\b/.test(blob);
}

/**
 * One @ / % / # tag per identity. View stills (front, side, back) must not
 * each become their own tag. When a sheet token exists (@CadeCRS), it is the
 * only candidate; the other tags for that identity are dropped.
 */
export function collapseDuplicateIdentityCandidates(
  candidates: AddReferenceCandidate[],
): AddReferenceCandidate[] {
  const groups = new Map<string, AddReferenceCandidate[]>();
  const passthrough: AddReferenceCandidate[] = [];
  for (const candidate of candidates || []) {
    if (!candidate?.assetId) continue;
    const key = identityAliasKey(candidate.alias);
    if (!key || (candidate.semanticType !== "character" && candidate.semanticType !== "prop" && candidate.semanticType !== "environment")) {
      passthrough.push(candidate);
      continue;
    }
    const groupKey = `${candidate.semanticType}:${key}`;
    const list = groups.get(groupKey) || [];
    list.push(candidate);
    groups.set(groupKey, list);
  }
  // Angle stills can carry a placeholder name ("New Character") while the
  // profile and the sheet share one character id. Those are the same tag.
  const characterOwners = new Map<string, string>();
  for (const [groupKey, list] of groups) {
    for (const candidate of list) {
      const characterId = String(candidate.characterId || "").trim();
      if (!characterId) continue;
      const ownerKey = `${candidate.semanticType}:${characterId}`;
      const prior = characterOwners.get(ownerKey);
      if (!prior) {
        characterOwners.set(ownerKey, groupKey);
        continue;
      }
      if (prior === groupKey) continue;
      const into = groups.get(prior) || [];
      into.push(...list);
      groups.set(prior, into);
      groups.delete(groupKey);
      break;
    }
  }
  const kept: AddReferenceCandidate[] = [...passthrough];
  for (const list of groups.values()) {
    const sheets = list.filter(prefersSheetToken);
    const pool = sheets.length ? sheets : list;
    pool.sort((a, b) => {
      const aSheet = SHEET_SUFFIX.test(sanitizeAlias(a.alias)) ? 0 : 1;
      const bSheet = SHEET_SUFFIX.test(sanitizeAlias(b.alias)) ? 0 : 1;
      if (aSheet !== bSheet) return aSheet - bSheet;
      return a.displayToken.localeCompare(b.displayToken);
    });
    kept.push(pool[0]);
  }
  return kept.sort((a, b) => a.displayToken.localeCompare(b.displayToken));
}

/** Prefer creator-registry rows (authoritative names) when assetId collides. */
export function mergeAddReferenceCandidates(
  assetCandidates: AddReferenceCandidate[],
  creatorCandidates: AddReferenceCandidate[],
): AddReferenceCandidate[] {
  const byAsset = new Map<string, AddReferenceCandidate>();
  for (const c of assetCandidates || []) {
    if (!c?.assetId) continue;
    byAsset.set(c.assetId, c);
  }
  for (const c of creatorCandidates || []) {
    if (!c?.assetId) continue;
    const prev = byAsset.get(c.assetId);
    if (!prev || c.source === "creator") {
      // Keep richer search blob when merging over an asset row
      if (prev) {
        byAsset.set(c.assetId, {
          ...c,
          searchBlob: `${c.searchBlob} ${prev.searchBlob}`.toLowerCase(),
          thumbnailUrl: c.thumbnailUrl || prev.thumbnailUrl,
        });
      } else {
        byAsset.set(c.assetId, c);
      }
    }
  }
  return Array.from(byAsset.values()).sort((a, b) => a.displayToken.localeCompare(b.displayToken));
}

export function filterAddReferenceCandidates(
  candidates: AddReferenceCandidate[],
  rawQuery: string,
): AddReferenceCandidate[] {
  const { prefix, query } = parseTokenQuery(rawQuery);
  const q = query.trim().toLowerCase();

  return candidates.filter((row) => {
    if (prefix === "@" && row.semanticType !== "character") return false;
    if (prefix === "%" && row.semanticType !== "prop") return false;
    if (prefix === "#" && row.semanticType !== "environment") return false;
    if (prefix === "*" || prefix === "~") return false;
    // Prefix-only queries (@ / % / #) are valid — list all of that semantic type.
    if (!q) return Boolean(prefix);
    return (
      row.searchBlob.includes(q) ||
      row.alias.toLowerCase().includes(q) ||
      row.displayToken.toLowerCase().includes(q) ||
      row.assetName.toLowerCase().includes(q)
    );
  });
}

export function isAlreadyBound(
  candidate: Pick<AddReferenceCandidate, "assetId" | "alias">,
  bound: BoundIdentity[],
): boolean {
  const aliasKey = sanitizeAlias(candidate.alias).toLowerCase();
  const identityKey = identityAliasKey(candidate.alias);
  return bound.some((b) => {
    if (b.assetId === candidate.assetId) return true;
    const boundAlias = sanitizeAlias(b.alias).toLowerCase();
    if (boundAlias && boundAlias === aliasKey) return true;
    const boundIdentity = identityAliasKey(b.alias);
    return Boolean(identityKey) && boundIdentity === identityKey;
  });
}

export function formatAddReferenceRow(c: AddReferenceCandidate): string {
  const typeLabel =
    c.semanticType === "character"
      ? "Character"
      : c.semanticType === "prop"
        ? "Prop"
        : c.semanticType === "environment"
          ? "Environment"
          : c.semanticType === "video"
            ? "Video"
            : c.semanticType === "audio"
              ? "Audio"
              : String(c.semanticType);
  return `${c.displayToken} · ${typeLabel} · ${c.scopeLabel}`;
}

/** Pick a bindable asset id from character reference rows. */
export function pickCharacterBindAssetId(
  refs: Array<{ asset_id?: string; reference_role?: string } | null | undefined>,
): string | null {
  const rows = (refs || []).filter((r) => r && r.asset_id) as Array<{ asset_id: string; reference_role?: string }>;
  const hero = rows.find((r) => String(r.reference_role || "").toLowerCase() === "hero_identity");
  if (hero?.asset_id) return hero.asset_id;
  const image = rows.find((r) => String(r.reference_role || "").toLowerCase() === "reference_image");
  if (image?.asset_id) return image.asset_id;
  return rows[0]?.asset_id || null;
}
