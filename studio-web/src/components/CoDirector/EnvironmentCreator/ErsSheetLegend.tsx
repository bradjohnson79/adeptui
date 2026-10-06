import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { api } from "../../../api";

import { type DrawColor } from "./ersAnnotationPalette";
import {
  ersLegendEditHasUnsavedChanges,
  ersLegendStateKey,
  clampDirectionMovementText,
  ERS_DIRECTION_MOVEMENT_MAX_WORDS,
  loadErsLegendEditState,
  saveErsLegendEditState,
  updateErsLegendEditState,
  type ErsLegendEditSnapshot,
  type ErsLegendSlot,
} from "./ersLegendEditState";
import {
  ERS_LEGEND_FOOTNOTE,
  ERS_MIDDLE_ROW,
  ersMiddleColumnBox,
  moveErsLegendBoxByPointerDelta,
  type ErsNormalizedBox,
} from "./ersSheetLayout";

type Props = {
  activeColor: DrawColor;
  /** Legend accepts marker clicks, name typing, header-drag. Hand and View leave it inert. */
  interactive: boolean;
  projectId?: string;
  sheetId?: string;
  sourceAssetId?: string;
  /** Fires when live Legend dirty state changes (for Submit enablement). */
  onDirtyChange?: (dirty: boolean) => void;
};

function pct(value: number): string {
  return `${value * 100}%`;
}

