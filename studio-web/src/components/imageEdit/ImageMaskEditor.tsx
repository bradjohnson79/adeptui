import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from "react";

export type MaskTool = "brush" | "erase" | "rect" | "pan";

export type ImageMaskEditorHandle = {
  exportPng: () => Promise<string>;
  clear: () => void;
  measureCoverage: () => number;
  /** Restore mask from PNG base64 (or data URL). Native-pixel sized preferred. */
  restorePng: (pngBase64: string) => Promise<void>;
  /** Natural source image size (master pixels). */
  getSourceNaturalSize: () => { width: number; height: number };
  /** Display CSS pixel size (fitted view size, not buffer). */
  getDisplaySize: () => { width: number; height: number };
  /** Mask buffer is always native ERS pixels when nativeMask is on. */
  getMaskBufferSize: () => { width: number; height: number };
  undo: () => void;
  canUndo: () => boolean;
  fitToView: () => void;
};

type Props = {
  imageUrl: string;
  brushSize?: number;
  tool?: MaskTool;
  feather?: number;
  hideChrome?: boolean;
  fill?: boolean;
  overlayOpacity?: number;
  interactive?: boolean;
  /** External zoom multiplier (1 = fit-to-view). */
  zoom?: number;
  /** When true, mask + display buffers are native ERS pixels; CSS scales for fit. */
  nativeMask?: boolean;
  onExport?: (pngBase64: string) => void;
  onChange?: (hasMask: boolean) => void;
  onReady?: (info: { naturalWidth: number; naturalHeight: number; displayWidth: number; displayHeight: number }) => void;
  frameChildren?: ReactNode;
  frameInteractive?: boolean;
};

