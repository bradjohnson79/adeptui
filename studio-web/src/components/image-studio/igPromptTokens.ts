/**
 * Image Generator prompt-native reference tagging.
 * Grammar (IG only — do not use Timeline *): @Character %Prop #Environment ~GenericImage
 * PoseCraft: ~PoseCraft_<SanitizedName> under ~ namespace.
 * Parser is punctuation-safe and does NOT split on spaces alone.
 */
import { sanitizeAlias } from "../../sceneReferences/referenceTokens";
import type { CisAuthorityKind, CisAuthorityRef } from "./cisAuthorityTypes";

export type IgSigil = "@" | "%" | "#" | "~";

export type IgParsedToken = {
  sigil: IgSigil;
  /** Alias without sigil (may be PoseCraft_Name). */
  alias: string;
  /** Full token including sigil. */
  raw: string;
  start: number;
  end: number;
  isPoseCraft: boolean;
};

export type IgCatalogOption = {
  key: string;
  kind: CisAuthorityKind;
  assetId: string;
  name: string;
  chip: string;
  disabled?: boolean;
  label: string;
  hint?: string;
};

/** Soft cap for ~ generic images (provider-capability limited). */
export const IG_GENERIC_MAX = 8;

export const IG_CARDINALITY: Record<
  CisAuthorityKind,
  { max: number; mode: "multi" | "replace" }
> = {
  character: { max: Number.POSITIVE_INFINITY, mode: "multi" },
  prop: { max: Number.POSITIVE_INFINITY, mode: "multi" },
  environment: { max: 1, mode: "replace" },
  posecraft: { max: 1, mode: "replace" },
  other: { max: IG_GENERIC_MAX, mode: "multi" },
};

const TOKEN_BODY = String.raw`(?:PoseCraft_)?[A-Za-z][A-Za-z0-9_]*`;
const TOKEN_FIND_RE = new RegExp(`([@#%~])(${TOKEN_BODY})`, "g");
const CARET_RE = new RegExp(`([@#%~])((?:PoseCraft_)?[A-Za-z0-9_]*)$`);

export function isPoseCraftAlias(alias: string): boolean {
  return /^PoseCraft_/i.test(alias || "");
}

export function poseCraftChip(name: string): string {
  const sanitized = sanitizeAlias(name) || "Pose";
  return `~PoseCraft_${sanitized}`;
}

export function poseCraftAliasFromName(name: string): string {
  return `PoseCraft_${sanitizeAlias(name) || "Pose"}`;
}

export function kindFromSigil(sigil: IgSigil, alias: string): CisAuthorityKind {
  if (sigil === "@") return "character";
  if (sigil === "%") return "prop";
  if (sigil === "#") return "environment";
  if (isPoseCraftAlias(alias)) return "posecraft";
  return "other";
}

export function sigilForKind(kind: CisAuthorityKind): IgSigil {
  if (kind === "character") return "@";
  if (kind === "prop") return "%";
  if (kind === "environment") return "#";
  return "~";
}

/** Canonical chip for a catalog/authority ref (PoseCraft → ~PoseCraft_Name). */
export function canonicalChipFor(kind: CisAuthorityKind, name: string): string {
  if (kind === "posecraft") return poseCraftChip(name);
  const alias = sanitizeAlias(name) || "Ref";
  return `${sigilForKind(kind)}${alias}`;
}

function isTokenBoundary(text: string, index: number): boolean {
  if (index <= 0) return true;
  const prev = text[index - 1];
  return !/[A-Za-z0-9_]/.test(prev);
}

/**
 * Identify @ % # ~ tokens with punctuation-safe boundaries.
 * Examples: "@Korri," "@Anadriya." "#VentureCorridor;"
 */
export function parseIgPromptTokens(text: string): IgParsedToken[] {
  const src = text || "";
  const out: IgParsedToken[] = [];
  TOKEN_FIND_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = TOKEN_FIND_RE.exec(src)) !== null) {
    const start = match.index;
    if (!isTokenBoundary(src, start)) continue;
    const sigil = match[1] as IgSigil;
    const alias = match[2];
    out.push({
      sigil,
      alias,
      raw: `${sigil}${alias}`,
      start,
      end: start + sigil.length + alias.length,
      isPoseCraft: isPoseCraftAlias(alias),
    });
  }
  return out;
}

