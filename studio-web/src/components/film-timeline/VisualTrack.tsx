import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type PointerEvent as ReactPointerEvent } from "react";
import { api } from "../../api";
import { getFilmTimelineZoom, setFilmTimelineZoom, subscribeFilmTimelineZoom } from "../../filmTimeline/filmTimelineZoom";
import { stepFilmTimelineZoom } from "../../timelineMaster/timelineZoom";
import {
  compositionUnitBounds,
  pxToSeconds,
  sceneDuration,
  secondsToPx,
  trackFollowScroll,
  trackViewportOverflow,
  visualPixelsPerSecond,
  visualRulerTicks,
  type VisualClip,
} from "../../filmTimeline/visualTrack";

type PendingClip = { id: string; label: string; durationSec: number; placement?: "start" | "end" };

type Props = {
  clips: VisualClip[];
  pending: PendingClip | null;
  selectedId: string;
  playheadSec: number;
  rangeStart: number | null;
  rangeEnd: number | null;
  projectId: string;
  onSelect: (clip: VisualClip) => void;
  onDelete: (clip: VisualClip) => void;
  onSeek: (sceneTime: number) => void;
  onAdd: () => void;
  onAddPrevious?: () => void;
  onAddFromLibrary: () => void;
  onMove: (clip: VisualClip, direction: "earlier" | "later") => void;
  onStitch: () => void;
  canStitch: boolean;
  stitching: boolean;
  stitchNote: string;
  sceneId?: string;
  initialScrollLeft?: number;
  onViewportScroll?: (scrollLeft: number) => void;
};

function filmstripCount(widthPx: number): number {
  const width = Math.max(160, widthPx);
  return Math.min(16, Math.max(2, Math.round(width / 140)));
}

function Filmstrip({ src, widthPx }: { src: string; widthPx: number }) {
  const [frames, setFrames] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);
  const count = filmstripCount(widthPx);
  useEffect(() => {
    let cancel = false;
    const video = document.createElement("video");
    video.muted = true;
    video.preload = "auto";
    // The asset host is a different origin from the creator UI. Anonymous CORS
    // lets the existing frame sampler read pixels; without it the canvas is
    // tainted and every shot stays a blank block.
    video.crossOrigin = "anonymous";
    video.src = src;
    const canvas = document.createElement("canvas");
    canvas.width = 160;
    canvas.height = 90;
    const ctx = canvas.getContext("2d");
    const finish = (shots: string[]) => {
      if (!cancel && shots.length) setFrames(shots);
    };
    video.onerror = () => {
      if (!cancel) setFailed(true);
    };
    video.onloadedmetadata = () => {
      if (!ctx) {
        if (!cancel) setFailed(true);
        return;
      }
      const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 1;
      const shots: string[] = [];
      let index = 0;
      const capture = () => {
        if (cancel) return;
        if (index >= count) {
          finish(shots);
          return;
        }
        const at = ((index + 0.5) / count) * Math.max(0.05, duration - 0.05);
        const onSeeked = () => {
          video.removeEventListener("seeked", onSeeked);
          try {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            shots.push(canvas.toDataURL("image/jpeg", 0.62));
          } catch {
            if (!cancel) setFailed(true);
            return;
          }
          index += 1;
          capture();
        };
        video.addEventListener("seeked", onSeeked);
        video.currentTime = Math.min(at, Math.max(0, duration - 0.04));
      };
      capture();
    };
    return () => {
      cancel = true;
      video.removeAttribute("src");
      video.load();
    };
  }, [src, count]);
  if (failed) return <video className="film-visual__filmstrip-video" src={src} muted playsInline preload="metadata" />;
  if (!frames.length) return <div className="film-visual__filmstrip is-loading" />;
  return (
    <div className="film-visual__filmstrip">
      {frames.map((frame, index) => (
        <img key={index} src={frame} alt="" />
      ))}
    </div>
  );
}

