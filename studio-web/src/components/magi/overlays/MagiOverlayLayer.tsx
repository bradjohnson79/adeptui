import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { MagiOverlayComposition, MagiOverlayElement } from "./types";

function pct(n: number) {
  return `${(n * 100).toFixed(3)}%`;
}

function renderEl(
  el: MagiOverlayElement,
  selectedId: string | null,
  onSelect: (id: string) => void,
  editingId: string | null,
  onEditText: (id: string, text: string) => void,
  onBeginEdit: (id: string) => void,
  onEndEdit: () => void
): React.ReactNode {
  if (!el.visible) return null;
  if (el.type === "group") {
    return (
      <div
        key={el.id}
        className={`magi-ov-el magi-ov-group ${selectedId === el.id ? "is-selected" : ""}`}
        style={{
          left: pct(el.x),
          top: pct(el.y),
          width: pct(el.width),
          height: pct(el.height),
          opacity: el.opacity,
          transform: `rotate(${el.rotation}deg)`,
          zIndex: el.zIndex,
        }}
        data-overlay-id={el.id}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(el.id);
        }}
      >
        {el.children.map((c) =>
          renderEl(c, selectedId, onSelect, editingId, onEditText, onBeginEdit, onEndEdit)
        )}
      </div>
    );
  }
  if (el.type === "vector") {
    const radius = el.shape === "rounded_rectangle" || el.shape === "circle" ? el.cornerRadius || 8 : 0;
    return (
      <div
        key={el.id}
        className={`magi-ov-el magi-ov-vector ${selectedId === el.id ? "is-selected" : ""}`}
        data-overlay-id={el.id}
        style={{
          left: pct(el.x),
          top: pct(el.y),
          width: pct(el.width),
          height: pct(el.height),
          opacity: el.opacity,
          transform: `rotate(${el.rotation}deg)`,
          zIndex: el.zIndex,
          background: el.fill || "transparent",
          border: el.stroke ? `${el.strokeWidth || 1}px solid ${el.stroke}` : undefined,
          borderRadius: el.shape === "circle" || el.shape === "ellipse" ? "50%" : radius,
        }}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(el.id);
        }}
      />
    );
  }
  const style = el.textStyle;
  const bg = el.backgroundStyle;
  const editing = editingId === el.id;
  return (
    <div
      key={el.id}
      className={`magi-ov-el magi-ov-text ${selectedId === el.id ? "is-selected" : ""}`}
      data-overlay-id={el.id}
      style={{
        left: pct(el.x),
        top: pct(el.y),
        width: pct(el.width),
        height: pct(el.height),
        opacity: el.opacity,
        transform: `rotate(${el.rotation}deg)`,
        zIndex: el.zIndex,
        color: style.color,
        fontSize: `clamp(10px, ${style.fontSize / 20}cqi, ${style.fontSize}px)`,
        fontWeight: style.fontWeight,
        fontStyle: style.fontStyle,
        textDecoration: style.textDecoration,
        textAlign: style.alignment,
        letterSpacing: style.letterSpacing,
        lineHeight: style.lineHeight,
        textTransform: style.uppercase ? "uppercase" : undefined,
        background: bg?.enabled
          ? (() => {
              const hex = bg.fill || "#000";
              const a = Math.round((bg.opacity ?? 0.55) * 255)
                .toString(16)
                .padStart(2, "0");
              return hex.length === 7 ? `${hex}${a}` : hex;
            })()
          : "transparent",
        padding: bg?.enabled
          ? `${bg.paddingTop}px ${bg.paddingRight}px ${bg.paddingBottom}px ${bg.paddingLeft}px`
          : undefined,
        borderRadius: bg?.cornerRadius,
        textShadow: style.shadowEnabled
          ? `${style.shadowOffsetX}px ${style.shadowOffsetY}px ${style.shadowBlur}px ${style.shadowColor}`
          : undefined,
        WebkitTextStroke:
          style.strokeWidth && style.strokeColor
            ? `${style.strokeWidth}px ${style.strokeColor}`
            : undefined,
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(el.id);
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (!el.locked) onBeginEdit(el.id);
      }}
    >
      {editing ? (
        <textarea
          className="magi-ov-text-input"
          aria-label="Edit overlay text"
          autoFocus
          value={el.text}
          onChange={(e) => onEditText(el.id, e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              onEndEdit();
            }
          }}
          onBlur={() => onEndEdit()}
        />
      ) : (
        el.text
      )}
    </div>
  );
}

