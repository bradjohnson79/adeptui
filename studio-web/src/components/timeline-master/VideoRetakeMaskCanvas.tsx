import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import { mediaContainRect } from "../../timelineMaster/videoRetake";

export type VideoRetakeMaskHandle = {
  exportPng: () => Promise<string>;
  importPng: (pngBase64: string) => void;
  clear: () => void;
  hasPaint: () => boolean;
  captureFrame: () => Promise<Blob | null>;
};

export const VideoRetakeMaskCanvas = forwardRef<
  VideoRetakeMaskHandle,
  {
    video: HTMLVideoElement | null;
    tool: "idle" | "brush" | "erase";
    brushSize: number;
    interactive: boolean;
    onChange?: (hasMask: boolean) => void;
  }
>(function VideoRetakeMaskCanvas({ video, tool, brushSize, interactive, onChange }, ref) {
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const maskRef = useRef<HTMLCanvasElement>(document.createElement("canvas"));
  const drawingRef = useRef(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const syncOverlay = useCallback(() => {
    const overlay = overlayRef.current;
    const mask = maskRef.current;
    if (!overlay || !video) return;
    const parent = overlay.parentElement;
    if (!parent) return;
    const cw = parent.clientWidth;
    const ch = parent.clientHeight;
    if (overlay.width !== cw) overlay.width = cw;
    if (overlay.height !== ch) overlay.height = ch;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cw, ch);
    const mw = video.videoWidth || 0;
    const mh = video.videoHeight || 0;
    if (mw < 2 || mh < 2 || !mask.width) return;
    const rect = mediaContainRect(cw, ch, mw, mh);
    ctx.globalAlpha = 0.42;
    ctx.drawImage(mask, rect.x, rect.y, rect.w, rect.h);
    ctx.globalAlpha = 1;
  }, [video]);

  const ensureMaskSize = useCallback(() => {
    if (!video) return;
    const mw = video.videoWidth || 0;
    const mh = video.videoHeight || 0;
    if (mw < 2 || mh < 2) return;
    const mask = maskRef.current;
    if (mask.width !== mw || mask.height !== mh) {
      mask.width = mw;
      mask.height = mh;
      const ctx = mask.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, mw, mh);
      }
      onChangeRef.current?.(false);
    }
    syncOverlay();
  }, [syncOverlay, video]);

  useEffect(() => {
    ensureMaskSize();
    const onMeta = () => ensureMaskSize();
    video?.addEventListener("loadedmetadata", onMeta);
    window.addEventListener("resize", syncOverlay);
    return () => {
      video?.removeEventListener("loadedmetadata", onMeta);
      window.removeEventListener("resize", syncOverlay);
    };
  }, [ensureMaskSize, syncOverlay, video]);

  const pointOnMask = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!video || !overlayRef.current) return null;
    const overlay = overlayRef.current;
    const rect = overlay.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const media = mediaContainRect(overlay.width, overlay.height, video.videoWidth, video.videoHeight);
    if (x < media.x || y < media.y || x > media.x + media.w || y > media.y + media.h) return null;
    return {
      x: ((x - media.x) / media.w) * maskRef.current.width,
      y: ((y - media.y) / media.h) * maskRef.current.height,
    };
  };

  const paint = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!interactive || tool === "idle") return;
    const pt = pointOnMask(event);
    if (!pt) return;
    const ctx = maskRef.current.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = tool === "erase" ? "#000" : "#fff";
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, brushSize / 2, 0, Math.PI * 2);
    ctx.fill();
    syncOverlay();
    onChangeRef.current?.(true);
  };

  useImperativeHandle(
    ref,
    () => ({
      exportPng: async () => {
        const mask = maskRef.current;
        if (!mask.width) return "";
        return mask.toDataURL("image/png").replace(/^data:image\/png;base64,/, "");
      },
      importPng: (pngBase64: string) => {
        const img = new Image();
        img.onload = () => {
          ensureMaskSize();
          const ctx = maskRef.current.getContext("2d");
          if (!ctx) return;
          ctx.fillStyle = "#000";
          ctx.fillRect(0, 0, maskRef.current.width, maskRef.current.height);
          ctx.drawImage(img, 0, 0, maskRef.current.width, maskRef.current.height);
          syncOverlay();
          onChangeRef.current?.(true);
        };
        img.src = pngBase64.startsWith("data:") ? pngBase64 : `data:image/png;base64,${pngBase64}`;
      },
      clear: () => {
        const ctx = maskRef.current.getContext("2d");
        if (!ctx || !maskRef.current.width) return;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, maskRef.current.width, maskRef.current.height);
        syncOverlay();
        onChangeRef.current?.(false);
      },
      hasPaint: () => {
        const mask = maskRef.current;
        if (!mask.width) return false;
        const ctx = mask.getContext("2d");
        if (!ctx) return false;
        const data = ctx.getImageData(0, 0, mask.width, mask.height).data;
        for (let i = 0; i < data.length; i += 4) {
          if (data[i] >= 128) return true;
        }
        return false;
      },
      captureFrame: async () => {
        if (!video || video.videoWidth < 2) return null;
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) return null;
        ctx.drawImage(video, 0, 0);
        return await new Promise<Blob | null>((resolve) => {
          canvas.toBlob((blob) => resolve(blob), "image/png");
        });
      },
    }),
    [ensureMaskSize, syncOverlay, video],
  );

  if (!video) return null;

  return (
    <canvas
      ref={overlayRef}
      className="timeline-retake-mask-canvas"
      data-testid="timeline-retake-mask-canvas"
      onPointerDown={(event) => {
        if (!interactive || tool === "idle") return;
        event.preventDefault();
        event.stopPropagation();
        drawingRef.current = true;
        event.currentTarget.setPointerCapture(event.pointerId);
        paint(event);
      }}
      onPointerMove={(event) => {
        if (!drawingRef.current) return;
        paint(event);
      }}
      onPointerUp={() => {
        drawingRef.current = false;
      }}
      onPointerLeave={() => {
        drawingRef.current = false;
      }}
      style={{
        cursor: interactive && tool !== "idle" ? "crosshair" : "default",
        pointerEvents: interactive && tool !== "idle" ? "auto" : "none",
      }}
    />
  );
});

VideoRetakeMaskCanvas.displayName = "VideoRetakeMaskCanvas";
