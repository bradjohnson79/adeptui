import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  magneticSnapMovingEdge,
  type MagneticSnapTarget,
} from "../../timelineMaster/magneticSnap";

export type ClipDragMode = "move" | "trim-left" | "trim-right";

export type ClipGeometry = { start: number; length: number };

type DragState = {
  mode: ClipDragMode;
  originStart: number;
  originLength: number;
  startX: number;
  preview: ClipGeometry;
  moved: boolean;
};

export function TrackClipInteractive({
  clipId,
  start,
  length,
  boardDuration,
  dragMaxSec,
  boardWidthPx,
  snapEnabled,
  snapTargets = [],
  selected,
  className,
  style,
  testId,
  domId,
  ariaLabel,
  onSelect,
  onCommit,
  onActivate,
  children,
}: {
  clipId: string;
  start: number;
  length: number;
  boardDuration: number;
  /** Sequence end for drag clamp. Defaults to the visible scale. */
  dragMaxSec?: number;
  boardWidthPx: number;
  snapEnabled: boolean;
  snapTargets?: MagneticSnapTarget[];
  selected?: boolean;
  className?: string;
  style?: CSSProperties;
  testId?: string;
  domId?: string;
  ariaLabel?: string;
  onSelect: () => void;
  onCommit: (next: ClipGeometry, mode: ClipDragMode) => void;
  /** Double-click opens the existing clip editor. Not a drag. */
  onActivate?: () => void;
  children: ReactNode;
}) {
  const [drag, setDrag] = useState<DragState | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const listenersRef = useRef<{ move: (event: PointerEvent) => void; up: () => void } | null>(null);
  const lastClickRef = useRef<{ t: number }>({ t: 0 });
  const pxPerSec = boardWidthPx / Math.max(0.1, boardDuration);
  const preview = drag?.preview || { start, length };
  const leftPct = (preview.start / Math.max(0.1, boardDuration)) * 100;
  const widthPct = (Math.max(0.15, preview.length) / Math.max(0.1, boardDuration)) * 100;

  const stopListening = () => {
    const listeners = listenersRef.current;
    if (!listeners) return;
    window.removeEventListener("pointermove", listeners.move);
    window.removeEventListener("pointerup", listeners.up);
    listenersRef.current = null;
  };

  useEffect(() => () => stopListening(), []);

  const begin = (mode: ClipDragMode, clientX: number) => {
    onSelect();
    stopListening();
    const initial: DragState = {
      mode,
      originStart: start,
      originLength: length,
      startX: clientX,
      preview: { start, length },
      moved: false,
    };
    dragRef.current = initial;
    setDrag(initial);

    const onMove = (event: PointerEvent) => {
      const current = dragRef.current;
      if (!current) return;
      const deltaSec = (event.clientX - current.startX) / Math.max(1, pxPerSec);
      const moved = current.moved || Math.abs(event.clientX - current.startX) > 1;
      const rawStart = current.mode === "trim-right" ? current.originStart : current.originStart + deltaSec;
      const rawLength =
        current.mode === "move"
          ? current.originLength
          : current.mode === "trim-left"
            ? current.originLength - deltaSec
            : current.originLength + deltaSec;
      const snapped = magneticSnapMovingEdge({
        mode: current.mode,
        start: rawStart,
        length: rawLength,
        targets: snapTargets,
        pxPerSec,
        enabled: snapEnabled,
        ignoreSourceId: clipId,
      });
      const limit = Math.max(0.15, dragMaxSec ?? boardDuration);
      const startSec = Math.min(Math.max(0, snapped.start), Math.max(0, limit - 0.15));
      const nextLength = Math.min(Math.max(0.15, snapped.length), Math.max(0.15, limit - startSec));
      const next = { ...current, moved, preview: { start: startSec, length: nextLength } };
      dragRef.current = next;
      setDrag(next);
    };
    const onUp = () => {
      stopListening();
      const current = dragRef.current;
      dragRef.current = null;
      setDrag(null);
      if (current?.moved) {
        lastClickRef.current.t = 0;
        onCommit(current.preview, current.mode);
        return;
      }
      if (!onActivate) return;
      const now = Date.now();
      if (now - lastClickRef.current.t < 400) {
        lastClickRef.current.t = 0;
        onActivate();
        return;
      }
      lastClickRef.current.t = now;
    };
    listenersRef.current = { move: onMove, up: onUp };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  return (
    <div
      id={domId}
      role={ariaLabel ? "button" : undefined}
      aria-label={ariaLabel}
      data-testid={testId || `track-clip-${clipId}`}
      data-clip-id={clipId}
      data-start={String(preview.start)}
      data-length={String(preview.length)}
      className={`track-clip track-clip--interactive ${className || ""} ${selected ? "active" : ""} ${drag ? "is-dragging" : ""}`.trim()}
      style={{
        ...style,
        left: `${leftPct}%`,
        width: `${widthPct}%`,
        userSelect: "none",
        touchAction: "none",
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      onDoubleClick={(e) => {
        if ((e.target as HTMLElement).closest(".track-clip__trim, .track-clip__remove, select, button")) return;
        e.preventDefault();
        e.stopPropagation();
        lastClickRef.current.t = 0;
        onActivate?.();
      }}
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).closest(".track-clip__trim, .track-clip__remove, select, button")) return;
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.setPointerCapture?.(e.pointerId);
        begin("move", e.clientX);
      }}
    >
      <button
        type="button"
        className="track-clip__trim track-clip__trim--left"
        data-testid={`track-clip-trim-left-${clipId}`}
        aria-label="Trim left"
        title="Drag to trim start"
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.setPointerCapture?.(e.pointerId);
          begin("trim-left", e.clientX);
        }}
      />
      <div className="track-clip__body">{children}</div>
      {drag ? (
        <span className="track-clip__drag-readout" data-testid="track-clip-drag-readout">
          {preview.start.toFixed(2)}s · {preview.length.toFixed(2)}s
        </span>
      ) : null}
      <button
        type="button"
        className="track-clip__trim track-clip__trim--right"
        data-testid={`track-clip-trim-right-${clipId}`}
        aria-label="Trim right"
        title="Drag to trim end"
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          e.currentTarget.setPointerCapture?.(e.pointerId);
          begin("trim-right", e.clientX);
        }}
      />
    </div>
  );
}
