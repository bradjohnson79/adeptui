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
import { ERSGenerationMonitor } from "./ERSGenerationMonitor";
import { ERS_GENERATOR_OPTIONS } from "./ersGenerator";
import { useErsGeneration } from "./useErsGeneration";
import { persistThenOpenSceneCreator } from "../SceneCreator/persistThenOpenSceneCreator";
import { CharacterInspector } from "./CharacterInspector";
import { PlacementSlot } from "./PlacementSlot";
import { PropAttachmentEditor, type PropAttachmentApply } from "./PropAttachmentEditor";
import { SpatialGrid, toGridPlacements } from "./SpatialGrid";
import { spatialMapApi } from "./spatialMapApi";
import { CameraInspector } from "./CameraInspector";
import {
  assignedSpatialMapCharacters,
  attachedPropsForCharacter,
  independentAssignedProps,
  INDEPENDENT_ATTACHMENT,
  isAttachedProp,
  normalizeMapDocumentProps,
} from "./attachmentUi";
import {
  ENTITY_ENABLED_SWITCH_LABEL,
  isEntityEnabled,
  placementSwitchAriaLabel,
  slotPlacementBadge,
} from "./placementArm";
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
  SLOT_COLORS,
  type ActivePlacement,
  type SlotDef,
  type SpatialCamera,
  type SpatialCharacterPlacement,
  type SpatialMapDocument,
  type SpatialPropPlacement,
  propPlacementIdentity,
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

// Atlas Scene Intent law: manual Atlas creation requires a short description.
// Mirrors the light server-side validation (studio-api spatial_map/scene_intent.py).
const SCENE_DESCRIPTION_MIN = 12;
const GENERIC_SCENE_WORDS = new Set([
  "test", "room", "scene", "image", "atlas", "place", "location",
  "environment", "stuff", "thing", "asdf", "n/a", "none",
]);

function sceneDescriptionError(text: string): string | null {
  const cleaned = text.trim().replace(/\s+/g, " ");
  const norm = cleaned.toLowerCase();
  if (!norm) return "Describe this location in a few words first — it guides the Atlas Shot and the Environment Reference Sheet.";
  if (norm.length < SCENE_DESCRIPTION_MIN) {
    return "Describe this location in a few more words — what kind of place is it and what is the scene for?";
  }
  if (GENERIC_SCENE_WORDS.has(norm)) {
    return `"${cleaned}" is too generic. Name the kind of place (e.g. "a warm neighborhood coffee shop for our commercial").`;
  }
  return null;
}

/**
 * CDX-021: an Atlas Shot is applied to the existing map document whenever one
 * exists — including the post-Remove empty state — so placements are never
 * orphaned into a brand-new document. A new document is created only when no
 * map exists yet.
 */
