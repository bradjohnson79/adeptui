import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { getFullscreenAdapter } from "./platformAdapter";
import type {
  FullscreenWorkspaceController,
  WorkspaceId,
  WorkspaceViewportMode,
} from "./types";
import { loadWorkspaceViewPreference, rememberViewportMode } from "./workspaceViewPrefs";

const BODY_CLASS = "adept-workspace-fullscreen";
const ATTR = "data-adept-workspace-fs";

export type UseWorkspaceFullscreenOptions = {
  workspaceId: WorkspaceId;
  /** Current non-fullscreen viewport mode (STANDARD or EXPANDED). */
  viewMode: WorkspaceViewportMode;
  /** Restore EXPANDED/STANDARD when leaving browser fullscreen. */
  onRestoreViewMode?: (mode: WorkspaceViewportMode) => void;
  /** Optional layout refresh after enter/exit. */
  onLayoutRefresh?: () => void;
  enabled?: boolean;
};

export type UseWorkspaceFullscreenResult = FullscreenWorkspaceController & {
  containerRef: RefObject<HTMLDivElement | null>;
  showBanner: boolean;
  error: string | null;
  clearError: () => void;
  previousViewMode: WorkspaceViewportMode;
};

function syncBodyClass(active: boolean, workspaceId: WorkspaceId | null) {
  if (typeof document === "undefined") return;
  document.body.classList.toggle(BODY_CLASS, active);
  if (active && workspaceId) {
    document.body.setAttribute(ATTR, workspaceId);
  } else {
    document.body.removeAttribute(ATTR);
  }
}

export function useWorkspaceFullscreen(options: UseWorkspaceFullscreenOptions): UseWorkspaceFullscreenResult {
  const { workspaceId, viewMode, onRestoreViewMode, onLayoutRefresh, enabled = true } = options;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const previousViewModeRef = useRef<WorkspaceViewportMode>(
    loadWorkspaceViewPreference(workspaceId).lastViewMode === "EXPANDED" ? "EXPANDED" : "STANDARD",
  );
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showBanner, setShowBanner] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previousViewMode, setPreviousViewMode] = useState<WorkspaceViewportMode>(previousViewModeRef.current);
  const wasOursRef = useRef(false);

  const isOurElement = useCallback((el: Element | null) => {
    if (!el || !containerRef.current) return false;
    return el === containerRef.current || containerRef.current.contains(el);
  }, []);

  const syncFromDocument = useCallback(() => {
    const adapter = getFullscreenAdapter();
    const el = adapter.getFullscreenElement();
    const ours = isOurElement(el);
    const wasOurs = wasOursRef.current;
    wasOursRef.current = ours;
    setIsFullscreen(ours);
    if (ours) {
      syncBodyClass(true, workspaceId);
      setShowBanner(true);
      window.setTimeout(() => setShowBanner(false), 3200);
      onLayoutRefresh?.();
      return;
    }
    if (wasOurs) {
      syncBodyClass(false, null);
      onRestoreViewMode?.(previousViewModeRef.current);
      onLayoutRefresh?.();
      const focusEl = triggerRef.current;
      if (focusEl && typeof focusEl.focus === "function") {
        window.setTimeout(() => focusEl.focus(), 0);
      }
    } else if (!el) {
      syncBodyClass(false, null);
    }
  }, [isOurElement, onLayoutRefresh, onRestoreViewMode, workspaceId]);

  useEffect(() => {
    if (!enabled) return;
    const onChange = () => syncFromDocument();
    const onError = () => {
      setError("Unable to enter full screen. Your browser may have blocked the request.");
      setIsFullscreen(false);
      syncBodyClass(false, null);
    };
    document.addEventListener("fullscreenchange", onChange);
    document.addEventListener("webkitfullscreenchange", onChange as EventListener);
    document.addEventListener("fullscreenerror", onError);
    document.addEventListener("webkitfullscreenerror", onError as EventListener);
    return () => {
      document.removeEventListener("fullscreenchange", onChange);
      document.removeEventListener("webkitfullscreenchange", onChange as EventListener);
      document.removeEventListener("fullscreenerror", onError);
      document.removeEventListener("webkitfullscreenerror", onError as EventListener);
    };
  }, [enabled, syncFromDocument]);

  // Esc exits our fullscreen (native + explicit exit for automation); Ctrl+Shift+F toggles.
  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      const adapter = getFullscreenAdapter();
      if (event.key === "Escape" && isOurElement(adapter.getFullscreenElement())) {
        event.preventDefault();
        void adapter.exitFullscreen();
        return;
      }
      if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.key.toLowerCase() !== "f") return;
      const root = containerRef.current;
      if (!root) return;
      // Only when focus is inside this workspace (or none claimed)
      const active = document.activeElement;
      if (active && root !== active && !root.contains(active)) return;
      event.preventDefault();
      void (async () => {
        if (isOurElement(adapter.getFullscreenElement())) {
          await adapter.exitFullscreen();
        } else if (root) {
          previousViewModeRef.current = viewMode === "EXPANDED" ? "EXPANDED" : "STANDARD";
          setPreviousViewMode(previousViewModeRef.current);
          rememberViewportMode(workspaceId, previousViewModeRef.current);
          try {
            root.setAttribute("data-workspace-fullscreen", workspaceId);
            await adapter.requestFullscreen(root);
            setError(null);
          } catch {
            setError("Unable to enter full screen. Your browser may have blocked the request.");
          }
        }
      })();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [enabled, isOurElement, viewMode, workspaceId]);

  const enterFullscreen = useCallback(async () => {
    if (!enabled) return;
    const root = containerRef.current;
    if (!root) {
      setError("Unable to enter full screen. Workspace is not ready.");
      return;
    }
    triggerRef.current = (document.activeElement as HTMLElement) || null;
    previousViewModeRef.current = viewMode === "EXPANDED" ? "EXPANDED" : "STANDARD";
    setPreviousViewMode(previousViewModeRef.current);
    rememberViewportMode(workspaceId, previousViewModeRef.current);
    const adapter = getFullscreenAdapter();
    try {
      root.setAttribute("data-workspace-fullscreen", workspaceId);
      await adapter.requestFullscreen(root);
      setError(null);
      // State confirmed via fullscreenchange
    } catch {
      setError("Unable to enter full screen. Your browser may have blocked the request.");
      setIsFullscreen(false);
    }
  }, [enabled, viewMode, workspaceId]);

  const exitFullscreen = useCallback(async () => {
    const adapter = getFullscreenAdapter();
    if (!isOurElement(adapter.getFullscreenElement())) return;
    try {
      await adapter.exitFullscreen();
    } catch {
      /* fullscreenchange will still sync */
    }
  }, [isOurElement]);

  const toggleFullscreen = useCallback(async () => {
    if (isFullscreen) await exitFullscreen();
    else await enterFullscreen();
  }, [enterFullscreen, exitFullscreen, isFullscreen]);

  return {
    workspaceId,
    isFullscreen,
    enterFullscreen,
    exitFullscreen,
    toggleFullscreen,
    containerRef,
    showBanner,
    error,
    clearError: () => setError(null),
    previousViewMode,
  };
}