export function MagiOverlayLayer({
  composition,
  selectedId,
  onSelect,
  onPatchElement,
  snapEnabled,
  safeAreaEnabled,
}: {
  composition: MagiOverlayComposition;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onPatchElement: (id: string, patch: Partial<MagiOverlayElement>) => void;
  snapEnabled: boolean;
  safeAreaEnabled: boolean;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const drag = useRef<{ id: string; ox: number; oy: number; sx: number; sy: number } | null>(null);

  const onPointerDown = (e: ReactPointerEvent) => {
    if (editingId) return;
    const target = (e.target as HTMLElement).closest("[data-overlay-id]") as HTMLElement | null;
    if (!target || !rootRef.current) {
      onSelect(null);
      return;
    }
    const id = target.dataset.overlayId!;
    onSelect(id);
    const el = composition.overlays
      .flatMap((o) => (o.type === "group" ? [o, ...o.children] : [o]))
      .find((x) => x.id === id);
    if (!el || el.locked) return;
    const rect = rootRef.current.getBoundingClientRect();
    drag.current = {
      id,
      ox: el.x,
      oy: el.y,
      sx: (e.clientX - rect.left) / rect.width,
      sy: (e.clientY - rect.top) / rect.height,
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!drag.current || !rootRef.current) return;
    const rect = rootRef.current.getBoundingClientRect();
    let nx = drag.current.ox + (e.clientX - rect.left) / rect.width - drag.current.sx;
    let ny = drag.current.oy + (e.clientY - rect.top) / rect.height - drag.current.sy;
    if (snapEnabled) {
      const snaps = [0.05, 0.5, 0.95, 0.1, 0.9];
      for (const s of snaps) {
        if (Math.abs(nx - s) < 0.015) nx = s;
        if (Math.abs(ny - s) < 0.015) ny = s;
      }
    }
    onPatchElement(drag.current.id, {
      x: Math.min(1.2, Math.max(-0.2, nx)),
      y: Math.min(1.2, Math.max(-0.2, ny)),
    } as Partial<MagiOverlayElement>);
  };

  return (
    <div
      ref={rootRef}
      className="magi-overlay-layer"
      data-testid="magi-overlay-layer"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={() => {
        drag.current = null;
      }}
      onKeyDown={(e) => {
        if (!selectedId || editingId) return;
        const step = e.shiftKey ? 0.02 : 0.005;
        if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) {
          e.preventDefault();
          const el = composition.overlays
            .flatMap((o) => (o.type === "group" ? [o, ...o.children] : [o]))
            .find((x) => x.id === selectedId);
          if (!el || el.locked) return;
          const patch: Partial<MagiOverlayElement> = {};
          if (e.key === "ArrowLeft") patch.x = el.x - step;
          if (e.key === "ArrowRight") patch.x = el.x + step;
          if (e.key === "ArrowUp") patch.y = el.y - step;
          if (e.key === "ArrowDown") patch.y = el.y + step;
          onPatchElement(selectedId, patch);
        }
        if (e.key === "Enter" && !editingId) {
          const el = composition.overlays
            .flatMap((o) => (o.type === "group" ? [o, ...o.children] : [o]))
            .find((x) => x.id === selectedId);
          if (el?.type === "text") setEditingId(el.id);
        }
        if (e.key === "Escape") setEditingId(null);
      }}
      tabIndex={0}
      aria-label="Overlay composition canvas"
    >
      {safeAreaEnabled || composition.safeAreaEnabled ? (
        <div className="magi-safe-guides" aria-hidden="true">
          <div className="magi-safe-title" />
          <div className="magi-safe-action" />
          <div className="magi-safe-center-x" />
          <div className="magi-safe-center-y" />
          <div className="magi-safe-lt-baseline" />
        </div>
      ) : null}
      {composition.overlays.map((el) =>
        renderEl(
          el,
          selectedId,
          onSelect,
          editingId,
          (id, text) => onPatchElement(id, { text } as Partial<MagiOverlayElement>),
          setEditingId,
          () => setEditingId(null)
        )
      )}
    </div>
  );
}
