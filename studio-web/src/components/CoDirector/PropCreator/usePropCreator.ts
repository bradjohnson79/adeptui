/**
 * usePropCreator — shared Prop Creator state/controller.
 * Express (and Standard) are views over this hook.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_GENERATOR_PLAN, type CharacterGeneratorPlan } from "../../generators/generatorPlan";
import { persistGeneratorPayload, propGenerateRequest, sourcesFromPropGenerator } from "./propGenerator";
import { propCreatorApi } from "./propCreatorApi";
import { candidateIsFinished, type PropCreatorWorkspace, type PropEntity } from "./types";

export type PropCreatorVariant = "express" | "standard";

export const PROP_PROFILE_SAVED_NOTICE = "Prop profile saved";
export const PROP_SAVE_NOTICE_MS = 4500;

export function persistSaveFeedback(ok: boolean, failure?: unknown): { notice: string | null; error: string | null } {
  if (ok) return { notice: PROP_PROFILE_SAVED_NOTICE, error: null };
  return {
    notice: null,
    error: failure instanceof Error ? failure.message : failure != null ? String(failure) : "Could not save the Prop profile.",
  };
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
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    setDescription(next.description || next.notes || "");
    setPlan(sourcesFromPropGenerator(next.generator));
    const refId = (next.reference_asset_id || "").trim();
    const approved = (next.approved_asset_id || "").trim();
    setUseAsIdentity(Boolean(refId && approved && refId === approved));
  }, []);

  const startPoll = useCallback(
    (propId: string) => {
      stopPoll();
      const tick = () => {
        void propCreatorApi
          .get(projectId, propId)
          .then((res) => {
            applyProp(res.prop);
            // GET hydrates live job status (including failed + job.message).
            const pending = (res.prop.candidates || []).some((c) => !candidateIsFinished(c));
            if (!pending) stopPoll();
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
    void refresh()
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
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
      try {
        const refId = (prop?.reference_asset_id || "").trim();
        const identity = Boolean(opts?.useAsIdentity && refId);
        const res = await propCreatorApi.upsert(projectId, {
          prop_id: prop?.id,
          name,
          visual_style: visualStyle,
          description,
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
        const fb = persistSaveFeedback(false, err);
        setNotice(fb.notice);
        setError(fb.error);
        throw err;
      }
    },
    [applyProp, description, name, plan, projectId, prop?.id, prop?.reference_asset_id, refresh, visualStyle],
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
    setNotice("New Prop. Name it, then Save.");
    setError(null);
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
      startPoll(res.prop.id);
      setNotice("Generating prop looks.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
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
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [applyProp, projectId, prop, refresh],
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
        setError(err instanceof Error ? err.message : String(err));
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
        reference_asset_id: assetId,
        clear_reference: !assetId,
      });
      applyProp(res.prop);
      if (!assetId) setUseAsIdentity(false);
    },
    [applyProp, description, name, persist, projectId, prop, visualStyle],
  );

  const remove = useCallback(async (confirmMessage?: string) => {
    if (!prop) return;
    const message =
      confirmMessage ||
      "Remove this Prop profile? If it is on the Spatial Map, those placements will be unlinked. Library images stay in the project.";
    if (!window.confirm(message)) return;
    setBusy(true);
    try {
      await propCreatorApi.delete(projectId, prop.id);
      setNotice("Prop profile removed. Library images were kept.");
      newProp();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [newProp, projectId, prop, refresh]);

  const reset = useCallback(() => {
    if (prop) applyProp(prop);
    else newProp();
    setError(null);
    setNotice("Unsaved changes cleared.");
  }, [applyProp, newProp, prop]);

  const generating = (prop?.candidates || []).some((c) => !candidateIsFinished(c));

  return {
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
    loading,
    busy,
    error,
    notice,
    generating,
    apiAvailable: Boolean(workspace?.api_generation_available),
    refresh,
    persist,
    save,
    generate,
    approve,
    retry,
    setReference,
    selectProp,
    newProp,
    remove,
    reset,
  };
}