export function ErsSheetLegend({ activeColor, interactive, projectId, sheetId, sourceAssetId, onDirtyChange }: Props) {
  const stateKey =
    projectId && sheetId && sourceAssetId
      ? ersLegendStateKey({ projectId, sheetId, sourceAssetId })
      : "ers-legend:local";

  const [snap, setSnap] = useState<ErsLegendEditSnapshot>(() => loadErsLegendEditState(stateKey));
  const [saveFlash, setSaveFlash] = useState<"idle" | "saved">("idle");
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    origin: ErsNormalizedBox;
  } | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setSnap(loadErsLegendEditState(stateKey));
    setSaveFlash("idle");
    onDirtyChange?.(ersLegendEditHasUnsavedChanges(stateKey));
  }, [stateKey, onDirtyChange]);

  // Hydrate Direction/Movement + Legend from master overlayState so notes survive reopen.
  useEffect(() => {
    if (!projectId || !sheetId || !sourceAssetId) return;
    if (ersLegendEditHasUnsavedChanges(stateKey)) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await api.environmentReferenceSheet.getSheet(projectId, sheetId);
        const sheet = (res as { sheet?: Record<string, unknown> })?.sheet || {};
        const overlay = (sheet.overlayState || null) as Record<string, unknown> | null;
        const legend = (overlay?.legend || null) as Record<string, unknown> | null;
        const serverMove =
          typeof legend?.directionMovement === "string"
            ? legend.directionMovement
            : typeof sheet.directionMovement === "string"
              ? sheet.directionMovement
              : "";
        if (cancelled) return;
        const current = loadErsLegendEditState(stateKey);
        if (ersLegendEditHasUnsavedChanges(stateKey)) return;
        const next = {
          ...current,
          ...(legend && typeof legend === "object"
            ? {
                position:
                  legend.position && typeof legend.position === "object"
                    ? (legend.position as ErsLegendEditSnapshot["position"])
                    : current.position,
                characters: Array.isArray(legend.characters)
                  ? (legend.characters as ErsLegendEditSnapshot["characters"])
                  : current.characters,
                props: Array.isArray(legend.props)
                  ? (legend.props as ErsLegendEditSnapshot["props"])
                  : current.props,
                userMoved: Boolean(legend.userMoved ?? current.userMoved),
              }
            : {}),
          directionMovement: clampDirectionMovementText(
            serverMove || current.directionMovement || "",
          ),
        };
        const committed = saveErsLegendEditState(stateKey, next);
        setSnap(committed);
        onDirtyChange?.(false);
      } catch {
        /* offline / missing sheet ? keep local Legend state */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onDirtyChange, projectId, sheetId, sourceAssetId, stateKey]);

  const sync = useCallback(
    (next: ErsLegendEditSnapshot) => {
      const stored = updateErsLegendEditState(stateKey, next);
      setSnap(stored);
      setSaveFlash("idle");
      onDirtyChange?.(ersLegendEditHasUnsavedChanges(stateKey));
    },
    [onDirtyChange, stateKey],
  );

  const spatial = ersMiddleColumnBox("spatial");
  const structuring = ersMiddleColumnBox("structuring");
  const legend = snap.position;

  const paintSlot = (kind: "character" | "prop", index: number) => {
    const apply = (slots: ErsLegendSlot[]) =>
      slots.map((slot, i) => (i === index ? { ...slot, color: activeColor } : slot));
    sync({
      ...snap,
      characters: kind === "character" ? apply(snap.characters) : snap.characters,
      props: kind === "prop" ? apply(snap.props) : snap.props,
    });
  };

  const renameSlot = (kind: "character" | "prop", index: number, label: string) => {
    const apply = (slots: ErsLegendSlot[]) => slots.map((slot, i) => (i === index ? { ...slot, label } : slot));
    sync({
      ...snap,
      characters: kind === "character" ? apply(snap.characters) : snap.characters,
      props: kind === "prop" ? apply(snap.props) : snap.props,
    });
  };

  const onHeaderPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!interactive || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const sheet = rootRef.current;
    if (!sheet) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    dragRef.current = {
      pointerId: e.pointerId,
      startClientX: e.clientX,
      startClientY: e.clientY,
      origin: { ...snap.position },
    };
    setDragging(true);
  };

  const onHeaderPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    e.preventDefault();
    e.stopPropagation();
    const sheet = rootRef.current;
    if (!sheet) return;
    // sheet.client* is the zoomed frame CSS size (same transform as ERS sheet).
    // Keep origin W/H — never remasure/resize Legend during drag or zoom.
    const next = moveErsLegendBoxByPointerDelta(
      drag.origin,
      e.clientX - drag.startClientX,
      e.clientY - drag.startClientY,
      sheet.clientWidth,
      sheet.clientHeight,
    );
    setSnap((prev) => {
      const updated = { ...prev, position: next, userMoved: true };
      updateErsLegendEditState(stateKey, updated);
      setSaveFlash("idle");
      onDirtyChange?.(ersLegendEditHasUnsavedChanges(stateKey));
      return updated;
    });
  };

  const endDrag = (e: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    setDragging(false);
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  };

  const handleSave = () => {
    const committed = saveErsLegendEditState(stateKey, snap);
    setSnap(committed);
    setSaveFlash("saved");
    onDirtyChange?.(false);
  };

  const guide = (box: ErsNormalizedBox, id: string, label: string) => (
    <div
      data-testid={`ers-sheet-panel-${id}`}
      style={{
        position: "absolute",
        left: pct(box.left),
        top: pct(box.top),
        width: pct(box.width),
        height: pct(box.height),
        boxSizing: "border-box",
        border: "1px solid rgba(234,240,246,0.28)",
        pointerEvents: "none",
        display: "flex",
        alignItems: "flex-start",
        padding: "0.2rem 0.35rem",
      }}
    >
      <span
        style={{
          fontSize: "0.68rem",
          fontWeight: 700,
          letterSpacing: "0.02em",
          color: "#f4f7fb",
          background: "rgba(8,12,18,0.55)",
          borderRadius: 4,
          padding: "0.05rem 0.3rem",
        }}
      >
        {label}
      </span>
    </div>
  );

  const renderSlots = (kind: "character" | "prop", title: string, slots: ErsLegendSlot[]) => (
    <div data-testid={`ers-legend-${kind}-section`}>
      <div style={{ fontSize: "0.62rem", fontWeight: 700, margin: "0.15rem 0 0.1rem" }}>{title}</div>
      {slots.map((slot, index) => (
        <div
          key={`${kind}-${index}`}
          data-testid={`ers-legend-${kind}-slot-${index}`}
          style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}
        >
          <button
            type="button"
            title={`Match ${title.toLowerCase()} ${index + 1} to the selected color`}
            data-testid={`ers-legend-${kind}-marker-${index}`}
            disabled={!interactive}
            onClick={() => paintSlot(kind, index)}
            style={{
              width: 14,
              height: 14,
              minWidth: 14,
              borderRadius: "50%",
              padding: 0,
              border: "1px solid rgba(255,255,255,0.7)",
              background: slot.color,
              cursor: interactive ? "pointer" : "default",
            }}
          />
          <input
            type="text"
            aria-label={`${title} ${index + 1}`}
            data-testid={`ers-legend-${kind}-label-${index}`}
            value={slot.label}
            disabled={!interactive}
            placeholder="Name"
            onChange={(e) => renameSlot(kind, index, e.target.value)}
            onPointerDown={(e) => e.stopPropagation()}
            style={{
              flex: 1,
              minWidth: 0,
              fontSize: "0.62rem",
              lineHeight: 1.2,
              padding: "1px 4px",
              borderRadius: 3,
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(0,0,0,0.35)",
              color: "#f4f7fb",
              letterSpacing: "normal",
              transform: "none",
            }}
          />
        </div>
      ))}
    </div>
  );

  return (
    <div
      ref={rootRef}
      data-testid="ers-sheet-middle-row"
      data-master="2048x1536"
      data-legend-user-moved={snap.userMoved ? "1" : "0"}
      data-legend-coord-space="source-sheet"
      data-legend-attach="frame-transform"
      style={{ position: "absolute", inset: 0, pointerEvents: "none", transform: "none" }}
    >
      {guide(spatial, "spatial", ERS_MIDDLE_ROW.columns[0].label)}
      {guide(structuring, "structuring", ERS_MIDDLE_ROW.columns[2].label)}
      <aside
        data-testid="ers-sheet-panel-legend"
        data-legend-left={legend.left.toFixed(4)}
        data-legend-top={legend.top.toFixed(4)}
        style={{
          position: "absolute",
          left: pct(legend.left),
          top: pct(legend.top),
          width: pct(legend.width),
          height: pct(legend.height),
          boxSizing: "border-box",
          pointerEvents: interactive ? "auto" : "none",
          overflow: "auto",
          // No transform/scale/inverse-scale — geometry rides ImageMaskEditor frame zoom+pan.
          transform: "none",
          background: "rgba(10,14,22,0.88)",
          border: "1px solid rgba(234,240,246,0.45)",
          color: "#f4f7fb",
          padding: "0.25rem 0.3rem 0.3rem",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          data-testid="ers-legend-header"
          onPointerDown={onHeaderPointerDown}
          onPointerMove={onHeaderPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          style={{
            fontSize: "0.72rem",
            fontWeight: 800,
            marginBottom: 2,
            cursor: interactive ? (dragging ? "grabbing" : "grab") : "default",
            userSelect: "none",
            touchAction: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 6,
          }}
          title={interactive ? "Drag to move Legend" : undefined}
        >
          <span>Legend</span>
          <button
            type="button"
            data-testid="ers-legend-save"
            disabled={!interactive}
            onClick={(e) => {
              e.stopPropagation();
              handleSave();
            }}
            onPointerDown={(e) => e.stopPropagation()}
            style={{
              fontSize: "0.58rem",
              fontWeight: 700,
              padding: "1px 6px",
              borderRadius: 3,
              border: "1px solid rgba(255,255,255,0.35)",
              background: saveFlash === "saved" ? "rgba(34,197,94,0.35)" : "rgba(0,0,0,0.35)",
              color: "#f4f7fb",
              cursor: interactive ? "pointer" : "default",
            }}
          >
            {saveFlash === "saved" ? "Saved" : "Save"}
          </button>
        </div>
        {renderSlots("character", "Characters", snap.characters)}
        {renderSlots("prop", "Props", snap.props)}
        <div data-testid="ers-legend-direction-movement-section" style={{ marginTop: "0.2rem" }}>
          <div style={{ fontSize: "0.62rem", fontWeight: 700, margin: "0.15rem 0 0.1rem" }}>
            Direction / Movement
          </div>
          <textarea
            data-testid="ers-legend-direction-movement"
            aria-label="Direction / Movement"
            disabled={!interactive}
            value={snap.directionMovement || ""}
            placeholder="Describe direction or movement (max 50 words)"
            rows={3}
            spellCheck
            onPointerDown={(e) => e.stopPropagation()}
            onChange={(e) => {
              // Clamp word count only — do not collapse spaces/newlines while typing.
              const next = clampDirectionMovementText(e.target.value);
              sync({ ...snap, directionMovement: next });
            }}
            style={{
              width: "100%",
              boxSizing: "border-box",
              resize: "vertical",
              minHeight: "2.4rem",
              flex: "0 0 auto",
              fontSize: "0.62rem",
              lineHeight: 1.35,
              padding: "3px 4px",
              borderRadius: 3,
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(0,0,0,0.35)",
              color: "#f4f7fb",
              // Normal textarea metrics — no zoom compensation / scale / letter-spacing hacks.
              whiteSpace: "pre-wrap",
              wordBreak: "normal",
              overflowWrap: "break-word",
              letterSpacing: "normal",
              transform: "none",
            }}
          />
          <div
            className="muted"
            data-testid="ers-legend-direction-movement-count"
            style={{ fontSize: "0.55rem", opacity: 0.75, marginTop: 2 }}
          >
            {((snap.directionMovement || "").match(/\S+/g) || []).length}
            /{ERS_DIRECTION_MOVEMENT_MAX_WORDS} words
          </div>
        </div>
        <p
          data-testid="ers-legend-footnote"
          style={{ margin: "0.25rem 0 0", fontSize: "0.58rem", lineHeight: 1.25, color: "rgba(234,240,246,0.78)" }}
        >
          {ERS_LEGEND_FOOTNOTE}
        </p>
      </aside>
    </div>
  );
}

