/**
 * useCharacterProfile — shared load/save/patch/reset/delete hook wrapping the
 * character_identity REST API. Consolidates the debounced-save logic that was
 * previously duplicated in CharacterCompactView.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../../api";
import { PROFILE_NAME_ALREADY_EXISTS, characterOwnedByProject } from "../../creatorScope";
import type { CharacterProfile, CharacterReference } from "./types";

/**
 * Resolve the character's hero identity (CDX-004). "Selected" truth is
 * canonical + approved only. Auto-attached generation drafts
 * (canonical=false, approval_status=draft) must NOT surface as the hero, so
 * no fallback chain picks an unapproved row.
 */
export function getHeroIdentity(refs: CharacterReference[]): CharacterReference | undefined {
  return refs.find(
    (r) =>
      (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") &&
      r.canonical === true &&
      r.approval_status === "approved",
  );
}

/**
 * Hero reference attached but NOT yet canonical+approved (pending owner
 * review). Used to label the draft candidate "Pending review" instead of
 * "Selected" before approval (CDX-004).
 */
export function getPendingHeroIdentity(refs: CharacterReference[]): CharacterReference | undefined {
  return refs.find(
    (r) =>
      (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") &&
      !(r.canonical === true && r.approval_status === "approved"),
  );
}

export function getReferenceImage(refs: CharacterReference[]): CharacterReference | undefined {
  return refs.find((r) => r.reference_role === "reference_image" && r.asset_id);
}

/** Form fields that must fully replace on load so empty legacy values do not keep the previous character. */
const CHARACTER_FORM_STRING_KEYS = [
  "name",
  "role",
  "description",
  "visual_description",
  "visual_style",
  "gender_presentation",
  "apparent_age",
  "species_or_type",
  "body_type",
  "height_description",
] as const;

export type PendingCharacterPatch = {
  characterId: string;
  fields: Record<string, unknown>;
};

/**
 * Instant saved-character dropdown refresh (Character Creator Express + Standard).
 *
 * When a profile is saved (create POST or rename PATCH), the hook dispatches
 * this window event carrying the canonical saved profile. Every mounted
 * saved-character dropdown listens and upserts in place — no refetch, no
 * remount, no stale "New Character" label after a rename. The event also
 * covers cross-surface updates when the Co-Director overlay and the
 * standalone Character Creator are mounted at the same time.
 */
export const CHARACTER_PROFILE_SAVED_EVENT = "adept:character-profile-saved";

export type CharacterProfileSavedDetail = {
  projectId: string;
  profile: CharacterProfile;
};

export function notifyCharacterProfileSaved(projectId: string, profile: CharacterProfile): void {
  try {
    window.dispatchEvent(
      new CustomEvent<CharacterProfileSavedDetail>(CHARACTER_PROFILE_SAVED_EVENT, {
        detail: { projectId, profile },
      }),
    );
  } catch {
    /* non-DOM environment (tests) — listeners simply never fire */
  }
}

/**
 * Upsert a saved profile into a dropdown list by id. Renames update the label
 * in place (position preserved); a brand-new profile is appended. Never
 * duplicates an id.
 */
export function upsertCharacterSummary<T extends { id: string }>(list: T[], saved: T): T[] {
  const idx = list.findIndex((c) => c.id === saved.id);
  if (idx === -1) return [...list, saved];
  const next = list.slice();
  next[idx] = { ...next[idx], ...saved };
  return next;
}

/** Full replace: null/undefined form strings become "" so Load Character cannot leak the previous profile. */
export function replaceCharacterProfile(raw: CharacterProfile | null | undefined): CharacterProfile | null {
  if (!raw) return null;
  const next: CharacterProfile = { ...raw };
  for (const key of CHARACTER_FORM_STRING_KEYS) {
    if (next[key] == null) next[key] = "";
  }
  return next;
}

export function pendingPatchForCurrentCharacter(
  pending: PendingCharacterPatch | null,
  currentCharacterId: string | null,
): Record<string, unknown> | null {
  if (!pending || !currentCharacterId || pending.characterId !== currentCharacterId) return null;
  return pending.fields;
}

/** True when this load started before a newer load or an explicit save. */
export function characterLoadIsStale(loadGeneration: number, currentGeneration: number): boolean {
  return loadGeneration !== currentGeneration;
}

/**
 * Local-only selection for a character that has not been created yet.
 * It is never sent to the API. The first Save POSTs the visible form.
 */
export const DRAFT_CHARACTER_ID = "__draft_character__";

const PLACEHOLDER_CHARACTER_NAME = /^(?:new character|untitled character)$/i;

export function isUnsavedCharacterId(id: string | null | undefined): boolean {
  const value = String(id || "").trim();
  return !value || value === DRAFT_CHARACTER_ID;
}

/** Server id for load/save. A draft selection has no row yet. */
export function serverCharacterId(id: string | null | undefined): string | null {
  const value = String(id || "").trim();
  if (!value || value === DRAFT_CHARACTER_ID) return null;
  return value;
}

export function isPlaceholderCharacterName(name: string | null | undefined): boolean {
  return PLACEHOLDER_CHARACTER_NAME.test(String(name || "").trim());
}

/** Fields the Character Profile form owns. A reference reload must not replace these while they are unsaved. */
export function characterProfileFingerprint(
  profile: Partial<CharacterProfile> | null | undefined,
): string {
  return JSON.stringify({
    name: String(profile?.name ?? ""),
    gender_presentation: String(profile?.gender_presentation ?? ""),
    visual_style: String(profile?.visual_style ?? ""),
    description: String(profile?.description ?? ""),
    is_global: Boolean(profile?.is_global || profile?.isGlobal),
  });
}

/**
 * Apply a server profile without letting a placeholder row replace unsaved form fields.
 * Reset passes force=true and takes the server row.
 */
export function profileAfterServerLoad(args: {
  local: CharacterProfile | null;
  loaded: CharacterProfile | null;
  committedFingerprint: string;
  force: boolean;
}): CharacterProfile | null {
  if (args.force || !args.local) return args.loaded;
  if (characterProfileFingerprint(args.local) !== args.committedFingerprint) return args.local;
  return args.loaded;
}

export function applyLoadedCharacterState(args: {
  requestedCharacterId: string;
  currentCharacterId: string | null;
  profile: CharacterProfile | null | undefined;
  references: CharacterReference[] | undefined;
}): { profile: CharacterProfile | null; references: CharacterReference[] } | "stale" {
  if (!args.currentCharacterId || args.currentCharacterId !== args.requestedCharacterId) return "stale";
  return {
    profile: replaceCharacterProfile(args.profile ?? null),
    references: Array.isArray(args.references) ? args.references : [],
  };
}

const SAVE_FIELD_KEYS = [
  "name",
  "gender_presentation",
  "visual_style",
  "description",
  "is_global",
  "isGlobal",
] as const;

export type CharacterSaveIntent =
  | { ok: false; error: string }
  | { ok: true; method: "POST"; name: string; extra: Record<string, unknown> }
  | { ok: true; method: "PATCH"; characterId: string; fields: Record<string, unknown> };

function definedFields(raw: Record<string, unknown> | null | undefined): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!raw) return out;
  for (const [key, value] of Object.entries(raw)) {
    if (value !== undefined) out[key] = value;
  }
  return out;
}

