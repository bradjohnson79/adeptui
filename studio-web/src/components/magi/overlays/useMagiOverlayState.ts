import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import { OVERLAY_PRESETS } from "./presets";
import {
  createImageElement,
  createLowerThirdGroup,
  createTextElement,
  createVectorElement,
  emptyComposition,
  flattenOverlayIds,
  overlayObjectsTrack,
  type MagiOverlayComposition,
  type MagiOverlayElement,
  type MagiVectorShape,
} from "./types";

type OverlayHistoryCommit = {
  type: string;
  label: string;
  before: MagiOverlayComposition;
  after: MagiOverlayComposition;
  selectedOverlayId: string | null;
};

type OverlayStateOptions = {
  onHistoryCommit?: (entry: OverlayHistoryCommit) => void;
  onPersistStateChange?: (state: { dirty: boolean; saving: boolean; error: string | null }) => void;
};

function mapDeep(
  overlays: MagiOverlayElement[],
  id: string,
  fn: (el: MagiOverlayElement) => MagiOverlayElement
): MagiOverlayElement[] {
  return overlays.map((el) => {
    if (el.id === id) return fn(el);
    if (el.type === "group") return { ...el, children: mapDeep(el.children, id, fn) };
    return el;
  });
}

function filterDeep(overlays: MagiOverlayElement[], id: string): MagiOverlayElement[] {
  return overlays
    .filter((el) => el.id !== id)
    .map((el) => (el.type === "group" ? { ...el, children: filterDeep(el.children, id) } : el));
}