/** Partial token at caret for autocomplete (@Kor → prefix @ query Kor). */
export function igTokenAtCaret(
  text: string,
  caret: number,
): { sigil: IgSigil; query: string; start: number; end: number } | null {
  const pos = Math.max(0, Math.min(caret, (text || "").length));
  const before = (text || "").slice(0, pos);
  const match = before.match(CARET_RE);
  if (!match || match.index == null) return null;
  if (!isTokenBoundary(before, match.index)) return null;
  return {
    sigil: match[1] as IgSigil,
    query: match[2] || "",
    start: match.index,
    end: pos,
  };
}

export function normalizeChipKey(chip: string): string {
  return (chip || "").trim().toLowerCase();
}

export function findCatalogByChip(
  catalogs: IgCatalogOption[],
  chipOrRaw: string,
): IgCatalogOption | undefined {
  const want = normalizeChipKey(chipOrRaw);
  if (!want) return undefined;
  return catalogs.find((o) => normalizeChipKey(o.chip) === want);
}

export function findCatalogSuggestions(
  catalogs: IgCatalogOption[],
  sigil: IgSigil,
  alias: string,
  limit = 3,
): string[] {
  const q = (alias || "").toLowerCase();
  const kind = kindFromSigil(sigil, alias);
  const pool = catalogs
    .filter((o) => !o.disabled && o.assetId)
    .filter((o) => {
      if (sigil === "~" && isPoseCraftAlias(alias)) return o.kind === "posecraft";
      if (sigil === "~") return o.kind === "other" || o.kind === "posecraft";
      return o.kind === kind;
    });
  const matched = pool.filter((o) => {
    if (!q) return true;
    return (
      o.chip.toLowerCase().includes(q) ||
      o.name.toLowerCase().includes(q) ||
      sanitizeAlias(o.name).toLowerCase().includes(q) ||
      // soft prefix / contains either way for Did-you-mean
      q.includes(sanitizeAlias(o.name).toLowerCase().slice(0, 3)) ||
      sanitizeAlias(o.name).toLowerCase().startsWith(q.slice(0, 3))
    );
  });
  const rows = matched.length ? matched : pool;
  return rows.slice(0, limit).map((o) => o.chip);
}

export function optionToAuthorityRef(o: IgCatalogOption): CisAuthorityRef {
  return {
    key: o.key,
    kind: o.kind,
    assetId: o.assetId,
    name: o.name,
    chip: o.chip,
  };
}

/**
 * Apply cardinality laws when activating a ref.
 * Environment / PoseCraft: replace existing of that kind.
 * Characters / Props: multi append (no duplicate key).
 * Generic (~): multi up to IG_GENERIC_MAX.
 */
export function applyAuthoritySelection(
  selected: CisAuthorityRef[],
  next: CisAuthorityRef,
): { refs: CisAuthorityRef[]; blockedReason?: string; replaced?: CisAuthorityRef | null } {
  const card = IG_CARDINALITY[next.kind];
  if (card.mode === "replace") {
    const replaced = selected.find((s) => s.kind === next.kind) || null;
    const without = selected.filter((s) => s.kind !== next.kind);
    return { refs: [...without, next], replaced };
  }
  if (selected.some((s) => s.key === next.key || s.assetId === next.assetId)) {
    return { refs: selected };
  }
  const sameKind = selected.filter((s) => s.kind === next.kind);
  if (Number.isFinite(card.max) && sameKind.length >= card.max) {
    return {
      refs: selected,
      blockedReason: `At most ${card.max} ${next.kind} reference(s) can be active.`,
    };
  }
  return { refs: [...selected, next] };
}

export function insertChipAtCaret(
  text: string,
  caret: number,
  chip: string,
): { text: string; caret: number; alreadyPresent: boolean } {
  const src = text || "";
  const at = igTokenAtCaret(src, caret);
  if (at) {
    const next = `${src.slice(0, at.start)}${chip}${src.slice(at.end)}`;
    return { text: next, caret: at.start + chip.length, alreadyPresent: false };
  }
  // Focus existing: if chip already in prompt, no blind duplicate insert.
  const tokens = parseIgPromptTokens(src);
  const existing = tokens.find((t) => normalizeChipKey(t.raw) === normalizeChipKey(chip));
  if (existing) {
    return { text: src, caret: existing.end, alreadyPresent: true };
  }
  const needsSpace = src.length > 0 && !/\s$/.test(src);
  const next = needsSpace ? `${src} ${chip}` : `${src}${chip}`;
  return { text: next, caret: next.length, alreadyPresent: false };
}

