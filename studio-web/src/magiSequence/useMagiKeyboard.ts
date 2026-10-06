import { useEffect, useLayoutEffect, useRef } from "react";
import { matchHotkey, registerWorkspaceKeyHandler } from "../timelineMaster/timelineHotkeys";
import {
  canControlPlayback,
  canDeleteTimelineSelection,
  canFrameStep,
  canUseMagiClipboard,
  canUseMagiUndo,
  isTypingTarget,
} from "./focus";
import { loadMagiHotkeys } from "./magiHotkeys";
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
  onSplit: () => void;
  onCompare: () => void;
  onSplitView: () => void;
  onOpenHotkeys: () => void;
  onZoom: (dir: -1 | 1) => void;
};

export function useMagiKeyboard(handlers: KeyboardHandlers) {
  const handlersRef = useRef(handlers);

  useLayoutEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    return registerWorkspaceKeyHandler("magi", (event) => {
      const currentHandlers = handlersRef.current;
      const region = currentHandlers.focusRegion;
      if (isTypingTarget(event.target)) return;
      const binding = matchHotkey(event, loadMagiHotkeys());
      if (!binding) return;

      const act = (fn: () => void) => {
        event.preventDefault();
        fn();
      };
      const id = binding.actionId;

      if (id === "deleteClip" || id === "deleteClipBackspace") {
        if (!canDeleteTimelineSelection(region)) return;
        act(currentHandlers.onDeleteSelection);
        return;
      }
      if (id === "playPause" || id === "playPauseK") {
        if (!canControlPlayback(region)) return;
        act(currentHandlers.onTogglePlay);
        return;
      }
      if (id === "jogBack" || id === "jogForward") {
        if (!canControlPlayback(region)) return;
        act(() => currentHandlers.onJog(id === "jogBack" ? -1 : 1));
        return;
      }
      if (id === "frameBack" || id === "frameForward") {
        if (!canFrameStep(region)) return;
        act(() => currentHandlers.onFrameStep(id === "frameBack" ? -1 : 1));
        return;
      }
      if (id === "goToStart") {
        if (!canFrameStep(region)) return;
        act(currentHandlers.onHome);
        return;
      }
      if (id === "goToEnd") {
        if (!canFrameStep(region)) return;
        act(currentHandlers.onEnd);
        return;
      }
      if (id === "copy") {
        if (!canUseMagiClipboard(region, currentHandlers.hasSelection)) return;
        act(currentHandlers.onCopy);
        return;
      }
      if (id === "paste") {
        if (!canUseMagiClipboard(region, true)) return;
        act(currentHandlers.onPaste);
        return;
      }
      if (id === "undo") {
        if (!canUseMagiUndo(region)) return;
        act(currentHandlers.onUndo);
        return;
      }
      if (id === "redo") {
        if (!canUseMagiUndo(region)) return;
        act(currentHandlers.onRedo);
        return;
      }
      if (id === "splitAtPlayhead") {
        if (!canDeleteTimelineSelection(region)) return;
        act(currentHandlers.onSplit);
        return;
      }
      if (id === "zoomIn" || id === "zoomOut") {
        act(() => currentHandlers.onZoom(id === "zoomIn" ? 1 : -1));
        return;
      }
      if (id === "compare") {
        act(currentHandlers.onCompare);
        return;
      }
      if (id === "splitView") {
        act(currentHandlers.onSplitView);
        return;
      }
      if (id === "openHotkeys") {
        act(currentHandlers.onOpenHotkeys);
      }
    });
  }, []);
}