export function VisualTrack({
  clips,
  pending,
  selectedId,
  playheadSec,
  rangeStart,
  rangeEnd,
  projectId,
  onSelect,
  onDelete,
  onSeek,
  onAdd,
  onAddPrevious,
  onAddFromLibrary,
  onMove,
  onStitch,
  canStitch,
  stitching,
  stitchNote,
  sceneId = "",
  initialScrollLeft = 0,
  onViewportScroll,
}: Props) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [menuId, setMenuId] = useState("");
  const moveBounds = compositionUnitBounds(clips);
  const tickerDrag = useRef(false);
  const [viewport, setViewport] = useState({ scrollLeft: 0, clientWidth: 0, scrollWidth: 0 });
  const overflow = trackViewportOverflow(viewport.scrollWidth, viewport.clientWidth);
  const fits = overflow < 2;

  const measure = () => {
    const el = scrollRef.current;
    if (!el) return;
    const next = { scrollLeft: el.scrollLeft, clientWidth: el.clientWidth, scrollWidth: el.scrollWidth };
    setViewport((current) =>
      current.scrollLeft === next.scrollLeft && current.clientWidth === next.clientWidth && current.scrollWidth === next.scrollWidth
        ? current
        : next,
    );
    onViewportScroll?.(el.scrollLeft);
  };

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollLeft = Math.max(0, initialScrollLeft);
    measure();
    // Restore once per scene visit. Later scroll reports stay in the parent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sceneId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => measure();
    el.addEventListener("scroll", onScroll, { passive: true });
    const observer = new ResizeObserver(() => measure());
    observer.observe(el);
    measure();
    return () => {
      el.removeEventListener("scroll", onScroll);
      observer.disconnect();
    };
  }, [clips.length, pending?.id, sceneId]);

  const zoom = useSyncExternalStore(subscribeFilmTimelineZoom, getFilmTimelineZoom, getFilmTimelineZoom);
  const pxPerSec = visualPixelsPerSecond(zoom);
  const toPx = (seconds: number) => secondsToPx(seconds, pxPerSec);
  const sceneEnd = sceneDuration(clips);
  const pendingAtStart = Boolean(pending && pending.placement === "start" && clips.length);
  const pendingTail = pending && !pendingAtStart ? Math.max(0, pending.durationSec) : 0;
  const span = sceneEnd + pendingTail;
  const lead = clips.length ? 52 : 0;
  const gutter = pendingAtStart ? toPx(Math.max(0, pending?.durationSec || 0)) : 0;
  const origin = lead + gutter;
  const ticks = visualRulerTicks(Math.max(span, sceneEnd), pxPerSec);
  const boardWidth = origin + toPx(Math.max(span, 1));
  const playheadTime = Math.min(Math.max(0, playheadSec), Math.max(sceneEnd, 0));
  const playhead = origin + toPx(playheadTime);
  const zoomAnchor = useRef(zoom);

  useLayoutEffect(() => {
    const previous = zoomAnchor.current;
    if (previous === zoom) return;
    const el = scrollRef.current;
    zoomAnchor.current = zoom;
    if (!el) return;
    const oldPx = visualPixelsPerSecond(previous);
    const oldPlayhead = (lead + (pendingAtStart ? secondsToPx(Math.max(0, pending?.durationSec || 0), oldPx) : 0)) + secondsToPx(playheadTime, oldPx);
    const viewX = oldPlayhead - el.scrollLeft;
    const inView = viewX >= -1 && viewX <= el.clientWidth + 1;
    const next = inView ? playhead - viewX : (trackFollowScroll(0, el.clientWidth, playhead) ?? el.scrollLeft);
    const limit = Math.max(0, el.scrollWidth - el.clientWidth);
    el.scrollLeft = Math.max(0, Math.min(next, limit));
    measure();
    // Zoom keeps the playhead's time. Scene changes restore scroll separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoom]);

  useEffect(() => {
    if (tickerDrag.current) return;
    const el = scrollRef.current;
    if (!el) return;
    const next = trackFollowScroll(el.scrollLeft, el.clientWidth, playhead);
    if (next == null || Math.abs(next - el.scrollLeft) < 1) return;
    el.scrollLeft = next;
  }, [playhead]);
  const inPx = rangeStart == null ? null : origin + toPx(rangeStart);
  const outPx = rangeEnd == null ? null : origin + toPx(rangeEnd);
  const range =
    inPx != null && outPx != null && Math.abs(outPx - inPx) > 0.5
      ? { left: Math.min(inPx, outPx), width: Math.abs(outPx - inPx), start: Math.min(rangeStart ?? 0, rangeEnd ?? 0), end: Math.max(rangeStart ?? 0, rangeEnd ?? 0) }
      : null;

  const scrub = (event: ReactPointerEvent<HTMLDivElement>) => {
    const board = event.currentTarget;
    const timeAt = (clientX: number) => {
      const rect = board.getBoundingClientRect();
      return Math.min(span, Math.max(0, pxToSeconds(clientX - rect.left - origin, pxPerSec)));
    };
    const clicked = timeAt(event.clientX);
    try {
      board.setPointerCapture(event.pointerId);
    } catch {
      /* The pointer can already be released. Seeking still follows the drag. */
    }
    onSeek(clicked);
    const move = (ev: PointerEvent) => {
      onSeek(timeAt(ev.clientX));
    };
    const up = () => {
      board.removeEventListener("pointermove", move);
      board.removeEventListener("pointerup", up);
    };
    board.addEventListener("pointermove", move);
    board.addEventListener("pointerup", up);
  };

  return (
    <div className="film-visual" data-testid="film-timeline-track">
      <div className="film-visual__label">Visual</div>
      <div className="film-visual__body">
      <div className="film-visual__tools">
        <div className="film-visual__zoom" data-testid="film-timeline-zoom" data-zoom={zoom}>
          <span className="film-visual__zoom-label">Zoom</span>
          <button
            type="button"
            className="film-visual__zoom-step"
            data-testid="film-timeline-zoom-out"
            aria-label="Zoom out"
            disabled={zoom <= 1}
            onClick={() => setFilmTimelineZoom(stepFilmTimelineZoom(zoom, -1))}
          >
            −
          </button>
          <input
            type="range"
            min={1}
            max={8}
            step={1}
            value={zoom}
            aria-label="Timeline zoom"
            data-testid="film-timeline-zoom-slider"
            onChange={(event) => setFilmTimelineZoom(Number(event.target.value))}
          />
          <button
            type="button"
            className="film-visual__zoom-step"
            data-testid="film-timeline-zoom-in"
            aria-label="Zoom in"
            disabled={zoom >= 8}
            onClick={() => setFilmTimelineZoom(stepFilmTimelineZoom(zoom, 1))}
          >
            +
          </button>
          <span className="film-visual__zoom-value" data-testid="film-timeline-zoom-value">{zoom}×</span>
        </div>
        <button type="button" className="film-visual__library" data-testid="film-timeline-add-from-library" onClick={onAddFromLibrary}>
          Add from Library
        </button>
        <button type="button" className="film-visual__library" data-testid="film-timeline-stitch" disabled={!canStitch} onClick={onStitch}>
          {stitching ? "Stitching scene…" : "Stitch"}
        </button>
        {stitchNote ? (
          <span className="film-visual__stitch-note" data-testid="film-timeline-stitch-note" role="status">
            {stitchNote}
          </span>
        ) : null}
      </div>
      <div className="film-visual__scroll" ref={scrollRef} data-testid="film-timeline-track-scroll">
        <div className="film-visual__board" style={{ width: boardWidth + 52 }} data-px-per-sec={pxPerSec}>
          <div className="film-visual__ruler" data-testid="film-timeline-ruler" onPointerDown={scrub}>
            {ticks.map((tick) => (
              <span key={tick} className="film-visual__tick" style={{ left: origin + toPx(tick) }}>
                {tick}s
              </span>
            ))}
          </div>
          <div className="film-visual__lane" onPointerDown={scrub}>
            {clips.map((clip) => (
              <div
                key={clip.id}
                className={`film-visual__clip${selectedId === clip.id ? " is-selected" : ""}${menuId === clip.id ? " is-menu-open" : ""}`}
                style={{ left: origin + toPx(clip.start), width: toPx(clip.durationSec) }}
                data-testid="film-timeline-batch"
                data-shot-number={clip.shotNumber || undefined}
                data-start={clip.start}
                data-end={clip.end}
                onPointerDown={(event) => event.stopPropagation()}
              >
                <button
                  type="button"
                  className="film-visual__menu"
                  data-testid="film-timeline-clip-menu"
                  aria-label={`Clip menu for ${clip.label}`}
                  aria-expanded={menuId === clip.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    setMenuId((current) => (current === clip.id ? "" : clip.id));
                  }}
                >
                  ⋯
                </button>
                {menuId === clip.id ? (
                  <div className="film-visual__menu-list" role="menu">
                    <button
                      type="button"
                      role="menuitem"
                      data-testid="film-timeline-move-earlier"
                      disabled={!moveBounds.get(clip.id)?.earlier}
                      onClick={(event) => {
                        event.stopPropagation();
                        setMenuId("");
                        onMove(clip, "earlier");
                      }}
                    >
                      Move Earlier
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      data-testid="film-timeline-move-later"
                      disabled={!moveBounds.get(clip.id)?.later}
                      onClick={(event) => {
                        event.stopPropagation();
                        setMenuId("");
                        onMove(clip, "later");
                      }}
                    >
                      Move Later
                    </button>
                  </div>
                ) : null}
                <button
                  type="button"
                  className="film-visual__open"
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelect(clip);
                  }}
                >
                  <Filmstrip src={api.assetUrl(clip.assetId, null, projectId)} widthPx={toPx(clip.durationSec)} />
                  <span>{clip.label}</span>
                </button>
                <button
                  type="button"
                  className="film-timeline__remove"
                  aria-label={`Remove ${clip.label}`}
                  data-testid="film-timeline-delete-video"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(clip);
                  }}
                >
                  ×
                </button>
              </div>
            ))}
            {pending ? (
              <div
                className="film-visual__clip is-pending"
                style={{
                  left: pendingAtStart ? lead : origin + toPx(sceneEnd),
                  width: toPx(pending.durationSec),
                }}
                data-testid="film-timeline-batch-pending"
                data-placement={pendingAtStart ? "start" : "end"}
              >
                {pending.label}
              </div>
            ) : null}
          </div>
          {range ? (
            <div
              className="film-visual__range"
              data-testid="film-timeline-retake-range"
              data-start={range.start}
              data-end={range.end}
              style={{ left: range.left, width: range.width }}
            />
          ) : null}
          {inPx != null ? (
            <div className="film-visual__mark is-in" data-testid="film-timeline-mark-in" data-time={rangeStart ?? 0} style={{ left: inPx }}>
              <span>In</span>
            </div>
          ) : null}
          {outPx != null ? (
            <div className="film-visual__mark is-out" data-testid="film-timeline-mark-out" data-time={rangeEnd ?? 0} style={{ left: outPx }}>
              <span>Out</span>
            </div>
          ) : null}
          <div className="film-visual__playhead" data-testid="film-timeline-playhead" data-scene-time={playheadSec} style={{ left: playhead }} />
          {clips.length ? (
            <button
              type="button"
              className="film-timeline__add-batch film-visual__add"
              data-testid="film-timeline-add-previous"
              style={{ left: 0 }}
              title="Create Previous Shot"
              aria-label="Create Previous Shot"
              onClick={onAddPrevious}
            >
              +
            </button>
          ) : null}
          <button
            type="button"
            className="film-timeline__add-batch film-visual__add"
            data-testid="film-timeline-add-batch"
            style={{ left: origin + toPx(span) }}
            title={clips.length ? "Create Next Shot" : "Generate Shot"}
            aria-label={clips.length ? "Create Next Shot" : "Generate Shot"}
            onClick={onAdd}
          >
            +
          </button>
        </div>
      </div>
      <div className="film-visual__ticker">
        <input
          type="range"
          data-testid="film-timeline-track-ticker"
          aria-label="Move through the track"
          min={0}
          max={fits ? 1 : overflow}
          step={1}
          value={fits ? 1 : Math.min(overflow, Math.round(viewport.scrollLeft))}
          disabled={fits}
          onPointerDown={() => {
            tickerDrag.current = true;
          }}
          onPointerUp={() => {
            tickerDrag.current = false;
          }}
          onBlur={() => {
            tickerDrag.current = false;
          }}
          onChange={(event) => {
            const el = scrollRef.current;
            if (!el || fits) return;
            el.scrollLeft = Number(event.target.value);
          }}
        />
      </div>
      </div>
    </div>
  );
}
