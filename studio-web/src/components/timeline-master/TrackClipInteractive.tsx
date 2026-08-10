import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

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

function snap(t: number, enabled: boolean, step: number) {
  if (!enabled) return Math.max(0, t);
  return Math.max(0, Math.round(t / step) * step);
}

export function TrackClipInteractive({
  clipId,
  start,
  length,
  boardDuration,
  boardWidthPx,
  snapEnabled,
  snapStep = 0.25,
  selected,
  className,
  style,
  testId,
  domId,
  onSelect,
  onCommit,
  children,
}: {
  clipId: string;
  start: number;
  length: number;
  boardDuration: number;
  boardWidthPx: number;
  snapEnabled: boolean;
  snapStep?: number;
  selected?: boolean;
  className?: string;
  style?: CSSProperties;
  testId?: string;
  domId?: string;
  onSelect: () => void;
  onCommit: (next: ClipGeometry, mode: ClipDragMode) => void;
  children: ReactNode;
}) {
  const [drag, setDrag] = useState<DragState | null>(null);
  const pxPerSec = boardWidthPx / Math.max(0.1, boardDuration);
  const preview = drag?.preview || { start, length };
  const leftPct = (preview.start / Math.max(0.1, boardDuration)) * 100;
  const widthPct = (Math.max(0.15, preview.length) / Math.max(0.1, boardDuration)) * 100;

  useEffect(() => {
    if (!drag) return;
    const onMove = (event: PointerEvent) => {
      const deltaSec = (event.clientX - drag.startX) / Math.max(1, pxPerSec);
      setDrag((current) => {
        if (!current) return current;
        const moved = current.moved || Math.abs(event.clientX - current.startX) > 1;
        if (current.mode === "move") {
          const nextStart = snap(
            Math.min(Math.max(0, current.originStart + deltaSec), Math.max(0, boardDuration - current.originLength)),
            snapEnabled,
            snapStep,
          );
          return { ...current, moved, preview: { start: nextStart, length: current.originLength } };
        }
        if (current.mode === "trim-left") {
          const rawStart = snap(current.originStart + deltaSec, snapEnabled, snapStep);
          const maxStart = current.originStart + current.originLength - 0.15;
          const nextStart = Math.min(Math.max(0, rawStart), maxStart);
          const nextLength = current.originStart + current.originLength - nextStart;
          return { ...current, moved, preview: { start: nextStart, length: Math.max(0.15, nextLength) } };
        }
        const nextLength = snap(
          Math.max(0.15, current.originLength + deltaSec),
          snapEnabled,
          snapStep,
        );
        const capped = Math.min(nextLength, Math.max(0.15, boardDuration - current.originStart));
        return { ...current, moved, preview: { start: current.originStart, length: capped } };
      });
    };
    const onUp = () => {
      setDrag((current) => {
        // Only commit when the geometry actually changed. A plain select click
        // starts a "move" drag on pointer-down and ends here on pointer-up with
        // no movement — committing it would trigger save → refresh → scene
        // selection reset (the Prompt clip selection slip). NO_PASSIVE_SELECTION_LOSS.
        if (current && current.moved) onCommit(current.preview, current.mode);
        return null;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [boardDuration, drag, onCommit, pxPerSec, snapEnabled, snapStep]);

  const begin = (mode: ClipDragMode, clientX: number) => {
    onSelect();
    setDrag({
      mode,
      originStart: start,
      originLength: length,
      startX: clientX,
      preview: { start, length },
      moved: false,
    });
  };

  return (
    <div
      id={domId}
      data-testid={testId || `track-clip-${clipId}`}
      data-clip-id={clipId}
      className={`track-clip track-clip--interactive ${className || ""} ${selected ? "active" : ""} ${drag ? "is-dragging" : ""}`.trim()}
      style={{
        ...style,
        left: `${leftPct}%`,
        width: `${widthPct}%`,
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).closest(".track-clip__trim, .track-clip__remove, select, button")) return;
        e.preventDefault();
        e.stopPropagation();
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
          begin("trim-right", e.clientX);
        }}
      />
    </div>
  );
}
