import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { DirectorSelection, WorkspaceTab } from "../directorSelection";
import {
  TIMELINE_LAYOUT_EVENT,
  loadTimelineWorkspaceLayout,
  saveTimelineWorkspaceLayout,
  type TimelineWorkspaceLayout,
} from "../timelineMaster/workspaceLayout";

type Ctx = {
  selection: DirectorSelection;
  setSelection: (s: DirectorSelection) => void;
  clearSelection: () => void;
  workspaceTab: WorkspaceTab;
  setWorkspaceTab: (t: WorkspaceTab) => void;
  snap: boolean;
  setSnap: (v: boolean) => void;
  zoom: number;
  setZoom: (z: number) => void;
};

const DirectorSelectionContext = createContext<Ctx | null>(null);

export function DirectorSelectionProvider({ children }: { children: ReactNode }) {
  const initialLayout = loadTimelineWorkspaceLayout();
  const [selection, setSelection] = useState<DirectorSelection>({ kind: null });
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("timeline");
  const [snapState, setSnapState] = useState(initialLayout.snapEnabled);
  const [zoomState, setZoomState] = useState(initialLayout.zoom ?? 1);

  useEffect(() => {
    const onLayout = (event: Event) => {
      const detail = (event as CustomEvent<TimelineWorkspaceLayout>).detail;
      const next = detail || loadTimelineWorkspaceLayout();
      setSnapState(Boolean(next.snapEnabled));
      setZoomState(next.zoom ?? 1);
    };
    window.addEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
    return () => window.removeEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
  }, []);

  const setSnap = (value: boolean) => {
    setSnapState(value);
    saveTimelineWorkspaceLayout({ snapEnabled: value });
  };

  const setZoom = (value: number) => {
    const next = Math.min(3, Math.max(0.5, value));
    setZoomState(next);
    saveTimelineWorkspaceLayout({ zoom: next });
  };

  const value = useMemo(
    () => ({
      selection,
      setSelection,
      clearSelection: () => setSelection({ kind: null }),
      workspaceTab,
      setWorkspaceTab,
      snap: snapState,
      setSnap,
      zoom: zoomState,
      setZoom,
    }),
    [selection, workspaceTab, snapState, zoomState]
  );

  return <DirectorSelectionContext.Provider value={value}>{children}</DirectorSelectionContext.Provider>;
}

export function useDirectorSelection() {
  const ctx = useContext(DirectorSelectionContext);
  if (!ctx) {
    throw new Error("useDirectorSelection requires DirectorSelectionProvider");
  }
  return ctx;
}

/** Optional hook when provider may be absent (Character/Spatial pages). */
export function useDirectorSelectionOptional() {
  return useContext(DirectorSelectionContext);
}
