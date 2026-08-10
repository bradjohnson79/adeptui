import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import "./split-pane.css";

type SplitPaneProps = {
  storageKey: string;
  initialPrimarySize?: number;
  minPrimary?: number;
  minSecondary?: number;
  orientation?: "horizontal" | "vertical";
  primaryCollapsed?: boolean;
  secondaryCollapsed?: boolean;
  primary: ReactNode;
  secondary: ReactNode;
  className?: string;
  /** When token changes, apply `size` (pixels) and persist — used by layout presets. */
  primarySizeRequest?: { size: number; token: number } | null;
  onPrimarySizeChange?: (size: number) => void;
};

function loadSize(key: string, fallback: number): number {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const n = Number(raw);
    return Number.isFinite(n) ? n : fallback;
  } catch {
    return fallback;
  }
}

export function SplitPane({
  storageKey,
  initialPrimarySize = 280,
  minPrimary = 200,
  minSecondary = 240,
  orientation = "horizontal",
  primaryCollapsed = false,
  secondaryCollapsed = false,
  primary,
  secondary,
  className = "",
  primarySizeRequest = null,
  onPrimarySizeChange,
}: SplitPaneProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [primarySize, setPrimarySize] = useState(() => loadSize(storageKey, initialPrimarySize));
  const dragging = useRef(false);
  const lastRequestToken = useRef<number | null>(null);

  useEffect(() => {
    if (!primarySizeRequest) return;
    if (lastRequestToken.current === primarySizeRequest.token) return;
    lastRequestToken.current = primarySizeRequest.token;
    const next = Math.max(minPrimary, primarySizeRequest.size);
    setPrimarySize(next);
  }, [primarySizeRequest, minPrimary]);

  const onPrimarySizeChangeRef = useRef(onPrimarySizeChange);
  onPrimarySizeChangeRef.current = onPrimarySizeChange;

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, String(primarySize));
    } catch {
      /* ignore */
    }
    onPrimarySizeChangeRef.current?.(primarySize);
  }, [primarySize, storageKey]);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, []);

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging.current || !rootRef.current) return;
      const rect = rootRef.current.getBoundingClientRect();
      const total = orientation === "horizontal" ? rect.width : rect.height;
      const pos = orientation === "horizontal" ? e.clientX - rect.left : e.clientY - rect.top;
      const maxPrimary = total - minSecondary - 6;
      const next = Math.min(Math.max(pos, minPrimary), maxPrimary);
      setPrimarySize(next);
    },
    [minPrimary, minSecondary, orientation],
  );

  const onPointerUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!rootRef.current) return;
      const step = e.shiftKey ? 40 : 16;
      let delta = 0;
      if (orientation === "horizontal") {
        if (e.key === "ArrowLeft") delta = -step;
        if (e.key === "ArrowRight") delta = step;
      } else {
        if (e.key === "ArrowUp") delta = -step;
        if (e.key === "ArrowDown") delta = step;
      }
      if (!delta) return;
      e.preventDefault();
      const rect = rootRef.current.getBoundingClientRect();
      const total = orientation === "horizontal" ? rect.width : rect.height;
      const maxPrimary = total - minSecondary - 6;
      setPrimarySize((prev) => Math.min(Math.max(prev + delta, minPrimary), maxPrimary));
    },
    [minPrimary, minSecondary, orientation],
  );

  const row = orientation === "horizontal";

  return (
    <div
      ref={rootRef}
      className={["ds-split", row ? "ds-split--row" : "ds-split--col", className].filter(Boolean).join(" ")}
      data-testid="ds-split-pane"
    >
      <div
        className={["ds-split__pane", primaryCollapsed ? "is-collapsed" : ""].filter(Boolean).join(" ")}
        style={row ? { width: primarySize, flex: "0 0 auto" } : { height: primarySize, flex: "0 0 auto" }}
        data-testid="ds-split-primary"
      >
        {primary}
      </div>
      {!primaryCollapsed && !secondaryCollapsed ? (
        <div
          className="ds-split__handle"
          role="separator"
          aria-orientation={row ? "vertical" : "horizontal"}
          aria-valuenow={Math.round(primarySize)}
          tabIndex={0}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onKeyDown={onKeyDown}
        />
      ) : null}
      <div
        className={["ds-split__pane", secondaryCollapsed ? "is-collapsed" : ""].filter(Boolean).join(" ")}
        style={{ flex: "1 1 auto" }}
        data-testid="ds-split-secondary"
      >
        {secondary}
      </div>
    </div>
  );
}
