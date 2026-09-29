import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from "react";
import { IconSend } from "../CoDirector/icons";
import type { VideoRetakeSession } from "../../timelineMaster/videoRetake";
import { formatRetakeClock, resolveRetakeMarks } from "../../timelineMaster/videoRetake";
import {
  RETAKE_OVERLAY_DEFAULT_W,
  RETAKE_OVERLAY_PAD,
  clampOverlayFrame,
  defaultRetakeOverlayFrame,
  moveOverlayFrame,
  parentBoundsFromElement,
  resizeOverlayFrame,
  type OverlayFrame,
  type ResizeEdge,
} from "../../timelineMaster/retakeOverlayFrame";

const RESIZE_EDGES: ResizeEdge[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];

type DragKind = { mode: "move" | "resize"; edge?: ResizeEdge; pointerId: number; lastX: number; lastY: number };

let cachedFrame: OverlayFrame | null = null;
let cachedUserSized = false;
let cachedUserMoved = false;

function isInteractiveTarget(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    Boolean(target.closest("button:not([data-retake-move]), input, textarea, select, a, [data-resize]"))
  );
}

export function TimelineRetakeOverlay({
  session,
  videoAvailable,
  onMarkIn,
  onMarkOut,
  onPrompt,
  onRemoveBackground,
  onCancel,
  onSubmit,
}: {
  session: VideoRetakeSession;
  videoAvailable: boolean;
  onMarkIn: () => void;
  onMarkOut: () => void;
  onPrompt: (value: string) => void;
  onRemoveBackground: () => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragKind | null>(null);
  const frameRef = useRef<OverlayFrame | null>(cachedFrame);
  const [frame, setFrame] = useState<OverlayFrame | null>(cachedFrame);
  const [userSized, setUserSized] = useState(cachedUserSized);
  const [dragging, setDragging] = useState(false);
  frameRef.current = frame;

  const applyFrame = useCallback((next: OverlayFrame, sized = cachedUserSized) => {
    cachedFrame = next;
    cachedUserSized = sized;
    frameRef.current = next;
    setFrame((prev) =>
      prev && prev.x === next.x && prev.y === next.y && prev.w === next.w && prev.h === next.h ? prev : next,
    );
    setUserSized((prev) => (prev === sized ? prev : sized));
  }, []);

  const syncToStage = useCallback(
    (measureNatural: boolean) => {
      const el = overlayRef.current;
      const bounds = parentBoundsFromElement(el);
      if (!el || !bounds) return;
      if (cachedUserMoved && cachedFrame && (cachedUserSized || !measureNatural)) {
        applyFrame(clampOverlayFrame(cachedFrame, bounds), cachedUserSized);
        return;
      }
      if (cachedUserSized || !measureNatural) {
        if (cachedFrame) applyFrame(clampOverlayFrame(cachedFrame, bounds), cachedUserSized);
        return;
      }
      const seed = cachedFrame
        ? clampOverlayFrame(cachedFrame, bounds)
        : defaultRetakeOverlayFrame(bounds, el.offsetHeight || undefined);
      const prevWidth = el.style.width;
      const prevHeight = el.style.height;
      el.style.width = `${seed.w}px`;
      el.style.height = "auto";
      const natural = Math.max(seed.h, Math.ceil(el.getBoundingClientRect().height));
      el.style.width = prevWidth;
      el.style.height = prevHeight;
      applyFrame(clampOverlayFrame({ ...seed, h: natural }, bounds), false);
    },
    [applyFrame],
  );

  useLayoutEffect(() => {
    if (!session.open || dragRef.current) return;
    syncToStage(!cachedUserSized);
  }, [session.open, session.error, session.emptyCopy, session.disclosure, session.stage, syncToStage]);

  useEffect(() => {
    if (!session.open) return;
    const parent = overlayRef.current?.offsetParent;
    if (!parent || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => syncToStage(false));
    observer.observe(parent);
    return () => observer.disconnect();
  }, [session.open, syncToStage]);

  const applyDragDelta = useCallback(
    (clientX: number, clientY: number) => {
      const drag = dragRef.current;
      const current = frameRef.current;
      const bounds = parentBoundsFromElement(overlayRef.current);
      if (!drag || !current || !bounds) return;
      const dx = clientX - drag.lastX;
      const dy = clientY - drag.lastY;
      if (!dx && !dy) return;
      drag.lastX = clientX;
      drag.lastY = clientY;
      if (drag.mode === "move") {
        cachedUserMoved = true;
        applyFrame(moveOverlayFrame(current, dx, dy, bounds), cachedUserSized);
        return;
      }
      if (drag.edge) {
        cachedUserMoved = true;
        applyFrame(resizeOverlayFrame(current, drag.edge, dx, dy, bounds), true);
      }
    },
    [applyFrame],
  );

  useEffect(() => {
    const onMove = (event: globalThis.PointerEvent | globalThis.MouseEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const isPointer = "pointerId" in event;
      if (drag.pointerId >= 0 && (!isPointer || event.pointerId !== drag.pointerId)) return;
      if (drag.pointerId < 0 && isPointer) return;
      event.preventDefault();
      applyDragDelta(event.clientX, event.clientY);
    };
    const onUp = (event: globalThis.PointerEvent | globalThis.MouseEvent) => {
      if (!dragRef.current) return;
      applyDragDelta(event.clientX, event.clientY);
      dragRef.current = null;
      setDragging(false);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("mouseup", onUp);
    };
  }, [applyDragDelta]);

  const startMove = (event: PointerEvent<HTMLElement> | MouseEvent<HTMLElement>) => {
    if (event.button !== 0 || isInteractiveTarget(event.target) || dragRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    const pointerId = "pointerId" in event ? event.pointerId : -1;
    dragRef.current = { mode: "move", pointerId, lastX: event.clientX, lastY: event.clientY };
    setDragging(true);
  };

  const startResize = (edge: ResizeEdge) => (event: PointerEvent<HTMLElement> | MouseEvent<HTMLElement>) => {
    if (event.button !== 0 || dragRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    cachedUserSized = true;
    cachedUserMoved = true;
    setUserSized(true);
    const pointerId = "pointerId" in event ? event.pointerId : -1;
    dragRef.current = { mode: "resize", edge, pointerId, lastX: event.clientX, lastY: event.clientY };
    setDragging(true);
  };

  if (!session.open) return null;
  const marks = resolveRetakeMarks(session.rangeStart, session.rangeEnd);
  const rangeText = marks.ok
    ? `Repair Range ${formatRetakeClock(marks.start)}\u2013${formatRetakeClock(marks.end)}`
    : "";

  const onOverlayKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    event.preventDefault();
    onCancel();
  };

  const onPromptKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (session.busy) return;
    onSubmit();
  };

  return (
    <div
      ref={overlayRef}
      className={`timeline-retake-overlay${dragging ? " is-dragging" : ""}`}
      data-testid="timeline-retake-overlay"
      role="dialog"
      aria-label="Re-Take"
      onKeyDown={onOverlayKeyDown}
      style={
        frame
          ? {
              left: frame.x,
              top: frame.y,
              width: frame.w,
              height: userSized ? frame.h : undefined,
              minHeight: userSized ? undefined : frame.h,
              transform: "none",
            }
          : {
              left: "50%",
              top: RETAKE_OVERLAY_PAD,
              width: RETAKE_OVERLAY_DEFAULT_W,
              transform: "translateX(-50%)",
            }
      }
    >
      <div className="timeline-retake-overlay__menu">
        <div
          className="timeline-retake-overlay__chrome"
          data-testid="timeline-retake-drag"
          onPointerDown={startMove}
          onMouseDown={startMove}
        >
          <span className="timeline-retake-overlay__grip" aria-hidden />
          <button
            type="button"
            className="timeline-retake-overlay__title"
            data-retake-move=""
            data-testid="timeline-retake-move"
            aria-label="Move Re-Take menu"
            title="Drag to move"
            onPointerDown={startMove}
            onMouseDown={startMove}
            onDragStart={(event) => event.preventDefault()}
          >
            Re-Take
          </button>
          {rangeText ? (
            <div className="timeline-retake-overlay__range" data-testid="timeline-retake-range-label">
              {rangeText}
            </div>
          ) : (
            <div className="timeline-retake-overlay__range is-empty" data-testid="timeline-retake-range-label" />
          )}
          <button
            type="button"
            className="timeline-retake-overlay__close"
            data-testid="timeline-retake-close"
            aria-label="Close Re-Take"
            title="Close Re-Take"
            onClick={onCancel}
          >
            {"\u00d7"}
          </button>
        </div>
        <div className="timeline-retake-overlay__row" role="toolbar" aria-label="Re-Take tools">
          <button type="button" data-testid="timeline-retake-mark-in" title="Mark In" aria-label="Mark In" onClick={onMarkIn}>
            In
          </button>
          <button type="button" data-testid="timeline-retake-mark-out" title="Mark Out" aria-label="Mark Out" onClick={onMarkOut}>
            Out
          </button>
          <button
            type="button"
            className={session.removeBackgroundUsed ? "is-active" : ""}
            data-testid="timeline-retake-remove-background"
            title="Remove Background"
            aria-label="Remove Background"
            aria-pressed={session.removeBackgroundUsed}
            disabled={session.busy || !videoAvailable}
            onClick={onRemoveBackground}
          >
            No BG
          </button>
        </div>
        <div className="timeline-retake-overlay__prompt">
          <label>
            <span className="sr-only">Describe what you want to change</span>
            <textarea
              data-testid="timeline-retake-prompt"
              value={session.prompt}
              placeholder={"Describe what you want to change\u2026"}
              autoComplete="off"
              rows={2}
              disabled={session.busy}
              onChange={(event) => onPrompt(event.target.value)}
              onKeyDown={onPromptKeyDown}
            />
          </label>
          <button
            type="button"
            className="timeline-retake-overlay__send"
            data-testid="timeline-retake-submit"
            aria-label="Re-Take"
            title="Re-Take"
            onClick={onSubmit}
            disabled={session.busy}
          >
            <IconSend width={13} height={13} />
          </button>
        </div>
        {session.stage ? (
          <p className="timeline-retake-overlay__stage" data-testid="timeline-retake-progress">
            {session.stage}
          </p>
        ) : null}
        {session.disclosure ? (
          <p className="timeline-retake-overlay__disclosure" data-testid="timeline-retake-disclosure">
            {session.disclosure}
          </p>
        ) : null}
        {session.emptyCopy ? (
          <p className="timeline-retake-overlay__error" data-testid="timeline-retake-empty" role="status">
            {session.emptyCopy}
          </p>
        ) : null}
        {session.error ? (
          <p className="timeline-retake-overlay__error" data-testid="timeline-retake-error">
            {session.error}
          </p>
        ) : null}
      </div>
      {RESIZE_EDGES.map((edge) => {
        const southEast = edge === "se";
        const Handle = southEast ? "button" : "span";
        return (
          <Handle
            key={edge}
            type={southEast ? "button" : undefined}
            className={`timeline-retake-overlay__resize timeline-retake-overlay__resize--${edge}`}
            data-resize={edge}
            data-testid={southEast ? "timeline-retake-resize" : undefined}
            aria-label={southEast ? "Resize Re-Take menu" : undefined}
            onPointerDown={startResize(edge)}
            onMouseDown={startResize(edge)}
          />
        );
      })}
    </div>
  );
}
