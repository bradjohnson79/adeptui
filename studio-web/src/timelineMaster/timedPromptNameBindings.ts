/**
 * FROZEN Timed Prompt reference-binding contract.
 *
 * Two surfaces, one clip list. Do not add a second store.
 *
 * Walked 2026-09-01 on Korri Anadriya Scene 1:
 * - Double-click modal: EXISTS (Prompt / Start / Length / Temperature / Movement).
 *   Vertical scroll: EXISTS on `.codirector-modal` (overflow:auto).
 *   Type / Reference / Prompt Name rows: MISSING.
 *   Modal write of `reference_binding_ids`: DISCONNECTED.
 * - Right Drawer Inspect: EXISTS for Batch; Timed Prompt Inspect EXISTS via
 *   PromptReferenceField (chips + @/#/% token insert into prose).
 *   Type / Reference / Prompt Name rows: MISSING.
 * - Shared clip state: EXISTS as `PromptSegment.reference_binding_ids`.
 * - Prompt Name / type / canonical tag per binding: MISSING.
 * - Persistence of binding IDs via Master promptSegments: EXISTS.
 * - W46 reconcile of binding IDs on update: DISCONNECTED (copied on create only).
 * - Compile IDs → R2V roles → selected generator .md: EXISTS.
 * - Compile Prompt Name → binding ID (no text-replace of prose): DISCONNECTED.
 * - Scene References @ CRS / # ERS / % PRS / * Video / & Audio: EXISTS. Natural TP tags @VideoN / @AudioN compile on H3.
 * - Inspect `ensureBinding` can attach Library / `character:` synthetics — do not
 *   reuse that here. Only References already on this Timeline scene.
 *
 * Persist on the Timed Prompt clip:
 *   reference_name_bindings: [{ binding_id, prompt_name, type, tag }]
 *   reference_binding_ids: derived [binding_id] — kept for the existing compiler.
 *
 * Prompt Name is creator prose, not generator syntax.
 * Binding ID is the production reference.
 * tag is the locked Adept grammar (@ / # / %).
 * The selected generator .md decides how that role reaches the model.
 */

import {
  displayToken,
  isRealBindingId,
  normalizeTimelineReference,
  prefixForBinding,
  sanitizeAlias,
  stripReferencePrefix,
  type ReferenceBindingView,
} from "../sceneReferences/referenceTokens";
import { resolveTimelineReference } from "./loadTimelineReferenceCatalog";

export type TimedPromptBindingType = "character" | "prop" | "environment" | "video" | "audio";

export type TimedPromptNameBinding = {
  binding_id: string;
  prompt_name: string;
  type: TimedPromptBindingType;
  tag: string;
  asset_id?: string;
  identity_id?: string;
  reference_sheet_id?: string;
};

export const TIMED_PROMPT_BINDING_TYPES: { id: TimedPromptBindingType; label: string }[] = [
  { id: "character", label: "Character" },
  { id: "prop", label: "Prop" },
  { id: "environment", label: "Environment" },
  { id: "video", label: "Video" },
  { id: "audio", label: "Audio" },
];

export function emptyTimedPromptNameBinding(
  type: TimedPromptBindingType = "character",
): TimedPromptNameBinding {
  return { binding_id: "", prompt_name: "", type, tag: "", asset_id: "", identity_id: "", reference_sheet_id: "" };
}

export function normalizeTimedPromptBindingType(raw: string | null | undefined): TimedPromptBindingType {
  const token = String(raw || "").trim().toLowerCase();
  if (token === "prop" || token === "vehicle") return "prop";
  if (token === "environment" || token === "location" || token === "place" || token === "scene") {
    return "environment";
  }
  if (token === "video" || token === "motion") return "video";
  if (token === "audio" || token === "voice") return "audio";
  return "character";
}

export function timedPromptTypeForBinding(
  binding:
    | Pick<ReferenceBindingView, "reference_type" | "media_kind" | "display_token" | "alias" | "asset_name">
    | null
    | undefined,
): TimedPromptBindingType | null {
  if (!binding) return null;
  const normalized = normalizeTimelineReference(binding);
  if (normalized.semanticType === "video") return "video";
  if (normalized.semanticType === "audio") return "audio";
  return normalized.timedPromptType;
}

export function isSceneSheetBinding(binding: ReferenceBindingView | null | undefined): boolean {
  if (!binding || !isRealBindingId(binding.id)) return false;
  return timedPromptTypeForBinding(binding) != null;
}

