import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { frameToTimecode } from "../../magiSequence/engine";
import type { MagiClip, MagiSequenceDocument } from "../../magiSequence/types";
import { useMagiFocus } from "../../magiSequence/MagiFocusContext";

type DragState = {
  mode: "move" | "trim-left" | "trim-right" | "playhead";
  clipId?: string;
  trackId?: string;
  startFrame: number;
  startX: number;
  currentFrame: number;
};

export function MagiSequenceTimeline({
  sequence,
  selection,
  playing,
  selectedAssetId,
  onSelect,
  onSeek,
  onTrim,
  onMove,
  onDropAsset,
  failedAssetIds,
}: {
  sequence: MagiSequenceDocument;
  selection: string[];
  playing: boolean;
  selectedAssetId?: string | null;
  onSelect: (ids: string[], additive?: boolean) => void;
  onSeek: (frame: number) => void;
  onTrim: (clipId: string, edge: "left" | "right", deltaFrames: number) => void;
  onMove: (clipId: string, startFrame: number, trackId?: string) => void;
  onDropAsset: (trackId: string, startFrame: number, assetId: string, mode: "Insert" | "Overwrite") => void;
  failedAssetIds?: ReadonlySet<string> | null;
}) {
  const { t } = useTranslation("magi");
  const { bindRegionProps, setFocusRegion } = useMagiFocus();
  const pxPerFrame = 2;
  const width = Math.max(960, sequence.durationFrames * pxPerFrame);
  const selectedSet = useMemo(() => new Set(selection), [selection]);
  const failedSet = useMemo(() => failedAssetIds || new Set<string>(), [failedAssetIds]);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  const frameFromClientX = (clientX: number, currentTarget: HTMLElement) => {
    const rect = currentTarget.getBoundingClientRect();
    const x = clientX - rect.left + currentTarget.scrollLeft;
    return Math.max(0, Math.round(x / pxPerFrame));
  };

  useEffect(() => {
    if (!dragState) return;
    const onPointerMove = (event: globalThis.PointerEvent) => {
      if (dragState.mode === "playhead" && boardRef.current) {
        const frame = frameFromClientX(event.clientX, boardRef.current);
        setDragState((current) => (current ? { ...current, currentFrame: frame } : current));
        return;
      }
      const deltaFrames = Math.round((event.clientX - dragState.startX) / pxPerFrame);
      setDragState((current) => {
        if (!current) return current;
        if (current.mode === "move") {
          return { ...current, currentFrame: Math.max(0, current.startFrame + deltaFrames) };
        }
        return { ...current, currentFrame: current.startFrame + deltaFrames };
      });
    };
    const onPointerUp = () => {
      if (!dragState) return;
      if (dragState.mode === "playhead") {
        onSeek(dragState.currentFrame);
      } else if (dragState.clipId) {
        if (dragState.mode === "move") {
          onMove(dragState.clipId, dragState.currentFrame, dragState.trackId);
        } else {
          onTrim(
            dragState.clipId,
            dragState.mode === "trim-left" ? "left" : "right",
            dragState.currentFrame - dragState.startFrame,
          );
        }
      }
      setDragState(null);
    };
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp, { once: true });
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [dragState, onMove, onSeek, onTrim]);

  const clipPreview = (clip: MagiClip) => {
    if (!dragState || dragState.clipId !== clip.id) {
      return { startFrame: clip.startFrame, durationFrames: clip.durationFrames };
    }
    if (dragState.mode === "move") {
      return { startFrame: dragState.currentFrame, durationFrames: clip.durationFrames };
    }
    if (dragState.mode === "trim-left") {
      const nextStart = Math.max(0, dragState.currentFrame);
      const shrink = nextStart - clip.startFrame;
      return {
        startFrame: nextStart,
        durationFrames: Math.max(1, clip.durationFrames - shrink),
      };
    }
    return {
      startFrame: clip.startFrame,
      durationFrames: Math.max(1, clip.durationFrames + (dragState.currentFrame - dragState.startFrame)),
    };
  };

  const visualPlayhead =
    dragState?.mode === "playhead" ? dragState.currentFrame * pxPerFrame : sequence.playheadFrame * pxPerFrame;

  return (
    <section
      className="magi-sequence-timeline"
      data-testid="magi-sequence-timeline"
      {...bindRegionProps("timeline")}
    >
      <header className="magi-sequence-timeline__chrome">
        <strong data-testid="magi-timecode">
          {frameToTimecode(
            dragState?.mode === "playhead" ? dragState.currentFrame : sequence.playheadFrame,
            sequence.frameRate,
          )}
        </strong>
        <span data-testid="magi-frame-indicator">
          f{dragState?.mode === "playhead" ? dragState.currentFrame : sequence.playheadFrame}
        </span>
        <span className="magi-sequence-timeline__play-state" data-playing={playing}>
          {playing ? t("playing") : t("paused")}
        </span>
        <span>Snap {sequence.snapEnabled ? "On" : "Off"}</span>
        {selectedAssetId ? (
          <span className="magi-sequence-timeline__drop-hint">Drop to insert, Shift+drop to overwrite</span>
        ) : null}
      </header>

      <div className="magi-sequence-timeline__board track-board-scroll" data-testid="magi-track-board" ref={boardRef}>
        <div
          className="magi-sequence-timeline__ruler track-ruler"
          style={{ width }}
          onMouseDown={() => setFocusRegion("timeline")}
          onClick={(event) => onSeek(frameFromClientX(event.clientX, event.currentTarget))}
          onPointerDown={(event) => {
            setFocusRegion("timeline");
            setDragState({
              mode: "playhead",
              startFrame: sequence.playheadFrame,
              startX: event.clientX,
              currentFrame: frameFromClientX(event.clientX, event.currentTarget),
            });
          }}
        >
          {Array.from({ length: Math.ceil(sequence.durationFrames / sequence.frameRate) + 1 }, (_, i) => (
            <span key={i} className="track-ruler__tick" style={{ left: i * sequence.frameRate * pxPerFrame }}>
              {i}s
            </span>
          ))}
          <div
            className="track-playhead magi-sequence-timeline__playhead"
            data-testid="magi-playhead"
            style={{ left: visualPlayhead }}
          >
            <span className="track-playhead__head" />
          </div>
        </div>

        {sequence.tracks.map((track) => (
          <div key={track.id} className="track-row magi-sequence-timeline__row" data-track={track.label}>
            <div className="magi-sequence-timeline__label">{track.label}</div>
            <div
              className="track-lane"
              style={{ width }}
              data-testid={`magi-track-lane-${track.label}`}
              onClick={(event) => {
                setFocusRegion("timeline");
                if (event.target === event.currentTarget) onSelect([]);
              }}
              onDragOver={(event) => {
                if (event.dataTransfer.types.includes("application/x-adept-asset")) {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = event.shiftKey ? "move" : "copy";
                }
              }}
              onDrop={(event) => {
                const assetId = event.dataTransfer.getData("application/x-adept-asset");
                if (!assetId) return;
                event.preventDefault();
                const frame = frameFromClientX(event.clientX, event.currentTarget);
                onDropAsset(track.id, frame, assetId, event.shiftKey ? "Overwrite" : "Insert");
              }}
            >
              {sequence.clips
                .filter((clip) => clip.trackId === track.id)
                .map((clip) => (
                  <ClipBlock
                    key={clip.id}
                    clip={clip}
                    preview={clipPreview(clip)}
                    pxPerFrame={pxPerFrame}
                    selected={selectedSet.has(clip.id)}
                    failed={failedSet.has(clip.assetId)}
                    onSelect={onSelect}
                    onActivate={() => setFocusRegion("timeline")}
                    onDragStart={(mode, startFrame, startX) =>
                      setDragState({
                        mode,
                        clipId: clip.id,
                        trackId: clip.trackId,
                        startFrame,
                        startX,
                        currentFrame: startFrame,
                      })
                    }
                  />
                ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ClipBlock({
  clip,
  preview,
  pxPerFrame,
  selected,
  failed,
  onSelect,
  onActivate,
  onDragStart,
}: {
  clip: MagiClip;
  preview: { startFrame: number; durationFrames: number };
  pxPerFrame: number;
  selected: boolean;
  failed: boolean;
  onSelect: (ids: string[], additive?: boolean) => void;
  onActivate: () => void;
  onDragStart: (
    mode: "move" | "trim-left" | "trim-right",
    startFrame: number,
    startX: number,
  ) => void;
}) {
  return (
    <div
      className={`track-clip magi-clip${selected ? " is-selected" : ""}${failed ? " is-failed" : ""}`}
      data-testid={`magi-clip-${clip.id}`}
      style={{
        left: preview.startFrame * pxPerFrame,
        width: Math.max(8, preview.durationFrames * pxPerFrame),
      }}
      onMouseDown={(event) => {
        event.stopPropagation();
        onActivate();
        onSelect([clip.id], event.shiftKey || event.metaKey || event.ctrlKey);
      }}
      onPointerDown={(event) => {
        if ((event.target as HTMLElement).closest(".magi-clip__trim")) return;
        event.stopPropagation();
        onActivate();
        onDragStart("move", clip.startFrame, event.clientX);
      }}
    >
      <button
        type="button"
        className="magi-clip__trim magi-clip__trim--left"
        aria-label="Trim left"
        onPointerDown={(event) => {
          event.stopPropagation();
          onActivate();
          onDragStart("trim-left", clip.startFrame, event.clientX);
        }}
      />
      <span>{clip.name || "Clip"}{failed ? " ⚠" : ""}</span>
      <button
        type="button"
        className="magi-clip__trim magi-clip__trim--right"
        aria-label="Trim right"
        onPointerDown={(event) => {
          event.stopPropagation();
          onActivate();
          onDragStart("trim-right", clip.durationFrames, event.clientX);
        }}
      />
    </div>
  );
}
