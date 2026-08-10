import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";
import { IconButton } from "../ui/Button";
import { PROJECT_TEMPLATES } from "../../dashboardImages";

const SWIPE_THRESHOLD_PX = 40;
const WHEEL_STEP_MS = 320;

export function ProjectTemplateCarousel({
  onSelect,
}: {
  onSelect: (templateId: string) => void;
}) {
  const count = PROJECT_TEMPLATES.length;
  const [active, setActive] = useState(0);
  const [reduceMotion, setReduceMotion] = useState(false);
  const labelId = useId();
  const viewportRef = useRef<HTMLDivElement>(null);
  const pointerStartX = useRef<number | null>(null);
  const pointerDeltaX = useRef(0);
  const wheelLockUntil = useRef(0);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduceMotion(mq.matches);
    sync();
    mq.addEventListener?.("change", sync);
    return () => mq.removeEventListener?.("change", sync);
  }, []);

  const goTo = useCallback(
    (next: number) => {
      if (!count) return;
      setActive(((next % count) + count) % count);
    },
    [count],
  );

  const step = useCallback(
    (dir: -1 | 1) => {
      goTo(active + dir);
    },
    [active, goTo],
  );

  const onPointerDown = (e: ReactPointerEvent) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    pointerStartX.current = e.clientX;
    pointerDeltaX.current = 0;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (pointerStartX.current == null) return;
    pointerDeltaX.current = e.clientX - pointerStartX.current;
  };

  const onPointerUp = () => {
    if (pointerStartX.current == null) return;
    const dx = pointerDeltaX.current;
    pointerStartX.current = null;
    pointerDeltaX.current = 0;
    if (Math.abs(dx) < SWIPE_THRESHOLD_PX) return;
    step(dx < 0 ? 1 : -1);
  };

  const onWheel = (e: ReactWheelEvent) => {
    const horizontal = Math.abs(e.deltaX) > Math.abs(e.deltaY);
    const shiftVertical = e.shiftKey && Math.abs(e.deltaY) > 0;
    if (!horizontal && !shiftVertical) return;
    e.preventDefault();
    const now = Date.now();
    if (now < wheelLockUntil.current) return;
    wheelLockUntil.current = now + WHEEL_STEP_MS;
    const delta = horizontal ? e.deltaX : e.deltaY;
    if (delta === 0) return;
    step(delta > 0 ? 1 : -1);
  };

  // Slide width is percentage of viewport; step by one card (gap handled in CSS via calc).
  const trackStyle: CSSProperties = {
    transform: `translate3d(calc(-${active} * (var(--gs-carousel-slide-basis) + var(--gs-carousel-gap))), 0, 0)`,
    transition: reduceMotion ? "none" : "transform 300ms ease",
  };

  return (
    <div className="gs-carousel" data-testid="template-carousel" aria-labelledby={labelId}>
      <span id={labelId} className="sr-only">
        Browse project templates
      </span>

      <IconButton
        type="button"
        className="gs-carousel__arrow gs-carousel__arrow--prev"
        aria-label="Previous templates"
        data-testid="carousel-prev"
        onClick={() => step(-1)}
      >
        ‹
      </IconButton>

      <div className="gs-carousel__stage">
        <div
          ref={viewportRef}
          className="gs-carousel__viewport"
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div
            className="gs-carousel__track"
            style={trackStyle}
            tabIndex={0}
            role="listbox"
            aria-label="Template slides"
            aria-activedescendant={`carousel-option-${PROJECT_TEMPLATES[active]?.id ?? active}`}
            data-testid="carousel-track"
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") {
                e.preventDefault();
                step(1);
              } else if (e.key === "ArrowLeft") {
                e.preventDefault();
                step(-1);
              } else if (e.key === "Home") {
                e.preventDefault();
                goTo(0);
              } else if (e.key === "End") {
                e.preventDefault();
                goTo(count - 1);
              } else if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                const t = PROJECT_TEMPLATES[active];
                if (t) onSelect(t.id);
              }
            }}
          >
            {PROJECT_TEMPLATES.map((t, i) => (
              <button
                key={t.id}
                id={`carousel-option-${t.id}`}
                type="button"
                role="option"
                aria-selected={i === active}
                className={`gs-carousel__slide ${i === active ? "is-active" : ""}`}
                data-testid={`carousel-slide-${t.id}`}
                onClick={() => {
                  setActive(i);
                  onSelect(t.id);
                }}
              >
                <div className="gs-carousel__media">
                  <div
                    className={`cinematic-media-fallback ${t.image.plate || "aurora-plate"} ${t.image.motif || ""}`.trim()}
                    aria-hidden="true"
                  />
                  <img
                    src={t.image.src}
                    alt={t.image.alt || `${t.title} template — ${t.description}`}
                    loading="lazy"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                  <div className="gs-carousel__lower-third">
                    <span className="gs-carousel__lower-third-kicker">{t.type}</span>
                    <span className="gs-carousel__lower-third-title">{t.title}</span>
                  </div>
                </div>
                <div className="gs-carousel__body">
                  <span className="gs-carousel__desc">{t.description}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="gs-carousel__meta">
          <div className="gs-carousel__dots" role="group" aria-label="Carousel pages">
            {PROJECT_TEMPLATES.map((t, i) => (
              <button
                key={t.id}
                type="button"
                className={`gs-carousel__dot ${i === active ? "is-active" : ""}`}
                aria-label={`Go to template ${i + 1}: ${t.title}`}
                aria-current={i === active ? "true" : undefined}
                data-testid={`carousel-dot-${i}`}
                onClick={() => goTo(i)}
              />
            ))}
          </div>
          <p
            className="gs-carousel__page"
            data-testid="carousel-page-indicator"
            aria-live="polite"
          >
            {active + 1} / {count}
          </p>
        </div>
      </div>

      <IconButton
        type="button"
        className="gs-carousel__arrow gs-carousel__arrow--next"
        aria-label="Next templates"
        data-testid="carousel-next"
        onClick={() => step(1)}
      >
        ›
      </IconButton>
    </div>
  );
}
