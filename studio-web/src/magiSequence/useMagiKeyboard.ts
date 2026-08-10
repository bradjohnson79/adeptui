import { useEffect, useLayoutEffect, useRef } from "react";
import {
  canControlPlayback,
  canDeleteTimelineSelection,
  canFrameStep,
  canUseMagiClipboard,
  canUseMagiUndo,
  isTypingTarget,
} from "./focus";
import type { MagiFocusRegion } from "./types";

type KeyboardHandlers = {
  focusRegion: MagiFocusRegion;
  hasSelection: boolean;
  onDeleteSelection: () => void;
  onTogglePlay: () => void;
  onJog: (dir: -1 | 1) => void;
  onShuttle: (rate: number) => void;
  onFrameStep: (delta: number) => void;
  onHome: () => void;
  onEnd: () => void;
  onCopy: () => void;
  onPaste: () => void;
  onUndo: () => void;
  onRedo: () => void;
};

export function useMagiKeyboard(handlers: KeyboardHandlers) {
  const handlersRef = useRef(handlers);

  useLayoutEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const currentHandlers = handlersRef.current;
      const region = currentHandlers.focusRegion;
      const typing = isTypingTarget(event.target);

      if (event.key === "Delete" || event.key === "Backspace") {
        if (typing || !canDeleteTimelineSelection(region)) return;
        event.preventDefault();
        currentHandlers.onDeleteSelection();
        return;
      }

      if (event.key === " " || event.code === "Space") {
        if (typing || !canControlPlayback(region)) return;
        event.preventDefault();
        currentHandlers.onTogglePlay();
        return;
      }

      const key = event.key.toLowerCase();
      if (key === "j" || key === "k" || key === "l") {
        if (typing || !canControlPlayback(region)) return;
        event.preventDefault();
        if (key === "k") currentHandlers.onTogglePlay();
        if (key === "j") currentHandlers.onJog(-1);
        if (key === "l") currentHandlers.onJog(1);
        return;
      }

      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        if (typing || !canFrameStep(region)) return;
        event.preventDefault();
        currentHandlers.onFrameStep(event.key === "ArrowLeft" ? -1 : 1);
        return;
      }

      if (event.key === "Home") {
        if (typing || !canFrameStep(region)) return;
        event.preventDefault();
        currentHandlers.onHome();
        return;
      }
      if (event.key === "End") {
        if (typing || !canFrameStep(region)) return;
        event.preventDefault();
        currentHandlers.onEnd();
        return;
      }

      const mod = event.metaKey || event.ctrlKey;
      if (!mod) return;
      const lower = event.key.toLowerCase();
      if (lower === "c") {
        if (typing || !canUseMagiClipboard(region, currentHandlers.hasSelection)) return;
        event.preventDefault();
        currentHandlers.onCopy();
        return;
      }
      if (lower === "v") {
        if (typing || !canUseMagiClipboard(region, true)) return;
        event.preventDefault();
        currentHandlers.onPaste();
        return;
      }
      if (lower === "z") {
        if (typing || !canUseMagiUndo(region)) return;
        event.preventDefault();
        if (event.shiftKey) currentHandlers.onRedo();
        else currentHandlers.onUndo();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
