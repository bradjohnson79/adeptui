/**
 * useCharacterProfile — shared load/save/patch/reset/delete hook wrapping the
 * character_identity REST API. Consolidates the debounced-save logic that was
 * previously duplicated in CharacterCompactView.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { CharacterProfile, CharacterReference } from "./types";

export function getHeroIdentity(refs: CharacterReference[]): CharacterReference | undefined {
  return (
    refs.find(
      (r) =>
        (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") &&
        r.canonical &&
        r.approval_status === "approved",
    ) ||
    refs.find(
      (r) =>
        (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") && r.canonical,
    ) ||
    refs.find(
      (r) =>
        (r.reference_role === "hero_identity" || r.reference_role === "hero_portrait") &&
        r.approval_status === "approved",
    ) ||
    refs.find((r) => r.reference_role === "hero_identity" || r.reference_role === "hero_portrait")
  );
}

export function getReferenceImage(refs: CharacterReference[]): CharacterReference | undefined {
  return refs.find((r) => r.reference_role === "reference_image" && r.asset_id);
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
  const pendingRef = useRef<Record<string, unknown> | null>(null);
  const idRef = useRef<string | null>(characterId);
  idRef.current = characterId;

  const refresh = useCallback(async () => {
    const cid = idRef.current;
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
      setProfile(p as CharacterProfile);
      setReferences(((refs as { items?: CharacterReference[] }).items || []) as CharacterReference[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load character.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const flushPending = useCallback(async () => {
    const cid = idRef.current;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!projectId || !cid || !pending) return;
    await api.patchCharacterProfile(projectId, cid, pending);
    setSavedAt(new Date().toISOString());
  }, [projectId]);

  const patchDebounced = useCallback(
    (fields: Record<string, unknown>) => {
      const cid = idRef.current;
      if (!projectId || !cid) return;
      setProfile((prev) => (prev ? ({ ...prev, ...fields } as CharacterProfile) : prev));
      pendingRef.current = { ...(pendingRef.current || {}), ...fields };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        void flushPending().catch(() => undefined);
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
        if (fields) {
          pendingRef.current = { ...(pendingRef.current || {}), ...fields };
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
