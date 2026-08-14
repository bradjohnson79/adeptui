/**
 * SpatialMapPanel — main Spatial Map panel for the Co-Director pane.
 *
 * Lifecycle:
 *   empty state (no document or no backgroundAssetId)
 *     → creator picks Atlas Shot / Library image / Upload
 *     → POST /api/spatial-map/projects/{pid}/maps with backgroundAssetId
 *   map view (document with backgroundAssetId)
 *     → circular working area + Cartesian square grid,
 *       character/prop/camera slots (ADD ≠ PLACE),
 *       click-to-place, mini-prompts, ERS generation/display.
 *
 * Reuses (Law #17): api.spatialMap, api.listCharacterProfiles, api.library,
 * api.uploadAsset, api.startExecution.
 *
 * Amendments honored:
 *   #1 Atlas Shot is an INPUT.
 *   #2 ERS composite is assembled in code — we just display the asset.
 *   #3 Spatial Map authoritative — generated imagery never mutates placement.
 *   #4 Orientation scene-relative (Atlas North = top edge).
 *   #5 @ uses real character names; # uses normalized tags.
 *   #25 Mini-prompts shown as compact expandable cards.
 *   #12/#13/#69 Accessible labels.
 *
 * Persistence (Law #10): every placement change POSTs/PATCHes immediately.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { CoDirectorEmptyState } from "../cards";
import { useCoDirectorSession } from "../CoDirectorSession";
import { isTerminal } from "../AgentWorkSurface/types";
import { EntityPicker } from "./EntityPicker";
import { ErsResultDisplay } from "./ErsResultDisplay";
import { PlacementSlot } from "./PlacementSlot";
import { SpatialGrid, toGridPlacements } from "./SpatialGrid";
import { spatialMapApi } from "./spatialMapApi";
import { CameraInspector } from "./CameraInspector";
import {
  cellLabel,
  cellToNormalized,
  isCellInsideCircle,
  DEFAULT_GRID_SCALE,
  densityForScale,
  gridScaleLabel,
  MAX_GRID_SCALE,
  MIN_GRID_SCALE,
  orientationToYaw,
  type GridScale,
} from "./gridGeometry";
import {
  CAMERA_SLOTS,
  CHARACTER_SLOTS,
  PROP_SLOTS,
  type SavedOption,
  type ActivePlacement,
  type SlotDef,
  type SpatialCamera,
  type SpatialCharacterPlacement,
  type SpatialMapDocument,
  type SpatialPropPlacement,
} from "./types";
import "./spatialMap.css";

type Props = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

type BusyState = { loading: boolean; error: string | null };
type PendingCoDirectorOp = "atlas" | "ers" | null;
type ActiveSlot = { kind: "character" | "prop" | "camera"; index: number } | null;
type PlacementMode = {
  action: "place" | "move";
  kind: "character" | "prop" | "camera";
  id: string;
  label: string;
} | null;

export function SpatialMapPanel({ projectId, onGoTab }: Props) {
  const { activeExecution, setActiveExecution } = useCoDirectorSession();
  const [document, setDocument] = useState<SpatialMapDocument | null>(null);
  const [busy, setBusy] = useState<BusyState>({ loading: true, error: null });
  const [activeSlot, setActiveSlot] = useState<ActiveSlot>(null);
  const [selectedPlacementId, setSelectedPlacementId] = useState<string | null>(null);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [placementMode, setPlacementMode] = useState<PlacementMode>(null);
  const [showGrid, setShowGrid] = useState(true);
  const [showCircles, setShowCircles] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [occupiedMessage, setOccupiedMessage] = useState<string | null>(null);
  const [savedCharacters, setSavedCharacters] = useState<SavedOption[]>([]);
  const [savedProps, setSavedProps] = useState<SavedOption[]>([]);
  const [busyOp, setBusyOp] = useState<PendingCoDirectorOp>(null);
  const [opMsg, setOpMsg] = useState<string | null>(null);
  const [ersCompositeAssetId, setErsCompositeAssetId] = useState<string | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [replacePickerOpen, setReplacePickerOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const emptyFileInputRef = useRef<HTMLInputElement>(null);
  const replaceModeRef = useRef(false);

  // ── Load most recent map on mount / project change ───────────────────────
  const loadMap = useCallback(async () => {
    setBusy({ loading: true, error: null });
    try {
      const doc = await spatialMapApi.getMostRecentMap(projectId);
      setDocument(doc);
    } catch (err) {
      setBusy({ loading: false, error: err instanceof Error ? err.message : String(err) });
      return;
    }
    setBusy({ loading: false, error: null });
  }, [projectId]);

  useEffect(() => {
    void loadMap();
  }, [loadMap]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const profiles = (await api.listCharacterProfiles(projectId)) as { items?: Array<{ id: string; name: string }> };
        const characters = (profiles.items || []).map((c) => ({ id: c.id, name: c.name, source: "character" as const }));
        if (!cancelled) setSavedCharacters(characters);

        const propOptions: SavedOption[] = [];
        const seen = new Set<string>();
        for (const character of characters) {
          try {
            const propsRes = (await api.listCharacterProps(projectId, character.id)) as {
              items?: Array<{ id: string; name: string; library_asset_id?: string | null }>;
            };
            for (const prop of propsRes.items || []) {
              if (!prop.id || seen.has(prop.id)) continue;
              seen.add(prop.id);
              propOptions.push({
                id: prop.id,
                name: prop.name,
                assetId: prop.library_asset_id || null,
                source: "character",
              });
            }
          } catch {
            // best-effort per character
          }
        }
        try {
          const library = await api.library(projectId, {});
          const items = Array.isArray((library as { items?: unknown[] }).items) ? (library as { items: Array<{ id: string; tag?: string; filename?: string }> }).items : [];
          for (const asset of items) {
            const tag = String(asset.tag || "").toLowerCase();
            if (!tag.includes("prop") && !tag.startsWith("#")) continue;
            if (seen.has(asset.id)) continue;
            seen.add(asset.id);
            const name = (asset.tag || asset.filename || "Prop").replace(/^#/, "");
            propOptions.push({ id: asset.id, name, assetId: asset.id, source: "library" });
          }
        } catch {
          // library fallback is optional
        }
        if (!cancelled) setSavedProps(propOptions);
      } catch {
        if (!cancelled) {
          setSavedCharacters([]);
          setSavedProps([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const activePlacement: ActivePlacement | null = placementMode
    ? { type: placementMode.kind, slot: activeSlot?.index ?? 0, entityId: placementMode.id }
    : null;

  const clearPlacementMode = useCallback(() => {
    setPlacementMode(null);
    setOccupiedMessage(null);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") clearPlacementMode();
    };
    window.document.addEventListener("keydown", onKey);
    return () => window.document.removeEventListener("keydown", onKey);
  }, [clearPlacementMode]);

  // ── Track active Co-Director execution for atlas / ERS results ──────────
  useEffect(() => {
    if (!activeExecution) return;
    if (activeExecution.project_id && activeExecution.project_id !== projectId) return;
    if (isTerminal(activeExecution)) {
      const resultIds = activeExecution.result_asset_ids || [];
      if (resultIds.length > 0) {
        if (busyOp === "atlas") {
          const atlasAssetId = resultIds[0];
          void (async () => {
            try {
              if (replaceModeRef.current && document) {
                const updated = await spatialMapApi.updateMap(projectId, document.id, { backgroundAssetId: atlasAssetId });
                setDocument(updated);
                setOpMsg("Atlas Shot replaced.");
              } else {
                const doc = await spatialMapApi.createMap(projectId, {
                  title: "Spatial Map",
                  backgroundAssetId: atlasAssetId,
                });
                setDocument(doc);
                setOpMsg("Atlas Shot generated and Spatial Map created.");
              }
              setBusyOp(null);
              replaceModeRef.current = false;
            } catch (err) {
              setOpMsg(err instanceof Error ? err.message : "Failed to create map from Atlas Shot.");
              setBusyOp(null);
              replaceModeRef.current = false;
            }
          })();
        } else if (busyOp === "ers") {
          const compositeId = resultIds[resultIds.length - 1];
          setErsCompositeAssetId(compositeId);
          setOpMsg("Environment Reference Sheet generated.");
          setBusyOp(null);
        }
      } else if (activeExecution.status === "failed" || activeExecution.status === "cancelled") {
        setOpMsg(activeExecution.error || `${busyOp || "Operation"} failed.`);
        setBusyOp(null);
      }
    }
  }, [activeExecution?.status, activeExecution?.execution_id, activeExecution?.result_asset_ids?.length, projectId, busyOp, document]);

  // ── Atlas Shot / ERS generation ────────────────────────────────────────
  const startAtlasGeneration = useCallback(async () => {
    setOpMsg(null);
    setBusyOp("atlas");
    try {
      const res = await api.startExecution(projectId, { capability: "atlas.generate", context: {} });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start Atlas Shot generation.");
      setBusyOp(null);
    }
  }, [projectId, setActiveExecution]);

  const startErsGeneration = useCallback(async () => {
    if (!document) return;
    setOpMsg(null);
    setBusyOp("ers");
    try {
      const res = await api.startExecution(projectId, { capability: "ers.generate", context: { spatial_map_id: document.id } });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start ERS generation.");
      setBusyOp(null);
    }
  }, [projectId, document, setActiveExecution]);

  // ── Library / upload / replace / remove atlas ──────────────────────────
  const handleChooseFromLibrary = () => setLibraryPickerOpen(true);
  const handleReplaceFromLibrary = () => setReplacePickerOpen(true);

  const handleReplaceUpload = useCallback(async (file: File) => {
    if (!document) return;
    setOpMsg(null);
    setBusyOp("atlas");
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      const updated = await spatialMapApi.updateMap(projectId, document.id, { backgroundAssetId: asset.id });
      setDocument(updated);
      setOpMsg("Atlas Shot replaced.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Replace failed.");
    } finally {
      setBusyOp(null);
    }
  }, [projectId, document]);

  const handleReplaceGenerate = useCallback(async () => {
    if (!document) return;
    setOpMsg(null);
    setBusyOp("atlas");
    replaceModeRef.current = true;
    try {
      const res = await api.startExecution(projectId, { capability: "atlas.generate", context: {} });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start Atlas Shot generation.");
      setBusyOp(null);
      replaceModeRef.current = false;
    }
  }, [projectId, document, setActiveExecution]);

  const handleRemoveAtlas = useCallback(async () => {
    if (!document?.backgroundAssetId) return;
    const ok = window.confirm("Remove the Atlas Shot from this Spatial Map? The Library image is kept; only the map background is cleared.");
    if (!ok) return;
    setOpMsg(null);
    try {
      const updated = await spatialMapApi.updateMap(projectId, document.id, { backgroundAssetId: null });
      setDocument(updated);
      setOpMsg("Atlas Shot removed from Spatial Map. The Library image is preserved.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to remove Atlas.");
    }
  }, [projectId, document]);

  const handleUploadImage = useCallback(async (file: File) => {
    setOpMsg(null);
    setBusyOp("atlas");
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      const doc = await spatialMapApi.createMap(projectId, { title: "Spatial Map", backgroundAssetId: asset.id });
      setDocument(doc);
      setOpMsg("Image uploaded and Spatial Map created.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusyOp(null);
    }
  }, [projectId]);

  // ── Placements ───────────────────────────────────────────────────────
  const placements = useMemo(() => (document ? toGridPlacements(document.characters, document.props) : []), [document]);
  const gridScale: GridScale = useMemo(() => {
    const s = document?.gridScale ?? DEFAULT_GRID_SCALE;
    return Math.max(MIN_GRID_SCALE, Math.min(MAX_GRID_SCALE, s)) as GridScale;
  }, [document?.gridScale]);

  const findPlacement = useCallback(
    (placementId: string | null): SpatialCharacterPlacement | SpatialPropPlacement | null => {
      if (!placementId || !document) return null;
      return document.characters.find((p) => p.id === placementId) || document.props.find((p) => p.id === placementId) || null;
    },
    [document],
  );

  const placementForSlot = useCallback(
    (slot: SlotDef): SpatialCharacterPlacement | SpatialPropPlacement | null => {
      if (!document) return null;
      const arr = slot.kind === "character" ? document.characters : document.props;
      return arr.find((p) => p.slotIndex === slot.index && p.colorKey === slot.colorKey) || arr.find((p) => p.colorKey === slot.colorKey) || null;
    },
    [document],
  );

  const cameraForSlot = useCallback(
    (slot: SlotDef): SpatialCamera | null => {
      if (!document || slot.kind !== "camera") return null;
      return document.cameras.find((c) => c.cameraSlot === slot.index) || null;
    },
    [document],
  );

  const findCamera = useCallback(
    (cameraId: string | null): SpatialCamera | null => {
      if (!cameraId || !document) return null;
      return document.cameras.find((c) => c.id === cameraId) || null;
    },
    [document],
  );

  // ── Grid scale ───────────────────────────────────────────────────────
  const handleGridScale = useCallback(
    async (delta: number) => {
      if (!document) return;
      const next = Math.max(MIN_GRID_SCALE, Math.min(MAX_GRID_SCALE, gridScale + delta)) as GridScale;
      if (next === gridScale) return;
      try {
        const updated = await spatialMapApi.updateMap(projectId, document.id, { gridScale: next });
        setDocument(updated);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to update placement precision.");
      }
    },
    [projectId, document, gridScale],
  );

  const handleCellClick = useCallback(
    async (column: number, row: number) => {
      setOccupiedMessage(null);
      if (!document || !placementMode) return;

      const occupied = placements.find(
        (p) => p.gridRow === row && p.gridColumn === column && p.id !== placementMode.id,
      );
      if (occupied && placementMode.kind !== "camera") {
        setOccupiedMessage(`Cell ${cellLabel(column, row)} is occupied by ${occupied.tag}. Choose another cell.`);
        return;
      }

      const density = densityForScale(gridScale);
      if (!isCellInsideCircle(column, row, density)) return;
      const center = cellToNormalized(column, row, density);
      const coords = {
        gridRow: row,
        gridColumn: column,
        normalizedX: center.x,
        normalizedY: center.y,
      };

      try {
        let updated: SpatialMapDocument;
        if (placementMode.kind === "camera") {
          updated = await spatialMapApi.updateCamera(projectId, document.id, placementMode.id, coords);
        } else if (placementMode.kind === "character") {
          updated = await spatialMapApi.updateCharacter(projectId, document.id, placementMode.id, coords);
        } else {
          updated = await spatialMapApi.updateProp(projectId, document.id, placementMode.id, coords);
        }
        setDocument(updated);
        setPlacementMode({ ...placementMode, action: "move" });
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to place.");
      }
    },
    [document, placementMode, placements, projectId, gridScale],
  );

  const handleAddCharacter = useCallback(
    async (slot: SlotDef, option: SavedOption) => {
      if (!document || !option.id) return;
      try {
        let assetId: string | null = null;
        try {
          const refs = (await api.listCharacterReferences(projectId, option.id)) as {
            items?: Array<{ asset_id?: string | null; canonical?: boolean; approval_status?: string }>;
          };
          const items = refs.items || [];
          const hero = items.find((r) => r.canonical && r.approval_status === "approved") || items.find((r) => r.canonical);
          if (hero?.asset_id) assetId = hero.asset_id;
        } catch {
          // best-effort
        }
        const updated = await spatialMapApi.placeCharacter(projectId, document.id, {
          characterId: option.id,
          label: option.name,
          assetId,
          tag: option.name,
          slotIndex: slot.index,
          colorKey: slot.colorKey,
          miniPrompt: "",
          gridRow: -1,
          gridColumn: -1,
          normalizedX: null,
          normalizedY: null,
        });
        setDocument(updated);
        setActiveSlot({ kind: "character", index: slot.index });
        setPlacementMode(null);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to add character.");
      }
    },
    [document, projectId],
  );

  const handleAddProp = useCallback(
    async (slot: SlotDef, option: SavedOption) => {
      if (!document || !option.id) return;
      try {
        const isCharacterProp = option.source !== "library";
        const updated = await spatialMapApi.placeProp(projectId, document.id, {
          label: option.name,
          assetId: option.assetId || null,
          propId: isCharacterProp ? option.id : null,
          category: "prop",
          state: "default",
          tag: option.name,
          slotIndex: slot.index,
          colorKey: slot.colorKey,
          miniPrompt: "",
          gridRow: -1,
          gridColumn: -1,
          normalizedX: null,
          normalizedY: null,
        });
        setDocument(updated);
        setActiveSlot({ kind: "prop", index: slot.index });
        setPlacementMode(null);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to add prop.");
      }
    },
    [document, projectId],
  );


  const applyVisible = (doc: SpatialMapDocument, kind: 'character' | 'prop' | 'camera', id: string, next: boolean): SpatialMapDocument => {
    if (kind === 'camera') return { ...doc, cameras: doc.cameras.map((c) => (c.id === id ? { ...c, visible: next } : c)) };
    if (kind === 'character') return { ...doc, characters: doc.characters.map((c) => (c.id === id ? { ...c, visible: next } : c)) };
    return { ...doc, props: doc.props.map((item) => (item.id === id ? { ...item, visible: next } : item)) };
  };

  const handleToggleVisible = useCallback(
    async (kind: "character" | "prop" | "camera", id: string, next: boolean) => {
      if (!document) return;
      setDocument((prev) => {
        if (!prev) return prev;
        if (kind === "camera") {
          return { ...prev, cameras: prev.cameras.map((c) => (c.id === id ? { ...c, visible: next } : c)) };
        }
        if (kind === "character") {
          return { ...prev, characters: prev.characters.map((c) => (c.id === id ? { ...c, visible: next } : c)) };
        }
        return { ...prev, props: prev.props.map((item) => (item.id === id ? { ...item, visible: next } : item)) };
      });
      try {
        if (kind === "camera") {
          const updated = await spatialMapApi.updateCamera(projectId, document.id, id, { visible: next } as never);
          setDocument(applyVisible(updated, kind, id, next));
        } else if (kind === "character") {
          const updated = await spatialMapApi.updateCharacter(projectId, document.id, id, { visible: next } as never);
          setDocument(applyVisible(updated, kind, id, next));
        } else {
          const updated = await spatialMapApi.updateProp(projectId, document.id, id, { visible: next } as never);
          setDocument(applyVisible(updated, kind, id, next));
        }
      } catch {
        // keep optimistic local state if the PATCH fails
      }
    },
    [document, projectId],
  );

  const beginPlacement = useCallback((action: "place" | "move", kind: "character" | "prop" | "camera", id: string, label: string, index: number) => {
    setPlacementMode({ action, kind, id, label });
    setActiveSlot({ kind, index });
    setOccupiedMessage(null);
    if (kind === "camera") {
      setSelectedCameraId(id);
      setSelectedPlacementId(null);
    } else {
      setSelectedPlacementId(id);
      setSelectedCameraId(null);
    }
  }, []);

  // ── Slot: remove ──────────────────────────────────────────────────────
  const handleSlotRemove = useCallback(
    async (slot: SlotDef) => {
      if (!document) return;
      try {
        let updated: SpatialMapDocument;
        if (slot.kind === "camera") {
          const camera = cameraForSlot(slot);
          if (!camera) return;
          updated = await spatialMapApi.removeCamera(projectId, document.id, camera.id);
          if (selectedCameraId === camera.id) setSelectedCameraId(null);
        } else {
          const placement = placementForSlot(slot);
          if (!placement) return;
          updated =
            slot.kind === "character"
              ? await spatialMapApi.removeCharacter(projectId, document.id, placement.id)
              : await spatialMapApi.removeProp(projectId, document.id, placement.id);
          if (selectedPlacementId === placement.id) setSelectedPlacementId(null);
        }
        setDocument(updated);
        setPlacementMode(null);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to remove.");
      }
    },
    [document, placementForSlot, cameraForSlot, projectId, selectedPlacementId, selectedCameraId],
  );

  // ── Slot: update mini-prompt ───────────────────────────────────────────
  const handleUpdateMiniPrompt = useCallback(
    async (slot: SlotDef, text: string) => {
      if (!document || slot.kind === "camera") return;
      const placement = placementForSlot(slot);
      if (!placement) return;
      try {
        const isChar = "characterId" in placement;
        const updated = isChar
          ? await spatialMapApi.updateCharacter(projectId, document.id, placement.id, { miniPrompt: text })
          : await spatialMapApi.updateProp(projectId, document.id, placement.id, { miniPrompt: text });
        setDocument(updated);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to save mini prompt.");
      }
    },
    [document, placementForSlot, projectId],
  );

  // ── Cameras ───────────────────────────────────────────────────────────
  const handleAddCamera = useCallback(
    async (slot: SlotDef) => {
      if (!document || slot.kind !== "camera") return;
      try {
        const updated = await spatialMapApi.createCamera(projectId, document.id, {
          label: `C${slot.index + 1}`,
          cameraSlot: slot.index,
          orientation: "N",
          fovPreset: "medium",
          gridRow: -1,
          gridColumn: -1,
          normalizedX: null,
          normalizedY: null,
        });
        const newCamera = updated.cameras.find((c) => c.cameraSlot === slot.index);
        setDocument(updated);
        setActiveSlot({ kind: "camera", index: slot.index });
        if (newCamera) {
          setSelectedCameraId(newCamera.id);
          setSelectedPlacementId(null);
          setPlacementMode(null);
        }
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to add camera.");
      }
    },
    [document, projectId],
  );

  const handleRotateCamera = useCallback(
    async (cameraId: string, orientation: string) => {
      if (!document) return;
      try {
        const updated = await spatialMapApi.updateCamera(projectId, document.id, cameraId, {
          orientation,
          yawDegrees: orientationToYaw(orientation),
        });
        setDocument(updated);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to rotate camera.");
      }
    },
    [document, projectId],
  );

  const handleFovCamera = useCallback(
    async (cameraId: string, fovPreset: string) => {
      if (!document) return;
      const nextFov = String(fovPreset || "medium").trim().toLowerCase();
      setDocument((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          cameras: prev.cameras.map((c) => (c.id === cameraId ? { ...c, fovPreset: nextFov } : c)),
        };
      });
      try {
        const updated = await spatialMapApi.updateCamera(projectId, document.id, cameraId, { fovPreset: nextFov });
        setDocument({
          ...updated,
          cameras: updated.cameras.map((c) =>
            c.id === cameraId ? { ...c, fovPreset: String(c.fovPreset || nextFov).trim().toLowerCase() } : c,
          ),
        });
      } catch (err) {
        setDocument(document);
        setOpMsg(err instanceof Error ? err.message : "Failed to set camera FOV.");
      }
    },
    [document, projectId],
  );

  const handleMoveCamera = useCallback((cameraId: string) => {
    const camera = findCamera(cameraId);
    if (!camera) return;
    beginPlacement("move", "camera", camera.id, camera.cameraSlot >= 0 ? `C${camera.cameraSlot + 1}` : camera.label, Math.max(0, camera.cameraSlot));
  }, [beginPlacement, findCamera]);

  const handleRemoveCamera = useCallback(
    async (cameraId: string) => {
      if (!document) return;
      try {
        const updated = await spatialMapApi.removeCamera(projectId, document.id, cameraId);
        setDocument(updated);
        if (selectedCameraId === cameraId) setSelectedCameraId(null);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to remove camera.");
      }
    },
    [document, projectId, selectedCameraId],
  );

  // ── Reset map ─────────────────────────────────────────────────────────
  const handleResetMap = useCallback(async () => {
    if (!document) return;
    const hasPlacements =
      document.characters.some((p) => p.gridRow >= 0 || p.miniPrompt) ||
      document.props.some((p) => p.gridRow >= 0 || p.miniPrompt) ||
      document.cameras.some((c) => c.gridRow >= 0);
    if (hasPlacements) {
      const ok = window.confirm(
        "Reset map? This clears placement coordinates and mini-prompts. Characters, props, cameras, the Atlas Shot, and Library assets are kept.",
      );
      if (!ok) return;
    }
    try {
      let doc = document;
      for (const c of doc.characters) {
        doc = await spatialMapApi.updateCharacter(projectId, doc.id, c.id, { gridRow: -1, gridColumn: -1, normalizedX: null, normalizedY: null, miniPrompt: "" });
      }
      for (const p of doc.props) {
        doc = await spatialMapApi.updateProp(projectId, doc.id, p.id, { gridRow: -1, gridColumn: -1, normalizedX: null, normalizedY: null, miniPrompt: "" });
      }
      for (const cam of doc.cameras) {
        doc = await spatialMapApi.updateCamera(projectId, doc.id, cam.id, { gridRow: -1, gridColumn: -1, normalizedX: null, normalizedY: null });
      }
      // Reset grid scale to neutral.
      doc = await spatialMapApi.updateMap(projectId, doc.id, { gridScale: DEFAULT_GRID_SCALE });
      setDocument(doc);
      setSelectedPlacementId(null);
      setSelectedCameraId(null);
      setPlacementMode(null);
      setOccupiedMessage(null);
      setOpMsg("Map reset.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Reset failed.");
    }
  }, [document, projectId]);

  // ── Render ────────────────────────────────────────────────────────────
  if (busy.loading) {
    return <p className="spatial-map__busy" data-testid="spatial-map-loading">Loading Spatial Map…</p>;
  }
  if (busy.error) {
    return (
      <div data-testid="spatial-map-error">
        <CoDirectorEmptyState
          title="Spatial Map could not load"
          description={busy.error}
          action={<button type="button" className="ui-btn ui-btn--secondary" onClick={() => void loadMap()}>Retry</button>}
        />
      </div>
    );
  }

  const hasBackground = !!document?.backgroundAssetId;
  const bgUrl = document?.backgroundAssetId ? api.assetUrl(document.backgroundAssetId) : "";
  const ersExists = !!ersCompositeAssetId;
  const isGenerating = busyOp !== null;
  const selectedCamera = findCamera(selectedCameraId);

  const placementBannerText = (function () {
    if (!placementMode) return '';
    const verb = placementMode.action === 'move' ? 'Moving' : 'Placing';
    const slot = activePlacement ? activePlacement.slot : 0;
    const type = activePlacement ? activePlacement.type : placementMode.kind;
    const slotName = type === 'character' ? ('Character ' + String(slot + 1)) : type === 'prop' ? ('Prop ' + String(slot + 1)) : ('C' + String(slot + 1));
    const raw = placementMode.label || '';
    const entity = raw.indexOf(' — ') >= 0 ? raw.split(' — ').slice(-1)[0] : raw;
    if (entity && entity !== slotName) return verb + ': ' + slotName + ' — ' + entity;
    return verb + ': ' + slotName;
  })();

  return (
    <div className="spatial-map" data-testid="spatial-map-panel">
      {!hasBackground ? (
        <>
          <h3 className="spatial-map__heading">Spatial Map</h3>
          <p className="spatial-map__subtitle">Start with an environment reference.</p>
          <p className="spatial-map__tip">
            An Atlas Shot is a roofless, top-down reference view designed specifically for Spatial Map.
          </p>
          <input
            ref={emptyFileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                void handleUploadImage(f);
              }
              e.target.value = "";
            }}
          />
          <div className="spatial-map__empty-actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => void startAtlasGeneration()}
              disabled={isGenerating}
              aria-label="Create Atlas Shot with Co-Director (recommended)"
            >
              {busyOp === "atlas" ? "Generating Atlas Shot…" : "Create Atlas Shot with Co-Director"}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={handleChooseFromLibrary}
              disabled={isGenerating}
              aria-label="Choose Atlas Shot from Library"
            >
              Choose from Library
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={() => emptyFileInputRef.current?.click()}
              disabled={isGenerating}
              aria-label="Upload an image as the Atlas Shot"
            >
              Upload Image
            </button>
          </div>
          {opMsg ? <p className="spatial-map__hint">{opMsg}</p> : null}
          {libraryPickerOpen ? (
            <EntityPicker
              kind="environment"
              projectId={projectId}
              title="Choose Atlas Shot from Library"
              onClose={() => setLibraryPickerOpen(false)}
              onConfirm={async (assetId) => {
                setLibraryPickerOpen(false);
                try {
                  const doc = await spatialMapApi.createMap(projectId, { title: "Spatial Map", backgroundAssetId: assetId });
                  setDocument(doc);
                } catch (err) {
                  setOpMsg(err instanceof Error ? err.message : "Failed to create map.");
                }
              }}
            />
          ) : null}
        </>
      ) : (
        <>
          <h3 className="spatial-map__heading">{document?.title || "Spatial Map"}</h3>

          <div className="spatial-map__atlas-panel" data-testid="active-atlas-panel">
            <div className="spatial-map__atlas-thumb">
              <img src={bgUrl} alt="Active Atlas Shot" />
            </div>
            <div className="spatial-map__atlas-info">
              <p className="spatial-map__atlas-label">Active Atlas Shot</p>
              <p className="spatial-map__atlas-source muted">
                {document?.backgroundAssetId ? `Asset ${document.backgroundAssetId.slice(0, 8)}…` : "No Atlas"}
              </p>
            </div>
            <div className="spatial-map__atlas-actions">
              <button type="button" className="ui-btn ui-btn--secondary spatial-map__atlas-btn" onClick={() => onGoTab?.("library")} aria-label="View Atlas Shot in Library" data-testid="atlas-view-btn">View</button>
              <button type="button" className="ui-btn ui-btn--secondary spatial-map__atlas-btn" onClick={handleReplaceFromLibrary} disabled={isGenerating} aria-label="Replace Atlas Shot" data-testid="atlas-replace-btn">Replace</button>
              <button type="button" className="ui-btn ui-btn--secondary spatial-map__atlas-btn" onClick={() => void handleReplaceGenerate()} disabled={isGenerating} aria-label="Generate another Atlas Shot with Co-Director" data-testid="atlas-regenerate-btn">Generate New</button>
              <button type="button" className="ui-btn ui-btn--secondary spatial-map__atlas-btn spatial-map__atlas-remove" onClick={() => void handleRemoveAtlas()} aria-label="Remove Atlas Shot from Spatial Map" data-testid="atlas-remove-btn">Remove</button>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                if (document?.backgroundAssetId) {
                  void handleReplaceUpload(f);
                } else {
                  void handleUploadImage(f);
                }
              }
              e.target.value = "";
            }}
          />

          <div className="spatial-map__grid-scale" data-testid="placement-precision-control">
            <span className="spatial-map__grid-scale-label">Placement Precision</span>
            <button
              type="button"
              className="spatial-map__grid-scale-btn"
              aria-label="Decrease placement precision"
              title={gridScale <= MIN_GRID_SCALE ? "Already at lowest placement precision" : "Decrease placement precision"}
              disabled={gridScale <= MIN_GRID_SCALE}
              onClick={() => void handleGridScale(-1)}
              data-testid="grid-scale-minus"
            >
              −
            </button>
            <span className="spatial-map__grid-scale-value" data-testid="grid-scale-value">
              {gridScaleLabel(gridScale)}
            </span>
            <button
              type="button"
              className="spatial-map__grid-scale-btn"
              aria-label="Increase placement precision"
              title={gridScale >= MAX_GRID_SCALE ? "Already at highest placement precision" : "Increase placement precision"}
              disabled={gridScale >= MAX_GRID_SCALE}
              onClick={() => void handleGridScale(1)}
              data-testid="grid-scale-plus"
            >
              +
            </button>
            <span className="spatial-map__grid-scale-label" data-testid="cell-size-label">Cell Size</span>
          </div>

          <div className="spatial-map__actions" data-testid="map-controls">
            <button type="button" className="spatial-map__slot-action" aria-label="Show grid" aria-pressed={showGrid} data-testid="map-toggle-grid" onClick={() => setShowGrid((v) => !v)}>Grid</button>
            <button type="button" className="spatial-map__slot-action" aria-label="Show circles" aria-pressed={showCircles} data-testid="map-toggle-circles" onClick={() => setShowCircles((v) => !v)}>Circles</button>
            <button type="button" className="spatial-map__slot-action" aria-label="Show labels" aria-pressed={showLabels} data-testid="map-toggle-labels" onClick={() => setShowLabels((v) => !v)}>Labels</button>
            <button type="button" className="spatial-map__slot-action" data-testid="map-zoom-out" aria-label="Zoom out" disabled={zoom <= 0.75} onClick={() => setZoom((z) => Math.max(0.75, Math.round((z - 0.25) * 100) / 100))}>−</button>
            <button type="button" className="spatial-map__slot-action" data-testid="map-zoom-in" aria-label="Zoom in" disabled={zoom >= 1.5} onClick={() => setZoom((z) => Math.min(1.5, Math.round((z + 0.25) * 100) / 100))}>+</button>
          </div>

          {placementMode ? (
            <div className="spatial-map__placement-banner" data-testid="placement-mode-banner">
              <span>
                {placementBannerText}
              </span>
              <button
                type="button"
                className="spatial-map__slot-action"
                onClick={clearPlacementMode}
                data-testid="placement-mode-cancel"
              >
                Cancel
              </button>
            </div>
          ) : null}

          <SpatialGrid
            backgroundAssetId={document!.backgroundAssetId!}
            imageUrl={bgUrl}
            placements={placements}
            cameras={document?.cameras || []}
            selectedPlacementId={selectedPlacementId}
            selectedCameraId={selectedCameraId}
            occupiedMessage={occupiedMessage}
            gridScale={gridScale}
            placementActive={!!placementMode}
            showGrid={showGrid}
            showCircles={showCircles}
            showLabels={showLabels}
            zoom={zoom}
            onCellClick={handleCellClick}
            onSelectPlacement={(id) => {
              setSelectedPlacementId(id);
              setSelectedCameraId(null);
              if (id) {
                const p = findPlacement(id);
                if (p && p.slotIndex >= 0) {
                  setActiveSlot({ kind: "characterId" in p ? "character" : "prop", index: p.slotIndex });
                }
              }
            }}
            onSelectCamera={(id) => {
              setSelectedCameraId(id);
              setSelectedPlacementId(null);
              if (id) {
                const c = findCamera(id);
                if (c && c.cameraSlot >= 0) {
                  setActiveSlot({ kind: "camera", index: c.cameraSlot });
                }
              }
            }}
          />

          {selectedCamera ? (
            <CameraInspector
              camera={selectedCamera}
              onRotate={(orientation) => void handleRotateCamera(selectedCamera.id, orientation)}
              onFovChange={(fovPreset) => void handleFovCamera(selectedCamera.id, fovPreset)}
              onMove={() => handleMoveCamera(selectedCamera.id)}
              onRemove={() => void handleRemoveCamera(selectedCamera.id)}
            />
          ) : null}

          <div className="spatial-map__slots">
            <div className="spatial-map__slot-group">
              <p className="spatial-map__slot-group-title">Characters</p>
              {CHARACTER_SLOTS.map((slot) => {
                const placement = placementForSlot(slot);
                return (
                  <PlacementSlot
                    key={`char-${slot.index}`}
                    slot={slot}
                    placement={placement}
                    active={activeSlot?.kind === "character" && activeSlot?.index === slot.index}
                    savedOptions={savedCharacters}
                    placing={placementMode?.kind === "character" && placementMode.id === placement?.id}
                    onSelect={() => {
                      if (placement) {
                        const placed = (typeof placement.normalizedX === "number" && typeof placement.normalizedY === "number") || (placement.gridRow >= 0 && placement.gridColumn >= 0);
                        beginPlacement(placed ? "move" : "place", "character", placement.id, `${slot.label} — ${placement.label || placement.tag}`, slot.index);
                      } else {
                        setActiveSlot({ kind: "character", index: slot.index });
                      }
                    }}
                    onAdd={(option) => void handleAddCharacter(slot, option)}
                    onPlace={() => placement && beginPlacement("place", "character", placement.id, placement.label || placement.tag, slot.index)}
                    onMove={() => placement && beginPlacement("move", "character", placement.id, placement.label || placement.tag, slot.index)}
                    onRemove={() => void handleSlotRemove(slot)}
                    onUpdateMiniPrompt={(text) => void handleUpdateMiniPrompt(slot, text)}
                    visible={placement ? placement.visible : undefined}
                    onToggleVisible={() => placement && void handleToggleVisible("character", placement.id, placement.visible === false)}
                  />
                );
              })}
            </div>
            <div className="spatial-map__slot-group">
              <p className="spatial-map__slot-group-title">Props</p>
              {PROP_SLOTS.map((slot) => {
                const placement = placementForSlot(slot);
                return (
                  <PlacementSlot
                    key={`prop-${slot.index}`}
                    slot={slot}
                    placement={placement}
                    active={activeSlot?.kind === "prop" && activeSlot?.index === slot.index}
                    savedOptions={savedProps}
                    placing={placementMode?.kind === "prop" && placementMode.id === placement?.id}
                    onSelect={() => {
                      if (placement) {
                        const placed = (typeof placement.normalizedX === "number" && typeof placement.normalizedY === "number") || (placement.gridRow >= 0 && placement.gridColumn >= 0);
                        beginPlacement(placed ? "move" : "place", "prop", placement.id, `${slot.label} — ${placement.label || placement.tag}`, slot.index);
                      } else {
                        setActiveSlot({ kind: "prop", index: slot.index });
                      }
                    }}
                    onAdd={(option) => void handleAddProp(slot, option)}
                    onPlace={() => placement && beginPlacement("place", "prop", placement.id, placement.label || placement.tag, slot.index)}
                    onMove={() => placement && beginPlacement("move", "prop", placement.id, placement.label || placement.tag, slot.index)}
                    onRemove={() => void handleSlotRemove(slot)}
                    onUpdateMiniPrompt={(text) => void handleUpdateMiniPrompt(slot, text)}
                    visible={placement ? placement.visible : undefined}
                    onToggleVisible={() => placement && void handleToggleVisible("prop", placement.id, placement.visible === false)}
                  />
                );
              })}
            </div>
            <div className="spatial-map__slot-group">
              <p className="spatial-map__slot-group-title">Cameras</p>
              {CAMERA_SLOTS.map((slot) => {
                const camera = cameraForSlot(slot);
                const placed = !!(
                  camera &&
                  ((typeof camera.normalizedX === "number" && typeof camera.normalizedY === "number") ||
                    (camera.gridRow >= 0 && camera.gridColumn >= 0))
                );
                return (
                  <div
                    key={`cam-${slot.index}`}
                    className={`spatial-map__camera-slot${activeSlot?.kind === "camera" && activeSlot?.index === slot.index ? " is-active" : ""}${camera ? " is-placed" : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-pressed={!!(activeSlot?.kind === "camera" && activeSlot?.index === slot.index)}
                    aria-current={activeSlot?.kind === "camera" && activeSlot?.index === slot.index && camera ? "true" : undefined}
                    aria-label={`${slot.label}${camera ? ", assigned" : ", empty"}${activeSlot?.kind === "camera" && activeSlot?.index === slot.index && camera ? ", active" : ""}`}
                    onClick={() => {
                      if (!camera) return;
                      beginPlacement(placed ? "move" : "place", "camera", camera.id, slot.label, slot.index);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        if (!camera) return;
                        beginPlacement(placed ? "move" : "place", "camera", camera.id, slot.label, slot.index);
                      }
                    }}
                    data-testid={`camera-slot-${slot.index}`}
                  >
                    {activeSlot && activeSlot.kind === 'camera' && activeSlot.index === slot.index && camera ? (
                      <span className='spatial-map__active-badge' data-testid={'slot-active-badge-camera-' + String(slot.index)}>ACTIVE</span>
                    ) : null}
                    <span className="spatial-map__slot-label">{slot.label}</span>
                    {camera ? (
                      <span className="spatial-map__slot-status">
                        {camera.orientation || "N"} · {String(camera.fovPreset || "medium").toLowerCase()}
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="spatial-map__slot-add"
                        aria-label={`Add ${slot.label}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleAddCamera(slot);
                        }}
                        data-testid={`camera-add-${slot.index}`}
                      >
                        Add Camera
                      </button>
                    )}
                    {camera ? (
                      <div className="spatial-map__slot-actions">
                        <button
                          type="button"
                          className="spatial-map__slot-action"
                          aria-label={`Toggle visibility of ${slot.label}`}
                          aria-pressed={camera.visible !== false}
                          data-testid={`camera-visible-${slot.index}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleToggleVisible("camera", camera.id, camera.visible === false);
                          }}
                        >
                          Visible
                        </button>
                        {!placed ? (
                          <button
                            type="button"
                            className="spatial-map__slot-action"
                            onClick={(e) => {
                              e.stopPropagation();
                              beginPlacement("place", "camera", camera.id, slot.label, slot.index);
                            }}
                            aria-label={`Place ${slot.label}`}
                            data-testid={`camera-place-${slot.index}`}
                          >
                            Place
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="spatial-map__slot-action"
                            onClick={(e) => {
                              e.stopPropagation();
                              beginPlacement("move", "camera", camera.id, slot.label, slot.index);
                            }}
                            aria-label={`Move ${slot.label}`}
                            data-testid={`camera-move-${slot.index}`}
                          >
                            Move
                          </button>
                        )}
                        <button
                          type="button"
                          className="spatial-map__slot-remove"
                          aria-label={`Remove ${slot.label}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleSlotRemove(slot);
                          }}
                          data-testid={`camera-remove-${slot.index}`}
                        >
                          Remove
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="spatial-map__actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => void startErsGeneration()}
              disabled={isGenerating}
              aria-label={ersExists ? "Regenerate Environment Reference Sheet" : "Generate Environment Reference Sheet"}
            >
              {busyOp === "ers" ? "Generating ERS…" : ersExists ? "Regenerate Environment Reference Sheet" : "Generate Environment Reference Sheet"}
            </button>
            <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void handleResetMap()} aria-label="Reset map placements">
              Reset Map
            </button>
          </div>

          {opMsg ? <p className="spatial-map__hint">{opMsg}</p> : null}

          {ersExists && ersCompositeAssetId ? (
            <ErsResultDisplay
              ersCompositeAssetId={ersCompositeAssetId}
              onRegenerate={() => void startErsGeneration()}
              onOpenInLibrary={() => onGoTab?.("library")}
              onUseInSceneCreator={() => onGoTab?.("scene_creator")}
            />
          ) : null}
        </>
      )}

      {replacePickerOpen && document ? (
        <EntityPicker
          kind="environment"
          projectId={projectId}
          title="Replace Atlas Shot from Library"
          onClose={() => setReplacePickerOpen(false)}
          onConfirm={async (assetId) => {
            setReplacePickerOpen(false);
            try {
              const updated = await spatialMapApi.updateMap(projectId, document.id, { backgroundAssetId: assetId });
              setDocument(updated);
              setOpMsg("Atlas Shot replaced from Library.");
            } catch (err) {
              setOpMsg(err instanceof Error ? err.message : "Failed to replace Atlas.");
            }
          }}
        />
      ) : null}
    </div>
  );
}

function normalizeExecution(res: any) {
  return {
    mode: "agent_work" as const,
    execution_id: String(res?.execution_id || res?.executionId || res?.id || ""),
    capability: String(res?.capability || "atlas.generate"),
    surface_type: (res?.surface_type || res?.surfaceType || "atlas_shot_generation") as any,
    status: String(res?.status || "running"),
    progress: Number(res?.progress || 0),
    focused_artifact_ids: Array.isArray(res?.focused_artifact_ids) ? res.focused_artifact_ids : [],
    child_jobs: Array.isArray(res?.child_jobs) ? res.child_jobs : [],
    result_asset_ids: Array.isArray(res?.result_asset_ids) ? res.result_asset_ids : [],
    collection_id: res?.collection_id ?? null,
    error: res?.error ?? null,
    project_id: res?.project_id || res?.projectId || "",
  };
}
