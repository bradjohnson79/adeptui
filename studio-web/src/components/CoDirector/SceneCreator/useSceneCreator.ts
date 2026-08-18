/**
 * useSceneCreator — shared Scene Creator state/controller.
 * Express and Standard are views over this hook. Do not duplicate API calls.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../../api";
import { sceneCreatorApi } from "./sceneCreatorApi";
import type { LoraSelection } from "../../lora/LoRASelector";
import { normalizeProductionAspect, type ProductionAspectRatio } from "../../../workspacePrefs";
import type {
  CinematicShotControls,
  SceneCreatorCamera,
  SceneCreatorWorkspace,
  SceneShot,
} from "./types";
import { DEFAULT_CINEMATIC } from "./types";
import {
  deriveProductionContextStatus,
  type ProductionContextStatus,
} from "./productionContextStatus";
import {
  deriveOrientationOperation,
  validateCameraCommand,
  type OrientationPatch,
  type SceneCinematographerPack,
} from "./cinematographer/cameraCommandEngine";
import { clampPitch, clampRoll, clampZoom, wrapYaw } from "./cinematographer/orientationMath";
import {
  approvedLookBlocksFinal,
  compileRegionEditFinalPrompt,
  shotWithSelectedFamily,
  VISUAL_INHERITANCE_BLOCKED_MESSAGE,
} from "./regionEdit/regionEdit";


const defaultCamera = (): SceneCreatorCamera => ({
  camera_id: "",
  camera_slot: null,
  label: "Default Camera",
  orientation: "",
  fov_preset: "",
  cinematic: { ...DEFAULT_CINEMATIC },
});

function readSceneCreatorQuery(): {
  sheet_id?: string;
  scene_id?: string;
  shot_id?: string;
  spatial_profile_id?: string;
} {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  return {
    sheet_id: params.get("sheet_id") || undefined,
    scene_id: params.get("scene_id") || undefined,
    shot_id: params.get("shot_id") || undefined,
    spatial_profile_id: params.get("spatialProfileId") || params.get("handoffId") || undefined,
  };
}


export function useSceneCreator(projectId: string) {
  const [workspace, setWorkspace] = useState<SceneCreatorWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [shot, setShot] = useState<SceneShot | null>(null);
  const [sheetId, setSheetId] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [intent, setIntent] = useState("");
  const [camera, setCamera] = useState<SceneCreatorCamera>(defaultCamera);
  const [characterIds, setCharacterIds] = useState<string[]>([]);
  const [propIds, setPropIds] = useState<string[]>([]);
  const [localEnabled, setLocalEnabled] = useState(true);
  const [localFamily, setLocalFamily] = useState("");
  const [lora, setLora] = useState<LoraSelection | null>(null);
  const [apiEnabled, setApiEnabled] = useState(false);
  const [apiModel, setApiModel] = useState("");
  const [cinematographer, setCinematographer] = useState<SceneCinematographerPack | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState("");
  const [cineOperation, setCineOperation] = useState("extreme_close_up");
  const [cineCharacterId, setCineCharacterId] = useState("");
  const [cinePropId, setCinePropId] = useState("");
  const [cineInstruction, setCineInstruction] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [productionContextStatus, setProductionContextStatus] = useState<ProductionContextStatus>("idle");
  const requestedProfileRef = useRef<string>("");
  const initialQueryRef = useRef(readSceneCreatorQuery());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [correction, setCorrection] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const orientGenRef = useRef(0);
  const inFlightRef = useRef(false);

  const beginSubmit = () => {
    if (inFlightRef.current) return false;
    inFlightRef.current = true;
    setBusy(true);
    return true;
  };

  const endSubmit = () => {
    inFlightRef.current = false;
    setBusy(false);
  };

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyShot = useCallback((next: SceneShot | null, placedPropIds: string[] = []) => {
    setShot(next);
    if (next?.lora) {
      setLora({
        loraId: String(next.lora.loraId || ""),
        name: String(next.lora.name || ""),
        strength: Number(next.lora.strength ?? 0.8),
      });
    }
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
    async (query?: { sheet_id?: string; scene_id?: string; shot_id?: string; spatial_profile_id?: string }) => {
      const initial = initialQueryRef.current;
      const shotId =
        query && Object.prototype.hasOwnProperty.call(query, "shot_id")
          ? query.shot_id
          : shot?.id || initial.shot_id;
      const profileId =
        query && Object.prototype.hasOwnProperty.call(query, "spatial_profile_id")
          ? query.spatial_profile_id
          : initial.spatial_profile_id || requestedProfileRef.current || selectedProfileId;
      const requestedProfile = String(profileId || "").trim();
      if (requestedProfile) {
        requestedProfileRef.current = requestedProfile;
        setProductionContextStatus("loading");
      } else {
        requestedProfileRef.current = "";
        setProductionContextStatus("idle");
      }
      const nextSheetId =
        query && Object.prototype.hasOwnProperty.call(query, "sheet_id")
          ? query.sheet_id
          : sheetId || initial.sheet_id || undefined;
      const nextSceneId =
        query && Object.prototype.hasOwnProperty.call(query, "scene_id")
          ? query.scene_id
          : sceneId || initial.scene_id || undefined;
      const data = await sceneCreatorApi.workspace(projectId, {
        sheet_id: nextSheetId || undefined,
        scene_id: nextSceneId || undefined,
        shot_id: shotId || undefined,
        spatial_profile_id: profileId || undefined,
      });
      initialQueryRef.current = {};
      setWorkspace(data);
      setSheetId(data.selected_sheet_id || "");
      setSceneId(data.selected_scene_id || "");
      setSelectedProfileId(data.selected_spatial_profile_id || "");
      const nextSelected = String(data.selected_spatial_profile_id || "").trim();
      setProductionContextStatus(
        deriveProductionContextStatus({
          selectedProfileId: nextSelected,
          requestedProfileId: requestedProfileRef.current,
          fetchInFlight: false,
          productionContext: data.production_context,
        }),
      );
      if (!nextSelected) requestedProfileRef.current = "";
      const placed = (data.props || []).map((p) => p.prop_id).filter((id): id is string => Boolean(id));
      if (data.workspace_reset && !data.selected_shot) {
        applyShot(null, placed);
        setIntent("");
        setCamera(defaultCamera());
        setCorrection("");
        setCineInstruction("");
      } else {
        applyShot(data.selected_shot, placed);
      }
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
        lora: lora ? { ...lora } : null,
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

  const deleteTake = useCallback(
    async (candidateId: string) => {
      if (!shot) return;
      const cand = (shot.candidates || []).find((item) => item.id === candidateId);
      if (!cand) return;
      const approved = candidateId === shot.approved_candidate_id;
      const message = approved
        ? "This take is approved. Deleting it will remove the approved look and the media from Library. Continue?"
        : "Delete this generation? This will also remove the media from Library.";
      if (typeof window !== "undefined" && !window.confirm(message)) return;
      setBusy(true);
      setError(null);
      try {
        const res = await sceneCreatorApi.deleteShotCandidate(projectId, shot.id, candidateId);
        applyShot(res.shot);
        setNotice("Generation removed from Scene Creator and Library.");
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
    if (!beginSubmit()) return;
    setError(null);
    try {
      const current = await persistShot();
      const res = await sceneCreatorApi.retakeShot(projectId, current.id, {
        correction,
        local_enabled: localEnabled,
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
        lora: lora ? { ...lora } : null,
      });
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Re-Take started. The approved look stays until you approve a new one.");
      setCorrection("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      endSubmit();
    }
  }, [applyShot, apiEnabled, apiModel, correction, lora, localEnabled, localFamily, persistShot, projectId, shot, startPoll]);

  const sendToTimeline = useCallback(async () => {
    if (!shot) return;
    if (!beginSubmit()) return;
    setError(null);
    try {
      const res = await sceneCreatorApi.sendShotToTimeline(projectId, shot.id);
      setNotice(`Sent to Timeline (${res.clips_sent} clip).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      endSubmit();
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

  const selectSpatialProfile = useCallback(
    async (nextId: string) => {
      const wanted = (nextId || "").trim();
      requestedProfileRef.current = wanted;
      setSelectedProfileId(wanted);
      if (!wanted) {
        setProductionContextStatus("idle");
      } else {
        setProductionContextStatus("loading");
      }
      setBusy(true);
      setError(null);
      try {
        const res = await sceneCreatorApi.selectSpatialProfile(projectId, wanted || "none");
        await refresh({
          spatial_profile_id: res.selectedProfileId || undefined,
          scene_id: res.sceneId || undefined,
          sheet_id: res.sheetId || undefined,
          shot_id: undefined,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Spatial Profile could not be loaded.");
        setProductionContextStatus(wanted ? "failed" : "idle");
      } finally {
        setBusy(false);
      }
    },
    [projectId, refresh],
  );

  const confirmResetWorkspace = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await sceneCreatorApi.resetWorkspace(projectId);
      if (typeof window !== "undefined") {
        const url = new URL(window.location.href);
        for (const key of ["spatialProfileId", "handoffId", "scene_id", "sheet_id", "shot_id"]) {
          url.searchParams.delete(key);
        }
        window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
      }
      initialQueryRef.current = {};
      setSelectedProfileId("");
      requestedProfileRef.current = "";
      setProductionContextStatus("idle");
      setSheetId("");
      setSceneId("");
      setIntent("");
      setCamera(defaultCamera());
      setCorrection("");
      setCineInstruction("");
      applyShot(null);
      setResetConfirmOpen(false);
      await refresh({
        spatial_profile_id: undefined,
        shot_id: undefined,
        sheet_id: "",
        scene_id: "",
      });
      setNotice("Scene Creator workspace cleared. Your Library and Spatial Profiles are unchanged.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset the workspace. Try again.");
    } finally {
      setBusy(false);
    }
  }, [applyShot, projectId, refresh]);

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

  const applyOrientation = useCallback(
    async (patch: OrientationPatch) => {
      if (!sceneId || !selectedCameraId) return;
      const rec = (cinematographer?.cameras || []).find((c) => c.cameraId === selectedCameraId);
      const pose = rec?.current;
      const o3d = pose?.orientation3d;
      const operation_id = deriveOrientationOperation(patch);
      const silent = patch.source === "gizmo";
      if (!silent) {
        setBusy(true);
        setError(null);
      }
      const gen = ++orientGenRef.current;
      try {
        const res = await sceneCreatorApi.cinematographerCommand(projectId, sceneId, {
          camera_id: selectedCameraId,
          operation_id,
          shot_id: shot?.id,
          character_id: patch.characterId,
          prop_id: patch.propId,
          orientation3d: {
            yawDegrees: wrapYaw(patch.yawDegrees ?? pose?.yawDegrees ?? 0),
            pitchDegrees: clampPitch(patch.pitchDegrees ?? pose?.pitchDegrees ?? 0),
            rollDegrees: clampRoll(patch.rollDegrees ?? pose?.rollDegrees ?? 0),
            zoom: clampZoom(patch.zoom ?? o3d?.zoom ?? 1),
            enabled: patch.enabled ?? o3d?.enabled ?? true,
            targetLock: patch.targetLock ?? o3d?.targetLock ?? true,
            axisLocks: patch.axisLocks ?? o3d?.axisLocks,
            snapId: patch.snapId,
            source: patch.source ?? "discrete",
          },
        });
        if (gen === orientGenRef.current) {
          applyPack(res.cinematographer, selectedCameraId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!silent) setBusy(false);
      }
    },
    [applyPack, cinematographer, projectId, sceneId, selectedCameraId, shot?.id],
  );

  const resetOrientation = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    setBusy(true);
    setError(null);
    const gen = ++orientGenRef.current;
    try {
      const res = await sceneCreatorApi.cinematographerCommand(projectId, sceneId, {
        camera_id: selectedCameraId,
        operation_id: "orient_reset",
        shot_id: shot?.id,
        orientation3d: {
          yawDegrees: 0,
          pitchDegrees: 0,
          rollDegrees: 0,
          zoom: 1,
          enabled: true,
          targetLock: true,
          source: "discrete",
        },
      });
      if (gen === orientGenRef.current) {
        applyPack(res.cinematographer, selectedCameraId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [applyPack, projectId, sceneId, selectedCameraId, shot?.id]);

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
    if (productionContextStatus === "failed") {
      setError("Co-Director production data is not loaded. Select a Spatial Profile and wait until it finishes loading before generating.");
      return;
    }
    const readiness = workspace?.production_readiness;
    if (/qwen/i.test(localFamily)) {
      // CDX-040: qwen2512 has zero pixel slots - disclose when the ERS
      // composite environment picture exists but cannot be loaded, even
      // without a loaded spatial profile.
      const composite = (workspace?.resolved_ers as { ers_composite_asset_id?: string } | null | undefined)?.ers_composite_asset_id;
      if (composite && productionContextStatus !== "loaded") {
        setError("The environment picture cannot be loaded by this generator. Choose Z-Image to keep the environment picture.");
        return;
      }
      if (productionContextStatus === "loaded") {
        const ticks = readiness?.ticks;
        if (ticks && (ticks.character !== "idle" || ticks.prop !== "idle" || ticks.environment !== "idle")) {
          setError("This generator cannot use the character and prop pictures already chosen. Choose Z-Image to keep those pictures.");
          return;
        }
      }
    }
    if (readiness?.status === "blocked") {
      setError(readiness.issues?.[0]?.message || "Production integrity check failed.");
      return;
    }
    if (!beginSubmit()) return;
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
      setNotice("Generating preview…");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      endSubmit();
    }
  }, [apiEnabled, apiModel, applyPack, applyShot, localEnabled, localFamily, persistShot, productionContextStatus, projectId, sceneId, selectedCameraId, startPoll, workspace?.production_readiness]);

  const finalRender = useCallback(async () => {
    if (!sceneId || !selectedCameraId) return;
    if (approvedLookBlocksFinal(shot)) {
      setError("Use Re-Take to change an approved look.");
      return;
    }
    const compiled = shot ? compileRegionEditFinalPrompt(shotWithSelectedFamily(shot, localFamily) || shot) : null;
    if (compiled?.visualInheritanceBlocked) {
      setError(VISUAL_INHERITANCE_BLOCKED_MESSAGE);
      return;
    }
    if (productionContextStatus === "failed") {
      setError("Co-Director production data is not loaded. Select a Spatial Profile and wait until it finishes loading before generating.");
      return;
    }
    const readiness = workspace?.production_readiness;
    if (/qwen/i.test(localFamily)) {
      // CDX-040: qwen2512 has zero pixel slots - disclose when the ERS
      // composite environment picture exists but cannot be loaded, even
      // without a loaded spatial profile.
      const composite = (workspace?.resolved_ers as { ers_composite_asset_id?: string } | null | undefined)?.ers_composite_asset_id;
      if (composite && productionContextStatus !== "loaded") {
        setError("The environment picture cannot be loaded by this generator. Choose Z-Image to keep the environment picture.");
        return;
      }
      if (productionContextStatus === "loaded") {
        const ticks = readiness?.ticks;
        if (ticks && (ticks.character !== "idle" || ticks.prop !== "idle" || ticks.environment !== "idle")) {
          setError("This generator cannot use the character and prop pictures already chosen. Choose Z-Image to keep those pictures.");
          return;
        }
      }
    }
    if (readiness?.status === "blocked") {
      setError(readiness.issues?.[0]?.message || "Production integrity check failed.");
      return;
    }
    if (!beginSubmit()) return;
    setError(null);
    setNotice(null);
    try {
      const current = await persistShot();
      const compiledAfter = compileRegionEditFinalPrompt(
        shotWithSelectedFamily(current, localFamily) || current,
      );
      const res = await sceneCreatorApi.cinematographerFinal(projectId, sceneId, {
        camera_id: selectedCameraId,
        shot_id: current.id,
        local_enabled: localEnabled,
        api_enabled: apiEnabled,
        local_family: localFamily,
        api_model: apiModel,
        sourceAssetId: compiledAfter.sourceAssetId,
        finalStrategy: compiledAfter.strategy,
      });
      applyPack(res.cinematographer, selectedCameraId);
      applyShot(res.shot);
      startPoll(res.shot.id);
      setNotice("Final rendering…");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      endSubmit();
    }
  }, [apiEnabled, apiModel, applyPack, applyShot, localEnabled, localFamily, persistShot, productionContextStatus, projectId, sceneId, selectedCameraId, shot, startPoll, workspace?.production_readiness]);

  const apiAvailable = workspace?.api_generation_available === true || apiEnabled;
  const approved = shot?.candidates.find((c) => c.id === shot.approved_candidate_id) || null;
  const generating = (shot?.candidates || []).some((c) => c.status === "queued" || c.status === "generating")
    || (cinematographer?.cameras || []).some((c) => c.lineage?.previewStatus === "generating");

  return {
    projectId,
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
    lora,
    setLora,
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
    productionAspect: normalizeProductionAspect(workspace?.production_aspect_ratio),
    setProductionAspect: async (ratio: ProductionAspectRatio) => {
      if (!sceneId) return;
      try {
        await api.updateScene(projectId, sceneId, { aspect_ratio: ratio } as never);
        await refresh({ scene_id: sceneId });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    generate: finalRender,
    approve,
    deleteTake,
    retake,
    sendToTimeline,
    selectSheet,
    selectScene,
    selectShot,
    newShot,
    selectSpatialProfile,
    confirmResetWorkspace,
    selectedProfileId,
    productionContextStatus,
    resetConfirmOpen,
    setResetConfirmOpen,
    setCinematic,
    pickCamera,
    toggleCharacter,
    toggleProp,
    persistShot,
    selectCinematographerCamera,
    enterCameraCommand,
    applyOrientation,
    resetOrientation,
    undoCamera,
    resetCamera,
    lockCamera,
    saveCineDelta,
    previewCamera,
    finalRender,
    regionEdit: async (body: {
      operation: string;
      prompt: string;
      maskAssetId: string;
      sourceAssetId?: string;
      stage?: "preview" | "final";
      local_family?: string;
      local_enabled?: boolean;
      api_enabled?: boolean;
      expand?: string;
      feather?: string;
    }) => {
      if (!shot?.id) {
        setError("Generate a look first, then paint the region to change.");
        return;
      }
      if (!beginSubmit()) return;
      setError(null);
      setNotice(null);
      try {
        const res = await sceneCreatorApi.regionEdit(projectId, shot.id, {
          ...body,
          local_family: body.local_family || localFamily,
          local_enabled: body.local_enabled ?? localEnabled,
          api_enabled: false,
        });
        applyShot(res.shot);
        startPoll(res.shot.id);
        setNotice("Generating region edit…");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        endSubmit();
      }
    },
    retryFailed: async (candidateId: string) => {
      if (!shot?.id) return;
      const cand = shot.candidates.find((item) => item.id === candidateId);
      if (!cand || cand.status !== "failed") return;
      if (cand.kind === "region_edit") {
        const edits = ((shot.take_memory?.userCorrection?.region_edits as Array<Record<string, unknown>>) || []).find(
          (edit) => edit.candidate_id === cand.id,
        );
        if (!edits?.maskAssetId && !cand.mask_id) {
          setError("Paint the region again, then Generate Inpaint.");
          return;
        }
        if (!beginSubmit()) return;
        setError(null);
        try {
          const res = await sceneCreatorApi.regionEdit(projectId, shot.id, {
            operation: String(edits?.operation || cand.edit_operation || "modify"),
            prompt: String(edits?.prompt || ""),
            maskAssetId: String(edits?.maskAssetId || cand.mask_id || ""),
            sourceAssetId: String(edits?.sourceAssetId || cand.source_preview_asset_id || ""),
            stage: (cand.quality_profile || "preview") === "final" ? "final" : "preview",
            local_family: localFamily,
            local_enabled: localEnabled,
            api_enabled: false,
          });
          applyShot(res.shot);
          startPoll(res.shot.id);
          setNotice("Generating region edit…");
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        } finally {
          endSubmit();
        }
        return;
      }
      if ((cand.quality_profile || "").toLowerCase() === "draft") {
        await previewCamera();
        return;
      }
      await finalRender();
    },
  };
}