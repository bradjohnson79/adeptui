/**
 * usePropCreator — shared Prop Creator state/controller.
 * Express (and Standard) are views over this hook.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../../api";
import { PROFILE_NAME_ALREADY_EXISTS, isStalePropHomeOnlyEditMessage, findVisibleNameCollision } from "../../../creatorScope";
import type { CreatorDeletePreview } from "../../creators/creatorProfileDelete";
import { shouldSuspendDependentPolling } from "../../../runtime/studioApiConnection";
import { DEFAULT_GENERATOR_PLAN, type CharacterGeneratorPlan } from "../../generators/generatorPlan";
import { persistGeneratorPayload, propGenerateRequest, sourcesFromPropGenerator } from "./propGenerator";
import { propCreatorApi } from "./propCreatorApi";
import { candidateIsFinished, markStaleQueuedFailed, PROP_QUEUED_NO_HYDRATE_MS, type PropCreatorWorkspace, type PropEntity } from "./types";

export type PropCreatorVariant = "express" | "standard";

export const PROP_PROFILE_SAVED_NOTICE = "Prop profile saved";
export const PROP_SAVE_NOTICE_MS = 4500;

export function persistSaveFeedback(ok: boolean, failure?: unknown): { notice: string | null; error: string | null } {
  if (ok) return { notice: PROP_PROFILE_SAVED_NOTICE, error: null };
  const raw =
    failure instanceof Error ? failure.message : failure != null ? String(failure) : "Could not save the Prop profile.";
  // ORDER 18: BE allows Global edit from any project — drop stale home-only edit lock copy.
  if (isStalePropHomeOnlyEditMessage(raw)) return { notice: null, error: null };
  return { notice: null, error: raw };
}

function emptyPlan(): CharacterGeneratorPlan {
  return {
    ...DEFAULT_GENERATOR_PLAN,
    autoSelect: { ...DEFAULT_GENERATOR_PLAN.autoSelect },
    localFamilies: [],
    apiModels: [],
  };
}

export function usePropCreator(projectId: string) {
  const [workspace, setWorkspace] = useState<PropCreatorWorkspace | null>(null);
  const [prop, setProp] = useState<PropEntity | null>(null);
  const [name, setName] = useState("");
  const [visualStyle, setVisualStyle] = useState("live_action");
  const [description, setDescription] = useState("");
  const [plan, setPlan] = useState<CharacterGeneratorPlan>(emptyPlan);
  const [useAsIdentity, setUseAsIdentity] = useState(false);
  const [isGlobal, setIsGlobal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadTimedOut, setLoadTimedOut] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [nameCollision, setNameCollision] = useState<{ id: string; name: string } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const genStartedAtRef = useRef<number | null>(null);

  const flashNotice = useCallback((message: string, ms = PROP_SAVE_NOTICE_MS) => {
    if (noticeTimerRef.current) {
      clearTimeout(noticeTimerRef.current);
      noticeTimerRef.current = null;
    }
    setNotice(message);
    noticeTimerRef.current = setTimeout(() => {
      setNotice((current) => (current === message ? null : current));
      noticeTimerRef.current = null;
    }, ms);
  }, []);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyProp = useCallback((next: PropEntity | null) => {
    setProp(next);
    if (!next) return;
    setName(next.display_label || "");
    setVisualStyle(next.visual_style || "live_action");
    setDescription(next.description || "");
    setPlan(sourcesFromPropGenerator(next.generator));
    const refId = (next.reference_asset_id || "").trim();
    const approved = (next.approved_asset_id || "").trim();
    setUseAsIdentity(Boolean(refId && approved && refId === approved));
    setIsGlobal(Boolean(next.isGlobal || next.is_global));
  }, []);

  const startPoll = useCallback(
    (propId: string) => {
      stopPoll();
      const tick = () => {
        if (shouldSuspendDependentPolling()) return;
        void propCreatorApi
          .get(projectId, propId)
          .then((res) => {
            const elapsed = genStartedAtRef.current != null ? Date.now() - genStartedAtRef.current : 0;
            const generatingNow = (res.prop.candidates || []).some((c) => !candidateIsFinished(c));
            const candidates = markStaleQueuedFailed(
              res.prop.candidates || [],
              generatingNow,
              elapsed,
              PROP_QUEUED_NO_HYDRATE_MS,
            );
            applyProp({ ...res.prop, candidates });
            const pending = candidates.some((c) => !candidateIsFinished(c));
            if (!pending) {
              genStartedAtRef.current = null;
              stopPoll();
            }
          })
          .catch(() => undefined);
      };
      tick();
      pollRef.current = setInterval(tick, 2000);
    },
    [applyProp, projectId, stopPoll],
  );

  const refresh = useCallback(
    async (propId?: string) => {
      const data = await propCreatorApi.workspace(projectId, propId || prop?.id);
      setWorkspace(data);
      applyProp(data.selected_prop);
      // Workspace list is last-saved and does not hydrate live jobs.
      // Resume the existing GET poller so failed imagegen jobs leave Generating.
      const selected = data.selected_prop;
      if (selected && (selected.candidates || []).some((c) => !candidateIsFinished(c))) {
        startPoll(selected.id);
      } else {
        stopPoll();
      }
      return data;
    },
    [applyProp, projectId, prop?.id, startPoll, stopPoll],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadTimedOut(false);
    const timeoutId = window.setTimeout(() => setLoadTimedOut(true), 10_000);
    void refresh()
      .catch((err) => {
        if (!cancelled) {
        const message = err instanceof Error ? err.message : String(err);
        setError(isStalePropHomeOnlyEditMessage(message) ? null : message);
      }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
      stopPoll();
      if (noticeTimerRef.current) {
        clearTimeout(noticeTimerRef.current);
        noticeTimerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const persist = useCallback(
    async (opts?: { useAsIdentity?: boolean }) => {
      setError(null);
      setNameCollision(null);
      const localHit = findVisibleNameCollision(workspace?.props || [], name, prop?.id || "");
      if (localHit) {
        const existingName = localHit.display_label || localHit.tag || name;
        setNameCollision({ id: localHit.id, name: existingName });
        const message = `${existingName} already exists in this project.`;
        setError(message);
        throw new Error(message);
      }
      try {
        const refId = (prop?.reference_asset_id || "").trim();
        const identity = Boolean(opts?.useAsIdentity && refId);
        const res = await propCreatorApi.upsert(projectId, {
          prop_id: prop?.id,
          name,
          visual_style: visualStyle,
          description,
          is_global: isGlobal,
          isGlobal,
          generator: persistGeneratorPayload(plan),
          ...(identity
            ? {
                use_as_identity: true,
                identity_asset_id: refId,
              }
            : {}),
        });
        // CDX-016: upsert(use_as_identity + identity_asset_id) performs the
        // identity point atomically server-side; the separate useAsIdentity
        // call was redundant.
        const next = res.prop;
        applyProp(next);
        await refresh(next.id);
        return next;
      } catch (err) {
        if (noticeTimerRef.current) {
          clearTimeout(noticeTimerRef.current);
          noticeTimerRef.current = null;
        }
        if (err instanceof ApiError && err.code === PROFILE_NAME_ALREADY_EXISTS) {
          const existingId = String(err.details?.existingId || "");
          const existingName = String(err.details?.existingName || name);
          if (existingId) setNameCollision({ id: existingId, name: existingName });
        }
        const fb = persistSaveFeedback(false, err);
        setNotice(fb.notice);
        setError(fb.error);
        throw err;
      }
    },
    [applyProp, description, isGlobal, name, plan, projectId, prop?.id, prop?.reference_asset_id, refresh, visualStyle, workspace?.props],
  );

  const save = useCallback(async () => {
    const next = await persist({ useAsIdentity });
    const fb = persistSaveFeedback(true);
    if (fb.notice) flashNotice(fb.notice);
    return next;
  }, [flashNotice, persist, useAsIdentity]);

  const newProp = useCallback(() => {
    stopPoll();
    setProp(null);
    setName("");
    setVisualStyle("live_action");
    setDescription("");
    setPlan(emptyPlan());
    setUseAsIdentity(false);
    setIsGlobal(false);
    setNotice("New Prop. Name it, then Save.");
    setError(null);
    setUploadError(null);
    setNameCollision(null);
  }, [stopPoll]);

  const selectProp = useCallback(
    async (propId: string) => {
      setLoading(true);
      try {
        await refresh(propId);
      } finally {
        setLoading(false);
      }
    },
    [refresh],
  );

  const generate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const current = await persist();
      const res = await propCreatorApi.generate(projectId, current.id, propGenerateRequest(plan));
      applyProp(res.prop);
      genStartedAtRef.current = Date.now();
      startPoll(res.prop.id);
      setNotice("Generating prop looks.");
    } catch (err) {
      {
        const message = err instanceof Error ? err.message : String(err);
        setError(isStalePropHomeOnlyEditMessage(message) ? null : message);
      }
    } finally {
      setBusy(false);
    }
  }, [applyProp, persist, plan, projectId, startPoll]);

  const approve = useCallback(
    async (candidateId: string) => {
      if (!prop) return;
      setBusy(true);
      setError(null);
      try {
        const res = await propCreatorApi.approve(projectId, prop.id, candidateId);
        applyProp(res.prop);
        setNotice("This look is now the Prop identity.");
        await refresh(res.prop.id);
      } catch (err) {
        {
        const message = err instanceof Error ? err.message : String(err);
        setError(isStalePropHomeOnlyEditMessage(message) ? null : message);
      }
      } finally {
        setBusy(false);
      }
    },
    [applyProp, projectId, prop, refresh],
  );

  const uploadLook = useCallback(
    async (file: File) => {
      setBusy(true);
      setUploadError(null);
      setError(null);
      try {
        const current = name.trim() ? await persist() : prop;
        if (!current) {
          setUploadError("Name the Prop first, then upload a view.");
          return;
        }
        const res = await propCreatorApi.uploadView(projectId, current.id, file);
        applyProp(res.prop);
        setNotice("Uploaded look saved to Library. Approve it to make it the current Prop view.");
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed.";
        setUploadError(message);
        setError(message);
      } finally {
        setBusy(false);
      }
    },
    [applyProp, name, persist, projectId, prop],
  );

  const retry = useCallback(
    async (candidateId: string) => {
      if (!prop) return;
      setBusy(true);
      try {
        const res = await propCreatorApi.retry(projectId, prop.id, candidateId);
        applyProp(res.prop);
        startPoll(res.prop.id);
      } catch (err) {
        {
        const message = err instanceof Error ? err.message : String(err);
        setError(isStalePropHomeOnlyEditMessage(message) ? null : message);
      }
      } finally {
        setBusy(false);
      }
    },
    [applyProp, projectId, prop, startPoll],
  );

  const setReference = useCallback(
    async (assetId: string | null) => {
      const current = name.trim() ? await persist() : prop;
      if (!current) {
        setError("Save the Prop name first.");
        return;
      }
      const res = await propCreatorApi.upsert(projectId, {
        prop_id: current.id,
        name: current.display_label,
        visual_style: visualStyle,
        description,
        is_global: isGlobal,
        isGlobal,
        reference_asset_id: assetId,
        clear_reference: !assetId,
      });
      applyProp(res.prop);
      if (!assetId) setUseAsIdentity(false);
    },
    [applyProp, description, isGlobal, name, persist, projectId, prop, visualStyle],
  );

  const remove = useCallback(async (opts?: { confirmCrossProject?: boolean }): Promise<boolean> => {
    if (!prop) return false;
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      await propCreatorApi.delete(projectId, prop.id, opts?.confirmCrossProject ?? false);
      setNotice(prop.isGlobal || prop.is_global ? "Global Prop deleted" : "Prop deleted");
      newProp();
      await refresh();
      return true;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return false;
    } finally {
      setBusy(false);
    }
  }, [newProp, projectId, prop, refresh]);

  const getDeletePreview = useCallback(async (): Promise<CreatorDeletePreview | null> => {
    if (!prop) return null;
    return propCreatorApi.deletePreview(projectId, prop.id);
  }, [projectId, prop]);

  const reset = useCallback(() => {
    if (prop) applyProp(prop);
    else newProp();
    setError(null);
    setNotice("Unsaved changes cleared.");
  }, [applyProp, newProp, prop]);

  const generating = (prop?.candidates || []).some((c) => !candidateIsFinished(c));


  const composeReferenceSheet = useCallback(async () => {
    if (!prop?.id) return null;
    setBusy(true);
    setError(null);
    try {
      const res = await propCreatorApi.composeReferenceSheet(projectId, prop.id);
      if (res?.prop) {
        applyProp(res.prop);
        await refresh(res.prop.id);
      } else {
        await refresh();
      }
      setNotice("Prop Reference Sheet ready. Original still unchanged.");
      return res;
    } catch (err) {
      {
        const message = err instanceof Error ? err.message : String(err);
        setError(isStalePropHomeOnlyEditMessage(message) ? null : message);
      }
      return null;
    } finally {
      setBusy(false);
    }
  }, [applyProp, projectId, prop?.id, refresh]);

  return {
    projectId,
    workspace,
    prop,
    name,
    setName,
    visualStyle,
    setVisualStyle,
    description,
    setDescription,
    plan,
    setPlan,
    useAsIdentity,
    setUseAsIdentity,
    isGlobal,
    setIsGlobal,
    loading,
    loadTimedOut,
    busy,
    error,
    notice,
    generating,
    apiAvailable: Boolean(workspace?.api_generation_available),
    refresh,
    persist,
    save,
    generate,
    uploadLook,
    uploadError,
    nameCollision,
    approve,
    composeReferenceSheet,
    retry,
    setReference,
    selectProp,
    newProp,
    remove,
    getDeletePreview,
    reset,
  };
}
