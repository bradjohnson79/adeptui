/**
 * Environment Creator ERS Edit / Inpaint — FULL-SCREEN workspace.
 * Reuses ImageMaskEditor (mask canvas only — not Edit Studio workspace).
 * Contract: mask via image-product (surface environment_creator.ers_edit),
 * then POST .../edit/enqueue → poll derivative → POST .../versions draft vN.
 * No overwrite; no auto-approve. Repeatable v1→edit→v2→edit→v3 loop.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { ApiError, api } from "../../../api";
import {
  ImageMaskEditor,
  type ImageMaskEditorHandle,
  type MaskTool,
} from "../../imageEdit/ImageMaskEditor";
import { ERS_ANNOTATION_COLORS, type DrawColor } from "./ersAnnotationPalette";
import {
  ErsDrawingLayer,
  type DrawThickness,
  type DrawTool,
  type ErsDrawingLayerHandle,
} from "./ErsDrawingLayer";
import { ErsSheetLegend } from "./ErsSheetLegend";
import {
  ersLegendStateKey,
  loadErsLegendEditState,
  saveErsLegendEditState,
} from "./ersLegendEditState";
import {
  ERS_SUBMIT_SNAPSHOT_FEEDBACK,
  ersSubmitHasWork,
  planErsSubmit,
  planErsSubmitClose,
} from "./ersSubmitGate";
import { ERS_EDIT_ZOOM_MAX, ERS_SHEET_MASTER } from "./ersSheetLayout";
import { ErsEditVersionChrome } from "./ErsEditVersionChrome";

export type ErsEditEnqueueResult = {
  jobId?: string;
  queueJobId?: string;
  status?: string;
  message?: string | null;
  progress?: number | null;
  error?: string | null;
  workflowKey?: string;
  family?: string;
  operation?: string;
  sheetId?: string;
  sourceAssetId?: string;
  derivativeAssetId?: string | null;
  resultAssetId?: string | null;
  previewUrl?: string | null;
  derivativeOnly?: boolean;
};


function looksLikeCheckpointProgressLabel(text: string | undefined | null): boolean {
  const t = String(text || "");
  return /\.safetensors\b/i.test(t) || /z_image_turbo/i.test(t) || /ImageGen[\s\S]{0,80}inpaint/i.test(t);
}

type Props = {
  projectId: string;
  sheetId: string;
  sourceAssetId: string;
  sheetName?: string;
  /** Optional Co-Director / caller pre-fill - creator may edit; frozen on submit. */
  initialPrompt?: string;
  /** Environment Creator selected API provider (fal|kie|wavespeed). */
  apiProvider?: string;
  apiModelId?: string;
  apiOfficialModelId?: string;
  apiModelLabel?: string;
  onClose: () => void;
  onDerivativeReady?: (info: {
    derivativeAssetId: string;
    jobId: string | null;
    editPrompt: string;
    sourceAssetId: string;
    sheetId: string;
    versionSheetId?: string | null;
  }) => void;
  /** Refresh main EC viewport after a successful draft version. */
  onViewportRefresh?: (info: {
    sheetId: string;
    sourceAssetId: string;
    sheetName?: string;
  }) => void;
  /**
   * Fired after Submit persistence succeeds, immediately before the modal closes.
   * Annotation-only: Legend/markers saved. Image-edit: enqueue accepted (job may still run).
   */
  onSubmitAccepted?: (info: {
    kind: "snapshot_capture" | "annotation_only" | "image_edit";
    jobId?: string | null;
    status?: string;
    message: string;
    sheetId: string;
    sourceAssetId: string;
    derivativeAssetId?: string | null;
    editPrompt?: string;
    snapshotSheetId?: string | null;
    snapshotNumber?: number | null;
    snapshotName?: string | null;
    bakedAssetId?: string | null;
    masterSheetId?: string | null;
    imageGenInvoked?: boolean;
  }) => void;
};


function formatJobError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return "ERS edit backend route is not available yet (HTTP 404). Mask was saved if that step succeeded; enqueue is blocked until Backend ships POST .../edit/enqueue.";
    }
    if (
      (err.status === 400 || err.status === 409) &&
      looksLikeCheckpointProgressLabel(err.message)
    ) {
      return (
        err.message ||
        `ERS edit reported HTTP ${err.status} with a checkpoint/model label in the message. ` +
          "If a jobId exists, re-poll GET .../edit/jobs/{jobId} — do not treat .safetensors text as terminal failure."
      );
    }
    return err.message || `ERS edit failed (HTTP ${err.status}).`;
  }
  return err instanceof Error ? err.message : String(err);
}

