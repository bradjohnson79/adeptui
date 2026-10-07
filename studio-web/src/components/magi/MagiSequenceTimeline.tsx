import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { frameToTimecode, recomputeDuration } from "../../magiSequence/engine";
import { resolveOutgoingCut } from "../../magiSequence/transitions";
import { MagiClipWaveform } from "./MagiClipWaveform";
import { trackFollowScroll, visualRulerTicks } from "../../filmTimeline/visualTrack";
import type { MagiClip, MagiSequenceDocument, MagiTrack } from "../../magiSequence/types";
import { canAddObjectsTrack, magiTrackHeaderControl, objectsSlotOf, visibleMagiTracks } from "../../magiSequence/tracks";
import { useMagiFocus } from "../../magiSequence/MagiFocusContext";
import {
  MAGI_TRACK_LABEL_WIDTH,
  MAGI_ZOOM_MAX,
  MAGI_ZOOM_MIN,
  bindMagiZoomStep,
  clampMagiZoom,
  magiClampFrame,
  magiContentWidth,
  magiPlayheadLeft,
  magiPxPerFrame,
  magiRulerLabel,
} from "./magiTimelineScale";

type DragState = {
  mode: "move" | "trim-left" | "trim-right" | "playhead";
  clipId?: string;
  trackId?: string;
  originTrackId?: string;
  startFrame: number;
  startX: number;
  currentFrame: number;
};

export type MagiTimelineMedia = {
  kind: "video" | "image" | "audio";
  thumbUrl: string | null;
  mediaUrl: string | null;
};

function TrackControlIcon({ name, pressed }: { name: "mute" | "eye"; pressed: boolean }) {
  const common = {
    width: 14,
    height: 14,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    "aria-hidden": true as const,
  };
  if (name === "mute") {
    return (
      <svg {...common}>
        <path d="M3 6.5h2.2L9 3.5v9L5.2 9.5H3z" />
        {pressed ? <path d="M11 6.2 14.2 9.8M14.2 6.2 11 9.8" /> : <path d="M11 5.2c1.6 1.4 1.6 4.2 0 5.6" />}
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M1.5 8s2.4-4.2 6.5-4.2S14.5 8 14.5 8 12.1 12.2 8 12.2 1.5 8 1.5 8z" />
      <circle cx="8" cy="8" r="1.7" />
      {pressed ? <path d="M3 13 13 3" /> : null}
    </svg>
  );
}

function formatClipDuration(frames: number, frameRate: number): string {
  const seconds = frames / Math.max(1, frameRate);
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return `${minutes}:${String(rest).padStart(2, "0")}`;
  }
  const rounded = seconds >= 10 ? Math.round(seconds) : Math.round(seconds * 10) / 10;
  return `${rounded}s`;
}

function mediaKindFor(_clip: MagiClip, track: MagiTrack, media?: MagiTimelineMedia): "video" | "image" | "audio" {
  if (track.kind === "audio" || track.kind === "music" || track.kind === "sfx" || track.kind === "fx") return "audio";
  if (media?.kind) return media.kind;
  if (track.kind === "image") return "image";
  return "video";
}

