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
import {
  validateCameraCommand,
  type SceneCinematographerPack,
} from "./cinematographer/cameraCommandEngine";

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
  const [apiEnabled, setApiEnabled] = useState(false);
  const [apiModel, setApiModel] = useState("");
  const [cinematographer, setCinematographer] = useState<SceneCinematographerPack | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState("");
  const [cineOperation, setCineOperation] = useState("extreme_close_up");
  const [cineCharacterId, setCineCharacterId] = useState("");
  const [cinePropId, setCinePropId] = useState("");
  const [cineInstruction, setCineInstruction] = useState("");
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
      if (data.cinematographer) {
        setCinematographer(data.cinematographer);
        const selected = data.cinematographer.selected_camera_id || data.cinematographer.cameras?.[0]?.cameraId || "";
        setSelectedCameraId(selected);
        const rec = (data.cinematographer.cameras || []).find((c) => c.cameraId === selected);
        if (rec) {
          setCineInstruction(rec.userCameraPromptDelta ? `${rec.displayInstruction}\n${rec.userCameraPromptDelta}`.trim() : rec.displayInstruction || "");
        }
      }
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
          .then(async (res) => {
            applyShot(res.shot, (workspace?.props || []).map((p) => p.prop_id).filter((id): id is string => Boolean(id)));
            const pendingShot = (res.shot.candidates || []).some(
              (c) => c.status === "queued" || c.status === "generating",
            );
            let pendingPreview = false;
            if (sceneId) {
              try {
                const cine = await sceneCreatorApi.cinematographer(projectId, sceneId);
                setCinematographer(cine.cinematographer);
                pendingPreview = (cine.cinematographer.cameras || []).some(
                  (c) => c.lineage?.previewStatus === "generating",
                );
              } catch {
                /* ignore */
              }
            }
            if (!pendingShot && !pendingPreview) stopPoll();
          })
          .catch(() => undefined);
      }, 2000);
    },
    [applyShot, projectId, sceneId, stopPoll, workspace?.props],
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
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
      },
    });
    applyShot(res.shot);
    return res.shot;
  }, [applyShot, apiEnabled, apiModel, camera, characterIds, intent, localEnabled, localFamily, projectId, propIds, sceneId, sheetId, shot?.id]);

  const applyPack = useCallback((pack: SceneCinematographerPack, cameraId?: string) => {
    setCinematographer(pack);
    const nextId = cameraId || pack.selected_camera_id || selectedCameraId || pack.cameras?.[0]?.cameraId || "";
    setSelectedCameraId(nextId);
    const rec = (pack.cameras || []).find((c) => c.cameraId === nextId);
    if (rec) {
      const structured = rec.displayInstruction || "";
      const delta = rec.userCameraPromptDelta || "";
      setCineInstruction(delta ? `${structured}\n${delta}`.trim() : structured);
      const cineSize = rec.current?.shotType || "medium";
      setCamera((prev) => ({
        ...prev,
        camera_id: rec.cameraId,
        camera_slot: rec.cameraSlot,
        label: rec.label || `C${rec.cameraSlot + 1}`,
        orientation: rec.current?.orientation || prev.orientation,
        fov_preset: rec.current?.fovPreset || prev.fov_preset,
        yaw_degrees: rec.current?.yawDegrees ?? prev.yaw_degrees,
        lens_mm: rec.current?.lensMm ?? prev.lens_mm,
        cinematic: {
          ...prev.cinematic,
          shot_size: cineSize.includes("close") ? "close_up" : cineSize.includes("wide") ? "wide" : prev.cinematic.shot_size,
        },
      }));
    }
  }, [selectedCameraId]);

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
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
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
  }, [applyShot, apiEnabled, apiModel, correction, localEnabled, localFamily, persistShot, projectId, shot, startPoll]);

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

  const selectCinematographerCamera = useCallback((cameraId: string) => {
    setSelectedCameraId(cameraId);
    const rec = (cinematographer?.cameras || []).find((c) => c.cameraId === cameraId);
    if (rec) {
      const structured = rec.displayInstruction || "";
      const delta = rec.userCameraPromptDelta || "";
      setCineInstruction(delta ? `${structured}\n${delta}`.trim() : structured);
    }
  }, [cinematographer]);

  const enterCameraCommand = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    const check = validateCameraCommand(cineOperation, cineCharacterId, cinePropId);
    if (!check.ok) {
      setError(check.error);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorApi.cinematographerCommand(projectId, sceneId, {
        camera_id: selectedCameraId,
        operation_id: cineOperation,
        character_id: cineCharacterId,
        prop_id: cinePropId,
        shot_id: shot?.id,
      });
      applyPack(res.cinematographer, selectedCameraId);
      setNotice("Camera updated. Generate a preview when you want to see it.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyPack, cineCharacterId, cineOperation, cinePropId, projectId, sceneId, selectedCameraId, shot?.id]);

  const undoCamera = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorApi.cinematographerUndo(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: shot?.id,
      });
      applyPack(res.cinematographer, selectedCameraId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyPack, projectId, sceneId, selectedCameraId, shot?.id]);

  const resetCamera = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorApi.cinematographerReset(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: shot?.id,
      });
      applyPack(res.cinematographer, selectedCameraId);
      setNotice("Camera restored to the Spatial Map starting position.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyPack, projectId, sceneId, selectedCameraId, shot?.id]);

  const lockCamera = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await sceneCreatorApi.cinematographerLock(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: shot?.id,
      });
      applyPack(res.cinematographer, selectedCameraId);
      setNotice("Camera locked. Final Quality Render will use this setup.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyPack, projectId, sceneId, selectedCameraId, shot?.id]);

  const saveCineDelta = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    const rec = (cinematographer?.cameras || []).find((c) => c.cameraId === selectedCameraId);
    const structured = rec?.displayInstruction || "";
    let delta = cineInstruction;
    if (structured && delta.startsWith(structured)) {
      delta = delta.slice(structured.length).trim();
    }
    try {
      const res = await sceneCreatorApi.cinematographerDelta(projectId, sceneId, {
        camera_id: selectedCameraId,
        delta,
      });
      applyPack(res.cinematographer, selectedCameraId);
    } catch {
      /* keep local text */
    }
  }, [applyPack, cineInstruction, cinematographer, projectId, sceneId, selectedCameraId]);

  const previewCamera = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const current = await persistShot();
      const res = await sceneCreatorApi.cinematographerPreview(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: current.id,
        local_enabled: localEnabled,
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
      });
      applyPack(res.cinematographer, selectedCameraId);
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Preview started. This is a draft look, not the final image.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [apiEnabled, apiModel, applyPack, applyShot, localEnabled, localFamily, persistShot, projectId, sceneId, selectedCameraId, startPoll]);

  const finalRender = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    if (shot?.approved_candidate_id) {
      setError("Use Re-Take to change an approved look.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const current = await persistShot();
      const res = await sceneCreatorApi.cinematographerFinal(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: current.id,
        local_enabled: localEnabled,
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
      });
      applyPack(res.cinematographer, selectedCameraId);
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Final quality render started.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [apiEnabled, apiModel, applyPack, applyShot, localEnabled, localFamily, persistShot, projectId, sceneId, selectedCameraId, shot?.approved_candidate_id, startPoll]);

  const apiAvailable = workspace?.api_generation_available === true || apiEnabled;
  const approved = shot?.candidates.find((c) => c.id === shot.approved_candidate_id) || null;
  const generating = (shot?.candidates || []).some((c) => c.status === "queued" || c.status === "generating")
    || (cinematographer?.cameras || []).some((c) => c.lineage?.previewStatus === "generating");

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
    apiEnabled,
    setApiEnabled,
    apiModel,
    setApiModel,
    cinematographer,
    selectedCameraId,
    cineOperation,
    setCineOperation,
    cineCharacterId,
    setCineCharacterId,
    cinePropId,
    setCinePropId,
    cineInstruction,
    setCineInstruction,
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
    generate: finalRender,
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
    selectCinematographerCamera,
    enterCameraCommand,
    undoCamera,
    resetCamera,
    lockCamera,
    saveCineDelta,
    previewCamera,
    finalRender,
  };
}