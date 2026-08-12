/**
 * SpatialMapPanel — main Spatial Map panel for the Co-Director pane.
 *
 * Lifecycle:
 *   empty state (no document or no backgroundAssetId)
 *     → creator picks Atlas Shot / Library image / Upload
 *     → POST /api/spatial-map/projects/{pid}/maps with backgroundAssetId
 *   map view (document with backgroundAssetId)
 *     → 10x10 grid overlay, slot panel (4 character + 4 prop slots),
 *       click-to-place, mini-prompts, ERS generation/display.
 *
 * Reuses (Law #17): api.spatialMap (REST client), api.listCharacterProfiles
 * (character picker), api.library (prop image picker), api.uploadAsset
 * (upload), api.startExecution (Co-Director atlas.generate / ers.generate).
 *
 * Amendments honored:
 *   #1 Atlas Shot is an INPUT (empty state offers 3 entry points).
 *   #2 ERS composite is assembled in code — we just display the asset.
 *   #3 Spatial Map authoritative — generated imagery never mutates placement.
 *   #4 Orientation scene-relative (Atlas North = top edge).
 *   #5 @ uses real character names; # uses normalized tags; UI pickers used.
 *   #25 Mini-prompts shown as compact expandable cards, not 8 large textareas.
 *   #12/#13/#69 Accessible labels in addition to color.
 *
 * Persistence (Law #10): every placement change POSTs/PATCHes immediately;
 * on mount we load the most recent SpatialMapDocument for the project.
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
import {
  cellLabel,
  CHARACTER_SLOTS,
  PROP_SLOTS,
  type SlotDef,
  type SpatialCharacterPlacement,
  type SpatialMapDocument,
  type SpatialPropPlacement,
} from "./types";
import "./spatialMap.css";

type Props = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

type BusyState = {
  loading: boolean;
  error: string | null;
};

type PendingCoDirectorOp = "atlas" | "ers" | null;

export function SpatialMapPanel({ projectId, onGoTab }: Props) {
  const { activeExecution, setActiveExecution } = useCoDirectorSession();
  const [document, setDocument] = useState<SpatialMapDocument | null>(null);
  const [busy, setBusy] = useState<BusyState>({ loading: true, error: null });
  const [activeSlot, setActiveSlot] = useState<{ kind: "character" | "prop"; index: number } | null>(null);
  const [selectedPlacementId, setSelectedPlacementId] = useState<string | null>(null);
  const [occupiedMessage, setOccupiedMessage] = useState<string | null>(null);
  const [picker, setPicker] = useState<{ kind: "character" | "prop"; slot: SlotDef } | null>(null);
  const [busyOp, setBusyOp] = useState<PendingCoDirectorOp>(null);
  const [opMsg, setOpMsg] = useState<string | null>(null);
  const [ersCompositeAssetId, setErsCompositeAssetId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const emptyFileInputRef = useRef<HTMLInputElement>(null);

  // ── Load most recent map on mount / project change ──────────────────────
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

  // ── Track active Co-Director execution for atlas / ERS results ─────────
  useEffect(() => {
    if (!activeExecution) return;
    if (activeExecution.project_id && activeExecution.project_id !== projectId) return;
    if (isTerminal(activeExecution)) {
      // On completion, capture result asset ids for the active op.
      const resultIds = activeExecution.result_asset_ids || [];
      if (resultIds.length > 0) {
        if (busyOp === "atlas") {
          // Use the first result asset as the Atlas Shot.
          const atlasAssetId = resultIds[0];
          void (async () => {
            try {
            if (replaceModeRef.current && document) {
              // Replace: PATCH existing map's backgroundAssetId (preserves placements).
              const updated = await spatialMapApi.updateMap(projectId, document.id, {
                backgroundAssetId: atlasAssetId,
              });
              setDocument(updated);
              setOpMsg("Atlas Shot replaced.");
            } else {
              // Create: new map document with the Atlas as background.
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
          // The ERS composite asset id is typically the last result for an
          // ers.generate execution. Take the first non-directional result;
          // if multiple are returned, prefer the last (composite).
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
  }, [activeExecution?.status, activeExecution?.execution_id, activeExecution?.result_asset_ids?.length, projectId, busyOp]);

  // ── Atlas Shot / ERS generation via Co-Director execution ───────────────
  const startAtlasGeneration = useCallback(async () => {
    setOpMsg(null);
    setBusyOp("atlas");
    try {
      const res = await api.startExecution(projectId, {
        capability: "atlas.generate",
        context: {},
      });
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
      const res = await api.startExecution(projectId, {
        capability: "ers.generate",
        context: { spatial_map_id: document.id },
      });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start ERS generation.");
      setBusyOp(null);
    }
  }, [projectId, document, setActiveExecution]);

  // ── Choose from Library (open a Library asset picker) ──────────────────
  // For V1 we reuse the EntityPicker prop kind with an image-only library.
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const handleChooseFromLibrary = () => setLibraryPickerOpen(true);

  // ── Replace Atlas (preserve placements via PATCH backgroundAssetId) ────
  const [replacePickerOpen, setReplacePickerOpen] = useState(false);
  const handleReplaceFromLibrary = () => setReplacePickerOpen(true);

  const handleReplaceUpload = useCallback(async (file: File) => {
    if (!document) return;
    setOpMsg(null);
    setBusyOp("atlas");
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      const updated = await spatialMapApi.updateMap(projectId, document.id, {
        backgroundAssetId: asset.id,
      });
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
    // Mark that the next atlas result should PATCH the existing map
    // instead of creating a new one.
    replaceModeRef.current = true;
    try {
      const res = await api.startExecution(projectId, {
        capability: "atlas.generate",
        context: {},
      });
      const exec = normalizeExecution(res);
      setActiveExecution(exec);
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to start Atlas Shot generation.");
      setBusyOp(null);
      replaceModeRef.current = false;
    }
  }, [projectId, document, setActiveExecution]);

  // ── Remove Atlas (clear backgroundAssetId, preserve placements + Library asset) ──
  const handleRemoveAtlas = useCallback(async () => {
    if (!document?.backgroundAssetId) return;
    const ok = window.confirm(
      "Remove the Atlas Shot from this Spatial Map? The Library image is kept; only the map background is cleared.",
    );
    if (!ok) return;
    setOpMsg(null);
    try {
      const updated = await spatialMapApi.updateMap(projectId, document.id, {
        backgroundAssetId: null,
      });
      setDocument(updated);
      setOpMsg("Atlas Shot removed from Spatial Map. The Library image is preserved.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Failed to remove Atlas.");
    }
  }, [projectId, document]);

  // Track whether a new atlas generation should replace (PATCH) vs create new.
  const replaceModeRef = useRef(false);

  // ── Upload image ───────────────────────────────────────────────────────
  const handleUploadImage = useCallback(async (file: File) => {
    setOpMsg(null);
    setBusyOp("atlas"); // treat upload as creating the map background
    try {
      const asset = await api.uploadAsset(projectId, file, "atlas_shot", "image");
      const doc = await spatialMapApi.createMap(projectId, {
        title: "Spatial Map",
        backgroundAssetId: asset.id,
      });
      setDocument(doc);
      setOpMsg("Image uploaded and Spatial Map created.");
    } catch (err) {
      setOpMsg(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusyOp(null);
    }
  }, [projectId]);

  // ── Placements ────────────────────────────────────────────────────────
  const placements = useMemo(() => {
    if (!document) return [];
    return toGridPlacements(document.characters, document.props);
  }, [document]);

  const findPlacement = useCallback(
    (placementId: string | null): SpatialCharacterPlacement | SpatialPropPlacement | null => {
      if (!placementId || !document) return null;
      const c = document.characters.find((p) => p.id === placementId);
      if (c) return c;
      const pr = document.props.find((p) => p.id === placementId);
      return pr || null;
    },
    [document],
  );

  // Slot → placement lookup by slotIndex+colorKey+kind.
  const placementForSlot = useCallback(
    (slot: SlotDef): SpatialCharacterPlacement | SpatialPropPlacement | null => {
      if (!document) return null;
      const arr = slot.kind === "character" ? document.characters : document.props;
      return (
        arr.find((p) => p.slotIndex === slot.index && p.colorKey === slot.colorKey) ||
        arr.find((p) => p.colorKey === slot.colorKey) ||
        null
      );
    },
    [document],
  );

  // ── Click-to-place ────────────────────────────────────────────────────
  const handleCellClick = useCallback(
    async (row: number, column: number) => {
      setOccupiedMessage(null);
      if (!document) return;
      // If a placement is selected, move it.
      if (selectedPlacementId) {
        const target = findPlacement(selectedPlacementId);
        if (!target) {
          setSelectedPlacementId(null);
          return;
        }
        // Occupancy check (excluding the moving placement itself).
        const occupied = placements.find(
          (p) => p.gridRow === row && p.gridColumn === column && p.id !== selectedPlacementId,
        );
        if (occupied) {
          setOccupiedMessage(`Cell ${cellLabel(row, column)} is occupied by ${occupied.tag}. Choose another cell.`);
          return;
        }
        const isChar = "characterId" in target;
        try {
          const updated = isChar
            ? await spatialMapApi.updateCharacter(projectId, document.id, target.id, {
                gridRow: row,
                gridColumn: column,
              } as any)
            : await spatialMapApi.updateProp(projectId, document.id, target.id, {
                gridRow: row,
                gridColumn: column,
              } as any);
          setDocument(updated);
          setSelectedPlacementId(null);
        } catch (err) {
          setOpMsg(err instanceof Error ? err.message : "Failed to move placement.");
        }
        return;
      }
      // Otherwise, place from the active slot.
      if (!activeSlot) {
        setOccupiedMessage("Pick a Character or Prop slot first, then click a cell.");
        return;
      }
      const occupied = placements.find((p) => p.gridRow === row && p.gridColumn === column);
      if (occupied) {
        setOccupiedMessage(`Cell ${cellLabel(row, column)} is occupied by ${occupied.tag}. Choose another cell.`);
        return;
      }
      const slot = activeSlot.kind === "character" ? CHARACTER_SLOTS[activeSlot.index] : PROP_SLOTS[activeSlot.index];
      const existing = placementForSlot(slot);
      if (!existing) {
        setOccupiedMessage(`Add a ${activeSlot.kind} to slot ${slot.index + 1} first.`);
        return;
      }
      // Move existing placement to the clicked cell.
      try {
        const isChar = "characterId" in existing;
        const updated = isChar
          ? await spatialMapApi.updateCharacter(projectId, document.id, existing.id, {
              gridRow: row,
              gridColumn: column,
            } as any)
          : await spatialMapApi.updateProp(projectId, document.id, existing.id, {
              gridRow: row,
              gridColumn: column,
            } as any);
        setDocument(updated);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to place.");
      }
    },
    [document, activeSlot, selectedPlacementId, placements, findPlacement, placementForSlot, projectId],
  );

  // ── Slot: add via picker ───────────────────────────────────────────────
  const handleSlotAdd = (slot: SlotDef) => {
    setPicker({ kind: slot.kind, slot });
  };

  const handlePickerConfirmCharacter = useCallback(
    async (tag: string, characterId: string, characterName: string) => {
      if (!document || !picker) return;
      const slot = picker.slot;
      try {
        // We need an assetId — attempt to resolve from the character's
        // approved hero portrait. Skip if unavailable.
        let assetId: string | null = null;
        try {
          const refs = (await api.listCharacterReferences(projectId, characterId)) as { items?: Array<{ asset_id?: string | null; canonical?: boolean; approval_status?: string }> };
          const items = refs.items || [];
          const hero = items.find((r) => r.canonical && r.approval_status === "approved") || items.find((r) => r.canonical);
          if (hero?.asset_id) assetId = hero.asset_id;
        } catch {
          // best-effort
        }
        const updated = await spatialMapApi.placeCharacter(projectId, document.id, {
          characterId,
          label: characterName,
          assetId,
          tag,
          slotIndex: slot.index,
          colorKey: slot.colorKey,
          miniPrompt: "",
        } as any);
        setDocument(updated);
        setPicker(null);
        setActiveSlot({ kind: "character", index: slot.index });
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to add character.");
      }
    },
    [document, picker, projectId],
  );

  const handlePickerConfirmProp = useCallback(
    async (tag: string, assetId: string, displayLabel: string) => {
      if (!document || !picker) return;
      const slot = picker.slot;
      try {
        const updated = await spatialMapApi.placeProp(projectId, document.id, {
          label: displayLabel,
          assetId,
          propId: null,
          category: "prop",
          state: "default",
          tag,
          slotIndex: slot.index,
          colorKey: slot.colorKey,
          miniPrompt: "",
        } as any);
        setDocument(updated);
        setPicker(null);
        setActiveSlot({ kind: "prop", index: slot.index });
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to add prop.");
      }
    },
    [document, picker, projectId],
  );

  // ── Slot: remove ──────────────────────────────────────────────────────
  const handleSlotRemove = useCallback(
    async (slot: SlotDef) => {
      if (!document) return;
      const placement = placementForSlot(slot);
      if (!placement) return;
      try {
        const updated =
          slot.kind === "character"
            ? await spatialMapApi.removeCharacter(projectId, document.id, placement.id)
            : await spatialMapApi.removeProp(projectId, document.id, placement.id);
        setDocument(updated);
        if (selectedPlacementId === placement.id) setSelectedPlacementId(null);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to remove.");
      }
    },
    [document, placementForSlot, projectId, selectedPlacementId],
  );

  // ── Slot: update mini-prompt ───────────────────────────────────────────
  const handleUpdateMiniPrompt = useCallback(
    async (slot: SlotDef, text: string) => {
      if (!document) return;
      const placement = placementForSlot(slot);
      if (!placement) return;
      try {
        const isChar = "characterId" in placement;
        const updated = isChar
          ? await spatialMapApi.updateCharacter(projectId, document.id, placement.id, { miniPrompt: text } as any)
          : await spatialMapApi.updateProp(projectId, document.id, placement.id, { miniPrompt: text } as any);
        setDocument(updated);
      } catch (err) {
        setOpMsg(err instanceof Error ? err.message : "Failed to save mini prompt.");
      }
    },
    [document, placementForSlot, projectId],
  );

  // ── Reset map ─────────────────────────────────────────────────────────
  const handleResetMap = useCallback(async () => {
    if (!document) return;
    const hasPlacements = document.characters.some((p) => p.gridRow >= 0 || p.miniPrompt) ||
      document.props.some((p) => p.gridRow >= 0 || p.miniPrompt);
    if (hasPlacements) {
      const ok = window.confirm(
        "Reset map? This clears placement coordinates and mini-prompts. Characters, props, the Atlas Shot, and Library assets are kept.",
      );
      if (!ok) return;
    }
    try {
      // Clear grid coordinates + mini-prompts on every placement via PATCH.
      let doc = document;
      for (const c of doc.characters) {
        doc = await spatialMapApi.updateCharacter(projectId, doc.id, c.id, {
          gridRow: -1,
          gridColumn: -1,
          miniPrompt: "",
        } as any);
      }
      for (const p of doc.props) {
        doc = await spatialMapApi.updateProp(projectId, doc.id, p.id, {
          gridRow: -1,
          gridColumn: -1,
          miniPrompt: "",
        } as any);
      }
      setDocument(doc);
      setSelectedPlacementId(null);
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
          action={
            <button type="button" className="ui-btn ui-btn--secondary" onClick={() => void loadMap()}>Retry</button>
          }
        />
      </div>
    );
  }

  const hasBackground = !!document?.backgroundAssetId;
  const bgUrl = document?.backgroundAssetId ? api.assetUrl(document.backgroundAssetId) : "";
  const ersExists = !!ersCompositeAssetId;
  const isGenerating = busyOp !== null;

  return (
    <div className="spatial-map" data-testid="spatial-map-panel">
      {!hasBackground ? (
        <>
          <h3 className="spatial-map__heading">Spatial Map</h3>
          <p className="spatial-map__subtitle">Start with an environment reference.</p>
          <p className="spatial-map__tip">
            An Atlas Shot is a roofless, top-down reference view designed specifically for Spatial Map.
            It gives Adept UI the clearest possible master view of your scene layout, making character,
            prop, and camera positioning more consistent.
          </p>
          <input
            ref={emptyFileInputRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void handleUploadImage(f);
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
            <LibraryAtlasPicker
              projectId={projectId}
              onClose={() => setLibraryPickerOpen(false)}
              onPick={async (assetId) => {
                setLibraryPickerOpen(false);
                try {
                  const doc = await spatialMapApi.createMap(projectId, {
                    title: "Spatial Map",
                    backgroundAssetId: assetId,
                  });
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

          {/* Active Atlas Shot panel — thumbnail + View/Replace/Remove */}
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
              <button
                type="button"
                className="ui-btn ui-btn--secondary spatial-map__atlas-btn"
                onClick={() => onGoTab?.("library")}
                aria-label="View Atlas Shot in Library"
                data-testid="atlas-view-btn"
              >
                View
              </button>
              <button
                type="button"
                className="ui-btn ui-btn--secondary spatial-map__atlas-btn"
                onClick={handleReplaceFromLibrary}
                disabled={isGenerating}
                aria-label="Replace Atlas Shot"
                data-testid="atlas-replace-btn"
              >
                Replace
              </button>
              <button
                type="button"
                className="ui-btn ui-btn--secondary spatial-map__atlas-btn"
                onClick={() => void handleReplaceGenerate()}
                disabled={isGenerating}
                aria-label="Generate another Atlas Shot with Co-Director"
                data-testid="atlas-regenerate-btn"
              >
                Generate New
              </button>
              <button
                type="button"
                className="ui-btn ui-btn--secondary spatial-map__atlas-btn spatial-map__atlas-remove"
                onClick={() => void handleRemoveAtlas()}
                aria-label="Remove Atlas Shot from Spatial Map"
                data-testid="atlas-remove-btn"
              >
                Remove
              </button>
            </div>
          </div>

          {/* Hidden file input for Replace via upload */}
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

          <SpatialGrid
            backgroundAssetId={document!.backgroundAssetId!}
            imageUrl={bgUrl}
            placements={placements}
            selectedPlacementId={selectedPlacementId}
            activeSlotColorKey={activeSlot ? (activeSlot.kind === "character" ? CHARACTER_SLOTS : PROP_SLOTS)[activeSlot.index].colorKey : null}
            occupiedMessage={occupiedMessage}
            onCellClick={handleCellClick}
            onSelectPlacement={(id) => {
              setSelectedPlacementId(id);
              if (id) {
                const p = findPlacement(id);
                if (p && p.slotIndex >= 0) {
                  setActiveSlot({ kind: "characterId" in p ? "character" : "prop", index: p.slotIndex });
                }
              }
            }}
          />

          <p className="spatial-map__hint">
            {selectedPlacementId
              ? "Click an empty cell to move the selected placement, or click another placement to select it."
              : activeSlot
                ? `Click an empty cell to place ${activeSlot.kind} ${activeSlot.index + 1}.`
                : "Pick a slot below, then click a cell to place it."}
          </p>

          <div className="spatial-map__slots">
            <div className="spatial-map__slot-group">
              <p className="spatial-map__slot-group-title">Characters</p>
              {CHARACTER_SLOTS.map((slot) => (
                <PlacementSlot
                  key={`char-${slot.index}`}
                  slot={slot}
                  placement={placementForSlot(slot)}
                  active={activeSlot?.kind === "character" && activeSlot?.index === slot.index}
                  onSelect={() => setActiveSlot({ kind: "character", index: slot.index })}
                  onAdd={() => handleSlotAdd(slot)}
                  onRemove={() => void handleSlotRemove(slot)}
                  onUpdateMiniPrompt={(text) => void handleUpdateMiniPrompt(slot, text)}
                />
              ))}
            </div>
            <div className="spatial-map__slot-group">
              <p className="spatial-map__slot-group-title">Props</p>
              {PROP_SLOTS.map((slot) => (
                <PlacementSlot
                  key={`prop-${slot.index}`}
                  slot={slot}
                  placement={placementForSlot(slot)}
                  active={activeSlot?.kind === "prop" && activeSlot?.index === slot.index}
                  onSelect={() => setActiveSlot({ kind: "prop", index: slot.index })}
                  onAdd={() => handleSlotAdd(slot)}
                  onRemove={() => void handleSlotRemove(slot)}
                  onUpdateMiniPrompt={(text) => void handleUpdateMiniPrompt(slot, text)}
                />
              ))}
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
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              onClick={() => void handleResetMap()}
              aria-label="Reset map placements"
            >
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

      {picker ? (
        <EntityPicker
          kind={picker.kind}
          projectId={projectId}
          slot={picker.slot}
          onClose={() => setPicker(null)}
          onConfirm={
            picker.kind === "character"
              ? (tag, characterId, name) => void handlePickerConfirmCharacter(tag, characterId, name)
              : (tag, assetId, label) => void handlePickerConfirmProp(tag, assetId, label)
          }
        />
      ) : null}

      {replacePickerOpen && document ? (
        <LibraryAtlasPicker
          projectId={projectId}
          onClose={() => setReplacePickerOpen(false)}
          onPick={async (assetId) => {
            setReplacePickerOpen(false);
            try {
              const updated = await spatialMapApi.updateMap(projectId, document.id, {
                backgroundAssetId: assetId,
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

// ── Helpers ────────────────────────────────────────────────────────────────

function normalizeExecution(res: any) {
  // The startExecution response shape varies; build a WorkSurfaceState.
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

/** Library asset picker for the "Choose from Library" Atlas Shot entry point. */
function LibraryAtlasPicker({
  projectId,
  onClose,
  onPick,
}: {
  projectId: string;
  onClose: () => void;
  onPick: (assetId: string) => void;
}) {
  return (
    <EntityPicker
      kind="environment"
      projectId={projectId}
      title="Select Spatial Map Image"
      onClose={onClose}
      onConfirm={(assetId) => onPick(assetId)}
    />
  );
}