export function sceneSheetBindings(
  bindings: ReferenceBindingView[] | null | undefined,
  type?: TimedPromptBindingType,
): ReferenceBindingView[] {
  return (bindings || []).filter((binding) => {
    if (!isSceneSheetBinding(binding)) return false;
    if (!type) return true;
    return timedPromptTypeForBinding(binding) === type;
  });
}

export function labelCharacterBindingFromIdentity(
  binding: ReferenceBindingView,
  identityName: string | null | undefined,
): ReferenceBindingView {
  const name = String(identityName || "").trim();
  if (!name || timedPromptTypeForBinding(binding) !== "character") return binding;
  // Canonical law: Character identity is the tag. The binding alias (from
  // the Library asset tag, e.g. "Korri40YearsOld") IS the canonical tag.
  // Only fall back to the character profile name if the binding has no alias.
  // Never override a real binding alias with the profile name — that would
  // make the prompt tag differ from the Library/References tag.
  const existingAlias = sanitizeAlias(binding.alias || binding.asset_name || "");
  const alias = existingAlias || name.replace(/\s+/g, "");
  return {
    ...binding,
    alias,
    display_token: binding.display_token || `@${alias}`,
    asset_name: binding.asset_name || name,
  };
}

export function canonicalTimedPromptTag(binding: ReferenceBindingView | null | undefined): string {
  if (!binding) return "";
  const normalized = normalizeTimelineReference(binding);
  return (
    normalized.tag ||
    binding.display_token ||
    displayToken(binding.alias || binding.asset_name, binding.media_kind, binding.reference_type) ||
    ""
  );
}

