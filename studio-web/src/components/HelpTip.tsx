import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

type BubblePos = {
  top: number;
  left: number;
  arrowLeft: number;
  placeAbove: boolean;
};

const VIEW_PAD = 10;
const BUBBLE_MAX_W = 260;
const GAP = 8;

function clampBubblePosition(anchor: DOMRect, bubble: DOMRect | null): BubblePos {
  const width = Math.min(BUBBLE_MAX_W, bubble?.width || BUBBLE_MAX_W);
  const height = bubble?.height || 72;
  const vw = window.innerWidth;
  const vh = window.innerHeight;

  let left = anchor.left;
  let placeAbove = false;
  let top = anchor.bottom + GAP;

  if (top + height > vh - VIEW_PAD && anchor.top - GAP - height >= VIEW_PAD) {
    placeAbove = true;
    top = anchor.top - GAP - height;
  }
  top = Math.max(VIEW_PAD, Math.min(top, vh - VIEW_PAD - height));

  if (left + width > vw - VIEW_PAD) {
    left = vw - VIEW_PAD - width;
  }
  left = Math.max(VIEW_PAD, left);

  const iconCenter = anchor.left + anchor.width / 2;
  const arrowLeft = Math.min(Math.max(14, iconCenter - left), width - 14);

  return { top, left, arrowLeft, placeAbove };
}

type HelpTipProps = {
  /** Legacy short tip body (also used as aria-label when `label` omitted). */
  text?: string;
  /** Accessible question label, e.g. "What is Production DNA Profile?" */
  label?: string;
  /** Explanation body shown in the bubble. */
  content?: string;
};

/** Circular (?) help tip — hover, focus, touch/click; Escape dismisses. Not title-only. */
export function HelpTip({ text, label, content }: HelpTipProps) {
  const tipId = useId();
  const btnRef = useRef<HTMLButtonElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<BubblePos | null>(null);
  const body = (content || text || "").trim();
  const ariaLabel = (label || text || "More information").trim();

  const reposition = useCallback(() => {
    const anchor = btnRef.current?.getBoundingClientRect();
    if (!anchor) return;
    const bubble = bubbleRef.current?.getBoundingClientRect() ?? null;
    setPos(clampBubblePosition(anchor, bubble));
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setPos(null);
      return;
    }
    reposition();
    const id = window.requestAnimationFrame(() => reposition());
    return () => window.cancelAnimationFrame(id);
  }, [open, body, reposition]);

  useEffect(() => {
    if (!open) return;
    const onReposition = () => reposition();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    window.addEventListener("scroll", onReposition, true);
    window.addEventListener("resize", onReposition);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onReposition, true);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, reposition]);

  const show = () => setOpen(true);
  const hide = () => setOpen(false);

  const bubble =
    open && typeof document !== "undefined"
      ? createPortal(
          <span
            ref={bubbleRef}
            id={tipId}
            className={`help-tip-bubble help-tip-bubble--portal${pos?.placeAbove ? " help-tip-bubble--above" : ""}`}
            role="tooltip"
            style={
              pos
                ? {
                    top: pos.top,
                    left: pos.left,
                    ["--help-tip-arrow-left" as string]: `${pos.arrowLeft}px`,
                  }
                : { top: 0, left: 0, opacity: 0 }
            }
          >
            {label ? <strong className="help-tip-bubble__label">{label}</strong> : null}
            {body}
          </span>,
          document.body,
        )
      : null;

  return (
    <button
      ref={btnRef}
      type="button"
      className={`help-tip${open ? " help-tip--open" : ""}`}
      aria-label={ariaLabel}
      aria-expanded={open}
      aria-describedby={open ? tipId : undefined}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        setOpen((v) => !v);
      }}
      onMouseDown={(e) => e.stopPropagation()}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span className="help-tip-icon" aria-hidden="true">
        ?
      </span>
      {bubble}
    </button>
  );
}

/** Panel title row with optional trailing actions and a help tip. */
export function PanelHeading({
  title,
  tip,
  children,
  as = "h2",
}: {
  title: string;
  tip: string;
  children?: ReactNode;
  as?: "h2" | "h3" | "h4" | "strong";
}) {
  const Tag = as;
  return (
    <div className="panel-heading">
      <div className="panel-heading-title">
        <Tag>{title}</Tag>
        <HelpTip text={tip} />
      </div>
      {children ? <div className="panel-heading-actions">{children}</div> : null}
    </div>
  );
}
