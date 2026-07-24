import { createContext, useContext, type ReactNode } from "react";

/** Shared Co-Director selection context. Behavior remains owned by existing UI. */
export interface CoDirectorContext {
  projectId?: string;
  projectName?: string;
  sceneId?: string;
  sceneName?: string;
  activeWorkspace?: string;
  selectedProfileId?: string;
  selectedAssetId?: string;
  selectedScriptSegmentId?: string;
  selectedStoryboardPanelId?: string;
  selectedDirectorSequenceId?: string;
  selectedEditorClipId?: string;
}

const Context = createContext<CoDirectorContext | null>(null);

export function CoDirectorProvider({
  value,
  children,
}: {
  value: CoDirectorContext;
  children: ReactNode;
}) {
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useCoDirectorContext(): CoDirectorContext {
  const value = useContext(Context);
  if (!value) {
    throw new Error("useCoDirectorContext must be used within CoDirectorProvider");
  }
  return value;
}

/** Safe outside ProjectEditor (e.g. Home) — returns empty selection. */
export function useCoDirectorContextOptional(): CoDirectorContext {
  return useContext(Context) || {};
}
