import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { DirectorSelection, WorkspaceTab } from "../directorSelection";

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
  const [selection, setSelection] = useState<DirectorSelection>({ kind: null });
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("timeline");
  const [snap, setSnap] = useState(true);
  const [zoom, setZoom] = useState(1);

  const value = useMemo(
    () => ({
      selection,
      setSelection,
      clearSelection: () => setSelection({ kind: null }),
      workspaceTab,
      setWorkspaceTab,
      snap,
      setSnap,
      zoom,
      setZoom,
    }),
    [selection, workspaceTab, snap, zoom]
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
