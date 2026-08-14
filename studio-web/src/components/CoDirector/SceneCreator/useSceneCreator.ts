/**
 * useSceneCreator — shared Scene Creator state/controller.
 * Express and Standard are views over this hook. Do not duplicate API calls.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { sceneCreatorApi } from "./sceneCreatorApi";
import type {
  CinematicShotControls,
  SceneCreatorCamera,
  SceneCreatorWorkspace,
  SceneShot,
} from "./types";
import { DEFAULT_CINEMATIC } from "./types";

export type SceneCreatorVariant = "express" | "standard";

const defaultCamera = (): SceneCreatorCamera => ({
  camera_id: "",
  camera_slot: null,
  label: "Default Camera",
  orientation: "",
  fov_preset: "",
  cinematic: { ...DEFAULT_CINEMATIC },
});

export function useSceneCreator(projectId: string) {
  const [workspace, setWorkspace] = useState<SceneCreatorWorkspace | null>(null);
  const [shot, setShot] = useState<SceneShot | null>(null);
  const [sheetId, setSheetId] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [intent, setIntent] = useState("");
  const [camera, setCamera] = useState<SceneCreatorCamera>(defaultCamera);
  const [characterIds, setCharacterIds] = useState<string[]>([]);
  const [propIds, setPropIds] = useState<string[]>([]);
  const [localEnabled, setLocalEnabled] = useState(true);
  const [localFamily, setLocalFamily] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [correction, setCorrection] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyShot = useCallback((next: SceneShot | null, placedPropIds: string[] = []) => {
    setShot(next);
    if (!next) {
      if (placedPropIds.length) setPropIds(placedPropIds);
      return;
    }
    setIntent(next.intent || next.prompt || "");
    setCamera(next.camera || defaultCamera());
    setCharacterIds(next.character_ids || []);
    const fromShot = next.prop_entity_ids || [];
    setPropIds(fromShot.length ? fromShot : placedPropIds);
    setLocalEnabled(next.generator?.local_enabled !== false);
    setLocalFamily(next.generator?.local_family || "");
    setSceneId(next.scene_id || "");
    setSheetId(next.sheet_id || "");
  }, []);

  const refresh = useCallback(
    async (query?: { sheet_id?: string; scene_id?: string; shot_id?: string }) => {
      const data = await sceneCreatorApi.workspace(projectId, {
        sheet_id: query?.sheet_id || sheetId || undefined,
        scene_id: query?.scene_id || sceneId || undefined,
        shot_id: query?.shot_id || shot?.id || undefined,
      });
      setWorkspace(data);
      setSheetId(data.selected_sheet_id || "");
      setSceneId(data.selected_scene_id || "");
      const placed = (data.props || []).map((p) => p.prop_id).filter((id): id is string => Boolean(id));
      applyShot(data.selected_shot, placed);
      return data;
    },
    [applyShot, projectId, sceneId, sheetId, shot?.id],
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
    (shotId: string) => {
      stopPoll();
      pollRef.current = setInterval(() => {
        void sceneCreatorApi
          .getShot(projectId, shotId)
          .then((res) => {
            applyShot(res.shot, (workspace?.props || []).map((p) => p.prop_id).filter((id): id is string => Boolean(id)));
            const pending = (res.shot.candidates || []).some(
              (c) => c.status === "queued" || c.status === "generating",
            );
            if (!pending) stopPoll();
          })
          .catch(() => undefined);
      }, 2000);
    },
    [applyShot, projectId, stopPoll, workspace?.props],
  );

  const persistShot = useCallback(async () => {
    if (!sheetId) throw new Error("Select an Environment Reference Sheet first.");
    const res = await sceneCreatorApi.upsertShot(projectId, {
      sheet_id: sheetId,
      scene_id: sceneId || undefined,
      shot_id: shot?.id || undefined,
      intent,
      character_ids: characterIds,
      prop_entity_ids: propIds,
      camera: camera as unknown as Record<string, unknown>,
      generator: {
        local_enabled: localEnabled,
        api_enabled: false,
        local_family: localFamily,
      },
    });
    applyShot(res.shot);
    return res.shot;
  }, [applyShot, camera, characterIds, intent, localEnabled, localFamily, projectId, propIds, sceneId, sheetId, shot?.id]);

  const generate = useCallback(async () => {
    if (shot?.approved_candidate_id) {
      setError("Use Re-Take to change an approved look.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const current = await persistShot();
      const res = await sceneCreatorApi.generateShot(projectId, current.id, {
        local_enabled: localEnabled,
        api_enabled: false,
        local_family: localFamily,
        candidate_count: 4,
      });
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Generating four looks for this shot.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyShot, localEnabled, localFamily, persistShot, projectId, shot?.approved_candidate_id, startPoll]);

  const approve = useCallback(
    async (candidateId: string) => {
      if (!shot) return;
      setBusy(true);
      setError(null);
      try {
        const res = await sceneCreatorApi.approveCandidate(projectId, shot.id, candidateId);
        applyShot(res.shot);
        setNotice("Look saved as the approved take.");
        await refresh({ shot_id: res.shot.id });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [applyShot, projectId, refresh, shot],
  );

  const retake = useCallback(async () => {
    if (!shot) return;
    setBusy(true);
    setError(null);
    try {
      const current = await persistShot();
      const res = await sceneCreatorApi.retakeShot(projectId, current.id, {
        correction,
        local_enabled: localEnabled,
        api_enabled: false,
        local_family: localFamily,
      });
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Re-Take started. The approved look stays until you approve a new one.");
      setCorrection("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyShot, correction, localEnabled, localFamily, persistShot, projectId, shot, startPoll]);

  const sendToTimeline = useCallback(async () => {
    if (!shot) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorApi.sendShotToTimeline(projectId, shot.id);
      setNotice(`Sent to Timeline (${res.clips_sent} clip).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, shot]);

  const selectSheet = useCallback(
    async (nextSheetId: string) => {
      setSheetId(nextSheetId);
      setLoading(true);
      try {
        await refresh({ sheet_id: nextSheetId, scene_id: sceneId });
      } finally {
        setLoading(false);
      }
    },
    [refresh, sceneId],
  );

  const selectScene = useCallback(
    async (nextSceneId: string) => {
      setSceneId(nextSceneId);
      await refresh({ scene_id: nextSceneId, sheet_id: sheetId });
    },
    [refresh, sheetId],
  );

  const selectShot = useCallback(
    async (nextShotId: string) => {
      await refresh({ shot_id: nextShotId, scene_id: sceneId, sheet_id: sheetId });
    },
    [refresh, sceneId, sheetId],
  );

  const newShot = useCallback(() => {
    setShot(null);
    setIntent("");
    setCamera(defaultCamera());
    setCorrection("");
    setPropIds((workspace?.props || []).map((p) => p.prop_id).filter((id): id is string => Boolean(id)));
    setNotice("New shot. Write what happens, then Generate.");
  }, [workspace?.props]);

  const setCinematic = useCallback((patch: Partial<CinematicShotControls>) => {
    setCamera((prev) => ({ ...prev, cinematic: { ...prev.cinematic, ...patch } }));
  }, []);

  const pickCamera = useCallback(
    (cameraId: string) => {
      const option = (workspace?.cameras || []).find((c) => c.id === cameraId);
      if (!option) {
        setCamera((prev) => ({ ...defaultCamera(), cinematic: prev.cinematic }));
        return;
      }
      setCamera((prev) => ({
        ...prev,
        camera_id: option.id,
        camera_slot: option.cameraSlot,
        label: option.label || `C${option.cameraSlot + 1}`,
        orientation: option.orientation,
        fov_preset: option.fovPreset,
        yaw_degrees: option.yawDegrees,
        lens_mm: option.lensMm,
      }));
    },
    [workspace?.cameras],
  );

  const toggleCharacter = useCallback((id: string) => {
    setCharacterIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const toggleProp = useCallback((id: string) => {
    setPropIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const apiAvailable = workspace?.api_generation_available === true;
  const approved = shot?.candidates.find((c) => c.id === shot.approved_candidate_id) || null;
  const generating = (shot?.candidates || []).some((c) => c.status === "queued" || c.status === "generating");

  return {
    workspace,
    shot,
    sheetId,
    sceneId,
    intent,
    setIntent,
    camera,
    characterIds,
    propIds,
    localEnabled,
    setLocalEnabled,
    localFamily,
    setLocalFamily,
    loading,
    busy,
    error,
    notice,
    correction,
    setCorrection,
    apiAvailable,
    approved,
    generating,
    refresh,
    generate,
    approve,
    retake,
    sendToTimeline,
    selectSheet,
    selectScene,
    selectShot,
    newShot,
    setCinematic,
    pickCamera,
    toggleCharacter,
    toggleProp,
    persistShot,
  };
}