export function atlasReuseDecision(document: SpatialMapDocument | null): "reuse" | "create" {
  return document ? "reuse" : "create";
}

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
  const [attachmentEditor, setAttachmentEditor] = useState<
    | { source: "prop"; propId: string }
    | { source: "character"; characterId: string; propId?: string }
    | null
  >(null);
  const [savedCharacters, setSavedCharacters] = useState<SavedOption[]>([]);
  const [savedProps, setSavedProps] = useState<SavedOption[]>([]);
  const [busyOp, setBusyOp] = useState<PendingCoDirectorOp>(null);
  const [opMsg, setOpMsg] = useState<string | null>(null);
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [replacePickerOpen, setReplacePickerOpen] = useState(false);
  const [sceneDescription, setSceneDescription] = useState("");
  const [sceneDetailsOpen, setSceneDetailsOpen] = useState(false);
  const [sceneEditOpen, setSceneEditOpen] = useState(false);
  const [sceneEditText, setSceneEditText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const emptyFileInputRef = useRef<HTMLInputElement>(null);
  const ers = useErsGeneration({
    projectId,
    spatialMapId: document?.id || null,
    document,
    activeExecution,
    setActiveExecution,
  });


  // ── Load most recent map on mount / project change ───────────────────────
  const loadMap = useCallback(async () => {
    setBusy({ loading: true, error: null });
    try {
      const doc = await spatialMapApi.getMostRecentMap(projectId);
      setDocument(doc ? normalizeMapDocumentProps(doc) : null);
    } catch (err) {
      setBusy({ loading: false, error: err instanceof Error ? err.message : String(err) });
      return;
    }
    setBusy({ loading: false, error: null });
  }, [projectId]);

  const handleUseInSceneCreator = useCallback(async () => {
    setOpMsg(null);
    try {
      await persistThenOpenSceneCreator({
        projectId,
        sceneId: document?.sceneId || undefined,
        spatialMapId: document?.id || undefined,
        onGoTab,
      });
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Could not continue to Scene Creator.");
    }
  }, [document?.id, document?.sceneId, onGoTab, projectId]);

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
        try {
          const projectProps = await api.propCreator.list(projectId, true);
          for (const prop of projectProps.props || []) {
            const visual = prop.approved_asset_id || prop.library_asset_id || "";
            if (!prop.id || seen.has(`project:${prop.id}`)) continue;
            seen.add(`project:${prop.id}`);
            if (visual) seen.add(`library:${visual}`);
            propOptions.push({
              id: prop.id,
              name: prop.display_label || prop.tag || "Prop",
              assetId: visual || null,
              source: "project",
            });
          }
        } catch {
          // project props are optional until Prop Creator is used
        }
        for (const character of characters) {
          try {
            const propsRes = (await api.listCharacterProps(projectId, character.id)) as {
              items?: Array<{ id: string; name: string; library_asset_id?: string | null }>;
            };
            for (const prop of propsRes.items || []) {
              if (!prop.id || seen.has(`character:${prop.id}`)) continue;
              seen.add(`character:${prop.id}`);
              if (prop.library_asset_id) seen.add(`library:${prop.library_asset_id}`);
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
            if (seen.has(`library:${asset.id}`)) continue;
            seen.add(`library:${asset.id}`);
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

  const ghostColor = (() => {
    if (!placementMode || !activeSlot) return undefined;
    if (activeSlot.kind === "character") return SLOT_COLORS[CHARACTER_SLOTS[activeSlot.index]?.colorKey || "red"];
    if (activeSlot.kind === "prop") return SLOT_COLORS[PROP_SLOTS[activeSlot.index]?.colorKey || "purple"];
    return SLOT_COLORS.gray;
  })();

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

  // Reuse-or-create for the Atlas Shot (CDX-021): when a map document already
  // exists — including the post-Remove empty state — update it in place so
  // placements are never orphaned into a brand-new document. A new document is
  // created only when no map exists yet.
  const applyAtlasToMap = useCallback(
    async (
      backgroundAssetId: string,
      lineage: {
        sceneDescription?: string;
        sceneIntent?: SpatialMapDocument["sceneIntent"];
        originalEnvironmentReferenceAssetId?: string;
      },
    ) => {
      if (document && atlasReuseDecision(document) === "reuse") {
        const updated = await spatialMapApi.updateMap(projectId, document.id, {
          backgroundAssetId,
          ...lineage,
        });
        setDocument(updated);
        return updated;
      }
      const doc = await spatialMapApi.createMap(projectId, {
        title: "Spatial Map",
        backgroundAssetId,
        ...lineage,
      });
      setDocument(doc);
      return doc;
    },
    [document, projectId],
  );

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
              // Scene Intent lineage: prefer the snapshot compiled by the
              // atlas.generate handler (CD path); fall back to the creator's
              // description typed in this panel (manual path).
              const atlasMeta = (activeExecution.child_jobs?.[0] as { metadata?: Record<string, unknown> } | undefined)?.metadata || {};
              const snapshottedIntent = (atlasMeta.scene_intent as SpatialMapDocument["sceneIntent"]) || undefined;
              const origRefs = Array.isArray(atlasMeta.original_environment_reference_asset_ids)
                ? (atlasMeta.original_environment_reference_asset_ids as unknown[]).map(String).filter(Boolean)
                : [];
              const description = sceneDescription.trim();
              const lineage = {
                sceneDescription: description || undefined,
                sceneIntent: snapshottedIntent,
                originalEnvironmentReferenceAssetId: origRefs[0] || undefined,
              };
              const updated = await applyAtlasToMap(atlasAssetId, lineage);
              setDocument(updated);
              setOpMsg(
                document
                  ? document.backgroundAssetId
                    ? "Atlas Shot replaced."
                    : "Atlas Shot generated."
                  : "Atlas Shot generated and Spatial Map created.",
              );
              setBusyOp(null);
            } catch (err) {
              setOpMsg(err instanceof Error ? err.message : "Failed to create map from Atlas Shot.");
              setBusyOp(null);
            }
          })();
        }
      } else if (activeExecution.status === "failed" || activeExecution.status === "cancelled") {
        if (busyOp === "ers") return;
        setOpMsg(activeExecution.error || `${busyOp || "Operation"} failed.`);
        setBusyOp(null);
      }
    }
  }, [activeExecution?.status, activeExecution?.execution_id, activeExecution?.result_asset_ids?.length, applyAtlasToMap, projectId, busyOp, document, sceneDescription]);

  // ── Atlas Shot / ERS generation ────────────────────────────────────────
  const startAtlasGeneration = useCallback(async () => {
    setOpMsg(null);
    const descError = sceneDescriptionError(sceneDescription);
    if (descError) {
      setOpMsg(descError);
      return;
    }
    const description = sceneDescription.trim();
    setBusyOp("atlas");
    try {
      const sourceId =
        document?.originalEnvironmentReferenceAssetId ||
        document?.backgroundAssetId ||
        "";
      const res = await api.startExecution(projectId, {
        capability: "atlas.generate",
        context: {
          scene_description: description,
          prompt: description,
          ...(sourceId ? { attachment_asset_ids: [sourceId] } : {}),
        },
      });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start Atlas Shot generation.");
      setBusyOp(null);
    }
  }, [projectId, document, sceneDescription, setActiveExecution]);

  const startErsGeneration = useCallback(() => {
    void ers.start();
  }, [ers.start]);

  // ── Library / upload / replace / remove atlas ──────────────────────────
  const handleChooseFromLibrary = () => setLibraryPickerOpen(true);
  const handleReplaceFromLibrary = () => setReplacePickerOpen(true);

  const handleReplaceUpload = useCallback(async (file: File) => {
    if (!document) return;
    setOpMsg(null);
    const description = sceneDescription.trim() || document.sceneIntent?.summary || "";
    const descError = sceneDescriptionError(description);
    if (descError) {
      setOpMsg(descError);
      return;
    }
    setBusyOp("atlas");
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      const updated = await spatialMapApi.updateMap(projectId, document.id, {
        backgroundAssetId: asset.id,
        sceneDescription: description,
        originalEnvironmentReferenceAssetId: asset.id,
      });
      setDocument(updated);
      setOpMsg("Atlas Shot replaced.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Replace failed.");
    } finally {
      setBusyOp(null);
    }
  }, [projectId, document, sceneDescription]);

  const handleSaveSceneDescription = useCallback(async () => {
    if (!document) return;
    const descError = sceneDescriptionError(sceneEditText);
    if (descError) {
      setOpMsg(descError);
      return;
    }
    setOpMsg(null);
    try {
      const updated = await spatialMapApi.updateMap(projectId, document.id, {
        sceneDescription: sceneEditText.trim(),
      });
      setDocument(updated);
      setSceneEditOpen(false);
      setOpMsg("Scene description updated. Environment Reference Sheet now needs regeneration.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to save scene description.");
    }
  }, [projectId, document, sceneEditText]);

  const handleReplaceGenerate = useCallback(async () => {
    if (!document) return;
    setOpMsg(null);
    const description = sceneDescription.trim() || document.sceneIntent?.summary || "";
    const descError = sceneDescriptionError(description);
    if (descError) {
      setOpMsg(descError);
      return;
    }
    if (!sceneDescription.trim()) setSceneDescription(description);
    setBusyOp("atlas");
    try {
      const sourceId =
        document.originalEnvironmentReferenceAssetId ||
        document.backgroundAssetId ||
        "";
      const res = await api.startExecution(projectId, {
        capability: "atlas.generate",
        context: {
          scene_description: description,
          prompt: description,
          ...(sourceId ? { attachment_asset_ids: [sourceId] } : {}),
        },
      });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start Atlas Shot generation.");
      setBusyOp(null);
    }
  }, [projectId, document, sceneDescription, setActiveExecution]);

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
    const descError = sceneDescriptionError(sceneDescription);
    if (descError) {
      setOpMsg(descError);
      return;
    }
    const description = sceneDescription.trim();
    setBusyOp("atlas");
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      await applyAtlasToMap(asset.id, {
        sceneDescription: description,
        originalEnvironmentReferenceAssetId: asset.id,
      });
      setOpMsg(document ? "Image uploaded and applied to the Spatial Map." : "Image uploaded and Spatial Map created.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusyOp(null);
    }
  }, [applyAtlasToMap, document, projectId, sceneDescription]);

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
          updated = await spatialMapApi.updateProp(projectId, document.id, placementMode.id, {
            ...coords,
            ...INDEPENDENT_ATTACHMENT,
          });
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
        const created = updated.characters.find((c) => c.slotIndex === slot.index);
        if (created) {
          setPlacementMode({ action: "place", kind: "character", id: created.id, label: `${slot.label} — ${created.label || created.tag}` });
          setActiveSlot({ kind: "character", index: slot.index });
          setSelectedPlacementId(created.id);
          setSelectedCameraId(null);
        } else {
          setActiveSlot({ kind: "character", index: slot.index });
        }
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
        const identity = propPlacementIdentity(option);
        const updated = await spatialMapApi.placeProp(projectId, document.id, {
          label: option.name,
          assetId: option.assetId || null,
          propId: identity.propId,
          category: identity.category,
          state: "default",
          tag: option.name,
          slotIndex: slot.index,
          colorKey: slot.colorKey,
          miniPrompt: "",
          gridRow: -1,
          gridColumn: -1,
          normalizedX: null,
          normalizedY: null,
          placementMode: "independent",
          attachedCharacterSlot: null,
          attachedCharacterId: null,
          relationship: null,
          attachmentPoint: null,
        });
        setDocument(normalizeMapDocumentProps(updated));
        const created = updated.props.find((item) => item.slotIndex === slot.index);
        if (created) {
          setPlacementMode({ action: "place", kind: "prop", id: created.id, label: `${slot.label} — ${created.label || created.tag}` });
          setActiveSlot({ kind: "prop", index: slot.index });
          setSelectedPlacementId(created.id);
          setSelectedCameraId(null);
        } else {
          setActiveSlot({ kind: "prop", index: slot.index });
        }
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

  const assignedCharacters = useMemo(
    () => assignedSpatialMapCharacters(document?.characters || []),
    [document?.characters],
  );

  const handleApplyAttachment = useCallback(
    async (propId: string, payload: PropAttachmentApply) => {
      if (!document || !payload.relationship) return;
      try {
        const existing = document.props.find((item) => item.id === propId);
        const sameCharacter = !!(
          existing &&
          isAttachedProp(existing) &&
          existing.attachedCharacterSlot === payload.attachedCharacterSlot &&
          (existing.attachedCharacterId || "") === (payload.attachedCharacterId || "")
        );
        const updated = sameCharacter
          ? await spatialMapApi.updatePropRelationship(projectId, document.id, propId, {
              relationship: payload.relationship,
              attachmentPoint: payload.attachmentPoint,
            })
          : await spatialMapApi.attachProp(projectId, document.id, propId, {
              placementMode: "attached",
              attachedCharacterSlot: payload.attachedCharacterSlot,
              attachedCharacterId: payload.attachedCharacterId,
              relationship: payload.relationship,
              attachmentPoint: payload.attachmentPoint,
            });
        setDocument(normalizeMapDocumentProps(updated));
        setAttachmentEditor(null);
        if (placementMode?.id === propId) {
          setPlacementMode(null);
          setOccupiedMessage(null);
        }
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to attach prop.");
      }
    },
    [document, projectId, placementMode],
  );

  const handleDetachAndPlace = useCallback(
    async (prop: SpatialPropPlacement) => {
      if (!document) return;
      try {
        const updated = await spatialMapApi.detachProp(projectId, document.id, prop.id);
        setDocument(normalizeMapDocumentProps(updated));
        setAttachmentEditor(null);
        // Arm this prop as the active independent placement; next cell click places it.
        beginPlacement("place", "prop", prop.id, prop.label || prop.tag, Math.max(0, prop.slotIndex));
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to detach prop.");
      }
    },
    [document, projectId, beginPlacement],
  );

  const didAutoArmDocId = useRef<string | null>(null);
  useEffect(() => {
    if (!document) return;
    if (didAutoArmDocId.current === document.id) return;
    if (placementMode) {
      didAutoArmDocId.current = document.id;
      return;
    }
    const assigned = CHARACTER_SLOTS.map((slot) => {
      const found = document.characters.find((c) => c.slotIndex === slot.index);
      return found ? { slot, found } : null;
    }).filter((row): row is { slot: (typeof CHARACTER_SLOTS)[number]; found: (typeof document.characters)[number] } => !!row);
    if (!assigned.length) return;
    const unplaced = assigned.find(({ found }) => {
      const hasNorm = typeof found.normalizedX === "number" && typeof found.normalizedY === "number";
      return !hasNorm && (found.gridRow < 0 || found.gridColumn < 0);
    });
    const pick = unplaced || assigned[0];
    const placed = (typeof pick.found.normalizedX === "number" && typeof pick.found.normalizedY === "number") || (pick.found.gridRow >= 0 && pick.found.gridColumn >= 0);
    beginPlacement(placed ? "move" : "place", "character", pick.found.id, `${pick.slot.label} - ${pick.found.label || pick.found.tag}`, pick.slot.index);
    didAutoArmDocId.current = document.id;
  }, [document, placementMode, beginPlacement]);

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
          setPlacementMode({ action: "place", kind: "camera", id: newCamera.id, label: slot.label });
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
  const ersExists = !!ers.compositeAssetId;
  const isGenerating = busyOp !== null || ers.busy;
  const selectedCamera = findCamera(selectedCameraId);
  const selectedCharacter = selectedPlacementId
    ? document?.characters.find((c) => c.id === selectedPlacementId) || null
    : null;
  const editorProp = attachmentEditor?.propId
    ? document?.props.find((item) => item.id === attachmentEditor.propId) || null
    : null;
  const editorCharacter = attachmentEditor?.source === "character"
    ? document?.characters.find((c) => c.id === attachmentEditor.characterId) || null
    : null;
  const editorAssigned = editorCharacter
    ? assignedCharacters.find((c) => c.id === editorCharacter.characterId) || assignedSpatialMapCharacters([editorCharacter])[0] || null
    : null;

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
          <label className="spatial-map__scene-desc" data-testid="scene-description-block">
            <span className="spatial-map__scene-desc-label">
              Scene / Location Description
              <span className="spatial-map__scene-desc-tip" title="A few words about the place (e.g. &quot;a warm neighborhood coffee shop for our commercial&quot;). This guides the Atlas Shot and the Environment Reference Sheet.">(?)</span>
            </span>
            <textarea
              rows={2}
              data-testid="scene-description-input"
              placeholder="e.g. a warm neighborhood coffee shop for our commercial"
              value={sceneDescription}
              onChange={(e) => setSceneDescription(e.target.value)}
              disabled={isGenerating}
            />
          </label>
          <div className="spatial-map__empty-actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => void startAtlasGeneration()}
              disabled={isGenerating || !!sceneDescriptionError(sceneDescription)}
              aria-label="Create Atlas Shot with Co-Director (recommended)"
            >
              {busyOp === "atlas" ? "Generating Atlas Shot…" : "Create Atlas Shot with Co-Director"}
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={handleChooseFromLibrary}
              disabled={isGenerating || !!sceneDescriptionError(sceneDescription)}
              aria-label="Choose Atlas Shot from Library"
            >
              Choose from Library
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={() => emptyFileInputRef.current?.click()}
              disabled={isGenerating || !!sceneDescriptionError(sceneDescription)}
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
                const descError = sceneDescriptionError(sceneDescription);
                if (descError) {
                  setOpMsg(descError);
                  return;
                }
                const description = sceneDescription.trim();
                try {
                  await applyAtlasToMap(assetId, {
                    sceneDescription: description,
                    originalEnvironmentReferenceAssetId: assetId,
                  });
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
              {document ? (
                <div className="spatial-map__scene-context" data-testid="scene-context-summary">
                  <p className="spatial-map__scene-context-summary">
                    {document.sceneIntent?.sceneTitle || "This Scene"}: {document.sceneIntent?.summary || "No scene description yet."}
                  </p>
                  <div className="spatial-map__scene-context-actions">
                    <button
                      type="button"
                      className="spatial-map__slot-action"
                      onClick={() => setSceneDetailsOpen((v) => !v)}
                      aria-expanded={sceneDetailsOpen}
                      data-testid="scene-context-details-btn"
                    >
                      {sceneDetailsOpen ? "Hide Details" : "View Details"}
                    </button>
                    <button
                      type="button"
                      className="spatial-map__slot-action"
                      onClick={() => {
                        setSceneEditText(document.sceneIntent?.summary || "");
                        setSceneEditOpen(true);
                      }}
                      data-testid="edit-scene-description-btn"
                    >
                      Edit Scene Description
                    </button>
                  </div>
                  {sceneDetailsOpen ? (
                    <dl className="spatial-map__scene-context-details" data-testid="scene-context-details">
                      {document.sceneIntent?.locationType ? (
                        <div><dt>Location Type</dt><dd>{document.sceneIntent.locationType.replace(/_/g, " ")}</dd></div>
                      ) : null}
                      {document.sceneIntent?.keySubjects?.length ? (
                        <div><dt>Featured</dt><dd>{document.sceneIntent.keySubjects.join(", ")}</dd></div>
                      ) : null}
                      {document.sceneIntent?.keyProps?.length ? (
                        <div><dt>Key Prop</dt><dd>{document.sceneIntent.keyProps.join(", ")}</dd></div>
                      ) : null}
                      {document.sceneIntent?.productionIntent ? (
                        <div><dt>Production Intent</dt><dd>{document.sceneIntent.productionIntent}</dd></div>
                      ) : null}
                      {document.sceneIntent?.sourcePromptSummary ? (
                        <div><dt>Creator Words</dt><dd>{document.sceneIntent.sourcePromptSummary}</dd></div>
                      ) : null}
                      {document.sceneIntent?.sourceReferenceAssetIds?.length ? (
                        <div><dt>Source Reference</dt><dd>{document.sceneIntent.sourceReferenceAssetIds.length} image(s)</dd></div>
                      ) : null}
                    </dl>
                  ) : null}
                  {sceneEditOpen ? (
                    <div className="spatial-map__scene-context-edit" data-testid="scene-description-editor">
                      <textarea
                        rows={2}
                        value={sceneEditText}
                        onChange={(e) => setSceneEditText(e.target.value)}
                        data-testid="scene-description-edit-input"
                        placeholder="Describe this location in a few words"
                      />
                      <div className="spatial-map__scene-context-actions">
                        <button
                          type="button"
                          className="spatial-map__slot-action"
                          disabled={!!sceneDescriptionError(sceneEditText)}
                          onClick={() => void handleSaveSceneDescription()}
                          data-testid="scene-description-save-btn"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="spatial-map__slot-action"
                          onClick={() => setSceneEditOpen(false)}
                          data-testid="scene-description-cancel-btn"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
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
            ghostColor={ghostColor}
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

          {selectedCharacter ? (
            <CharacterInspector
              character={selectedCharacter}
              assigned={assignedCharacters.find((c) => c.id === selectedCharacter.characterId) || assignedSpatialMapCharacters([selectedCharacter])[0] || null}
              attached={attachedPropsForCharacter(selectedCharacter, document?.props || [])}
              onAttachProp={() => setAttachmentEditor({ source: "character", characterId: selectedCharacter.id })}
              onEditAttachment={(prop) => setAttachmentEditor({ source: "character", characterId: selectedCharacter.id, propId: prop.id })}
              onDetachAndPlace={(prop) => void handleDetachAndPlace(prop)}
            />
          ) : null}

          {attachmentEditor ? (
            <PropAttachmentEditor
              key={`${attachmentEditor.source}-${attachmentEditor.source === "character" ? (attachmentEditor.propId || attachmentEditor.characterId) : attachmentEditor.propId}`}
              characters={assignedCharacters}
              props={attachmentEditor.source === "character" && !attachmentEditor.propId ? independentAssignedProps(document?.props || []) : undefined}
              requirePropChoice={attachmentEditor.source === "character" && !attachmentEditor.propId}
              lockCharacter={attachmentEditor.source === "character"}
              initial={{
                propPlacementId: editorProp?.id,
                attachedCharacterSlot: editorProp?.attachedCharacterSlot || editorAssigned?.slot || null,
                attachedCharacterId: editorProp?.attachedCharacterId || editorAssigned?.id || null,
                relationship: editorProp?.relationship || "held",
                attachmentPoint: editorProp?.attachmentPoint || "right_hand",
              }}
              onCancel={() => setAttachmentEditor(null)}
              onApply={(payload) => {
                const propId = payload.propPlacementId || attachmentEditor.propId;
                if (propId) void handleApplyAttachment(propId, payload);
              }}
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
                        const prop = placement as SpatialPropPlacement;
                        if (isAttachedProp(prop)) {
                          setActiveSlot({ kind: "prop", index: slot.index });
                          setSelectedPlacementId(placement.id);
                          setSelectedCameraId(null);
                          return;
                        }
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
                    onAttach={() => placement && setAttachmentEditor({ source: "prop", propId: placement.id })}
                    onEditAttachment={() => placement && setAttachmentEditor({ source: "prop", propId: placement.id })}
                    onDetachAndPlace={() => placement && void handleDetachAndPlace(placement as SpatialPropPlacement)}
                    assignedCharacters={assignedCharacters}
                    onApplyAttachment={(payload) => placement && void handleApplyAttachment(placement.id, payload)}
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
                const cameraEnabled = !!(camera && isEntityEnabled(camera.visible));
                const cameraPlacing = !!(camera && placementMode?.kind === "camera" && placementMode.id === camera.id);
                return (
                  <div
                    key={`cam-${slot.index}`}
                    className={`spatial-map__entity-card spatial-map__camera-slot${activeSlot?.kind === "camera" && activeSlot?.index === slot.index ? " is-active" : ""}${camera ? " is-placed" : ""}`}
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
                    <div className="spatial-map__entity-card-head spatial-map__slot-head">
                    {slotPlacementBadge(cameraPlacing) ? (
                      <span className="spatial-map__active-badge is-placement-active" data-testid={'slot-active-badge-camera-' + String(slot.index)}>
                        {slotPlacementBadge(true)}
                      </span>
                    ) : null}
                    <span className="spatial-map__slot-label">{slot.label}</span>
                    <div className="spatial-map__placement-arm">
                      <span
                        className={`spatial-map__placement-active-label${cameraEnabled ? " is-on" : ""}`}
                        data-testid={`camera-enabled-label-${slot.index}`}
                      >
                        {ENTITY_ENABLED_SWITCH_LABEL}
                      </span>
                      <button
                        type="button"
                        role="switch"
                        className={`spatial-map__slot-toggle${cameraEnabled ? " is-on" : ""}${!camera ? " is-disabled" : ""}`}
                        aria-checked={cameraEnabled}
                        aria-disabled={!camera}
                        disabled={!camera}
                        aria-label={placementSwitchAriaLabel(slot.label, cameraEnabled, { assigned: !!camera })}
                        data-testid={`camera-online-${slot.index}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!camera) return;
                          void handleToggleVisible("camera", camera.id, camera.visible === false);
                        }}
                      >
                        <span className="spatial-map__slot-toggle-thumb" aria-hidden="true" />
                      </button>
                    </div>
                    </div>
                    {camera ? (
                      <span className="spatial-map__entity-card-meta spatial-map__slot-status">
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

          <div className="spatial-map__ers-generator" data-testid="ers-generator">
            <label className="spatial-map__ers-generator-label" htmlFor="ers-generator-select">
              ERS Generator
            </label>
            <select
              id="ers-generator-select"
              className="spatial-map__ers-generator-select"
              data-testid="ers-generator-select"
              aria-label="ERS Generator"
              value={ers.selectedGenerator}
              disabled={ers.busy}
              onChange={(e) => ers.setSelectedGenerator(e.target.value as typeof ers.selectedGenerator)}
            >
              {ERS_GENERATOR_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            {ers.generatorBlockReason ? (
              <p className="spatial-map__ers-generator-reason" data-testid="ers-generator-reason" role="status">
                {ers.generatorBlockReason}
              </p>
            ) : null}
          </div>
          <div className="spatial-map__actions">
            <button
              type="button"
              className="ui-btn ui-btn--primary"
              onClick={() => void startErsGeneration()}
              disabled={isGenerating || !!ers.generatorBlockReason}
              aria-label={ersExists ? "Regenerate Environment Reference Sheet" : "Generate Environment Reference Sheet"}
            >
              {ers.busy ? "Generating…" : ersExists ? "Regenerate Environment Reference Sheet" : "Generate Environment Reference Sheet"}
            </button>
            <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void handleResetMap()} aria-label="Reset map placements">
              Reset Map
            </button>
          </div>

          <ERSGenerationMonitor
            state={ers}
            onRetry={() => void ers.retry()}
            onOpenInLibrary={() => onGoTab?.("library")}
            onUseInSceneCreator={() => void handleUseInSceneCreator()}
            onUseAnyway={() => void ers.useAnyway()}
          />

          {opMsg && ers.phase === "idle" ? <p className="spatial-map__hint">{opMsg}</p> : null}
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
            if (!document) return;
            const description = sceneDescription.trim() || document.sceneIntent?.summary || "";
            const descError = sceneDescriptionError(description);
            if (descError) {
              setOpMsg(descError);
              return;
            }
            if (!sceneDescription.trim()) setSceneDescription(description);
            try {
              const updated = await spatialMapApi.updateMap(projectId, document.id, {
                backgroundAssetId: assetId,
                sceneDescription: description,
                originalEnvironmentReferenceAssetId: assetId,
              });
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