export const ImageMaskEditor = forwardRef<ImageMaskEditorHandle, Props>(function ImageMaskEditor(
  {
    imageUrl,
    brushSize = 24,
    tool = "brush",
    feather = 0,
    hideChrome = false,
    fill = false,
    overlayOpacity = 0.45,
    interactive = true,
    zoom = 1,
    nativeMask = false,
    onExport,
    onChange,
    onReady,
    frameChildren,
    frameInteractive = true,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const maskCanvasRef = useRef<HTMLCanvasElement>(null);
  const displayCanvasRef = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const rectStartRef = useRef<{ x: number; y: number } | null>(null);
  const panStartRef = useRef<{ x: number; y: number; scrollLeft: number; scrollTop: number } | null>(null);
  const onChangeRef = useRef(onChange);
  const onReadyRef = useRef(onReady);
  const overlayOpacityRef = useRef(overlayOpacity);
  const syncDisplayRef = useRef<() => void>(() => undefined);
  const undoStackRef = useRef<ImageData[]>([]);
  const naturalRef = useRef({ w: 0, h: 0 });
  const [bufferDims, setBufferDims] = useState({ w: 0, h: 0 });
  const [cssDims, setCssDims] = useState({ w: 0, h: 0 });
  const [localBrush, setLocalBrush] = useState(brushSize);
  const [localTool, setLocalTool] = useState<MaskTool>(tool);
  const [localFeather, setLocalFeather] = useState(feather);
  const [undoTick, setUndoTick] = useState(0);

  useEffect(() => setLocalBrush(brushSize), [brushSize]);
  useEffect(() => setLocalTool(tool), [tool]);
  useEffect(() => setLocalFeather(feather), [feather]);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);
  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);
  useEffect(() => {
    overlayOpacityRef.current = overlayOpacity;
  }, [overlayOpacity]);

  const syncDisplay = useCallback(() => {
    const maskCanvas = maskCanvasRef.current;
    const displayCanvas = displayCanvasRef.current;
    const img = imageRef.current;
    const nw = naturalRef.current.w;
    const nh = naturalRef.current.h;
    if (!maskCanvas || !displayCanvas || !img || !nw || !nh) return;
    const ctx = displayCanvas.getContext("2d");
    if (!ctx) return;
    ctx.imageSmoothingEnabled = true;
    ctx.clearRect(0, 0, displayCanvas.width, displayCanvas.height);
    ctx.drawImage(img, 0, 0, displayCanvas.width, displayCanvas.height);
    ctx.globalAlpha = overlayOpacityRef.current;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(maskCanvas, 0, 0, displayCanvas.width, displayCanvas.height);
    ctx.globalAlpha = 1;
  }, []);
  syncDisplayRef.current = syncDisplay;

  const computeFitCss = useCallback(
    (nw: number, nh: number) => {
      const stage = stageRef.current || containerRef.current;
      const maxW = Math.max(120, stage?.clientWidth || containerRef.current?.clientWidth || 800);
      const maxH = Math.max(120, stage?.clientHeight || containerRef.current?.clientHeight || 600);
      const scaleW = maxW / nw;
      const scaleH = maxH / nh;
      // Aggressive fit: use full available stage while preserving aspect (may upscale).
      const base = Math.min(scaleW, scaleH);
      const z = Math.max(0.1, Number(zoom) || 1);
      const w = Math.max(1, Math.round(nw * base * z));
      const h = Math.max(1, Math.round(nh * base * z));
      return { w, h, base };
    },
    [zoom],
  );

  const applyCssSize = useCallback(
    (nw: number, nh: number) => {
      const fit = computeFitCss(nw, nh);
      setCssDims({ w: fit.w, h: fit.h });
      onReadyRef.current?.({
        naturalWidth: nw,
        naturalHeight: nh,
        displayWidth: fit.w,
        displayHeight: fit.h,
      });
      return fit;
    },
    [computeFitCss],
  );

  const initBuffers = useCallback(
    (img: HTMLImageElement, clearMask: boolean) => {
      const nw = img.naturalWidth;
      const nh = img.naturalHeight;
      naturalRef.current = { w: nw, h: nh };
      // Always prefer native ERS pixels for the mask buffer.
      const bufW = nativeMask ? nw : nw;
      const bufH = nativeMask ? nh : nh;
      setBufferDims({ w: bufW, h: bufH });
      const maskCanvas = maskCanvasRef.current;
      const displayCanvas = displayCanvasRef.current;
      if (maskCanvas && displayCanvas) {
        if (maskCanvas.width !== bufW || maskCanvas.height !== bufH) {
          maskCanvas.width = bufW;
          maskCanvas.height = bufH;
          clearMask = true;
        }
        displayCanvas.width = bufW;
        displayCanvas.height = bufH;
        if (clearMask) {
          const mctx = maskCanvas.getContext("2d");
          if (mctx) {
            mctx.fillStyle = "#000";
            mctx.fillRect(0, 0, bufW, bufH);
          }
          undoStackRef.current = [];
          setUndoTick((t) => t + 1);
          onChangeRef.current?.(false);
        }
        applyCssSize(nw, nh);
        syncDisplayRef.current();
      } else {
        applyCssSize(nw, nh);
      }
    },
    [applyCssSize, nativeMask],
  );

  const loadImage = useCallback(() => {
    if (!imageUrl) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imageRef.current = img;
      undoStackRef.current = [];
      setUndoTick((t) => t + 1);
      initBuffers(img, true);
      // Refit after layout settles so full-screen stage height is used (not collapsed).
      requestAnimationFrame(() => {
        const nw = img.naturalWidth;
        const nh = img.naturalHeight;
        if (nw && nh) applyCssSize(nw, nh);
        syncDisplayRef.current();
        requestAnimationFrame(() => {
          if (nw && nh) applyCssSize(nw, nh);
          syncDisplayRef.current();
        });
      });
    };
    img.src = imageUrl;
  }, [imageUrl, initBuffers, applyCssSize]);

  useEffect(() => {
    loadImage();
  }, [loadImage]);

  // Refit CSS size on zoom / container resize (keep native mask buffer).
  useEffect(() => {
    const nw = naturalRef.current.w;
    const nh = naturalRef.current.h;
    if (!nw || !nh) return;
    applyCssSize(nw, nh);
    syncDisplayRef.current();
  }, [zoom, applyCssSize]);

  useEffect(() => {
    const el = stageRef.current || containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => {
      const nw = naturalRef.current.w;
      const nh = naturalRef.current.h;
      if (!nw || !nh) return;
      applyCssSize(nw, nh);
      syncDisplayRef.current();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [applyCssSize]);

  useEffect(() => {
    syncDisplay();
  }, [syncDisplay, overlayOpacity]);

  const pushUndo = () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    try {
      const snap = ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
      undoStackRef.current.push(snap);
      if (undoStackRef.current.length > 30) undoStackRef.current.shift();
      setUndoTick((t) => t + 1);
    } catch {
      /* ignore tainted */
    }
  };

  const canvasPoint = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = displayCanvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    // Map viewport → native buffer pixels (never paint at CSS resolution).
    return {
      x: ((e.clientX - rect.left) / Math.max(1, rect.width)) * canvas.width,
      y: ((e.clientY - rect.top) / Math.max(1, rect.height)) * canvas.height,
    };
  };

  const screenBrushRadius = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = displayCanvasRef.current;
    if (!canvas) return localBrush / 2;
    const rect = canvas.getBoundingClientRect();
    const scale = canvas.width / Math.max(1, rect.width);
    return (localBrush / 2) * scale;
  };

  const paint = (x: number, y: number, erase: boolean, radius: number) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = erase ? "#000" : "#fff";
    ctx.beginPath();
    ctx.arc(x, y, Math.max(0.5, radius), 0, Math.PI * 2);
    ctx.fill();
    syncDisplay();
    onChangeRef.current?.(true);
  };

  const drawRect = (x0: number, y0: number, x1: number, y1: number, erase: boolean) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = erase ? "#000" : "#fff";
    const x = Math.min(x0, x1);
    const y = Math.min(y0, y1);
    const w = Math.abs(x1 - x0);
    const h = Math.abs(y1 - y0);
    ctx.fillRect(x, y, w, h);
    syncDisplay();
    onChangeRef.current?.(true);
  };

  const exportMask = useCallback(async () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return "";
    let outCanvas: HTMLCanvasElement = maskCanvas;
    if (localFeather > 0) {
      const blurred = document.createElement("canvas");
      blurred.width = maskCanvas.width;
      blurred.height = maskCanvas.height;
      const bctx = blurred.getContext("2d");
      if (bctx) {
        bctx.filter = `blur(${localFeather}px)`;
        bctx.drawImage(maskCanvas, 0, 0);
        outCanvas = blurred;
      }
    }
    const dataUrl = outCanvas.toDataURL("image/png");
    const base64 = dataUrl.replace(/^data:image\/png;base64,/, "");
    onExport?.(base64);
    return base64;
  }, [localFeather, onExport]);

  const clearMask = () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    pushUndo();
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
    syncDisplay();
    onChangeRef.current?.(false);
  };

  const undo = () => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const prev = undoStackRef.current.pop();
    if (!prev) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.putImageData(prev, 0, 0);
    syncDisplay();
    // Rough hasMask: any non-black
    const data = ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
    let painted = false;
    for (let i = 0; i < data.length; i += 16) {
      if (data[i] >= 128 || data[i + 1] >= 128 || data[i + 2] >= 128) {
        painted = true;
        break;
      }
    }
    onChangeRef.current?.(painted);
    setUndoTick((t) => t + 1);
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!interactive) return;
    e.preventDefault();
    if (localTool === "pan") {
      const stage = stageRef.current;
      if (!stage) return;
      panStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        scrollLeft: stage.scrollLeft,
        scrollTop: stage.scrollTop,
      };
      e.currentTarget.setPointerCapture(e.pointerId);
      drawingRef.current = true;
      return;
    }
    e.currentTarget.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    pushUndo();
    const pt = canvasPoint(e);
    if (localTool === "rect") {
      rectStartRef.current = pt;
    } else {
      paint(pt.x, pt.y, localTool === "erase", screenBrushRadius(e));
    }
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!interactive || !drawingRef.current) return;
    if (localTool === "pan" && panStartRef.current) {
      const stage = stageRef.current;
      if (!stage) return;
      const dx = e.clientX - panStartRef.current.x;
      const dy = e.clientY - panStartRef.current.y;
      stage.scrollLeft = panStartRef.current.scrollLeft - dx;
      stage.scrollTop = panStartRef.current.scrollTop - dy;
      return;
    }
    const pt = canvasPoint(e);
    if (localTool === "rect" && rectStartRef.current) {
      syncDisplay();
      const displayCanvas = displayCanvasRef.current;
      const ctx = displayCanvas?.getContext("2d");
      const img = imageRef.current;
      if (ctx && img && rectStartRef.current) {
        ctx.clearRect(0, 0, displayCanvas!.width, displayCanvas!.height);
        ctx.drawImage(img, 0, 0, displayCanvas!.width, displayCanvas!.height);
        ctx.fillStyle = "rgba(255,255,255,0.45)";
        const x = Math.min(rectStartRef.current.x, pt.x);
        const y = Math.min(rectStartRef.current.y, pt.y);
        ctx.fillRect(x, y, Math.abs(pt.x - rectStartRef.current.x), Math.abs(pt.y - rectStartRef.current.y));
      }
    } else if (localTool === "brush" || localTool === "erase") {
      paint(pt.x, pt.y, localTool === "erase", screenBrushRadius(e));
    }
  };

  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    if (localTool === "pan") {
      panStartRef.current = null;
      return;
    }
    if (localTool === "rect" && rectStartRef.current) {
      const pt = canvasPoint(e);
      drawRect(rectStartRef.current.x, rectStartRef.current.y, pt.x, pt.y, false);
      rectStartRef.current = null;
    }
  };

  const restorePng = useCallback(
    async (pngBase64: string) => {
      const maskCanvas = maskCanvasRef.current;
      if (!maskCanvas || !bufferDims.w) return;
      const raw = (pngBase64 || "").trim();
      if (!raw) return;
      const src = raw.startsWith("data:") ? raw : `data:image/png;base64,${raw}`;
      await new Promise<void>((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
          const ctx = maskCanvas.getContext("2d");
          if (!ctx) {
            reject(new Error("mask ctx missing"));
            return;
          }
          pushUndo();
          ctx.imageSmoothingEnabled = false;
          ctx.fillStyle = "#000";
          ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
          ctx.drawImage(img, 0, 0, maskCanvas.width, maskCanvas.height);
          syncDisplay();
          onChangeRef.current?.(true);
          resolve();
        };
        img.onerror = () => reject(new Error("Failed to restore mask PNG"));
        img.src = src;
      });
    },
    [bufferDims.w],
  );

  useImperativeHandle(
    ref,
    () => ({
      exportPng: exportMask,
      clear: clearMask,
      restorePng,
      undo,
      canUndo: () => undoStackRef.current.length > 0,
      fitToView: () => {
        const nw = naturalRef.current.w;
        const nh = naturalRef.current.h;
        if (nw && nh) applyCssSize(nw, nh);
      },
      getSourceNaturalSize: () => {
        const img = imageRef.current;
        return {
          width: img?.naturalWidth || naturalRef.current.w || 0,
          height: img?.naturalHeight || naturalRef.current.h || 0,
        };
      },
      getDisplaySize: () => ({ width: cssDims.w, height: cssDims.h }),
      getMaskBufferSize: () => ({
        width: maskCanvasRef.current?.width || bufferDims.w,
        height: maskCanvasRef.current?.height || bufferDims.h,
      }),
      measureCoverage: () => {
        const maskCanvas = maskCanvasRef.current;
        if (!maskCanvas || !maskCanvas.width) return 0;
        const ctx = maskCanvas.getContext("2d");
        if (!ctx) return 0;
        const data = ctx.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
        let painted = 0;
        const total = maskCanvas.width * maskCanvas.height;
        for (let i = 0; i < data.length; i += 4) {
          if (data[i] >= 128 || data[i + 1] >= 128 || data[i + 2] >= 128) painted += 1;
        }
        return total ? (painted / total) * 100 : 0;
      },
    }),
    [exportMask, restorePng, cssDims.w, cssDims.h, bufferDims.w, bufferDims.h, applyCssSize, undoTick],
  );

  const cursor =
    !interactive ? "default" : localTool === "pan" ? "grab" : localTool === "erase" ? "cell" : "crosshair";

  return (
    <div
      ref={containerRef}
      className={fill ? "image-mask-editor image-mask-editor--fill" : "image-mask-editor"}
      data-testid="image-mask-editor"
      data-native-mask={nativeMask ? "true" : "false"}
      data-buffer-w={bufferDims.w}
      data-buffer-h={bufferDims.h}
      data-css-w={cssDims.w}
      data-css-h={cssDims.h}
      style={
        fill
          ? { width: "100%", height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }
          : undefined
      }
    >
      {hideChrome ? null : (
        <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.5rem" }}>
          {(["brush", "erase", "rect"] as MaskTool[]).map((t) => (
            <button
              key={t}
              type="button"
              className={localTool === t ? "primary" : ""}
              onClick={() => setLocalTool(t)}
            >
              {t === "brush" ? "Brush" : t === "erase" ? "Erase" : "Rect"}
            </button>
          ))}
          <label className="pill" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            Size
            <input
              type="range"
              min={4}
              max={96}
              value={localBrush}
              onChange={(e) => setLocalBrush(Number(e.target.value))}
            />
            {localBrush}
          </label>
          <label className="pill" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            Feather
            <input
              type="range"
              min={0}
              max={32}
              value={localFeather}
              onChange={(e) => setLocalFeather(Number(e.target.value))}
            />
            {localFeather}
          </label>
          <button type="button" onClick={clearMask}>
            Clear
          </button>
          <button type="button" className="primary" onClick={() => void exportMask()}>
            Export mask
          </button>
        </div>
      )}
      <div
        ref={stageRef}
        className="image-mask-editor__stage"
        data-testid="image-mask-editor-stage"
        style={{
          flex: fill ? 1 : undefined,
          minHeight: fill ? 0 : undefined,
          width: "100%",
          height: fill ? "100%" : undefined,
          overflow: "auto",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#07090e",
        }}
      >
        <div
          data-testid="image-mask-editor-frame"
          style={{
            position: "relative",
            width: cssDims.w ? `${cssDims.w}px` : undefined,
            height: cssDims.h ? `${cssDims.h}px` : undefined,
            flex: "0 0 auto",
          }}
        >
          <canvas
            ref={displayCanvasRef}
            width={bufferDims.w || undefined}
            height={bufferDims.h || undefined}
            style={{
              width: cssDims.w ? `${cssDims.w}px` : "auto",
              height: cssDims.h ? `${cssDims.h}px` : "auto",
              maxWidth: "none",
              maxHeight: "none",
              borderRadius: 8,
              cursor,
              touchAction: "none",
              pointerEvents: interactive ? "auto" : "none",
              display: "block",
            }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerLeave={onPointerUp}
          />
          {frameChildren ? (
            <div
              data-testid="image-mask-editor-frame-overlay"
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: 8,
                pointerEvents: frameInteractive ? "auto" : "none",
                overflow: "hidden",
              }}
            >
              {frameChildren}
            </div>
          ) : null}
        </div>
        <canvas ref={maskCanvasRef} style={{ display: "none" }} />
      </div>
    </div>
  );
});

ImageMaskEditor.displayName = "ImageMaskEditor";
