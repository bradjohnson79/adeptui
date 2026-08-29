import { useState, type CSSProperties, type ReactNode } from "react";
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
  guideTime: number | null;
};

export function TrackClipInteractive({
  clipId,
  start,
  length,
  boardDuration,
  boardWidthPx,
  snapEnabled,
  snapTargets = [],
  selected,
  className,
  style,
  testId,
  domId,
  onSelect,
  onCommit,
  onDoubleClick,
  onSnapGuide,
  locked,
  children,
}: {
  clipId: string;
  start: number;
  length: number;
  boardDuration: number;
  boardWidthPx: number;
  snapEnabled: boolean;
  snapTargets?: MagneticSnapTarget[];
  selected?: boolean;
  className?: string;
  style?: CSSProperties;
  testId?: string;
  domId?: string;
  onSelect: (clipId: string) => void;
  onCommit: (next: ClipGeometry, mode: ClipDragMode) => void;
  onDoubleClick?: () => void;
  onSnapGuide?: (time: number | null) => void;
  locked?: boolean;
  children: ReactNode;
}) {
  const [drag, setDrag] = useState<DragState | null>(null);
  const pxPerSec = boardWidthPx / Math.max(0.1, boardDuration);
  const preview = drag?.preview || { start, length };
  const leftPct = (preview.start / Math.max(0.1, boardDuration)) * 100;
  const widthPct = (Math.max(0.15, preview.length) / Math.max(0.1, boardDuration)) * 100;

  const applyDelta = (current: DragState, clientX: number): DragState => {
    const deltaSec = (clientX - current.startX) / Math.max(1, pxPerSec);
    const moved = current.moved || Math.abs(clientX - current.startX) > 3;
    if (!moved) return current;
    let rawStart = current.originStart;
    let rawLength = current.originLength;
    if (current.mode === "move") {
      rawStart = Math.min(
        Math.max(0, current.originStart + deltaSec),
        Math.max(0, boardDuration - current.originLength),
      );
    } else if (current.mode === "trim-left") {
      const maxStart = current.originStart + current.originLength - 0.15;
      rawStart = Math.min(Math.max(0, current.originStart + deltaSec), maxStart);
      rawLength = current.originStart + current.originLength - rawStart;
    } else {
      rawLength = Math.min(
        Math.max(0.15, current.originLength + deltaSec),
        Math.max(0.15, boardDuration - current.originStart),
      );
    }
    const snapped = magneticSnapMovingEdge({
      mode: current.mode,
      start: rawStart,
      length: rawLength,
      targets: snapTargets,
      pxPerSec,
      enabled: snapEnabled,
      ignoreSourceId: clipId,
    });
    const next: DragState = {
      ...current,
      moved,
      preview: { start: snapped.start, length: snapped.length },
      guideTime: snapped.target ? snapped.time : null,
    };
    onSnapGuide?.(next.guideTime);
    return next;
  };

  const begin = (mode: ClipDragMode, clientX: number) => {
    onSelect(clipId);
    const initial: DragState = {
      mode,
      originStart: start,
      originLength: length,
      startX: clientX,
      preview: { start, length },
      moved: false,
      guideTime: null,
    };
    setDrag(initial);
    let latest = initial;
    const onMove = (event: PointerEvent) => {
      latest = applyDelta(latest, event.clientX);
      setDrag(latest);
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      onSnapGuide?.(null);
      const changed =
        latest.moved &&
        (Math.abs(latest.preview.start - latest.originStart) > 1e-6 ||
          Math.abs(latest.preview.length - latest.originLength) > 1e-6);
      if (changed) onCommit(latest.preview, latest.mode);
      setDrag(null);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };
  return (
    <div
      id={domId}
      data-testid={testId || `track-clip-${clipId}`}
      data-clip-id={clipId}
      data-start={String(preview.start)}
      data-length={String(preview.length)}
      className={`track-clip track-clip--interactive ${className || ""} ${selected ? "active" : ""} ${drag ? "is-dragging" : ""} ${locked ? "is-locked" : ""}`.trim()}
      style={{
        ...style,
        left: `${leftPct}%`,
        width: `${widthPct}%`,
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(clipId);
      }}
      onDoubleClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setDrag(null);
        onSelect(clipId);
        onDoubleClick?.();
      }}
      onPointerDown={(e) => {
        if (locked) {
          onSelect(clipId);
          return;
        }
        if ((e.target as HTMLElement).closest(".track-clip__trim, .track-clip__remove, select, button")) return;
        if (e.detail >= 2) {
          e.preventDefault();
          e.stopPropagation();
          setDrag(null);
          return;
        }
        e.preventDefault();
        e.stopPropagation();
        begin("move", e.clientX);
      }}
    >
      {locked ? null : (
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
      )}
      <div className="track-clip__body">{children}</div>
      {drag ? (
        <span className="track-clip__drag-readout" data-testid="track-clip-drag-readout">
          {preview.start.toFixed(3)}s · {preview.length.toFixed(3)}s
        </span>
      ) : null}
      {locked ? null : (
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
      )}
    </div>
  );
}
