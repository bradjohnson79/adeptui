/**
 * Spatial Map Correct Area — mask + prompt correction on source Atlas pixels.
 *
 * SINGLE VIEWPORT AUTHORITY: the map + mask are rendered by the SHARED
 * SpatialGrid (correctAreaViewport parity). This panel contributes only the
 * floating correction chrome / dock / result overlays — it does NOT re-render
 * the map, and maintains NO separate zoom / pan / fit / canvas. Mask pixels
 * are authored directly in source-image coordinates via the shared transform.
 * Certified engine (maps only): zimage.inpaint (Brad unlocked). Atlas/ERS gen
 * stays GPT Image 2 — do not wire zimage into atlas generate.
 * Apply disabled while executable===false / hold / blocked status; ungates only when honestly executable (zimage.inpaint, executable=true, engineHold=null).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../../api";
import type { MaskEditorTool, SpatialMaskHandle } from "./SpatialGrid";
import { spatialMapApi } from "./spatialMapApi";
import {
  CERTIFIED_CORRECT_AREA_ENGINE,
  CORRECT_AREA_PRESERVATION_HINT,
  asPngDataUrl,
  buildSubmitPreview,
  correctAreaSummary,
  isEngineBlocked,
  isQueuedSession,
  normalizeCorrectAreaSubmitResult,
  probeSourceNaturalSize,
  type CorrectAreaEngineState,
  type CorrectAreaSession,
} from "./correctArea";

export type CorrectAreaPanelProps = {
  projectId: string;
  documentId: string;
  backgroundAssetId: string;
  imageUrl: string;
  onDocumentChange?: (document: Record<string, unknown>) => void;
  /** Parent Map | Inpaint tab: request return to Map (Cancel / after Accept). */
  onRequestClose?: () => void;
  /**
   * Shared-viewport mask bridge. SpatialGrid (single viewport authority) owns
   * the source-pixel mask canvas; the panel drives it through this handle and
   * pushes its tool state up via onMaskConfigChange so the parent can feed the
   * SAME SpatialGrid.maskEditor. No separate renderer / zoom / pan / fit.
   */
  maskHandleRef?: React.MutableRefObject<SpatialMaskHandle | null>;
  onMaskConfigChange?: (cfg: {
    tool: MaskEditorTool;
    brushSize: number;
    active: boolean;
    onChange: (hasMask: boolean) => void;
    registerHandle: (handle: SpatialMaskHandle | null) => void;
  }) => void;
};

type PanelPhase = "idle" | "selecting" | "confirm" | "result";

