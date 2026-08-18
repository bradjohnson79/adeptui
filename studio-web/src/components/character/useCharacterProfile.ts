/**
 * useCharacterProfile — shared load/save/patch/reset/delete hook wrapping the
 * character_identity REST API. Consolidates the debounced-save logic that was
 * previously duplicated in CharacterCompactView.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
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
  /** Save immediately (flush pending + write). */
  save: (fields?: Record<string, unknown>) => Promise<boolean>;
  reset: () => void;
  remove: () => Promise<boolean>;
  refresh: () => Promise<void>;
  setLocal: (fields: Record<string, unknown>) => void;
};

export function useCharacterProfile(
  projectId: string,
  characterId: string | null,
): UseCharacterProfileResult {
  const [profile, setProfile] = useState<CharacterProfile | null>(null);
  const [references, setReferences] = useState<CharacterReference[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef<PendingCharacterPatch | null>(null);
  const loadGenRef = useRef(0);
  const idRef = useRef<string | null>(characterId);
  idRef.current = characterId;

  const refresh = useCallback(async () => {
    const cid = idRef.current;
    const gen = ++loadGenRef.current;
    if (!projectId || !cid) {
      setProfile(null);
      setReferences([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [p, refs] = await Promise.all([
        api.getCharacterProfile(projectId, cid),
        api.listCharacterReferences(projectId, cid).catch(() => ({ items: [] as CharacterReference[] })),
      ]);
      if (gen !== loadGenRef.current) return;
      const applied = applyLoadedCharacterState({
        requestedCharacterId: cid,
        currentCharacterId: idRef.current,
        profile: p as CharacterProfile,
        references: (refs as { items?: CharacterReference[] }).items,
      });
      if (applied === "stale") return;
      setProfile(applied.profile);
      setReferences(applied.references);
    } catch (e) {
      if (gen !== loadGenRef.current) return;
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
    setProfile(null);
    setReferences([]);
    void refresh();
  }, [refresh]);

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
        setProfile(p);
        setSavedAt(new Date().toISOString());
        return p.id;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create character.");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [projectId],
  );

  const save = useCallback(
    async (fields?: Record<string, unknown>): Promise<boolean> => {
      const cid = idRef.current;
      if (!projectId || !cid) return false;
      setSaving(true);
      setError("");
      try {
        if (fields && cid) {
          const prevFields = pendingPatchForCurrentCharacter(pendingRef.current, cid) || {};
          pendingRef.current = { characterId: cid, fields: { ...prevFields, ...fields } };
        }
        await flushPending();
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to save character.");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [projectId, flushPending],
  );

  const reset = useCallback(() => {
    pendingRef.current = null;
    if (timerRef.current) clearTimeout(timerRef.current);
    void refresh();
  }, [refresh]);

  const remove = useCallback(async (): Promise<boolean> => {
    const cid = idRef.current;
    if (!projectId || !cid) return false;
    setSaving(true);
    setError("");
    try {
      await api.deleteCharacterProfile(projectId, cid);
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
    setProfile((prev) => (prev ? ({ ...prev, ...fields } as CharacterProfile) : prev));
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
