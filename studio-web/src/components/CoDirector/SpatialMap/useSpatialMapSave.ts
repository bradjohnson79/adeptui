/**
 * Spatial Map Save Gate — shared by Spatial Map Express + Standard.
 *
 * Explicit Save commit boundary: "Use in Scene Creator" stays disabled until
 * the current revision has been successfully saved (savedVersion === version),
 * and is disabled again the moment any meaningful edit bumps the version.
 * This hook NEVER auto-saves; it only reports state and performs the explicit
 * save the user requested.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { spatialMapApi } from "./spatialMapApi";
import type { SpatialMapDocument } from "./types";

/** Pure Save Gate state derivation (unit-testable without React). */
export function spatialMapSaveDerivation(document: SpatialMapDocument | null): {
  isDirty: boolean;
  isSaved: boolean;
} {
  if (!document) return { isDirty: true, isSaved: false };
  const savedVersion = document.savedVersion ?? null;
  const isDirty = !savedVersion || savedVersion !== document.version;
  return { isDirty, isSaved: !isDirty };
}

export function spatialMapIsDirty(document: SpatialMapDocument | null): boolean {
  return spatialMapSaveDerivation(document).isDirty;
}

export function spatialMapIsSaved(document: SpatialMapDocument | null): boolean {
  return spatialMapSaveDerivation(document).isSaved;
}

export type SpatialMapSaveStatus = "idle" | "saving" | "saved" | "error";

export type SpatialMapSaveState = {
  /** True when the map has never been saved or any field changed since last save. */
  isDirty: boolean;
  /** True once a revision has been committed (savedVersion === version). */
  isSaved: boolean;
  status: SpatialMapSaveStatus;
  error: string | null;
  /** The document version captured at the last successful save. */
  savedVersion: string | null;
  /** Perform the explicit save. Resolves the freshly committed document. */
  save: () => Promise<SpatialMapDocument | null>;
  /** Clear transient error UI (does not change dirty/saved). */
  clearError: () => void;
};

export function useSpatialMapSave(params: {
  projectId: string;
  document: SpatialMapDocument | null;
}): SpatialMapSaveState {
  const { projectId, document } = params;
  const [status, setStatus] = useState<SpatialMapSaveStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [savedVersion, setSavedVersion] = useState<string | null>(
    document?.savedVersion ?? null,
  );
  const busyRef = useRef(false);

  // Keep the committed version in sync when a freshly saved doc arrives.
  useEffect(() => {
    if (document?.savedVersion != null) {
      setSavedVersion(document.savedVersion);
    }
  }, [document?.savedVersion]);

  const isDirty = spatialMapSaveDerivation(
    document ? { ...document, savedVersion } : document,
  ).isDirty;

  const save = useCallback(async (): Promise<SpatialMapDocument | null> => {
    if (!document) {
      setError("No Spatial Map document to save.");
      setStatus("error");
      return null;
    }
    if (busyRef.current) return document;
    busyRef.current = true;
    setStatus("saving");
    setError(null);
    try {
      const committed = await spatialMapApi.saveMap(projectId, document.id);
      setSavedVersion(committed.savedVersion ?? committed.version ?? null);
      setStatus("saved");
      return committed;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save Spatial Map.");
      setStatus("error");
      return null;
    } finally {
      busyRef.current = false;
    }
  }, [projectId, document]);

  const clearError = useCallback(() => setError(null), []);

  return {
    isDirty,
    isSaved: !isDirty,
    status,
    error,
    savedVersion,
    save,
    clearError,
  };
}

export function useSpatialMapSaveHooks(params: {
  projectId: string;
  document: SpatialMapDocument | null;
  onCommitted?: (doc: SpatialMapDocument) => void;
}): SpatialMapSaveState & { handleSave: () => Promise<void> } {
  const state = useSpatialMapSave(params);
  const handleSave = useCallback(async () => {
    const committed = await state.save();
    if (committed && params.onCommitted) params.onCommitted(committed);
  }, [state, params.onCommitted]);
  return { ...state, handleSave };
}
