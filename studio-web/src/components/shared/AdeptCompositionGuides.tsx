import { useEffect, useRef, useState } from "react";
import {
  EMPTY_COMPOSITION_RECT,
  getCompositionRect,
  type CompositionRect,
} from "../../workspace/compositionGuides";
import { normalizeProductionAspect } from "../../workspacePrefs";
import "../../styles/shared/adept-composition-guides.css";

function rectEquals(a: CompositionRect, b: CompositionRect): boolean {
  return (
    Math.abs(a.x - b.x) < 0.5 &&
    Math.abs(a.y - b.y) < 0.5 &&
    Math.abs(a.width - b.width) < 0.5 &&
    Math.abs(a.height - b.height) < 0.5
  );
}

function GuidePrimitives({ label }: { label: string }) {
  return (
    <>
      <div className="adept-composition-guides__frame" data-testid="adept-guides-frame" />
      <div className="adept-composition-guides__action-safe" data-testid="adept-guides-action-safe" />
      <div className="adept-composition-guides__title-safe" data-testid="adept-guides-title-safe" />
      <div className="adept-composition-guides__center-x" data-testid="adept-guides-center-x" />
      <div className="adept-composition-guides__center-y" data-testid="adept-guides-center-y" />
      <span className="adept-composition-guides__label" data-testid="adept-guides-label">
        {label}
      </span>
    </>
  );
}

/**
 * One Adept guide overlay. Viewer-only.
 *
 * mode="fit"  — host is the Preview Monitor viewport. Master rect =
 *               fitAspectRect(host, selected aspect).
 * mode="fill" — host/parent is already the composition (MAGI Fit frame).
 *               Guides fill that rectangle; no second aspect calculation.
 *
 * All primitives are percentage-relative to the master rect and clipped to it.
 */
export function AdeptCompositionGuides({
  host = null,
  aspectRatio,
  visible,
  mode = "fit",
  className = "",
}: {
  host?: HTMLElement | null;
  aspectRatio: string | null | undefined;
  visible: boolean;
  mode?: "fit" | "fill";
  className?: string;
}) {
  const [rect, setRect] = useState<CompositionRect>(EMPTY_COMPOSITION_RECT);
  const rectRef = useRef(EMPTY_COMPOSITION_RECT);
  const label = normalizeProductionAspect(aspectRatio);

  useEffect(() => {
    if (mode === "fill") return;
    if (!visible || !host) {
      if (!rectEquals(rectRef.current, EMPTY_COMPOSITION_RECT)) {
        rectRef.current = EMPTY_COMPOSITION_RECT;
        setRect(EMPTY_COMPOSITION_RECT);
      }
      return;
    }

    const update = () => {
      const box = host.getBoundingClientRect();
      const next = getCompositionRect(box.width, box.height, label);
      if (!rectEquals(rectRef.current, next)) {
        rectRef.current = next;
        setRect(next);
      }
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(host);
    window.addEventListener("resize", update);
    document.addEventListener("fullscreenchange", update);
    document.addEventListener("webkitfullscreenchange", update as EventListener);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
      document.removeEventListener("fullscreenchange", update);
      document.removeEventListener("webkitfullscreenchange", update as EventListener);
    };
  }, [host, label, mode, visible]);

  if (!visible) return null;
  if (mode === "fit" && (rect.width <= 0 || rect.height <= 0)) return null;

  const style =
    mode === "fill"
      ? undefined
      : {
          left: `${rect.x}px`,
          top: `${rect.y}px`,
          width: `${rect.width}px`,
          height: `${rect.height}px`,
        };

  return (
    <div
      key={label}
      className={`adept-composition-guides adept-composition-guides--${mode} ${className}`.trim()}
      data-testid="adept-composition-guides"
      data-guide-aspect={label}
      data-guide-mode={mode}
      style={style}
      aria-hidden="true"
    >
      <GuidePrimitives label={label} />
    </div>
  );
}