/** Decide POST vs PATCH vs visible error. Save never silently no-ops or fake-succeeds. */
export function characterSaveIntent(args: {
  projectId: string;
  characterId: string | null;
  fields?: Record<string, unknown>;
  pending?: PendingCharacterPatch | null;
  profile?: CharacterProfile | null;
}): CharacterSaveIntent {
  if (!args.projectId.trim()) {
    return { ok: false, error: "This project is missing, so the character cannot be saved." };
  }
  const cid = serverCharacterId(args.characterId) || "";
  const pending = pendingPatchForCurrentCharacter(args.pending || null, cid || null);
  const merged = {
    ...definedFields(pending),
    ...definedFields(args.fields),
  };
  if (args.profile) {
    for (const key of SAVE_FIELD_KEYS) {
      if (merged[key] === undefined && args.profile[key] != null) {
        merged[key] = args.profile[key];
      }
    }
  }
  const storedName = String(args.profile?.name ?? "").trim();
  let name = String(merged.name ?? storedName).trim();
  // A placeholder already stored on the row must not replace the name in the form.
  if (name && !isPlaceholderCharacterName(name)) {
    merged.name = name;
  } else if (
    cid &&
    storedName &&
    name &&
    isPlaceholderCharacterName(name) &&
    !isPlaceholderCharacterName(storedName)
  ) {
    name = storedName;
    merged.name = storedName;
  }
  if (cid && args.profile && !characterOwnedByProject(args.profile, args.projectId)) {
    return {
      ok: false,
      error: "Global characters can only be edited from the project that created them.",
    };
  }
  if (!cid) {
    if (!name) {
      return { ok: false, error: "Give the character a name, then Save Character." };
    }
    const extra = { ...merged };
    delete extra.name;
    return { ok: true, method: "POST", name, extra };
  }
  if (!Object.keys(merged).length) {
    if (!name) {
      return { ok: false, error: "Nothing to save yet. Add a name or profile, then Save Character." };
    }
    merged.name = name;
  }
  return { ok: true, method: "PATCH", characterId: cid, fields: merged };
}

