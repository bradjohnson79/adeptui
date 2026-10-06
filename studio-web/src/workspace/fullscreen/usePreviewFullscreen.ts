import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { browserFullscreenAdapter } from "./platformAdapter";

/**
 * Lightweight fullscreen hook for the Preview Monitor container.
 *
 * Unlike `useWorkspaceFullscreen` (which fullscreens the entire Timeline UI),
 * this hook fullscreens ONLY the Preview Monitor container so the creator
 * can view the current preview in isolation without losing playback state.
 *
 * The video element is NOT remounted — we fullscreen the container, so the
 * existing `<video>` keeps its current time, play/pause, and volume state.
 */

export type UsePreviewFullscreenResult = {
  containerRef: RefObject<HTMLDivElement | null>;
  isFullscreen: boolean;
  toggleFullscreen: () => Promise<void>;
  enterFullscreen: () => Promise<void>;
  exitFullscreen: () => Promise<void>;
  error: string | null;
};

export function usePreviewFullscreen(): UsePreviewFullscreenResult {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [apiFullscreen, setApiFullscreen] = useState(false);
  const [expandedFallback, setExpandedFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isFullscreen = apiFullscreen || expandedFallback;

  const isOurElement = useCallback((el: Element | null) => {
    if (!el || !containerRef.current) return false;
    return el === containerRef.current || containerRef.current.contains(el);
  }, []);

  const syncFromDocument = useCallback(() => {
    const fsEl = browserFullscreenAdapter.getFullscreenElement();
    const ours = isOurElement(fsEl);
    setApiFullscreen(ours);
    if (ours) setExpandedFallback(false);
  }, [isOurElement]);

  useEffect(() => {
    // Listen for fullscreenchange events to keep state in sync.
    const handler = () => syncFromDocument();
    document.addEventListener("fullscreenchange", handler);
    document.addEventListener("webkitfullscreenchange", handler as EventListener);
    return () => {
      document.removeEventListener("fullscreenchange", handler);
      document.removeEventListener("webkitfullscreenchange", handler as EventListener);
    };
  }, [syncFromDocument]);

  const enterFullscreen = useCallback(async () => {
    setError(null);
    if (!containerRef.current) return;
    try {
      await browserFullscreenAdapter.requestFullscreen(containerRef.current);
    } catch {
      // Headless and embedded browsers reject the Fullscreen API. Keep the
      // same transport on the Preview stage so play, seek, Re-Take, and Exit
      // stay available.
      setExpandedFallback(true);
      setError(null);
    }
  }, []);

  const exitFullscreen = useCallback(async () => {
    setError(null);
    setExpandedFallback(false);
    if (!browserFullscreenAdapter.getFullscreenElement()) return;
    try {
      await browserFullscreenAdapter.exitFullscreen();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not exit fullscreen");
    }
  }, []);

  const toggleFullscreen = useCallback(async () => {
    if (apiFullscreen || expandedFallback) {
      await exitFullscreen();
    } else {
      await enterFullscreen();
    }
  }, [apiFullscreen, expandedFallback, enterFullscreen, exitFullscreen]);

  return {
    containerRef,
    isFullscreen,
    toggleFullscreen,
    enterFullscreen,
    exitFullscreen,
    error,
  };
}