export function useMagiOverlayState(
  projectId: string,
  sourceAssetId: string,
  options?: OverlayStateOptions,
) {
  const [composition, setComposition] = useState<MagiOverlayComposition>(() =>
    emptyComposition(projectId, sourceAssetId || null)
  );
  const [selectedOverlayId, setSelectedOverlayId] = useState<string | null>(null);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [safeGuides, setSafeGuides] = useState(true);
  const [overlayProposal, setOverlayProposal] = useState<Record<string, unknown> | null>(null);
  const [persistError, setPersistError] = useState<string | null>(null);
  const [savePending, setSavePending] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const saveTimer = useRef<number | null>(null);
  const saveTimerCancelledRef = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    optionsRef.current?.onPersistStateChange?.({
      dirty: savePending,
      saving: isSaving,
      error: persistError,
    });
  }, [isSaving, persistError, savePending]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!sourceAssetId) {
        setComposition(emptyComposition(projectId, null));
        setPersistError(null);
        setSavePending(false);
        return;
      }
      try {
        const comp = (await api.magi.getOverlayForAsset(projectId, sourceAssetId)) as MagiOverlayComposition;
        if (!cancelled && comp?.compositionId) {
          setComposition(comp);
          setPersistError(null);
          setSavePending(false);
        }
      } catch {
        if (!cancelled) {
          setComposition(emptyComposition(projectId, sourceAssetId));
          setSavePending(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, sourceAssetId]);

  useEffect(() => {
    return () => {
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = null;
      saveTimerCancelledRef.current = true;
    };
  }, []);

  const persist = useCallback(
    (next: MagiOverlayComposition) => {
      setComposition(next);
      setSavePending(true);
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        saveTimer.current = null;
        setIsSaving(true);
        void api.magi
          .saveOverlay(projectId, next.compositionId, next as unknown as Record<string, unknown>)
          .then((saved) => {
            setComposition(saved as MagiOverlayComposition);
            setPersistError(null);
            setSavePending(false);
          })
          .catch((e: unknown) => setPersistError(e instanceof Error ? e.message : String(e)))
          .finally(() => setIsSaving(false));
      }, 400);
    },
    [projectId]
  );

  const persistNow = useCallback(async () => {
    if (!composition?.compositionId) return composition;
    if (saveTimer.current) {
      window.clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    setIsSaving(true);
    try {
      const saved = (await api.magi.saveOverlay(
        projectId,
        composition.compositionId,
        composition as unknown as Record<string, unknown>,
      )) as MagiOverlayComposition;
      setComposition(saved);
      setPersistError(null);
      setSavePending(false);
      return saved;
    } catch (e: unknown) {
      setPersistError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setIsSaving(false);
    }
  }, [composition, projectId]);

  const commit = useCallback(
    (type: string, label: string, mutator: (c: MagiOverlayComposition) => MagiOverlayComposition) => {
      setComposition((prev) => {
        const next = mutator(structuredClone(prev));
        next.updatedAt = new Date().toISOString();
        optionsRef.current?.onHistoryCommit?.({
          type,
          label,
          before: structuredClone(prev),
          after: structuredClone(next),
          selectedOverlayId,
        });
        setPersistError(null);
        setSavePending(true);
        if (saveTimer.current) window.clearTimeout(saveTimer.current);
        saveTimer.current = window.setTimeout(() => {
          saveTimer.current = null;
          setIsSaving(true);
          void api.magi
            .saveOverlay(projectId, next.compositionId, next as unknown as Record<string, unknown>)
            .then(() => {
              setPersistError(null);
              setSavePending(false);
            })
            .catch((e: unknown) => setPersistError(e instanceof Error ? e.message : String(e)))
            .finally(() => setIsSaving(false));
        }, 400);
        return next;
      });
    },
    [projectId, selectedOverlayId]
  );

  const addText = (partial?: Partial<import("./types").MagiTextElement>) => {
    const el = createTextElement(partial);
    commit("overlay.create", "Add text", (c) => {
      c.overlays.push(el);
      return c;
    });
    setSelectedOverlayId(el.id);
    return el.id;
  };
  const addLowerThird = (primary?: string, secondary?: string, partial?: Partial<import("./types").MagiOverlayGroup>) => {
    const el = { ...createLowerThirdGroup(primary, secondary), ...partial };
    commit("overlay.create", "Add lower third", (c) => {
      c.overlays.push(el);
      return c;
    });
    setSelectedOverlayId(el.id);
    return el.id;
  };
  const addShape = (shape: MagiVectorShape = "rectangle", partial?: Partial<import("./types").MagiVectorElement>) => {
    const el = { ...createVectorElement(shape), ...partial };
    commit("overlay.create", "Add shape", (c) => {
      c.overlays.push(el);
      return c;
    });
    setSelectedOverlayId(el.id);
    return el.id;
  };
  const addImage = (assetId: string, partial?: Partial<import("./types").MagiImageElement>) => {
    const el = createImageElement(assetId, partial);
    commit("overlay.create", "Add image overlay", (c) => {
      c.overlays.push(el);
      return c;
    });
    setSelectedOverlayId(el.id);
    return el.id;
  };
  const bringForward = () => {
    if (!selectedOverlayId) return;
    commit("overlay.z", "Bring forward", (c) => {
      const selected = c.overlays.find((el) => el.id === selectedOverlayId);
      if (!selected) return c;
      const slot = overlayObjectsTrack(selected);
      const sorted = c.overlays.filter((el) => overlayObjectsTrack(el) === slot).sort((a, b) => a.zIndex - b.zIndex);
      const i = sorted.findIndex((el) => el.id === selectedOverlayId);
      if (i < 0 || i >= sorted.length - 1) return c;
      const z = sorted[i].zIndex;
      sorted[i].zIndex = sorted[i + 1].zIndex;
      sorted[i + 1].zIndex = z;
      return c;
    });
  };
  const sendBackward = () => {
    if (!selectedOverlayId) return;
    commit("overlay.z", "Send backward", (c) => {
      const selected = c.overlays.find((el) => el.id === selectedOverlayId);
      if (!selected) return c;
      const slot = overlayObjectsTrack(selected);
      const sorted = c.overlays.filter((el) => overlayObjectsTrack(el) === slot).sort((a, b) => a.zIndex - b.zIndex);
      const i = sorted.findIndex((el) => el.id === selectedOverlayId);
      if (i <= 0) return c;
      const z = sorted[i].zIndex;
      sorted[i].zIndex = sorted[i - 1].zIndex;
      sorted[i - 1].zIndex = z;
      return c;
    });
  };
  const bringToFront = () => {
    if (!selectedOverlayId) return;
    commit("overlay.z", "Bring to front", (c) => {
      const selected = c.overlays.find((el) => el.id === selectedOverlayId);
      if (!selected) return c;
      const slot = overlayObjectsTrack(selected);
      const peers = c.overlays.filter((el) => overlayObjectsTrack(el) === slot);
      const max = peers.reduce((acc, el) => Math.max(acc, el.zIndex), 0);
      c.overlays = mapDeep(c.overlays, selectedOverlayId, (el) => ({ ...el, zIndex: max + 1 }));
      return c;
    });
  };
  const sendToBack = () => {
    if (!selectedOverlayId) return;
    commit("overlay.z", "Send to back", (c) => {
      const selected = c.overlays.find((el) => el.id === selectedOverlayId);
      if (!selected) return c;
      const slot = overlayObjectsTrack(selected);
      const peers = c.overlays.filter((el) => overlayObjectsTrack(el) === slot);
      const min = peers.reduce((acc, el) => Math.min(acc, el.zIndex), 0);
      c.overlays = mapDeep(c.overlays, selectedOverlayId, (el) => ({ ...el, zIndex: min - 1 }));
      return c;
    });
  };
  const reassignObjectsTrack = (fromSlot: 1 | 2, toSlot: 1 | 2) => {
    if (fromSlot === toSlot) return;
    commit("overlay.objectsTrack", "Move objects", (c) => {
      c.overlays = c.overlays.map((el) =>
        overlayObjectsTrack(el) === fromSlot ? { ...el, objectsTrack: toSlot } : el,
      );
      return c;
    });
  };
  const reloadFromServer = async () => {
    if (!sourceAssetId) return;
    try {
      const comp = (await api.magi.getOverlayForAsset(projectId, sourceAssetId)) as MagiOverlayComposition;
      if (comp?.compositionId) {
        setComposition(comp);
        setPersistError(null);
        setSavePending(false);
      }
    } catch {
      /* keep in-memory composition */
    }
  };
  const applyPreset = (presetId: string) => {
    const p = OVERLAY_PRESETS.find((x) => x.id === presetId);
    if (!p) return;
    commit("overlay.preset.apply", `Preset ${p.name}`, (c) => {
      c.overlays.push(...p.build());
      return c;
    });
  };

  const patchElement = (id: string, patch: Partial<MagiOverlayElement>) => {
    const type = "text" in patch ? "overlay.text.update" : "overlay.style.update";
    commit(type, "Update overlay", (c) => {
      c.overlays = mapDeep(c.overlays, id, (el) => {
        const next = { ...el, ...patch, updatedAt: new Date().toISOString() } as MagiOverlayElement;
        return next;
      });
      return c;
    });
  };

  const deleteOverlay = (id: string | null) => {
    if (!id) return;
    commit("overlay.delete", "Delete overlay", (c) => {
      c.overlays = filterDeep(c.overlays, id);
      return c;
    });
    setSelectedOverlayId((current) => (current === id ? null : current));
  };

  const deleteSelected = () => {
    deleteOverlay(selectedOverlayId);
  };

  const duplicateSelected = () => {
    if (!selectedOverlayId) return;
    commit("overlay.duplicate", "Duplicate overlay", (c) => {
      const all = flattenOverlayIds(c.overlays);
      const src = all.find((x) => x.id === selectedOverlayId);
      if (!src) return c;
      const copy = structuredClone(src);
      copy.id = `${src.type}-${Math.random().toString(36).slice(2, 10)}`;
      copy.x = Math.min(0.9, src.x + 0.03);
      copy.y = Math.min(0.9, src.y + 0.03);
      if (copy.type === "group") {
        copy.children = copy.children.map((ch) => ({
          ...ch,
          id: `${ch.type}-${Math.random().toString(36).slice(2, 10)}`,
        }));
      }
      c.overlays.push(copy);
      return c;
    });
  };

  const selected = useMemo(() => {
    if (!selectedOverlayId) return null;
    return flattenOverlayIds(composition.overlays).find((x) => x.id === selectedOverlayId) || null;
  }, [composition, selectedOverlayId]);

  const renderComposition = async () => {
    const result = await api.magi.renderOverlay(projectId, {
      compositionId: composition.compositionId,
      composition,
    });
    return result;
  };

  const approveOverlayProposal = () => {
    if (!overlayProposal) return;
    const op = String(overlayProposal.overlayOp || "");
    const payload = (overlayProposal.overlayPayload || {}) as Record<string, unknown>;
    if (op === "overlay.proposeCreateLowerThird") {
      addLowerThird(String(payload.primary || "NAME"), String(payload.secondary || "Role"));
    } else if (op === "overlay.proposeCreateText") {
      commit("overlay.create", "Add text (command)", (c) => {
        const el = createTextElement({
          text: String(payload.text || "Title"),
          textStyle: {
            ...createTextElement().textStyle,
            alignment: payload.align === "center" ? "center" : "left",
          },
          backgroundStyle: payload.background
            ? { ...createTextElement().backgroundStyle!, enabled: true }
            : createTextElement().backgroundStyle,
        });
        c.overlays.push(el);
        return c;
      });
    } else if (op === "overlay.proposeCreateShape") {
      addShape((payload.shape as MagiVectorShape) || "rectangle");
    } else if (op === "overlay.proposeDelete") {
      deleteSelected();
    }
    setOverlayProposal(null);
  };

  return {
    composition,
    selectedOverlayId,
    setSelectedOverlayId,
    selected,
    snapEnabled,
    setSnapEnabled,
    safeGuides,
    setSafeGuides,
    overlayProposal,
    setOverlayProposal,
    persistError,
    addText,
    addLowerThird,
    addShape,
    addImage,
    bringForward,
    sendBackward,
    bringToFront,
    sendToBack,
    reassignObjectsTrack,
    reloadFromServer,
    applyPreset,
    patchElement,
    deleteSelected,
    deleteOverlay,
    duplicateSelected,
    replaceComposition: (next: MagiOverlayComposition, nextSelectedId?: string | null) => {
      setPersistError(null);
      if (typeof nextSelectedId !== "undefined") setSelectedOverlayId(nextSelectedId);
      persist(next);
    },
    persistNow,
    savePending,
    isSaving,
    renderComposition,
    approveOverlayProposal,
    rejectOverlayProposal: () => setOverlayProposal(null),
    timelineItems: flattenOverlayIds(composition.overlays).filter((el) => el.type !== "group" || el.groupKind),
    presets: OVERLAY_PRESETS,
  };
}