export type UseCharacterProfileResult = {
  profile: CharacterProfile | null;
  references: CharacterReference[];
  loading: boolean;
  saving: boolean;
  error: string;
  savedAt: string | null;
  /** Create a new profile (name-only is valid). Returns the new id. */
  create: (name: string, extra?: Record<string, unknown>) => Promise<string | null>;
  /** Patch a subset of fields, debounced (for live editing). */
  patchDebounced: (fields: Record<string, unknown>) => void;
  /**
   * Save immediately (flush pending + write). Returns the canonical saved
   * profile (created on POST, updated on PATCH) so callers can refresh
   * saved-character dropdowns instantly; null on failure.
   */
  save: (fields?: Record<string, unknown>) => Promise<CharacterProfile | null>;
  reset: () => void;
  remove: (opts?: { confirmCrossProject?: boolean }) => Promise<boolean>;
  refresh: () => Promise<void>;
  setLocal: (fields: Record<string, unknown>) => void;
};

export function useCharacterProfile(
  projectId: string,
  characterId: string | null,
): UseCharacterProfileResult {
  const [profile, setProfile] = useState<CharacterProfile | null>(() =>
    characterId === DRAFT_CHARACTER_ID ? { id: "", name: "" } : null,
  );
  const [references, setReferences] = useState<CharacterReference[]>([]);
  const [loading, setLoading] = useState(() => Boolean(serverCharacterId(characterId)));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<PendingCharacterPatch | null>(null);
  const loadGenRef = useRef(0);
  const forceProfileRef = useRef(false);
  const committedFingerprintRef = useRef(
    characterId === DRAFT_CHARACTER_ID ? characterProfileFingerprint({ id: "", name: "" }) : "",
  );
  const idRef = useRef<string | null>(serverCharacterId(characterId));
  const draftSeededRef = useRef(false);
  idRef.current = serverCharacterId(characterId);

  const refresh = useCallback(async () => {
    const cid = idRef.current;
    const gen = ++loadGenRef.current;
    if (!projectId || !cid) {
      if (forceProfileRef.current && characterId === DRAFT_CHARACTER_ID) {
        const blank = { id: "", name: "" } as CharacterProfile;
        committedFingerprintRef.current = characterProfileFingerprint(blank);
        setProfile(blank);
        setReferences([]);
      }
      forceProfileRef.current = false;
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    const force = forceProfileRef.current;
    forceProfileRef.current = false;
    try {
      const [p, refs] = await Promise.all([
        api.getCharacterProfile(projectId, cid),
        api.listCharacterReferences(projectId, cid).catch(() => ({ items: [] as CharacterReference[] })),
      ]);
      if (characterLoadIsStale(gen, loadGenRef.current)) return;
      const applied = applyLoadedCharacterState({
        requestedCharacterId: cid,
        currentCharacterId: idRef.current,
        profile: p as CharacterProfile,
        references: (refs as { items?: CharacterReference[] }).items,
      });
      if (applied === "stale") return;
      setReferences(applied.references);
      setProfile((prev) => {
        const next = profileAfterServerLoad({
          local: prev,
          loaded: applied.profile,
          committedFingerprint: committedFingerprintRef.current,
          force,
        });
        if (next === applied.profile) {
          committedFingerprintRef.current = characterProfileFingerprint(applied.profile);
        }
        return next;
      });
    } catch (e) {
      if (characterLoadIsStale(gen, loadGenRef.current)) return;
      setError(e instanceof Error ? e.message : "Failed to load character.");
    } finally {
      if (gen === loadGenRef.current) setLoading(false);
    }
  }, [projectId, characterId]);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    pendingRef.current = null;
    if (characterId === DRAFT_CHARACTER_ID) {
      if (!draftSeededRef.current) {
        draftSeededRef.current = true;
        const blank = { id: "", name: "" } as CharacterProfile;
        committedFingerprintRef.current = characterProfileFingerprint(blank);
        setProfile(blank);
        setReferences([]);
      }
      setLoading(false);
      setError("");
      return;
    }
    draftSeededRef.current = false;
    if (!serverCharacterId(characterId)) {
      setProfile(null);
      setReferences([]);
      setLoading(false);
      return;
    }
    committedFingerprintRef.current = "";
    setProfile(null);
    setReferences([]);
    void refresh();
  }, [refresh, characterId]);

  const flushPending = useCallback(async () => {
    const cid = idRef.current;
    const fields = pendingPatchForCurrentCharacter(pendingRef.current, cid);
    if (timerRef.current) clearTimeout(timerRef.current);
    pendingRef.current = null;
    if (!projectId || !cid || !fields) return;
    await api.patchCharacterProfile(projectId, cid, fields);
    setSavedAt(new Date().toISOString());
  }, [projectId]);

  const patchDebounced = useCallback(
    (fields: Record<string, unknown>) => {
      const cid = idRef.current;
      if (!projectId || !cid) return;
      setProfile((prev) => (prev ? ({ ...prev, ...fields } as CharacterProfile) : prev));
      const prevFields = pendingPatchForCurrentCharacter(pendingRef.current, cid) || {};
      pendingRef.current = { characterId: cid, fields: { ...prevFields, ...fields } };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        void flushPending().catch((e) => {
          setError(e instanceof Error ? e.message : "Failed to save character.");
        });
      }, 700);
    },
    [projectId, flushPending],
  );

  const create = useCallback(
    async (name: string, extra?: Record<string, unknown>): Promise<string | null> => {
      if (!projectId) return null;
      setSaving(true);
      setError("");
      try {
        const created = await api.createCharacterProfile(projectId, { name: name.trim(), ...(extra || {}) });
        const p = created as CharacterProfile;
        idRef.current = p.id;
        committedFingerprintRef.current = characterProfileFingerprint(p);
        setProfile(p);
        pendingRef.current = null;
        if (timerRef.current) clearTimeout(timerRef.current);
        setSavedAt(new Date().toISOString());
        notifyCharacterProfileSaved(projectId, p);
        return p.id;
      } catch (e) {
        const message =
          e instanceof ApiError && e.code === PROFILE_NAME_ALREADY_EXISTS
            ? e.message
            : e instanceof Error
              ? e.message
              : "Failed to create character.";
        setError(message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [projectId],
  );

  const save = useCallback(
    async (fields?: Record<string, unknown>): Promise<CharacterProfile | null> => {
      const intent = characterSaveIntent({
        projectId,
        characterId: idRef.current,
        fields,
        pending: pendingRef.current,
        profile,
      });
      if (!intent.ok) {
        setError(intent.error);
        return null;
      }
      setSaving(true);
      setError("");
      // Drop a profile GET that started before this save. That response is the
      // pre-save row and would wipe the details the creator just wrote.
      loadGenRef.current += 1;
      try {
        if (intent.method === "POST") {
          const created = await api.createCharacterProfile(projectId, {
            name: intent.name,
            ...intent.extra,
          });
          const p = created as CharacterProfile;
          idRef.current = p.id;
          committedFingerprintRef.current = characterProfileFingerprint(p);
          setProfile(p);
          pendingRef.current = null;
          if (timerRef.current) clearTimeout(timerRef.current);
          setSavedAt(new Date().toISOString());
          notifyCharacterProfileSaved(projectId, p);
          return p;
        }
        if (timerRef.current) clearTimeout(timerRef.current);
        pendingRef.current = null;
        const updated = (await api.patchCharacterProfile(
          projectId,
          intent.characterId,
          intent.fields,
        )) as CharacterProfile | null;
        // Canonical saved profile for dropdown refresh: prefer the backend
        // response, fall back to the local merge so id + name are always present.
        const savedProfile = {
          ...(profile || {}),
          ...(updated || {}),
          id: (updated as CharacterProfile | null)?.id || intent.characterId,
        } as CharacterProfile;
        committedFingerprintRef.current = characterProfileFingerprint(savedProfile);
        setProfile(savedProfile);
        setSavedAt(new Date().toISOString());
        notifyCharacterProfileSaved(projectId, savedProfile);
        return savedProfile;
      } catch (e) {
        const message =
          e instanceof ApiError && e.code === PROFILE_NAME_ALREADY_EXISTS
            ? e.message
            : e instanceof Error
              ? e.message
              : "Failed to save character.";
        setError(message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [projectId, profile],
  );

  const reset = useCallback(() => {
    pendingRef.current = null;
    if (timerRef.current) clearTimeout(timerRef.current);
    forceProfileRef.current = true;
    if (isUnsavedCharacterId(characterId)) {
      const blank = { id: "", name: "" } as CharacterProfile;
      committedFingerprintRef.current = characterProfileFingerprint(blank);
      setProfile(characterId === DRAFT_CHARACTER_ID ? blank : null);
      setReferences([]);
      forceProfileRef.current = false;
      return;
    }
    void refresh();
  }, [characterId, refresh]);

  const remove = useCallback(async (opts?: { confirmCrossProject?: boolean }): Promise<boolean> => {
    const cid = idRef.current;
    if (!projectId || !cid) return false;
    setSaving(true);
    setError("");
    try {
      await api.deleteCharacterProfile(projectId, cid, opts?.confirmCrossProject ?? false);
      setProfile(null);
      setReferences([]);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete character.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  const setLocal = useCallback((fields: Record<string, unknown>) => {
    setProfile((prev) => ({ ...(prev || { id: "", name: "" }), ...fields } as CharacterProfile));
  }, []);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  return {
    profile,
    references,
    loading,
    saving,
    error,
    savedAt,
    create,
    patchDebounced,
    save,
    reset,
    remove,
    refresh,
    setLocal,
  };
}