export function CorrectAreaPanel({
  projectId,
  documentId,
  backgroundAssetId,
  imageUrl,
  onDocumentChange,
  onRequestClose,
  maskHandleRef,
  onMaskConfigChange,
}: CorrectAreaPanelProps) {
  const localMaskRef = useRef<SpatialMaskHandle | null>(null);
  const maskRef = maskHandleRef ?? localMaskRef;
  const undoStackRef = useRef<string[]>([]);
  const lastMaskPushRef = useRef(0);
  const [phase, setPhase] = useState<PanelPhase>("selecting");
  const [tool, setTool] = useState<MaskEditorTool>("brush");
  const [brushSize, setBrushSize] = useState(28);
  const [prompt, setPrompt] = useState("");
  const [hasMask, setHasMask] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<CorrectAreaEngineState | null>(null);
  const [lastSession, setLastSession] = useState<CorrectAreaSession | null>(null);
  const [maskPreview, setMaskPreview] = useState<string | null>(null);
  const [sourceDims, setSourceDims] = useState({ width: 0, height: 0 });
  const [preserveStyle, setPreserveStyle] = useState(true);
  const [preservePerspective, setPreservePerspective] = useState(true);
  const [preserveLighting, setPreserveLighting] = useState(true);
  const [resultPreviewUrl, setResultPreviewUrl] = useState<string | null>(null);

  const selecting = phase === "selecting" || phase === "confirm";
  const showResultSurface = phase === "result" && Boolean(resultPreviewUrl);

  const refresh = useCallback(async () => {
    try {
      const next = await spatialMapApi.getCorrectAreaState(projectId, documentId);
      setState(next as CorrectAreaEngineState);
      if (next.activeSession) {
        const sess = next.activeSession as CorrectAreaSession;
        // Poll bridge: mirror resultAssetId onto outputAssetId for Accept/preview.
        const bridged: CorrectAreaSession = {
          ...sess,
          outputAssetId: sess.outputAssetId || sess.resultAssetId || null,
          resultAssetId: sess.resultAssetId || sess.outputAssetId || null,
        };
        setLastSession(bridged);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [projectId, documentId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!isQueuedSession(lastSession)) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [lastSession, refresh]);

  useEffect(() => {
    // Poll bridge: Backend get_correction_state syncs queueJobId -> resultAssetId + preview_ready.
    const pollAsset = lastSession?.outputAssetId || lastSession?.resultAssetId || null;
    if (lastSession?.status === "preview_ready" && pollAsset) {
      setResultPreviewUrl(
        lastSession.previewUrl ||
          `/api/projects/${projectId}/assets/${pollAsset}/file`,
      );
      setPhase("result");
    }
  }, [lastSession, projectId]);

  useEffect(() => {
    let cancelled = false;
    void probeSourceNaturalSize(imageUrl)
      .then((dims) => {
        if (!cancelled) setSourceDims(dims);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [imageUrl]);

  /* Push the full mask config up so the parent feeds the SAME
   * SpatialGrid.maskEditor (single viewport authority). The handle registers
   * back into maskRef so export/clear/restore hit the shared source canvas.
   * Active only while selecting (not result). */
  const registerMaskHandle = useCallback((handle: SpatialMaskHandle | null) => {
    maskRef.current = handle;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    onMaskConfigChange?.({
      tool,
      brushSize,
      active: selecting && !showResultSurface,
      onChange: handleMaskChangeRef.current,
      registerHandle: registerMaskHandle,
    });
  }, [tool, brushSize, selecting, showResultSurface, onMaskConfigChange, registerMaskHandle]);

  const handleMaskChange = useCallback((next: boolean) => {
    setHasMask(next);
    if (!next) {
      setMaskPreview(null);
      return;
    }
    void (async () => {
      const png = (await maskRef.current?.exportPng()) || "";
      if (!png) return;
      const now = Date.now();
      // Debounce stroke snapshots so pointer-move paint does not flood undo.
      if (now - lastMaskPushRef.current > 280) {
        undoStackRef.current.push(png);
        if (undoStackRef.current.length > 40) undoStackRef.current.shift();
        lastMaskPushRef.current = now;
      }
      setMaskPreview(asPngDataUrl(png));
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const handleMaskChangeRef = useRef(handleMaskChange);
  useEffect(() => { handleMaskChangeRef.current = handleMaskChange; }, [handleMaskChange]);

  const handleMaskStrokeUndo = useCallback(async () => {
    const stack = undoStackRef.current;
    if (stack.length === 0) {
      maskRef.current?.clear();
      setHasMask(false);
      setMaskPreview(null);
      return;
    }
    // Discard current stroke snapshot, restore previous.
    stack.pop();
    const prev = stack.length ? stack[stack.length - 1] : null;
    if (!prev) {
      maskRef.current?.clear();
      setHasMask(false);
      setMaskPreview(null);
      return;
    }
    await maskRef.current?.restorePng(prev);
    setHasMask(true);
    setMaskPreview(asPngDataUrl(prev));
    setError(null);
  }, []);

  const exportAlignedMask = async (): Promise<{ maskAssetId: string; width: number; height: number }> => {
    // The shared SpatialGrid mask canvas is ALREADY at source natural resolution
    // (authored via viewBox→source-pixel transform). No display upscale pass.
    const pngBase64 = (await maskRef.current?.exportPng()) || "";
    if (!pngBase64) throw new Error("Paint a mask region first (brush or rectangle).");
    const srcSize = maskRef.current?.getSourceSize();
    const dims =
      srcSize && srcSize.width > 0 && srcSize.height > 0
        ? srcSize
        : sourceDims.width > 0 && sourceDims.height > 0
          ? sourceDims
          : await probeSourceNaturalSize(imageUrl);
    setMaskPreview(asPngDataUrl(pngBase64));
    setSourceDims({ width: dims.width, height: dims.height });
    const saved = await api.imageProduct.saveMask(projectId, {
      sourceAssetId: backgroundAssetId,
      pngBase64,
      role: "include",
      metadata: {
        surface: "spatial_map.correct_area",
        width: dims.width,
        height: dims.height,
        upscaledFromDisplay: false,
        alignment: "shared_viewport_source_pixels",
      },
      dimensions: { width: dims.width, height: dims.height },
    });
    return { maskAssetId: saved.maskId, width: dims.width, height: dims.height };
  };

  const submitPreview = useMemo(
    () =>
      buildSubmitPreview({
        prompt,
        sourceAssetId: backgroundAssetId,
        maskPreviewUrl: maskPreview,
        preserveStyle,
        preservePerspective,
        preserveLighting,
        sourceWidth: sourceDims.width,
        sourceHeight: sourceDims.height,
      }),
    [
      prompt,
      backgroundAssetId,
      maskPreview,
      preserveStyle,
      preservePerspective,
      preserveLighting,
      sourceDims.width,
      sourceDims.height,
    ],
  );

  const handlePrepareApply = () => {
    if (isEngineBlocked(state)) return;
    if (!prompt.trim() || !hasMask) return;
    setError(null);
    setPhase("confirm");
  };

  const handleCorrect = async () => {
    if (isEngineBlocked(state)) return;
    if (!prompt.trim() || !hasMask) return;
    setBusy(true);
    setError(null);
    try {
      const { maskAssetId, width, height } = await exportAlignedMask();
      const result = await spatialMapApi.startCorrectArea(projectId, documentId, {
        prompt: prompt.trim(),
        maskAssetId,
        sourceAssetId: backgroundAssetId,
        width,
        height,
        preserveStyle,
        preservePerspective,
        preserveLighting,
      });
      // Normalize resultAssetId/preview/acceptToken — ungates Accept when Backend
      // returns real pixels; stays honest (no fake success) under ENGINE_HOLD.
      const normalized = normalizeCorrectAreaSubmitResult(result as Record<string, unknown>);
      setLastSession(normalized.session);
      setState((prev) => ({
        ...(prev || { engineStatus: normalized.engineStatus, executable: normalized.executable }),
        engineStatus: normalized.engineStatus,
        executable: normalized.executable,
        reason: normalized.reason,
        engineHold: normalized.engineHold,
        activeSession: normalized.session,
        preferredModel: normalized.preferredModel,
        zimageWired: normalized.zimageWired,
      }));
      setResultPreviewUrl(normalized.previewUrl ?? null);
      setPhase("result");
      if (normalized.blocked) {
        setError(
          normalized.reason ||
            normalized.message ||
            "Correct Area engine hold — Backend still returns GPT_MASK_BLOCKED_NEED_BRAD / ENGINE_HOLD. No fake pixels.",
        );
      } else if (!normalized.resultAssetId) {
        setError(
          normalized.reason ||
            normalized.message ||
            "Correction returned no resultAssetId — original Spatial Map stays active.",
        );
      } else {
        setError(null);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleAccept = async () => {
    setBusy(true);
    setError(null);
    try {
      // OVERLAY_GUARD: never createMap. Backend Accept uses update_document({backgroundAssetId}).
      // UI also refuses Accept without an existing documentId (map must already exist).
      if (!documentId) {
        throw new Error("Accept requires an existing Spatial Map document — createMap is forbidden here.");
      }
      const outId = lastSession?.outputAssetId || lastSession?.resultAssetId || undefined;
      const result = await spatialMapApi.acceptCorrectArea(projectId, documentId, {
        sessionId: lastSession?.sessionId,
        outputAssetId: outId,
        resultAssetId: outId,
        acceptToken: lastSession?.acceptToken || undefined,
      });
      // Prefer server-returned document (background patched; overlays intact).
      if (result.document && onDocumentChange) {
        onDocumentChange(result.document as Record<string, unknown>);
      } else if (outId) {
        // Fallback: explicit background-only updateMap on the same document id.
        const updated = await spatialMapApi.updateMap(projectId, documentId, {
          backgroundAssetId: outId,
        });
        onDocumentChange?.(updated as unknown as Record<string, unknown>);
      } else {
        throw new Error(
          "Accept blocked: no corrected pixels yet (wait for zimage.inpaint preview_ready). Original stays active.",
        );
      }
      await refresh();
      setPhase("idle");
      onRequestClose?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleUndo = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await spatialMapApi.undoCorrectArea(projectId, documentId);
      if (result.document && onDocumentChange) onDocumentChange(result.document);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleCorrectAgain = () => {
    setPrompt("");
    setMaskPreview(null);
    setHasMask(false);
    maskRef.current?.clear();
    undoStackRef.current = [];
    setLastSession(null);
    setResultPreviewUrl(null);
    setError(null);
    setPhase("selecting");
  };

  const handleCancel = () => {
    setError(null);
    setPhase("idle");
    onRequestClose?.();
  };

  const handleEnterSelectRegion = () => {
    setPhase("selecting");
    setError(null);
    setResultPreviewUrl(null);
  };

  const blocked = isEngineBlocked(state);
  const outAsset = lastSession?.outputAssetId || lastSession?.resultAssetId || null;
  // Accept only with real pixels — never under hold with null resultAssetId.
  const canAccept =
    Boolean(outAsset) &&
    lastSession?.status !== "blocked" &&
    (lastSession?.status === "preview_ready" || Boolean(outAsset));
  const canUndo = Boolean(state?.canUndo);
  // Apply: disabled when blocked/hold/executable!==true. Ungates only for honest
  // certified path (zimage.inpaint + executable=true + engineHold=null).

  return (
    <section
      className="spatial-map__correct-workspace"
      data-testid="spatial-map-correct-area"
      aria-label={correctAreaSummary(state)}
    >
      {/* The map + mask are rendered by the SHARED SpatialGrid (single viewport
          authority). This panel contributes ONLY the floating chrome / dock /
          result overlays — no duplicate renderer, zoom, pan, or fit. */}
      <div
        className="spatial-map__correct-workspace-stage spatial-map__correct-workspace-stage--overlay-only"
        data-testid="spatial-map-correct-area-canvas"
      >
        {showResultSurface ? (
          <div className="spatial-map__correct-result-full" data-testid="spatial-map-correct-result">
            <img src={resultPreviewUrl!} alt="Corrected Spatial Map preview" />
            <p className="spatial-map__correct-result-caption muted">
              Result: {outAsset ? `corrected asset ${outAsset}` : "preview"}
            </p>
          </div>
        ) : null}

        <header className="spatial-map__correct-workspace-chrome spatial-map__correct-workspace-chrome--float">
          <div className="spatial-map__correct-workspace-meta">
            <p className="spatial-map__correct-workspace-title" data-testid="spatial-map-correct-area-summary">
              {correctAreaSummary(state)}
            </p>
            <p className="muted" data-testid="spatial-map-correct-area-hint">
              {CORRECT_AREA_PRESERVATION_HINT}
            </p>
            <p className="muted" data-testid="spatial-map-correct-area-engine">
              Engine: {state?.engineStatus || "…"} · Preferred:{" "}
              {state?.preferredModel ||
                (blocked ? "held (awaiting Backend unlock)" : CERTIFIED_CORRECT_AREA_ENGINE)}{" "}
              · zimageWired: {String(state?.zimageWired ?? false)}
              {state?.engineHold ? ` · Hold: ${state.engineHold}` : ""}
              {!blocked ? ` · Certified: ${CERTIFIED_CORRECT_AREA_ENGINE}` : ""}
              {sourceDims.width > 0
                ? ` · Source ${sourceDims.width}×${sourceDims.height}`
                : ""}
            </p>
          </div>

          <div className="spatial-map__correct-area-tools" data-testid="spatial-map-correct-area-tools">
            <button
              type="button"
              className={"spatial-map__slot-action" + (selecting && !showResultSurface ? " is-active" : "")}
              data-testid="spatial-map-correct-select-region"
              onClick={handleEnterSelectRegion}
            >
              Select Region
            </button>
            <button
              type="button"
              className={"spatial-map__slot-action" + (tool === "brush" ? " is-active" : "")}
              data-testid="spatial-map-correct-tool-brush"
              disabled={!selecting || showResultSurface}
              onClick={() => setTool("brush")}
            >
              Brush
            </button>
            <button
              type="button"
              className={"spatial-map__slot-action" + (tool === "rect" ? " is-active" : "")}
              data-testid="spatial-map-correct-tool-rect"
              disabled={!selecting || showResultSurface}
              onClick={() => setTool("rect")}
            >
              Rectangle
            </button>
            <button
              type="button"
              className={"spatial-map__slot-action" + (tool === "erase" ? " is-active" : "")}
              data-testid="spatial-map-correct-tool-erase"
              disabled={!selecting || showResultSurface}
              onClick={() => setTool("erase")}
            >
              Erase
            </button>
            <label className="spatial-map__correct-brush">
              Size
              <input
                type="range"
                min={8}
                max={96}
                value={brushSize}
                data-testid="spatial-map-correct-brush-size"
                disabled={!selecting || showResultSurface}
                onChange={(e) => setBrushSize(Number(e.target.value))}
              />
            </label>
            <button
              type="button"
              className="spatial-map__slot-action"
              data-testid="spatial-map-correct-mask-undo"
              disabled={(!hasMask && undoStackRef.current.length === 0) || showResultSurface}
              onClick={() => void handleMaskStrokeUndo()}
              title="Undo last mask stroke"
            >
              Undo
            </button>
            <button
              type="button"
              className="spatial-map__slot-action"
              data-testid="spatial-map-correct-clear-mask"
              disabled={!hasMask || showResultSurface}
              onClick={() => {
                maskRef.current?.clear();
                undoStackRef.current = [];
                setHasMask(false);
                setMaskPreview(null);
              }}
            >
              Clear Mask
            </button>
            <fieldset className="spatial-map__correct-preserve spatial-map__correct-preserve--inline" data-testid="spatial-map-correct-preserve">
              <legend>Preserve</legend>
              <label>
                <input
                  type="checkbox"
                  checked={preserveStyle}
                  data-testid="spatial-map-correct-preserve-style"
                  onChange={(e) => setPreserveStyle(e.target.checked)}
                />
                Style
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={preservePerspective}
                  data-testid="spatial-map-correct-preserve-perspective"
                  onChange={(e) => setPreservePerspective(e.target.checked)}
                />
                Perspective
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={preserveLighting}
                  data-testid="spatial-map-correct-preserve-lighting"
                  onChange={(e) => setPreserveLighting(e.target.checked)}
                />
                Lighting
              </label>
            </fieldset>
          </div>
        </header>

        {phase === "confirm" ? (
          <div className="spatial-map__correct-confirm spatial-map__correct-confirm--overlay" data-testid="spatial-map-correct-confirm">
            <p className="muted">Review before Apply Correction</p>
            <ul>
              {submitPreview.lines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="spatial-map__correct-workspace-dock spatial-map__correct-workspace-dock--float">
          <label className="spatial-map__correct-prompt-label" htmlFor="spatial-map-correct-prompt">
            Correction prompt (frozen on Apply — no silent Co-Director rewrite)
          </label>
          <textarea
            id="spatial-map-correct-prompt"
            className="spatial-map__correct-prompt"
            data-testid="spatial-map-correct-prompt"
            rows={2}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe only what should change inside the mask"
          />

          <div className="spatial-map__correct-area-actions">
            {phase === "confirm" ? (
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                data-testid="spatial-map-correct-submit"
                disabled={busy || blocked || !submitPreview.ready}
                onClick={() => void handleCorrect()}
              >
                {busy ? "Working…" : "Apply Correction"}
              </button>
            ) : (
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                data-testid="spatial-map-correct-submit"
                disabled={busy || blocked || !hasMask || !prompt.trim() || showResultSurface}
                onClick={handlePrepareApply}
              >
                Apply Correction
              </button>
            )}
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              data-testid="spatial-map-correct-accept"
              disabled={busy || !canAccept}
              onClick={() => void handleAccept()}
              title={canAccept ? "Accept corrected pixels as Active Atlas" : "Accept requires a preview output asset"}
            >
              Accept
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              data-testid="spatial-map-correct-undo"
              disabled={busy || !canUndo}
              onClick={() => void handleUndo()}
            >
              Undo Correction
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              data-testid="spatial-map-correct-again"
              disabled={busy}
              onClick={handleCorrectAgain}
            >
              Correct Again
            </button>
            <button
              type="button"
              className="ui-btn ui-btn--secondary"
              data-testid="spatial-map-correct-cancel"
              disabled={busy}
              onClick={handleCancel}
            >
              Back to Map
            </button>
          </div>

          {blocked ? (
            <p className="spatial-map__hint spatial-map__hint--warn" role="status" data-testid="spatial-map-correct-blocked">
              {state?.reason ||
                "Engine blocked — Correct Area requires an executable certified path."}
            </p>
          ) : null}
          {error ? (
            <p className="spatial-map__hint spatial-map__hint--error" role="alert" data-testid="spatial-map-correct-error">
              {error}
            </p>
          ) : null}
          {lastSession ? (
            <p className="muted" data-testid="spatial-map-correct-session">
              Session {lastSession.sessionId} · status {lastSession.status} · frozen={String(!!lastSession.frozen)} ·
              coDirectorRewrite={String(!!lastSession.coDirectorRewrite)}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

