/**
 * usePropCreator — shared Prop Creator state/controller.
 * Express (and a future Standard) are views over this hook.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { propCreatorApi } from "./propCreatorApi";
import type { PropCreatorWorkspace, PropEntity } from "./types";

export type PropCreatorVariant = "express" | "standard";

export function usePropCreator(projectId: string) {
  const [workspace, setWorkspace] = useState<PropCreatorWorkspace | null>(null);
  const [prop, setProp] = useState<PropEntity | null>(null);
  const [name, setName] = useState("");
  const [visualStyle, setVisualStyle] = useState("live_action");
  const [description, setDescription] = useState("");
  const [localEnabled, setLocalEnabled] = useState(true);
  const [localFamily, setLocalFamily] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    setLocalEnabled(next.generator?.local_enabled !== false);
    setLocalFamily(next.generator?.local_family || "");
  }, []);

  const refresh = useCallback(
    async (propId?: string) => {
      const data = await propCreatorApi.workspace(projectId, propId || prop?.id);
      setWorkspace(data);
      applyProp(data.selected_prop);
      return data;
    },
    [applyProp, projectId, prop?.id],
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
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const startPoll = useCallback(
    (propId: string) => {
      stopPoll();
      pollRef.current = setInterval(() => {
        void propCreatorApi
          .get(projectId, propId)
          .then((res) => {
            applyProp(res.prop);
            const pending = (res.prop.candidates || []).some((c) => c.status === "queued" || c.status === "generating");
            if (!pending) stopPoll();
          })
          .catch(() => undefined);
      }, 2000);
    },
    [applyProp, projectId, stopPoll],
  );

  const persist = useCallback(async () => {
    setError(null);
    try {
      const res = await propCreatorApi.upsert(projectId, {
        prop_id: prop?.id,
        name,
        visual_style: visualStyle,
        description,
        generator: { local_enabled: localEnabled, api_enabled: false, local_family: localFamily },
      });
      applyProp(res.prop);
      await refresh(res.prop.id);
      setNotice("Saved.");
      return res.prop;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      throw err;
    }
  }, [applyProp, description, localEnabled, localFamily, name, projectId, prop?.id, refresh, visualStyle]);

  const newProp = useCallback(() => {
    stopPoll();
    setProp(null);
    setName("");
    setVisualStyle("live_action");
    setDescription("");
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
      const res = await propCreatorApi.generate(projectId, current.id, {
        local_enabled: localEnabled,
        api_enabled: false,
        local_family: localFamily,
        candidate_count: 4,
      });
      applyProp(res.prop);
      startPoll(res.prop.id);
      setNotice("Generating prop looks.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyProp, localEnabled, localFamily, persist, projectId, startPoll]);

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
    },
    [applyProp, description, name, persist, projectId, prop, visualStyle],
  );

  const remove = useCallback(async () => {
    if (!prop) return;
    if (!window.confirm("Remove this Prop profile? If it is on the Spatial Map, those placements will be unlinked. Library images stay in the project.")) return;
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

  const generating = (prop?.candidates || []).some((c) => c.status === "queued" || c.status === "generating");

  return {
    workspace,
    prop,
    name,
    setName,
    visualStyle,
    setVisualStyle,
    description,
    setDescription,
    localEnabled,
    setLocalEnabled,
    localFamily,
    setLocalFamily,
    loading,
    busy,
    error,
    notice,
    generating,
    apiAvailable: Boolean(workspace?.api_generation_available),
    refresh,
    persist,
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