export type IgResolveResult = {
  toActivate: CisAuthorityRef[];
  unresolved: Array<{ raw: string; suggestions: string[] }>;
  /** #tags still in prompt that are not the active environment chip. */
  staleEnvTags: string[];
  /** ~PoseCraft tags in prompt that are not the active PoseCraft chip. */
  stalePoseTags: string[];
};

export function resolvePromptAgainstCatalog(
  prompt: string,
  catalogs: IgCatalogOption[],
  active: CisAuthorityRef[],
): IgResolveResult {
  const tokens = parseIgPromptTokens(prompt);
  const activeKeys = new Set(active.map((a) => a.key));
  const toActivate: CisAuthorityRef[] = [];
  const unresolved: IgResolveResult["unresolved"] = [];
  const seenActivate = new Set<string>();

  for (const tok of tokens) {
    const hit = findCatalogByChip(catalogs, tok.raw);
    if (hit && hit.assetId && !hit.disabled) {
      if (!activeKeys.has(hit.key) && !seenActivate.has(hit.key)) {
        toActivate.push(optionToAuthorityRef(hit));
        seenActivate.add(hit.key);
      }
      continue;
    }
    // Also try matching by alias within kind (legacy PoseCraft - Name chips).
    const kind = kindFromSigil(tok.sigil, tok.alias);
    const byAlias = catalogs.find((o) => {
      if (o.disabled || !o.assetId) return false;
      if (o.kind !== kind) return false;
      const alias = sanitizeAlias(o.name);
      if (kind === "posecraft") {
        return (
          normalizeChipKey(o.chip) === normalizeChipKey(tok.raw) ||
          normalizeChipKey(poseCraftAliasFromName(o.name)) === normalizeChipKey(tok.alias) ||
          alias.toLowerCase() === tok.alias.replace(/^PoseCraft_/i, "").toLowerCase()
        );
      }
      return alias.toLowerCase() === tok.alias.toLowerCase();
    });
    if (byAlias) {
      if (!activeKeys.has(byAlias.key) && !seenActivate.has(byAlias.key)) {
        toActivate.push(optionToAuthorityRef(byAlias));
        seenActivate.add(byAlias.key);
      }
      continue;
    }
    unresolved.push({
      raw: tok.raw,
      suggestions: findCatalogSuggestions(catalogs, tok.sigil, tok.alias),
    });
  }

  const activeEnv = active.find((a) => a.kind === "environment");
  const staleEnvTags = tokens
    .filter((t) => t.sigil === "#")
    .map((t) => t.raw)
    .filter((raw) => {
      if (!activeEnv) return false;
      return normalizeChipKey(raw) !== normalizeChipKey(activeEnv.chip);
    });

  const activePose = active.find((a) => a.kind === "posecraft");
  const stalePoseTags = tokens
    .filter((t) => t.isPoseCraft)
    .map((t) => t.raw)
    .filter((raw) => {
      if (!activePose) return false;
      return normalizeChipKey(raw) !== normalizeChipKey(activePose.chip);
    });

  return { toActivate, unresolved, staleEnvTags, stalePoseTags };
}

export function filterCatalogForAutocomplete(
  catalogs: IgCatalogOption[],
  sigil: IgSigil,
  query: string,
): IgCatalogOption[] {
  const q = (query || "").toLowerCase();
  const poseQuery = q.startsWith("posecraft_") || q.startsWith("posecraft");
  return catalogs
    .filter((o) => !o.disabled && o.assetId)
    .filter((o) => {
      if (sigil === "@") return o.kind === "character";
      if (sigil === "%") return o.kind === "prop";
      if (sigil === "#") return o.kind === "environment";
      // ~
      if (poseQuery || q.startsWith("pose")) {
        return o.kind === "posecraft" || o.kind === "other";
      }
      return o.kind === "other" || o.kind === "posecraft";
    })
    .filter((o) => {
      if (!q) return true;
      const hay = `${o.chip} ${o.name} ${o.label}`.toLowerCase();
      return hay.includes(q) || hay.includes(q.replace(/^posecraft_/, ""));
    });
}