export function MagiSequenceTimeline({
  sequence,
  selection,
  playing,
  selectedAssetId,
  mediaByAssetId,
  onSelect,
  onSeek,
  onTrim,
  onMove,
  onDropAsset,
  failedAssetIds,
  selectedTrackId,
  onSelectTrack,
  onAddObjectsTrack,
  onRemoveObjectsTrack,
  onToggleTrackControl,
}: {
  sequence: MagiSequenceDocument;
  selection: string[];
  playing: boolean;
  selectedAssetId?: string | null;
  mediaByAssetId?: Readonly<Record<string, MagiTimelineMedia>>;
  onSelect: (ids: string[], additive?: boolean) => void;
  onSeek: (frame: number) => void;
  onTrim: (clipId: string, edge: "left" | "right", deltaFrames: number) => void;
  onMove: (clipId: string, startFrame: number, trackId?: string) => void;
  onDropAsset: (trackId: string, startFrame: number, assetId: string, mode: "Insert" | "Overwrite") => void;
  failedAssetIds?: ReadonlySet<string> | null;
  selectedTrackId?: string | null;
  onSelectTrack?: (trackId: string) => void;
  onAddObjectsTrack?: () => void;
  onRemoveObjectsTrack?: () => void;
  onToggleTrackControl?: (trackId: string, control: "mute" | "eye") => void;
}) {
  const { t } = useTranslation("magi");
  const { bindRegionProps, setFocusRegion } = useMagiFocus();
  const [zoom, setZoom] = useState(MAGI_ZOOM_MIN);
  useEffect(() => {
    return bindMagiZoomStep((direction) => setZoom((current) => clampMagiZoom(current + direction)));
  }, []);
  const pxPerFrame = magiPxPerFrame(zoom);
  const extentFrames = recomputeDuration(sequence);
  const durationSec = extentFrames / Math.max(1, sequence.frameRate);
  const contentWidth = magiContentWidth(extentFrames, zoom);
  const sheetWidth = MAGI_TRACK_LABEL_WIDTH + contentWidth;
  const rulerTicks = visualRulerTicks(durationSec, pxPerFrame * Math.max(1, sequence.frameRate));
  const selectedSet = useMemo(() => new Set(selection), [selection]);
  const failedSet = useMemo(() => failedAssetIds || new Set<string>(), [failedAssetIds]);
  const boardRef = useRef<HTMLDivElement | null>(null);
  const laneRef = useRef<HTMLDivElement | null>(null);
  const playheadFrameRef = useRef(sequence.playheadFrame);
  playheadFrameRef.current = sequence.playheadFrame;
  const [dragState, setDragState] = useState<DragState | null>(null);

  const frameFromLane = (clientX: number, lane: HTMLElement) => {
    const rect = lane.getBoundingClientRect();
    const x = clientX - rect.left;
    return magiClampFrame(x / pxPerFrame, extentFrames);
  };
  const scrubRaf = useRef(0);
  const pendingScrub = useRef<number | null>(null);
  const onSeekRef = useRef(onSeek);
  onSeekRef.current = onSeek;
  const scheduleScrub = (frame: number) => {
    pendingScrub.current = frame;
    if (scrubRaf.current) return;
    scrubRaf.current = requestAnimationFrame(() => {
      scrubRaf.current = 0;
      const next = pendingScrub.current;
      pendingScrub.current = null;
      if (next != null) onSeekRef.current(next);
    });
  };

  useLayoutEffect(() => {
    if (dragState?.mode === "playhead") return;
    const board = boardRef.current;
    if (!board) return;
    const playX = MAGI_TRACK_LABEL_WIDTH + magiPlayheadLeft(playheadFrameRef.current, zoom);
    const next = trackFollowScroll(board.scrollLeft, board.clientWidth, playX, 48);
    if (next == null) return;
    board.scrollLeft = next;
  }, [zoom, sequence.playheadFrame, dragState?.mode]);

  useEffect(() => {
    if (!dragState) return;
    const onPointerMove = (event: globalThis.PointerEvent) => {
      if (dragState.mode === "playhead" && laneRef.current) {
        const frame = frameFromLane(event.clientX, laneRef.current);
        setDragState((current) => (current ? { ...current, currentFrame: frame } : current));
        scheduleScrub(frame);
        return;
      }
      const deltaFrames = Math.round((event.clientX - dragState.startX) / pxPerFrame);
      const hoverTrack = document
        .elementFromPoint(event.clientX, event.clientY)
        ?.closest("[data-magi-track-id]") as HTMLElement | null;
      const hoverTrackId = hoverTrack?.dataset.magiTrackId;
      setDragState((current) => {
        if (!current) return current;
        if (current.mode === "move") {
          return {
            ...current,
            currentFrame: Math.max(0, current.startFrame + deltaFrames),
            trackId: hoverTrackId || current.trackId,
          };
        }
        return { ...current, currentFrame: current.startFrame + deltaFrames };
      });
    };
    const onPointerUp = () => {
      if (!dragState) return;
      if (dragState.mode === "playhead") {
        if (scrubRaf.current) {
          cancelAnimationFrame(scrubRaf.current);
          scrubRaf.current = 0;
        }
        pendingScrub.current = null;
        onSeek(dragState.currentFrame);
      } else if (dragState.clipId) {
        if (dragState.mode === "move") {
          const samePlace =
            dragState.currentFrame === dragState.startFrame &&
            (dragState.trackId || dragState.originTrackId) === dragState.originTrackId;
          if (!samePlace) onMove(dragState.clipId, dragState.currentFrame, dragState.trackId);
        } else if (dragState.currentFrame !== dragState.startFrame) {
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
  }, [dragState, onMove, onSeek, onTrim, pxPerFrame]);

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

  const playheadFrame = dragState?.mode === "playhead" ? dragState.currentFrame : sequence.playheadFrame;
  const shownPlayhead =
    dragState?.mode === "playhead" ? dragState.currentFrame : playheadFrame;
  const visualPlayhead = magiPlayheadLeft(shownPlayhead, zoom);

  const setZoomTo = (next: number) => setZoom(clampMagiZoom(next));

  return (
    <section
      className={`magi-sequence-timeline${dragState?.mode === "playhead" ? " is-scrubbing" : ""}`}
      data-testid="magi-sequence-timeline"
      data-zoom={zoom}
      data-duration-frames={extentFrames}
      style={{ ["--magi-label-width" as string]: `${MAGI_TRACK_LABEL_WIDTH}px` }}
      {...bindRegionProps("timeline")}
    >
      <div className="magi-timeline-zoom" data-testid="magi-timeline-zoom">
        <span className="magi-timeline-zoom__label">Zoom</span>
        <button type="button" aria-label="Zoom out" data-testid="magi-timeline-zoom-out" onClick={() => setZoomTo(zoom - 1)}>
          −
        </button>
        <span className="magi-timeline-zoom__end">{MAGI_ZOOM_MIN}×</span>
        <input
          data-testid="magi-timeline-zoom-slider"
          type="range"
          min={MAGI_ZOOM_MIN}
          max={MAGI_ZOOM_MAX}
          step={1}
          value={zoom}
          aria-label="Timeline zoom"
          aria-valuemin={MAGI_ZOOM_MIN}
          aria-valuemax={MAGI_ZOOM_MAX}
          aria-valuenow={zoom}
          onChange={(event) => setZoomTo(Number(event.target.value))}
        />
        <span className="magi-timeline-zoom__end">{MAGI_ZOOM_MAX}×</span>
        <button type="button" aria-label="Zoom in" data-testid="magi-timeline-zoom-in" onClick={() => setZoomTo(zoom + 1)}>
          +
        </button>
        <strong data-testid="magi-timeline-zoom-readout">{zoom}×</strong>
      </div>

      <header className="magi-sequence-timeline__chrome">
        <strong data-testid="magi-timecode">
          {frameToTimecode(playheadFrame, sequence.frameRate)}
        </strong>
        <span data-testid="magi-frame-indicator">f{playheadFrame}</span>
        <span className="magi-sequence-timeline__play-state" data-playing={playing}>
          {playing ? t("playing") : t("paused")}
        </span>
        <span>Snap {sequence.snapEnabled ? "On" : "Off"}</span>
        {selectedAssetId ? (
          <span className="magi-sequence-timeline__drop-hint">Drop to insert, Shift+drop to overwrite</span>
        ) : null}
      </header>

      <div className="magi-sequence-timeline__board track-board-scroll" data-testid="magi-track-board" ref={boardRef}>
        <div className="magi-sequence-timeline__sheet" style={{ width: sheetWidth }}>
          <div className="magi-sequence-timeline__ruler track-ruler" onMouseDown={() => setFocusRegion("timeline")}>
            <div className="magi-sequence-timeline__gutter" data-testid="magi-ruler-gutter" />
            <div
              className="magi-sequence-timeline__time track-ruler__lane"
              data-testid="magi-time-lane"
              ref={laneRef}
              style={{ width: contentWidth }}
              onClick={(event) => onSeek(frameFromLane(event.clientX, event.currentTarget))}
              onPointerDown={(event) => {
                setFocusRegion("timeline");
                setDragState({
                  mode: "playhead",
                  startFrame: sequence.playheadFrame,
                  startX: event.clientX,
                  currentFrame: frameFromLane(event.clientX, event.currentTarget),
                });
              }}
            >
              {rulerTicks.map((seconds) => (
                <span
                  key={seconds}
                  className={`track-ruler__tick${seconds === 0 ? " track-ruler__tick--origin" : ""}`}
                  data-testid="magi-ruler-tick"
                  data-seconds={seconds}
                  style={{ left: seconds * sequence.frameRate * pxPerFrame }}
                >
                  {magiRulerLabel(seconds, durationSec)}
                </span>
              ))}
            </div>
          </div>

          {visibleMagiTracks(sequence.tracks).map((track) => {
            const objectsSlot = objectsSlotOf(track);
            const selected = selectedTrackId === track.id;
            const testId = objectsSlot ? `magi-track-objects-${objectsSlot}` : `magi-track-${track.label}`;
            return (
              <div
                key={track.id}
                className={`track-row magi-sequence-timeline__row${selected ? " is-selected-track" : ""}`}
                data-track={track.label}
                data-magi-track-id={track.id}
                data-objects-slot={objectsSlot ?? undefined}
                data-testid={testId}
              >
                <div
                  className="magi-sequence-timeline__label"
                  data-testid={`magi-track-label-${track.label}`}
                  onClick={() => onSelectTrack?.(track.id)}
                >
                  <span>{track.label}</span>
                  {(() => {
                    const control = magiTrackHeaderControl(track.kind);
                    if (!control || !onToggleTrackControl) return null;
                    const pressed = control === "mute" ? Boolean(track.muted) : Boolean(track.hidden);
                    const action =
                      control === "mute"
                        ? pressed
                          ? `Unmute ${track.label}`
                          : `Mute ${track.label}`
                        : pressed
                          ? `Show ${track.label}`
                          : `Hide ${track.label}`;
                    return (
                      <button
                        type="button"
                        className={`magi-track-control${pressed ? " is-pressed" : ""}`}
                        data-testid={`magi-track-${control}-${track.label}`}
                        aria-pressed={pressed}
                        aria-label={action}
                        title={action}
                        onClick={(event) => {
                          event.stopPropagation();
                          onToggleTrackControl(track.id, control);
                        }}
                      >
                        <TrackControlIcon name={control} pressed={pressed} />
                      </button>
                    );
                  })()}
                  {objectsSlot === 1 && canAddObjectsTrack(sequence.tracks) && onAddObjectsTrack ? (
                    <button
                      type="button"
                      className="magi-objects-add-track"
                      data-testid="magi-objects-add-track"
                      aria-label="Add Objects 2"
                      title="Add Objects 2"
                      onClick={(event) => {
                        event.stopPropagation();
                        onAddObjectsTrack();
                      }}
                    >
                      +
                    </button>
                  ) : null}
                  {objectsSlot === 2 && onRemoveObjectsTrack ? (
                    <button
                      type="button"
                      className="magi-objects-remove-track"
                      data-testid="magi-objects-remove-track"
                      aria-label="Remove Objects 2"
                      title="Remove Objects 2"
                      onClick={(event) => {
                        event.stopPropagation();
                        onRemoveObjectsTrack();
                      }}
                    >
                      ×
                    </button>
                  ) : null}
                </div>
                <div
                  className="track-lane"
                  style={{ width: contentWidth }}
                  data-testid={objectsSlot ? `magi-track-lane-objects-${objectsSlot}` : `magi-track-lane-${track.label}`}
                  onClick={(event) => {
                    setFocusRegion("timeline");
                    onSelectTrack?.(track.id);
                    if (event.target === event.currentTarget) {
                      onSelect([]);
                      onSeek(frameFromLane(event.clientX, event.currentTarget));
                    }
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
                    const frame = frameFromLane(event.clientX, event.currentTarget);
                    onDropAsset(track.id, frame, assetId, event.shiftKey ? "Overwrite" : "Insert");
                  }}
                >
                  {sequence.clips
                    .filter((clip) => {
                      const liveTrackId =
                        dragState?.clipId === clip.id && dragState.mode === "move" && dragState.trackId
                          ? dragState.trackId
                          : clip.trackId;
                      return liveTrackId === track.id;
                    })
                    .map((clip) => (
                      <ClipBlock
                        key={clip.id}
                        clip={clip}
                        track={track}
                        media={mediaByAssetId?.[clip.assetId]}
                        frameRate={sequence.frameRate}
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
                            originTrackId: clip.trackId,
                            startFrame,
                            startX,
                            currentFrame: startFrame,
                          })
                        }
                      />
                    ))}
                  {sequence.clips
                    .filter((clip) => clip.trackId === track.id)
                    .map((clip) => {
                      const cut = resolveOutgoingCut(sequence, clip);
                      const kind = clip.transitionOutId;
                      if (cut.status === "last" && kind === "fade") {
                        const frames = Math.max(1, clip.transitionDurationFrames || sequence.frameRate);
                        const end = clip.startFrame + clip.durationFrames;
                        const start = Math.max(clip.startFrame, end - frames);
                        return (
                          <div
                            key={`${clip.id}-edge-fade`}
                            className="magi-edge-fade"
                            data-testid={`magi-edge-fade-${clip.id}`}
                            style={{ left: start * pxPerFrame, width: Math.max(6, (end - start) * pxPerFrame) }}
                            title={`Fade out ${(frames / Math.max(1, sequence.frameRate)).toFixed(1)}s`}
                          />
                        );
                      }
                      if (cut.status !== "cut" || !kind || kind === "none") return null;
                      const frames = Math.max(1, clip.transitionDurationFrames || sequence.frameRate);
                      const cutFrame = clip.startFrame + clip.durationFrames;
                      return (
                        <button
                          key={`${clip.id}-transition`}
                          type="button"
                          className="magi-transition-marker"
                          data-testid={`magi-transition-${clip.id}`}
                          data-transition={kind}
                          style={{ left: cutFrame * pxPerFrame }}
                          title={`${kind} ${(frames / Math.max(1, sequence.frameRate)).toFixed(1)}s`}
                          aria-label={`${kind} at this cut`}
                          onPointerDown={(event) => event.stopPropagation()}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSelect([clip.id]);
                            onSeek(cutFrame);
                          }}
                        />
                      );
                    })}
                </div>
              </div>
            );
          })}

          <div
            className="magi-playhead-rail"
            data-testid="magi-playhead-rail"
            style={{ left: MAGI_TRACK_LABEL_WIDTH, width: contentWidth }}
          >
            <div
              className="track-playhead magi-sequence-timeline__playhead"
              data-testid="magi-playhead"
              style={{ left: visualPlayhead }}
              onPointerDown={(event) => {
                event.stopPropagation();
                event.preventDefault();
                setFocusRegion("timeline");
                const frame = magiClampFrame(shownPlayhead, extentFrames);
                setDragState({
                  mode: "playhead",
                  startFrame: frame,
                  startX: event.clientX,
                  currentFrame: frame,
                });
              }}
            >
              <span className="track-playhead__head" data-testid="magi-playhead-handle" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ClipBlock({
  clip,
  track,
  media,
  frameRate,
  preview,
  pxPerFrame,
  selected,
  failed,
  onSelect,
  onActivate,
  onDragStart,
}: {
  clip: MagiClip;
  track: MagiTrack;
  media?: MagiTimelineMedia;
  frameRate: number;
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
  const [thumbFailed, setThumbFailed] = useState(false);
  const kind = mediaKindFor(clip, track, media);
  const thumbUrl = kind === "audio" || thumbFailed ? null : media?.thumbUrl || null;
  const duration = formatClipDuration(preview.durationFrames, frameRate);
  return (
    <div
      className={`track-clip magi-clip magi-clip--${kind}${selected ? " is-selected" : ""}${failed ? " is-failed" : ""}${track.muted ? " is-track-muted" : ""}${track.hidden ? " is-track-hidden" : ""}`}
      data-testid={`magi-clip-${clip.id}`}
      data-kind={kind}
      style={{
        left: preview.startFrame * pxPerFrame,
        width: preview.durationFrames * pxPerFrame,
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
      <span className="magi-clip__body">
        {kind === "audio" && media?.mediaUrl ? (
          <MagiClipWaveform
            src={media.mediaUrl}
            inSeconds={Math.max(0, clip.inPoint) / Math.max(1, frameRate)}
            outSeconds={Math.max(clip.inPoint + 1, clip.outPoint || clip.inPoint + clip.durationFrames) / Math.max(1, frameRate)}
          />
        ) : null}
        {thumbUrl ? (
          <img
            className="magi-clip__thumb"
            data-testid={`magi-clip-thumb-${clip.id}`}
            src={thumbUrl}
            alt=""
            draggable={false}
            onError={() => setThumbFailed(true)}
          />
        ) : (
          <span className="magi-clip__glyph" aria-hidden="true">
            {kind === "audio" ? "\u266A" : "\u25B6"}
          </span>
        )}
        <span className="magi-clip__title">{clip.name || "Clip"}{failed ? " \u26A0" : ""}</span>
        <span className="magi-clip__dur">{duration}</span>
      </span>
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
