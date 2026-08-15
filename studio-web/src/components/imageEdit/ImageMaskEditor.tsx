import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";

export type MaskTool = "brush" | "erase" | "rect";

export type ImageMaskEditorHandle = {
  exportPng: () => Promise<string>;
  clear: () => void;
  measureCoverage: () => number;
};

export const ImageMaskEditor = forwardRef<
  ImageMaskEditorHandle,
  {
    imageUrl: string;
    brushSize?: number;
    tool?: MaskTool;
    feather?: number;
    hideChrome?: boolean;
    fill?: boolean;
    overlayOpacity?: number;
    interactive?: boolean;
    onExport?: (pngBase64: string) => void;
    onChange?: (hasMask: boolean) => void;
  }
>(function ImageMaskEditor(
  {
    imageUrl,
    brushSize = 24,
    tool = "brush",
    feather = 0,
    hideChrome = false,
    fill = false,
    overlayOpacity = 0.45,
    interactive = true,
    onExport,
    onChange,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const maskCanvasRef = useRef<HTMLCanvasElement>(null);
  const displayCanvasRef = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const rectStartRef = useRef<{ x: number; y: number } | null>(null);
  const onChangeRef = useRef(onChange);
  const overlayOpacityRef = useRef(overlayOpacity);
  const syncDisplayRef = useRef<() => void>(() => undefined);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  const [localBrush, setLocalBrush] = useState(brushSize);
  const [localTool, setLocalTool] = useState<MaskTool>(tool);
  const [localFeather, setLocalFeather] = useState(feather);

  useEffect(() => setLocalBrush(brushSize), [brushSize]);
  useEffect(() => setLocalTool(tool), [tool]);
  useEffect(() => setLocalFeather(feather), [feather]);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);
  useEffect(() => {
    overlayOpacityRef.current = overlayOpacity;
  }, [overlayOpacity]);

  const syncDisplay = useCallback(() => {
    const maskCanvas = maskCanvasRef.current;
    const displayCanvas = displayCanvasRef.current;
    const img = imageRef.current;
    if (!maskCanvas || !displayCanvas || !img || !dims.w) return;
    const ctx = displayCanvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, dims.w, dims.h);
    ctx.drawImage(img, 0, 0, dims.w, dims.h);
    ctx.globalAlpha = overlayOpacityRef.current;
    ctx.drawImage(maskCanvas, 0, 0);
    ctx.globalAlpha = 1;
  }, [dims.w, dims.h]);
  syncDisplayRef.current = syncDisplay;

  const loadImage = useCallback(() => {
    if (!imageUrl) return;
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      imageRef.current = img;
      const maxW = containerRef.current?.clientWidth || 480;
      const maxH = containerRef.current?.clientHeight || 0;
      const scaleW = maxW / img.naturalWidth;
      const scaleH = maxH > 40 ? maxH / img.naturalHeight : 1;
      const scale = Math.min(1, scaleW, scaleH || 1);
      const w = Math.round(img.naturalWidth * scale);
      const h = Math.round(img.naturalHeight * scale);
      setDims({ w, h });
      const maskCanvas = maskCanvasRef.current;
      const displayCanvas = displayCanvasRef.current;
      if (maskCanvas && displayCanvas) {
        maskCanvas.width = w;
        maskCanvas.height = h;
        displayCanvas.width = w;
        displayCanvas.height = h;
        const mctx = maskCanvas.getContext("2d");
        if (mctx) {
          mctx.fillStyle = "#000";
          mctx.fillRect(0, 0, w, h);
        }
        syncDisplayRef.current();
        onChangeRef.current?.(false);
      }
    };
    img.src = imageUrl;
  }, [imageUrl]);

  useEffect(() => {
    loadImage();
  }, [loadImage]);

  useEffect(() => {
    syncDisplay();
  }, [syncDisplay]);

  const canvasPoint = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = displayCanvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * canvas.width,
      y: ((e.clientY - rect.top) / rect.height) * canvas.height,
    };
  };

  const paint = (x: number, y: number, erase: boolean) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = erase ? "#000" : "#fff";
    ctx.beginPath();
    ctx.arc(x, y, localBrush / 2, 0, Math.PI * 2);
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
    let outCanvas = maskCanvas;
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
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
    syncDisplay();
    onChangeRef.current?.(false);
  };

  const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!interactive) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    const pt = canvasPoint(e);
    if (localTool === "rect") {
      rectStartRef.current = pt;
    } else {
      paint(pt.x, pt.y, localTool === "erase");
    }
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!interactive || !drawingRef.current) return;
    const pt = canvasPoint(e);
    if (localTool === "rect" && rectStartRef.current) {
      syncDisplay();
      const displayCanvas = displayCanvasRef.current;
      const ctx = displayCanvas?.getContext("2d");
      const img = imageRef.current;
      if (ctx && img && rectStartRef.current) {
        ctx.clearRect(0, 0, dims.w, dims.h);
        ctx.drawImage(img, 0, 0, dims.w, dims.h);
        ctx.fillStyle = "rgba(255,255,255,0.45)";
        const x = Math.min(rectStartRef.current.x, pt.x);
        const y = Math.min(rectStartRef.current.y, pt.y);
        ctx.fillRect(x, y, Math.abs(pt.x - rectStartRef.current.x), Math.abs(pt.y - rectStartRef.current.y));
      }
    } else if (localTool !== "rect") {
      paint(pt.x, pt.y, localTool === "erase");
    }
  };

  const onPointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    if (localTool === "rect" && rectStartRef.current) {
      const pt = canvasPoint(e);
      drawRect(rectStartRef.current.x, rectStartRef.current.y, pt.x, pt.y, false);
      rectStartRef.current = null;
    }
  };

  useImperativeHandle(
    ref,
    () => ({
      exportPng: exportMask,
      clear: clearMask,
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
    [exportMask],
  );

  return (
    <div ref={containerRef} className={fill ? "image-mask-editor image-mask-editor--fill" : "image-mask-editor"}>
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
      <div className="image-mask-editor__stage">
        <canvas
          ref={displayCanvasRef}
          style={{
            maxWidth: "100%",
            maxHeight: "100%",
            borderRadius: 8,
            cursor: interactive ? "crosshair" : "default",
            touchAction: "none",
            pointerEvents: interactive ? "auto" : "none",
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        />
        <canvas ref={maskCanvasRef} style={{ display: "none" }} />
      </div>
    </div>
  );
});

ImageMaskEditor.displayName = "ImageMaskEditor";
