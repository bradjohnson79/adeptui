import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { MagiOverlayComposition, MagiOverlayElement } from "./types";
import { compareOverlayPaintOrder, composeOverlayPaintZ, overlayVisibleAtFrame } from "./types";

function pct(n: number) {
  return `${(n * 100).toFixed(3)}%`;
}

function localizeGroupChild(child: MagiOverlayElement, group: MagiOverlayElement): MagiOverlayElement {
  const w = group.width || 1;
  const h = group.height || 1;
  return {
    ...child,
    x: (child.x - group.x) / w,
    y: (child.y - group.y) / h,
    width: child.width / w,
    height: child.height / h,
  };
}

function overlayOpacity(el: MagiOverlayElement, frame: number, fps: number): number {
  const preset = el.type === "text" || el.type === "group" ? el.animationPreset : null;
  let factor = 1;
  if (preset === "fade" && el.startFrame != null && el.endFrame != null) {
    const fade = Math.max(1, Math.round(0.35 * fps));
    if (frame < el.startFrame + fade) factor = (frame - el.startFrame) / fade;
    else if (frame > el.endFrame - fade) factor = (el.endFrame - frame) / fade;
    factor = Math.max(0, Math.min(1, factor));
  }
  return el.opacity * factor;
}

function renderEl(
  el: MagiOverlayElement,
  selectedId: string | null,
  onSelect: (id: string) => void,
  editingId: string | null,
  onEditText: (id: string, text: string) => void,
  onBeginEdit: (id: string) => void,
  onEndEdit: () => void,
  assetUrl: ((id: string) => string) | undefined,
  playheadFrame: number,
  frameRate: number,
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
          opacity: overlayOpacity(el, playheadFrame, frameRate),
          transform: `rotate(${el.rotation}deg)`,
          zIndex: composeOverlayPaintZ(el),
        }}
        data-overlay-id={el.id}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(el.id);
        }}
      >
        {el.children.map((c) =>
          renderEl(
            localizeGroupChild(c, el),
            selectedId,
            onSelect,
            editingId,
            onEditText,
            onBeginEdit,
            onEndEdit,
            assetUrl,
            playheadFrame,
            frameRate,
          ),
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
          opacity: overlayOpacity(el, playheadFrame, frameRate),
          transform: `rotate(${el.rotation}deg)`,
          zIndex: composeOverlayPaintZ(el),
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
  if (el.type === "image") {
    return (
      <div
        key={el.id}
        className={`magi-ov-el magi-ov-image ${selectedId === el.id ? "is-selected" : ""}`}
        data-overlay-id={el.id}
        style={{
          left: pct(el.x),
          top: pct(el.y),
          width: pct(el.width),
          height: pct(el.height),
          opacity: overlayOpacity(el, playheadFrame, frameRate),
          transform: `rotate(${el.rotation}deg)`,
          zIndex: composeOverlayPaintZ(el),
        }}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(el.id);
        }}
      >
        {assetUrl && el.assetId ? (
          <img src={assetUrl(el.assetId)} alt="" draggable={false} style={{ width: "100%", height: "100%", objectFit: el.fit || "contain" }} />
        ) : null}
      </div>
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
        opacity: overlayOpacity(el, playheadFrame, frameRate),
        transform: `rotate(${el.rotation}deg)`,
        zIndex: composeOverlayPaintZ(el),
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
  playheadFrame = 0,
  frameRate = 24,
  assetUrl,
  interactive = true,
}: {
  composition: MagiOverlayComposition;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onPatchElement: (id: string, patch: Partial<MagiOverlayElement>) => void;
  snapEnabled: boolean;
  playheadFrame?: number;
  frameRate?: number;
  assetUrl?: (id: string) => string;
  interactive?: boolean;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const drag = useRef<{
    id: string;
    mode: "move" | "se" | "nw";
    ox: number;
    oy: number;
    ow: number;
    oh: number;
    sx: number;
    sy: number;
  } | null>(null);

  const visibleOverlays = [...composition.overlays]
    .filter((el) => overlayVisibleAtFrame(el, playheadFrame))
    .sort(compareOverlayPaintOrder);

  const onPointerDown = (e: ReactPointerEvent) => {
    if (!interactive || editingId) return;
    const handle = (e.target as HTMLElement).closest("[data-ov-handle]") as HTMLElement | null;
    const target = handle || ((e.target as HTMLElement).closest("[data-overlay-id]") as HTMLElement | null);
    if (!target || !rootRef.current) {
      onSelect(null);
      return;
    }
    const id = target.dataset.overlayId || (target.closest("[data-overlay-id]") as HTMLElement | null)?.dataset.overlayId;
    if (!id) return;
    onSelect(id);
    const el = composition.overlays
      .flatMap((o) => (o.type === "group" ? [o, ...o.children] : [o]))
      .find((x) => x.id === id);
    if (!el || el.locked) return;
    const rect = rootRef.current.getBoundingClientRect();
    const mode = (handle?.dataset.ovHandle as "se" | "nw" | undefined) || "move";
    drag.current = {
      id,
      mode,
      ox: el.x,
      oy: el.y,
      ow: el.width,
      oh: el.height,
      sx: (e.clientX - rect.left) / rect.width,
      sy: (e.clientY - rect.top) / rect.height,
    };
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    e.stopPropagation();
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!drag.current || !rootRef.current) return;
    const rect = rootRef.current.getBoundingClientRect();
    const cx = (e.clientX - rect.left) / rect.width;
    const cy = (e.clientY - rect.top) / rect.height;
    const dx = cx - drag.current.sx;
    const dy = cy - drag.current.sy;
    if (drag.current.mode === "move") {
      let nx = drag.current.ox + dx;
      let ny = drag.current.oy + dy;
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
      return;
    }
    if (drag.current.mode === "se") {
      onPatchElement(drag.current.id, {
        width: Math.min(1.4, Math.max(0.04, drag.current.ow + dx)),
        height: Math.min(1.4, Math.max(0.04, drag.current.oh + dy)),
      } as Partial<MagiOverlayElement>);
      return;
    }
    onPatchElement(drag.current.id, {
      x: Math.min(1.2, Math.max(-0.2, drag.current.ox + dx)),
      y: Math.min(1.2, Math.max(-0.2, drag.current.oy + dy)),
      width: Math.min(1.4, Math.max(0.04, drag.current.ow - dx)),
      height: Math.min(1.4, Math.max(0.04, drag.current.oh - dy)),
    } as Partial<MagiOverlayElement>);
  };

  const selected = visibleOverlays
    .flatMap((o) => (o.type === "group" ? [o, ...o.children] : [o]))
    .find((x) => x.id === selectedId);

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
        if (!interactive || !selectedId || editingId) return;
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
        if (e.key === "Delete" || e.key === "Backspace") {
          e.preventDefault();
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
      {visibleOverlays.map((el) =>
        renderEl(
          el,
          selectedId,
          onSelect,
          editingId,
          (id, text) => onPatchElement(id, { text } as Partial<MagiOverlayElement>),
          setEditingId,
          () => setEditingId(null),
          assetUrl,
          playheadFrame,
          frameRate,
        ),
      )}
      {interactive && selected && !selected.locked ? (
        <>
          <button
            type="button"
            className="magi-ov-handle magi-ov-handle--nw"
            data-ov-handle="nw"
            data-overlay-id={selected.id}
            aria-label="Resize overlay"
            style={{ left: pct(selected.x), top: pct(selected.y), zIndex: 999 }}
          />
          <button
            type="button"
            className="magi-ov-handle magi-ov-handle--se"
            data-ov-handle="se"
            data-overlay-id={selected.id}
            aria-label="Resize overlay"
            style={{ left: pct(selected.x + selected.width), top: pct(selected.y + selected.height), zIndex: 999 }}
          />
        </>
      ) : null}
    </div>
  );
}