export function defaultTimedPromptName(binding: ReferenceBindingView | null | undefined): string {
  if (!binding) return "";
  const named = String(binding.asset_name || "").trim();
  if (named && !/^[@#%*]/.test(named)) return named;
  const alias = stripReferencePrefix(binding.alias || binding.asset_name || "");
  return alias.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[_-]+/g, " ").trim();
}

export function dumpTimedPromptNameBinding(row: unknown): TimedPromptNameBinding {
  const rec = row && typeof row === "object" ? (row as Record<string, unknown>) : {};
  return {
    binding_id: String(rec.binding_id || rec.bindingId || "").trim(),
    prompt_name: String(rec.prompt_name || rec.promptName || "").trim(),
    type: normalizeTimedPromptBindingType(String(rec.type || "character")),
    tag: String(rec.tag || "").trim(),
    asset_id: String(rec.asset_id || rec.assetId || "").trim(),
    identity_id: String(rec.identity_id || rec.identityId || "").trim(),
    reference_sheet_id: String(rec.reference_sheet_id || rec.referenceSheetId || "").trim(),
  };
}

export function dumpTimedPromptNameBindings(rows: unknown): TimedPromptNameBinding[] {
  return Array.isArray(rows) ? rows.map(dumpTimedPromptNameBinding) : [];
}

export function bindingIdsFromNameBindings(rows: TimedPromptNameBinding[] | null | undefined): string[] {
  const ids: string[] = [];
  for (const row of rows || []) {
    const token = (row.binding_id || "").trim();
    if (token && !ids.includes(token)) ids.push(token);
  }
  return ids;
}

/** Prompt Name key only: trim + casefold. Never strip @/#/% or compare to tag/display tokens. */
export function normalizePromptNameKey(name: string): string {
  return String(name || "").trim().toLowerCase();
}

/**
 * Exact normalized Prompt Name collisions only.
 * REF TAG namespace is separate — never compare prompt_name against tag / display tokens / stripped # aliases.
 */
export function duplicatePromptNameIndex(
  rows: TimedPromptNameBinding[],
  name: string,
  exceptIndex = -1,
): number {
  const needle = normalizePromptNameKey(name);
  if (!needle) return -1;
  return rows.findIndex(
    (row, index) => index !== exceptIndex && normalizePromptNameKey(row.prompt_name) === needle,
  );
}

/** Authoritative whole-list Prompt Name validation (exact normalized collisions only). */
export function validateTimedPromptNameBindings(rows: TimedPromptNameBinding[]): string | null {
  for (let index = 0; index < rows.length; index += 1) {
    const name = rows[index]?.prompt_name || "";
    if (!normalizePromptNameKey(name)) continue;
    if (duplicatePromptNameIndex(rows, name, index) >= 0) {
      return "This Prompt Name is already used on this clip.";
    }
  }
  return null;
}

export function hydrateTimedPromptNameBindings(args: {
  nameBindings?: unknown;
  bindingIds?: string[] | null;
  bindings: ReferenceBindingView[];
}): TimedPromptNameBinding[] {
  const existing = dumpTimedPromptNameBindings(args.nameBindings);
  const byId = new Map(args.bindings.map((binding) => [binding.id, binding]));
  const seen = new Set<string>();
  const out: TimedPromptNameBinding[] = [];

  const take = (row: TimedPromptNameBinding) => {
    const binding = byId.get(row.binding_id);
    const type = timedPromptTypeForBinding(binding) || row.type || "character";
    const next: TimedPromptNameBinding = {
      binding_id: row.binding_id,
      prompt_name: row.prompt_name,
      type,
      tag: canonicalTimedPromptTag(binding) || row.tag,
      asset_id: row.asset_id || binding?.asset_id || "",
      identity_id: row.identity_id || binding?.identity_id || "",
      reference_sheet_id: row.reference_sheet_id || "",
    };
    if (binding && !next.prompt_name) next.prompt_name = defaultTimedPromptName(binding);
    if (next.binding_id) seen.add(next.binding_id);
    out.push(next);
  };

  for (const row of existing) take(row);
  for (const id of args.bindingIds || []) {
    const token = String(id || "").trim();
    if (!token || seen.has(token)) continue;
    const binding = byId.get(token);
    take({
      binding_id: token,
      prompt_name: defaultTimedPromptName(binding),
      type: timedPromptTypeForBinding(binding) || "character",
      tag: canonicalTimedPromptTag(binding),
      asset_id: binding?.asset_id || "",
      identity_id: binding?.identity_id || "",
      reference_sheet_id: "",
    });
  }
  return out;
}

export function applyTimedPromptNameBindingPatch(
  rows: TimedPromptNameBinding[],
  index: number,
  patch: Partial<TimedPromptNameBinding>,
  bindings: ReferenceBindingView[],
  options?: { validateDuplicates?: boolean },
): { rows: TimedPromptNameBinding[]; error: string | null } {
  if (index < 0 || index >= rows.length) return { rows, error: "Missing reference row." };
  const next = rows.map((row) => ({ ...row }));
  const current = { ...next[index], ...patch };
  const validateDuplicates = options?.validateDuplicates !== false;

  if (patch.type && patch.type !== rows[index].type) {
    const stillFits =
      current.binding_id &&
      timedPromptTypeForBinding(bindings.find((item) => item.id === current.binding_id) || null) ===
        patch.type;
    if (!stillFits) {
      current.binding_id = "";
      current.tag = "";
      current.asset_id = "";
      current.identity_id = "";
      current.reference_sheet_id = "";
    }
  }

  if (patch.binding_id !== undefined) {
    const token = (patch.binding_id || "").trim();
    if (token && next.some((row, i) => i !== index && row.binding_id === token)) {
      return { rows, error: "That reference is already bound on this clip." };
    }
    const binding = bindings.find((item) => item.id === token);
    if (token && binding) {
      const typed = timedPromptTypeForBinding(binding);
      if (!typed) return { rows, error: "This editor binds Character, Prop, Environment, Video, or Audio already named in References." };
      current.type = typed;
      current.tag = current.tag || canonicalTimedPromptTag(binding);
      current.asset_id = binding.asset_id || current.asset_id || "";
      current.identity_id = binding.identity_id || current.identity_id || "";
      if (!current.prompt_name.trim()) current.prompt_name = defaultTimedPromptName(binding);
    } else if (token) {
      current.tag = current.tag || "";
    } else {
      current.tag = "";
      current.asset_id = "";
      current.identity_id = "";
      current.reference_sheet_id = "";
    }
  }

  // Duplicate Prompt Name checks run on commit paths (blur / idle / OK), not mid-keystroke.
  // Exact normalized prompt_name only — never against tag / display tokens.
  if (patch.prompt_name !== undefined && validateDuplicates) {
    const dup = duplicatePromptNameIndex(next, current.prompt_name, index);
    if (dup >= 0) {
      return { rows, error: "This Prompt Name is already used on this clip." };
    }
  }

  next[index] = current;
  return { rows: next, error: null };
}

export function timedPromptBindingMissing(
  row: TimedPromptNameBinding,
  bindings: ReferenceBindingView[],
): boolean {
  if (!row.binding_id) return false;
  const binding = resolveTimelineReference(row.binding_id, bindings);
  if (!binding) return true;
  return Boolean(binding.broken);
}

export function timedPromptBindingLabel(binding: ReferenceBindingView): string {
  const tag = canonicalTimedPromptTag(binding);
  const prefix = prefixForBinding(binding.reference_type, binding.media_kind);
  return tag || `${prefix}${stripReferencePrefix(binding.alias || binding.asset_name || "Reference")}`;
}