export function ErsEditModal({
  projectId,
  sheetId,
  sourceAssetId,
  sheetName,
  initialPrompt,
  apiProvider = "",
  apiModelId = "",
  apiModelLabel = "",
  onClose,
  onViewportRefresh,
  onSubmitAccepted,
}: Props) {
  const maskRef = useRef<ImageMaskEditorHandle>(null);
  const drawRef = useRef<ErsDrawingLayerHandle>(null);
  const frozenPromptRef = useRef<string | null>(null);
  const dirtyRef = useRef(false);
  const submitInFlightRef = useRef(false);
  /** Adept StudioChrome (menubar+breadcrumbs) paints above in-tree fixed modals due to app-shell isolation — offset below it. */
  const [chromeTopOffset, setChromeTopOffset] = useState(0);
  const [uiMode, setUiMode] = useState<"hand" | "mask" | "draw" | "text" | "view">("mask");
  const [tool, setTool] = useState<MaskTool>("brush");
  const [brushSize, setBrushSize] = useState(28);
  const [maskVisible, setMaskVisible] = useState(true);
  const [drawTool, setDrawTool] = useState<DrawTool>("pen");
  const [drawColor, setDrawColor] = useState<DrawColor>("#ef4444");
  const [drawThickness, setDrawThickness] = useState<DrawThickness>("medium");
  const [drawVisible, setDrawVisible] = useState(true);
  const [drawLocked, setDrawLocked] = useState(false);
  const [hasDrawing, setHasDrawing] = useState(false);
  const [legendDirty, setLegendDirty] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [hasMask, setHasMask] = useState(false);
  const [editPrompt, setEditPrompt] = useState(String(initialPrompt || ""));
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<
    "idle" | "saving_mask" | "enqueue" | "polling" | "creating_version" | "done" | "error"
  >("idle");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userError, setUserError] = useState<string | null>(null);
  const [techError, setTechError] = useState<string | null>(null);
  const [jobId] = useState<string | null>(null);
  const [derivativeAssetId] = useState<string | null>(null);
  const [maskAssetId] = useState<string | null>(null);
  const [versionSheetId] = useState<string | null>(null);
  const [activeSheetId, setActiveSheetId] = useState(sheetId);
  const [activeSourceAssetId, setActiveSourceAssetId] = useState(sourceAssetId);
  const [editorKey, setEditorKey] = useState(0);
  const [naturalInfo, setNaturalInfo] = useState<string | null>(null);
  const [naturalSize, setNaturalSize] = useState({ w: 0, h: 0 });
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [overlayGap, setOverlayGap] = useState<string | null>(null);

  const imageUrl = api.assetUrl(activeSourceAssetId);

  useEffect(() => {
    setActiveSourceAssetId(sourceAssetId);
  }, [sourceAssetId]);

  useEffect(() => {
    setActiveSheetId(sheetId);
  }, [sheetId]);

  useEffect(() => {
    if (initialPrompt && !editPrompt) setEditPrompt(String(initialPrompt));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPrompt]);

  useEffect(() => {
    dirtyRef.current = hasMask || hasDrawing || legendDirty || Boolean(editPrompt.trim());
  }, [hasMask, hasDrawing, legendDirty, editPrompt]);

  const requestClose = useCallback(() => {
    if (busy) return;
    if (dirtyRef.current && phase !== "done") {
      const ok = window.confirm("Discard this ERS edit?");
      if (!ok) return;
    }
    onClose();
  }, [busy, onClose, phase]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) requestClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, requestClose]);

  useLayoutEffect(() => {
    const measure = () => {
      const chrome = document.querySelector('[data-testid="app-chrome"]') as HTMLElement | null;
      const h = chrome ? Math.ceil(chrome.getBoundingClientRect().height) : 0;
      // Keep Close fully below Adept nav/breadcrumbs; floor for typical menubar+crumbs.
      setChromeTopOffset(Math.max(h, 72));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  const clearMask = useCallback(() => {
    maskRef.current?.clear();
    setHasMask(false);
    setCanUndo(Boolean(maskRef.current?.canUndo?.()));
  }, []);

  const refreshHistoryFlags = useCallback(() => {
    setCanUndo(Boolean(maskRef.current?.canUndo?.()) || Boolean(drawRef.current?.canUndo?.()));
    setCanRedo(Boolean(drawRef.current?.canRedo?.()));
  }, []);

  const handleUndo = useCallback(() => {
    if (uiMode === "draw" && drawRef.current?.canUndo?.()) drawRef.current.undo();
    else maskRef.current?.undo?.();
    refreshHistoryFlags();
  }, [refreshHistoryFlags, uiMode]);

  const handleRedo = useCallback(() => {
    drawRef.current?.redo?.();
    refreshHistoryFlags();
  }, [refreshHistoryFlags]);

  const clearDrawing = useCallback(() => {
    drawRef.current?.clear();
    setHasDrawing(false);
    refreshHistoryFlags();
  }, [refreshHistoryFlags]);

  const fitToView = useCallback(() => {
    setZoom(1);
    maskRef.current?.fitToView?.();
  }, []);

  const handleSubmit = useCallback(async () => {
    if (submitInFlightRef.current || busy) return;
    const prompt = editPrompt.trim();
    const drawingLive = Boolean(drawRef.current?.hasContent?.());
    const sources = {
      editPrompt: prompt,
      hasMask,
      hasDrawing: hasDrawing || drawingLive,
      legendDirty,
    };
    const plan = planErsSubmit(sources);
    if (plan.kind === "empty") {
      setError(plan.userMessage);
      setUserError(plan.userMessage);
      setTechError(null);
      return;
    }

    const legendKey = ersLegendStateKey({
      projectId,
      sheetId: activeSheetId,
      sourceAssetId: activeSourceAssetId,
    });

    // Instant local snapshot capture - NEVER calls fal/GPT/Kie/imagegen.
    submitInFlightRef.current = true;
    setBusy(true);
    setError(null);
    setUserError(null);
    setTechError(null);
    setOverlayGap(null);
    try {
      setPhase("enqueue");
      setStatusMessage("Capturing snapshot...");

      // Commit Legend so labels/position ride with the bake.
      saveErsLegendEditState(legendKey);
      setLegendDirty(false);

      let drawingOverlay: {
        rasterPngBase64?: string | null;
        vectors?: Array<{ type: string; points: number[]; stroke: string; width: number }>;
      } | null = null;
      let textLabels: Array<{ id: string; text: string; x: number; y: number; fontSize: number; color: string }> | null = null;
      let numberedMarkers: Array<{ id: string; number: number; x: number; y: number; label?: string }> | null = null;
      if (drawRef.current?.hasContent()) {
        const payload = drawRef.current.exportPayload();
        const raster = await drawRef.current.exportRasterPng();
        drawingOverlay = {
          rasterPngBase64: raster,
          vectors: payload.drawingOverlay.vectors,
        };
        textLabels = payload.textLabels;
        numberedMarkers = payload.numberedMarkers;
      }

      const legendSnap = loadErsLegendEditState(legendKey);
      const captured = await api.environmentReferenceSheet.captureSnapshot(projectId, activeSheetId, {
        sourceAssetId: activeSourceAssetId,
        legend: legendSnap,
        drawingOverlay,
        textLabels,
        numberedMarkers,
      });

      if (captured?.imageGenInvoked) {
        throw new Error("Snapshot path unexpectedly invoked image generation.");
      }
      const snapId = String(captured.snapshotSheetId || "").trim();
      const bakedId = String(captured.bakedAssetId || "").trim();
      const snapNum = Number(captured.snapshotNumber || 0);
      if (!snapId || !bakedId || !snapNum) {
        throw new Error("Snapshot capture did not return sheetId / bakedAssetId / SS-N.");
      }

      setPhase("done");
      setStatusMessage(captured.message || ERS_SUBMIT_SNAPSHOT_FEEDBACK);
      dirtyRef.current = false;

      const closePlan = planErsSubmitClose({
        outcome: "success",
        planKind: "snapshot_capture",
        snapshotAccepted: true,
      });
      if (closePlan.close) {
        onSubmitAccepted?.({
          kind: "snapshot_capture",
          message: captured.message || ERS_SUBMIT_SNAPSHOT_FEEDBACK,
          sheetId: activeSheetId,
          sourceAssetId: activeSourceAssetId,
          snapshotSheetId: snapId,
          snapshotNumber: snapNum,
          snapshotName: captured.snapshotName || null,
          bakedAssetId: bakedId,
          masterSheetId: captured.masterSheetId || activeSheetId,
          imageGenInvoked: false,
          derivativeAssetId: bakedId,
        });
        onViewportRefresh?.({
          sheetId: activeSheetId,
          sourceAssetId: activeSourceAssetId,
          sheetName: sheetName,
        });
        onClose();
      }
    } catch (err) {
      setPhase("error");
      const detail = formatJobError(err);
      setUserError("The snapshot could not be captured.");
      setTechError(detail);
      setError("The snapshot could not be captured.");
      setStatusMessage(null);
      // Failure: keep Edit/Inpaint open; preserve unsaved work; no partial snapshot.
    } finally {
      submitInFlightRef.current = false;
      setBusy(false);
    }
  }, [
    activeSheetId,
    activeSourceAssetId,
    busy,
    editPrompt,
    hasDrawing,
    hasMask,
    legendDirty,
    onClose,
    onSubmitAccepted,
    onViewportRefresh,
    projectId,
    sheetName,
  ]);

  const submitEnabled =
    !busy &&
    Boolean(activeSourceAssetId) &&
    phase !== "polling" &&
    ersSubmitHasWork({
      editPrompt,
      hasMask,
      hasDrawing,
      legendDirty,
    });

  const btn = (active: boolean): CSSProperties => ({
    border: active ? "1px solid var(--accent, #6ea8fe)" : "1px solid var(--border, #2c3346)",
    background: active ? "rgba(110,168,254,0.18)" : "transparent",
    color: "inherit",
    borderRadius: 6,
    padding: "0.28rem 0.55rem",
    fontSize: "0.82rem",
    cursor: busy ? "not-allowed" : "pointer",
  });

  const modal = (
    <div
      className="ers-edit-modal-backdrop ers-edit-modal-backdrop--fullscreen"
      data-testid="ers-edit-modal"
      data-api-provider={apiProvider || ""}
      data-api-model={apiModelLabel || apiModelId || ""}
      data-fullscreen="true"
      data-chrome-offset={chromeTopOffset}
      role="dialog"
      aria-modal="true"
      aria-labelledby="ers-edit-modal-title"
      style={{
        position: "fixed",
        top: chromeTopOffset,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 1200,
        background: "rgba(4, 6, 12, 0.96)",
        display: "flex",
        flexDirection: "column",
        padding: 0,
        margin: 0,
        width: "100vw",
        height: `calc(100vh - ${chromeTopOffset}px)`,
        maxHeight: `calc(100vh - ${chromeTopOffset}px)`,
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      {/* Sticky header: title + Close on SAME row, inset inside modal safe area (below Adept nav). */}
      <header
        data-testid="ers-edit-modal-header"
        style={{
          flex: "0 0 auto",
          position: "sticky",
          top: 0,
          zIndex: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.75rem",
          padding: "12px 16px",
          minHeight: 52,
          borderBottom: "1px solid var(--border, #2c3346)",
          background: "var(--panel, #121722)",
          boxShadow: "0 2px 10px rgba(0,0,0,0.35)",
        }}
      >
        <div style={{ minWidth: 0, flex: "1 1 auto", paddingRight: 8 }}>
          <h3
            id="ers-edit-modal-title"
            data-testid="ers-edit-modal-title"
            style={{
              margin: 0,
              fontSize: "1.1rem",
              fontWeight: 700,
              lineHeight: 1.25,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            Edit / Inpaint
            {sheetName ? (
              <span className="muted" style={{ fontWeight: 500, fontSize: "0.92rem" }}>
                {" — "}
                {sheetName}
              </span>
            ) : null}
          </h3>
          <p className="muted" style={{ margin: "2px 0 0", fontSize: "0.72rem" }} data-testid="ers-edit-sheet-layout">
            Sheet {ERS_SHEET_MASTER.width}×{ERS_SHEET_MASTER.height} · middle row Spatial Map · Legend · Structuring / 3D
          </p>
          <p className="muted" style={{ margin: "2px 0 0", fontSize: "0.72rem" }} data-testid="ers-edit-natural-info">
            Environment Creator · ERS Edit
            {naturalInfo ? ` · ${naturalInfo}` : ""}
            {` · sheet ${activeSheetId.slice(0, 8)}…`}
            {versionSheetId ? ` · draft ${versionSheetId.slice(0, 8)}…` : ""}
          </p>
        </div>
        <button
          type="button"
          data-testid="ers-edit-modal-close"
          aria-label="Close"
          title="Close"
          onClick={requestClose}
          disabled={busy}
          style={{
            flex: "0 0 auto",
            flexShrink: 0,
            zIndex: 21,
            position: "relative",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            minWidth: 48,
            minHeight: 44,
            height: 44,
            padding: "0 14px",
            margin: 0,
            borderRadius: 8,
            border: "2px solid #ffffff",
            background: "#7f1d1d",
            color: "#ffffff",
            fontSize: "1rem",
            fontWeight: 800,
            letterSpacing: 0.02,
            lineHeight: 1,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.55 : 1,
            boxShadow: "0 0 0 1px rgba(0,0,0,0.45), 0 4px 14px rgba(0,0,0,0.45)",
          }}
        >
          <span aria-hidden="true" style={{ fontSize: "1.4rem", lineHeight: 1, fontWeight: 900 }}>
            ×
          </span>
          <span style={{ fontSize: "0.9rem", fontWeight: 800 }}>Close</span>
        </button>
      </header>

      {/* Mode + Undo/Redo */}
      <div
        data-testid="ers-edit-mode-bar"
        style={{
          flex: "0 0 auto",
          display: "flex",
          flexWrap: "wrap",
          gap: "0.35rem",
          padding: "0.35rem 0.85rem",
          alignItems: "center",
          borderBottom: "1px solid var(--border, #2c3346)",
          background: "rgba(10,14,22,0.98)",
        }}
      >
        {([
          ["hand", "Hand"],
          ["mask", "Mask"],
          ["draw", "Draw"],
          ["text", "Text"],
          ["view", "View"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            style={btn(uiMode === id)}
            data-testid={`ers-edit-mode-${id}`}
            aria-pressed={uiMode === id}
            title={
              id === "hand"
                ? "Pan — move around the sheet"
                : id === "text"
                  ? "Type legend labels"
                  : id === "view"
                    ? "Inspect only"
                    : undefined
            }
            disabled={busy}
            onClick={() => {
              setUiMode(id);
              if (id === "hand") setTool("pan");
              if (id === "mask" && tool === "pan") setTool("brush");
              if (id === "text") setDrawTool("text");
              if (id === "draw" && drawTool === "text") setDrawTool("pen");
            }}
          >
            {label}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 8 }}>|</span>
        <button type="button" style={btn(false)} data-testid="ers-edit-mask-undo" onClick={handleUndo} disabled={busy || !canUndo}>
          Undo
        </button>
        <button type="button" style={btn(false)} data-testid="ers-edit-mask-redo" onClick={handleRedo} disabled={busy || !canRedo}>
          Redo
        </button>
      </div>

      {/* Tool row by mode */}
      <div
        className="ers-edit-modal__tools"
        data-testid="ers-edit-mask-tools"
        style={{
          flex: "0 0 auto",
          display: "flex",
          flexWrap: "wrap",
          gap: "0.3rem",
          padding: "0.35rem 0.85rem",
          alignItems: "center",
          borderBottom: "1px solid var(--border, #2c3346)",
          background: "rgba(12,16,24,0.95)",
        }}
      >
        {uiMode === "mask" ? (
          <>
            {(["brush", "erase"] as MaskTool[]).map((tname) => (
              <button
                key={tname}
                type="button"
                style={btn(tool === tname)}
                data-testid={`ers-edit-tool-${tname}`}
                aria-pressed={tool === tname}
                onClick={() => setTool(tname)}
                disabled={busy}
              >
                {tname === "brush" ? "Brush" : "Erase"}
              </button>
            ))}
            <label className="pill muted" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.8rem" }}>
              Size
              <input
                type="range"
                min={4}
                max={96}
                value={brushSize}
                data-testid="ers-edit-brush-size"
                disabled={busy}
                onChange={(e) => setBrushSize(Number(e.target.value))}
              />
              {brushSize}
            </label>
            <button type="button" style={btn(false)} data-testid="ers-edit-mask-clear" onClick={clearMask} disabled={busy}>
              Clear
            </button>
          </>
        ) : null}

        {uiMode === "draw" ? (
          <>
            {([
              ["pen", "Pen"],
              ["line", "Line"],
              ["arrow", "Arrow"],
              ["rect", "Rectangle"],
              ["ellipse", "Ellipse"],
              ["text", "Text"],
              ["marker", "Marker"],
              ["select", "Select"],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                type="button"
                style={btn(drawTool === id)}
                data-testid={`ers-edit-draw-${id}`}
                aria-pressed={drawTool === id}
                onClick={() => setDrawTool(id)}
                disabled={busy || drawLocked}
              >
                {label}
              </button>
            ))}
            <span className="muted" style={{ marginLeft: 4 }}>Color</span>
            {ERS_ANNOTATION_COLORS.map(({ value: c, name }) => (
              <button
                key={c}
                type="button"
                title={name}
                data-testid={`ers-edit-draw-color-${name.toLowerCase()}`}
                aria-pressed={drawColor === c}
                disabled={busy || drawLocked}
                onClick={() => setDrawColor(c)}
                style={{
                  ...btn(drawColor === c),
                  width: 22,
                  height: 22,
                  padding: 0,
                  background: c,
                  borderColor: drawColor === c ? "#fff" : "#555",
                }}
              />
            ))}
            {(["thin", "medium", "thick"] as DrawThickness[]).map((th) => (
              <button
                key={th}
                type="button"
                style={btn(drawThickness === th)}
                data-testid={`ers-edit-draw-thickness-${th}`}
                onClick={() => setDrawThickness(th)}
                disabled={busy || drawLocked}
              >
                {th[0].toUpperCase() + th.slice(1)}
              </button>
            ))}
          </>
        ) : null}

        {uiMode === "text" ? (
          <>
            <span className="muted" style={{ fontSize: "0.8rem" }}>
              Click a legend name and type. Match its circle to a color.
            </span>
            <span className="muted" style={{ marginLeft: 4 }}>Color</span>
            {ERS_ANNOTATION_COLORS.map(({ value: c, name }) => (
              <button
                key={c}
                type="button"
                title={name}
                data-testid={`ers-edit-draw-color-${name.toLowerCase()}`}
                aria-pressed={drawColor === c}
                disabled={busy || drawLocked}
                onClick={() => setDrawColor(c)}
                style={{
                  ...btn(drawColor === c),
                  width: 22,
                  height: 22,
                  padding: 0,
                  background: c,
                  borderColor: drawColor === c ? "#fff" : "#555",
                }}
              />
            ))}
          </>
        ) : null}

        {uiMode === "hand" ? (
          <span className="muted" data-testid="ers-edit-tool-pan" style={{ fontSize: "0.8rem" }}>
            Drag to move around the sheet. Drawing stays put.
          </span>
        ) : null}

        {uiMode === "view" ? (
          <span className="muted" style={{ fontSize: "0.8rem" }}>
            Inspect only. Use Hand to move the sheet.
          </span>
        ) : null}

        <span className="muted" style={{ marginLeft: 8 }}>|</span>
        <button
          type="button"
          style={btn(false)}
          data-testid="ers-edit-zoom-out"
          disabled={busy}
          onClick={() => setZoom((z) => Math.max(0.25, Math.round((z - 0.25) * 100) / 100))}
        >
          Zoom −
        </button>
        <button
          type="button"
          style={btn(false)}
          data-testid="ers-edit-zoom-in"
          disabled={busy}
          onClick={() => setZoom((z) => Math.min(ERS_EDIT_ZOOM_MAX, Math.round((z + 0.25) * 100) / 100))}
        >
          Zoom +
        </button>
        <span className="muted" data-testid="ers-edit-zoom-label" style={{ fontSize: "0.8rem", minWidth: "2.6rem" }}>
          {zoom.toFixed(2)}×
        </span>
        <button type="button" style={btn(zoom === 1)} data-testid="ers-edit-fit" onClick={fitToView} disabled={busy}>
          Fit
        </button>
      </div>

      {/* Layer row */}
      <div
        data-testid="ers-edit-layer-row"
        style={{
          flex: "0 0 auto",
          display: "flex",
          flexWrap: "wrap",
          gap: "0.3rem",
          padding: "0.3rem 0.85rem",
          alignItems: "center",
          borderBottom: "1px solid var(--border, #2c3346)",
          background: "rgba(8,10,16,0.95)",
          fontSize: "0.8rem",
        }}
      >
        <button type="button" style={btn(!maskVisible)} data-testid="ers-edit-mask-visibility" onClick={() => setMaskVisible((v) => !v)} disabled={busy}>
          {maskVisible ? "Mask Show" : "Mask Hide"}
        </button>
        <button type="button" style={btn(false)} data-testid="ers-edit-mask-clear-layer" onClick={clearMask} disabled={busy}>
          Mask Clear
        </button>
        <button type="button" style={btn(!drawVisible)} data-testid="ers-edit-draw-visibility" onClick={() => setDrawVisible((v) => !v)} disabled={busy}>
          {drawVisible ? "Drawing Show" : "Drawing Hide"}
        </button>
        <button type="button" style={btn(false)} data-testid="ers-edit-draw-clear" onClick={clearDrawing} disabled={busy}>
          Drawing Clear
        </button>
        <button type="button" style={btn(drawLocked)} data-testid="ers-edit-draw-lock" onClick={() => setDrawLocked((v) => !v)} disabled={busy}>
          {drawLocked ? "Unlock Drawing" : "Lock Drawing"}
        </button>
        <span className="muted">Mask=edit region · Draw=guidance only · Bake=guidance_only</span>
      </div>

      {/* LARGE ERS stage — most of the viewport */}
      <div
        className="ers-edit-modal__stage"
        data-testid="ers-edit-mask-stage"
        style={{
          flex: "1 1 auto",
          minHeight: 0,
          position: "relative",
          background: "#05070c",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <ImageMaskEditor
          key={editorKey}
          ref={maskRef}
          imageUrl={imageUrl}
          tool={uiMode === "hand" ? "pan" : tool === "erase" ? "erase" : "brush"}
          brushSize={brushSize}
          hideChrome
          fill
          nativeMask
          fullSheetScroll
          zoom={zoom}
          overlayOpacity={maskVisible ? 0.45 : 0}
          interactive={!busy && (uiMode === "mask" || uiMode === "hand")}
          frameInteractive={!busy && (uiMode === "draw" || uiMode === "text") && !drawLocked}
          onChange={(painted) => {
            setHasMask(painted);
            refreshHistoryFlags();
            dirtyRef.current = painted || hasDrawing || Boolean(editPrompt.trim());
          }}
          onReady={(info) => {
            setNaturalSize((prev) =>
              prev.w === info.naturalWidth && prev.h === info.naturalHeight
                ? prev
                : { w: info.naturalWidth, h: info.naturalHeight },
            );
            const label = `${info.naturalWidth}×${info.naturalHeight} → view ${info.displayWidth}×${info.displayHeight}`;
            setNaturalInfo((prev) => (prev === label ? prev : label));
          }}
          frameChildren={
            <>
              {naturalSize.w > 0 ? (
                <ErsDrawingLayer
                  ref={drawRef}
                  naturalWidth={naturalSize.w}
                  naturalHeight={naturalSize.h}
                  tool={uiMode === "text" ? "text" : drawTool}
                  color={drawColor}
                  thickness={drawThickness}
                  visible={drawVisible}
                  locked={drawLocked}
                  interactive={!busy && (uiMode === "draw" || uiMode === "text") && !drawLocked}
                  onChange={(has) => {
                    setHasDrawing(has);
                    dirtyRef.current = hasMask || has || Boolean(editPrompt.trim());
                    refreshHistoryFlags();
                  }}
                  onHistoryChange={refreshHistoryFlags}
                />
              ) : null}
              <ErsSheetLegend
                activeColor={drawColor}
                interactive={!busy && (uiMode === "mask" || uiMode === "draw" || uiMode === "text") && !drawLocked}
                projectId={projectId}
                sheetId={activeSheetId}
                sourceAssetId={activeSourceAssetId}
                onDirtyChange={setLegendDirty}
              />
            </>
          }
        />
      </div>

      {/* Prompt + submit footer */}
      <footer
        data-testid="ers-edit-modal-footer"
        style={{
          flex: "0 0 auto",
          borderTop: "1px solid var(--border, #2c3346)",
          background: "var(--panel, #121722)",
          padding: "0.55rem 0.85rem 0.7rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.4rem",
          maxHeight: "34vh",
          overflow: "auto",
        }}
      >
        <label style={{ display: "block" }}>
          <span style={{ fontWeight: 600 }}>Edit prompt</span>
          <span className="muted"> (exact creator text — frozen on submit)</span>
          <textarea
            data-testid="ers-edit-prompt"
            rows={2}
            value={editPrompt}
            disabled={busy}
            onChange={(e) => {
              setEditPrompt(e.target.value);
              dirtyRef.current = hasMask || Boolean(e.target.value.trim());
              if (phase === "done") setPhase("idle");
            }}
            placeholder="Describe only the masked region change…"
            style={{ width: "100%", boxSizing: "border-box", marginTop: "0.25rem", resize: "vertical" }}
          />
        </label>

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="primary"
            data-testid="ers-edit-submit"
            disabled={!submitEnabled}
            onClick={() => void handleSubmit()}
            style={{ minWidth: "9rem" }}
          >
            {busy
              ? phase === "saving_mask" || phase === "enqueue"
                ? "Submitting edit…"
                : phase === "polling"
                  ? "Generating edit…"
                  : phase === "creating_version"
                    ? "Creating draft…"
                    : "Working…"
              : "Submit"}
          </button>
          {maskAssetId ? (
            <span className="muted" data-testid="ers-edit-mask-id">
              mask {maskAssetId.slice(0, 8)}…
            </span>
          ) : null}
          {jobId ? (
            <span className="muted" data-testid="ers-edit-job-id">
              job {jobId.slice(0, 8)}…
            </span>
          ) : null}
          {phase === "done" ? (
            <span className="muted" data-testid="ers-edit-ready-next">
              Ready for next pass — paint + prompt again.
            </span>
          ) : null}
        </div>

        {statusMessage ? (
          <p className="muted" role="status" data-testid="ers-edit-status" style={{ margin: 0 }}>
            {statusMessage}
          </p>
        ) : null}
        {overlayGap ? (
          <p className="muted" role="status" data-testid="ers-edit-overlay-gap" style={{ margin: 0 }}>
            {overlayGap}
          </p>
        ) : null}
        {(userError || error) ? (
          <div role="alert" data-testid="ers-edit-error" style={{ margin: 0, color: "var(--danger, #f07178)" }}>
            <p style={{ margin: 0 }}>{userError || error}</p>
            {techError ? (
              <details data-testid="ers-edit-error-tech" style={{ marginTop: "0.35rem" }}>
                <summary style={{ cursor: "pointer", color: "inherit" }}>Technical details</summary>
                <pre
                  style={{
                    margin: "0.35rem 0 0",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    fontSize: "0.78rem",
                    opacity: 0.9,
                  }}
                >
                  {techError}
                </pre>
              </details>
            ) : null}
          </div>
        ) : null}

        {derivativeAssetId ? (
          <div data-testid="ers-edit-derivative">
            <ErsEditVersionChrome
              projectId={projectId}
              sheetId={activeSheetId}
              sourceAssetId={activeSourceAssetId}
              derivativeAssetId={derivativeAssetId}
              editPrompt={frozenPromptRef.current || editPrompt}
              onSelectVersion={(info) => {
                setActiveSheetId(info.versionSheetId);
                if (info.compositeAssetId) {
                  setActiveSourceAssetId(info.compositeAssetId);
                  setEditorKey((k) => k + 1);
                } else {
                  void (async () => {
                    try {
                      const loaded = await api.environmentReferenceSheet.getSheet(projectId, info.versionSheetId);
                      const summary = ((loaded as { summary?: Record<string, unknown> }).summary || {}) as Record<string, unknown>;
                      const sheet = ((loaded as { sheet?: Record<string, unknown> }).sheet || {}) as Record<string, unknown>;
                      const comp = String(
                        summary.composite || summary.ers_composite_asset_id || summary.derivativeAssetId || sheet.ers_composite_asset_id || "",
                      ).trim();
                      if (comp) {
                        setActiveSourceAssetId(comp);
                        setEditorKey((k) => k + 1);
                      }
                    } catch {
                      /* keep current image */
                    }
                  })();
                }
              }}
            />
          </div>
        ) : null}
      </footer>
    </div>
  );

  return createPortal(modal, document.body);
}
