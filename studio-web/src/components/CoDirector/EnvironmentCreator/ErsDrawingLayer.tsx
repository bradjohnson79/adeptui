/**
 * ERS Edit drawing overlay (guidance only — never bakes into ERS unless prompt asks).
 * Tools: Pen | Line | Arrow | Rect | Ellipse | Text | Marker
 * Native-pixel coords; CSS frame matches ImageMaskEditor fit.
 */
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";

import type { DrawColor } from "./ersAnnotationPalette";

export type { DrawColor };
export type DrawTool = "pen" | "line" | "arrow" | "rect" | "ellipse" | "text" | "marker" | "select";
export type DrawThickness = "thin" | "medium" | "thick";

export type DrawVector = {
  id: string;
  type: "path" | "line" | "arrow" | "rect" | "ellipse";
  points: number[]; // flat [x,y,...] native px
  stroke: string;
  width: number;
};

export type TextLabel = {
  id: string;
  text: string;
  x: number;
  y: number;
  fontSize: number;
  color: string;
};

export type NumberedMarker = {
  id: string;
  number: number;
  x: number;
  y: number;
  label?: string;
};

export type DrawingDocument = {
  vectors: DrawVector[];
  textLabels: TextLabel[];
  numberedMarkers: NumberedMarker[];
};

export type ErsDrawingLayerHandle = {
  clear: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  getDocument: () => DrawingDocument;
  setDocument: (doc: DrawingDocument) => void;
  hasContent: () => boolean;
  /** Rasterize guidance overlay at native ERS pixels (transparent bg). */
  exportRasterPng: () => Promise<string | null>;
  exportPayload: () => {
    drawingOverlay: {
      rasterPngBase64: string | null;
      vectors: Array<{ type: string; points: number[]; stroke: string; width: number }>;
    };
    textLabels: TextLabel[];
    numberedMarkers: NumberedMarker[];
  };
};

const THICK: Record<DrawThickness, number> = { thin: 2, medium: 4, thick: 8 };

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

function emptyDoc(): DrawingDocument {
  return { vectors: [], textLabels: [], numberedMarkers: [] };
}

function cloneDoc(d: DrawingDocument): DrawingDocument {
  return JSON.parse(JSON.stringify(d)) as DrawingDocument;
}

type Props = {
  naturalWidth: number;
  naturalHeight: number;
  tool: DrawTool;
  color: DrawColor;
  thickness: DrawThickness;
  visible?: boolean;
  locked?: boolean;
  interactive?: boolean;
  onChange?: (hasContent: boolean) => void;
  onHistoryChange?: () => void;
};

export const ErsDrawingLayer = forwardRef<ErsDrawingLayerHandle, Props>(function ErsDrawingLayer(
  {
    naturalWidth,
    naturalHeight,
    tool,
    color,
    thickness,
    visible = true,
    locked = false,
    interactive = true,
    onChange,
    onHistoryChange,
  },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const liveCanvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [doc, setDoc] = useState<DrawingDocument>(() => emptyDoc());
  const docRef = useRef(doc);
  const undoStack = useRef<DrawingDocument[]>([]);
  const redoStack = useRef<DrawingDocument[]>([]);
  const drawing = useRef(false);
  const draftPts = useRef<number[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const dragRef = useRef<{ id: string; kind: "text" | "marker" | "vector"; ox: number; oy: number } | null>(null);

  useEffect(() => {
    docRef.current = doc;
  }, [doc]);

  const strokeW = THICK[thickness];

  const pushHistory = useCallback(() => {
    undoStack.current.push(cloneDoc(docRef.current));
    if (undoStack.current.length > 40) undoStack.current.shift();
    redoStack.current = [];
  }, []);

  const notify = useCallback(
    (next: DrawingDocument) => {
      const has =
        next.vectors.length > 0 || next.textLabels.length > 0 || next.numberedMarkers.length > 0;
      onChange?.(has);
      onHistoryChange?.();
    },
    [onChange, onHistoryChange],
  );

  const toNative = (e: React.PointerEvent) => {
    const el = wrapRef.current;
    if (!el || !naturalWidth || !naturalHeight) return { x: 0, y: 0 };
    const r = el.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) / Math.max(1, r.width)) * naturalWidth,
      y: ((e.clientY - r.top) / Math.max(1, r.height)) * naturalHeight,
    };
  };

  const ensureBitmap = (canvas: HTMLCanvasElement | null) => {
    if (!canvas || !naturalWidth || !naturalHeight) return null;
    if (canvas.width !== naturalWidth || canvas.height !== naturalHeight) {
      canvas.width = naturalWidth;
      canvas.height = naturalHeight;
    }
    return canvas.getContext("2d");
  };

  const drawVec = (ctx: CanvasRenderingContext2D, v: DrawVector, alpha = 1) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = v.stroke;
    ctx.fillStyle = v.stroke;
    ctx.lineWidth = v.width;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const pts = v.points;
    if (v.type === "path" && pts.length >= 4) {
      ctx.beginPath();
      ctx.moveTo(pts[0], pts[1]);
      for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
      ctx.stroke();
    } else if ((v.type === "line" || v.type === "arrow") && pts.length >= 4) {
      const [x0, y0, x1, y1] = pts;
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      if (v.type === "arrow") {
        const ang = Math.atan2(y1 - y0, x1 - x0);
        const head = 12 + v.width * 2;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x1 - head * Math.cos(ang - 0.4), y1 - head * Math.sin(ang - 0.4));
        ctx.lineTo(x1 - head * Math.cos(ang + 0.4), y1 - head * Math.sin(ang + 0.4));
        ctx.closePath();
        ctx.fill();
      }
    } else if (v.type === "rect" && pts.length >= 4) {
      const x = Math.min(pts[0], pts[2]);
      const y = Math.min(pts[1], pts[3]);
      const w = Math.abs(pts[2] - pts[0]);
      const h = Math.abs(pts[3] - pts[1]);
      ctx.strokeRect(x, y, w, h);
    } else if (v.type === "ellipse" && pts.length >= 4) {
      const cx = (pts[0] + pts[2]) / 2;
      const cy = (pts[1] + pts[3]) / 2;
      const rx = Math.abs(pts[2] - pts[0]) / 2;
      const ry = Math.abs(pts[3] - pts[1]) / 2;
      ctx.beginPath();
      ctx.ellipse(cx, cy, Math.max(1, rx), Math.max(1, ry), 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  };

  const paintCommitted = useCallback(() => {
    const ctx = ensureBitmap(canvasRef.current);
    if (!ctx || !naturalWidth || !naturalHeight) return;
    ctx.clearRect(0, 0, naturalWidth, naturalHeight);
    if (!visible) return;
    const current = docRef.current;
    for (const v of current.vectors) drawVec(ctx, v);
    for (const t of current.textLabels) {
      ctx.save();
      ctx.fillStyle = t.color;
      ctx.font = `${t.fontSize}px system-ui, Segoe UI, sans-serif`;
      ctx.textBaseline = "top";
      ctx.fillText(t.text || "Text", t.x, t.y);
      ctx.restore();
    }
    for (const m of current.numberedMarkers) {
      const r = 14;
      ctx.save();
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      ctx.arc(m.x, m.y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 14px system-ui, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(m.number), m.x, m.y);
      ctx.restore();
    }
  }, [naturalHeight, naturalWidth, visible]);

  const paintLive = useCallback(() => {
    const ctx = ensureBitmap(liveCanvasRef.current);
    if (!ctx || !naturalWidth || !naturalHeight) return;
    ctx.clearRect(0, 0, naturalWidth, naturalHeight);
    if (!visible || draftPts.current.length < 2) return;
    const draft: DrawVector = {
      id: "draft",
      type:
        tool === "pen"
          ? "path"
          : tool === "line"
            ? "line"
            : tool === "arrow"
              ? "arrow"
              : tool === "ellipse"
                ? "ellipse"
                : "rect",
      points: draftPts.current,
      stroke: color,
      width: strokeW,
    };
    if (tool === "pen" || tool === "line" || tool === "arrow" || tool === "rect" || tool === "ellipse") {
      drawVec(ctx, draft, 0.85);
    }
  }, [color, naturalHeight, naturalWidth, strokeW, tool, visible]);

  const paint = useCallback(() => {
    paintCommitted();
    paintLive();
  }, [paintCommitted, paintLive]);

  useEffect(() => {
    paintCommitted();
  }, [doc, paintCommitted]);

  const commitDoc = (next: DrawingDocument) => {
    setDoc(next);
    docRef.current = next;
    notify(next);
    paint();
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!interactive || locked || !visible) return;
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    const pt = toNative(e);

    if (tool === "text") {
      const text = window.prompt("Label text", "Label");
      if (text == null) return;
      pushHistory();
      const next = cloneDoc(docRef.current);
      next.textLabels.push({
        id: uid("t"),
        text: text.trim() || "Label",
        x: pt.x,
        y: pt.y,
        fontSize: 28,
        color,
      });
      commitDoc(next);
      return;
    }

    if (tool === "marker") {
      pushHistory();
      const next = cloneDoc(docRef.current);
      const number = next.numberedMarkers.length + 1;
      next.numberedMarkers.push({ id: uid("m"), number, x: pt.x, y: pt.y });
      // renumber
      next.numberedMarkers.forEach((m, i) => {
        m.number = i + 1;
      });
      commitDoc(next);
      return;
    }

    if (tool === "select") {
      // hit-test markers/texts roughly
      const hitT = [...docRef.current.textLabels].reverse().find((t) => {
        return pt.x >= t.x - 4 && pt.x <= t.x + Math.max(40, t.text.length * t.fontSize * 0.55) && pt.y >= t.y - 4 && pt.y <= t.y + t.fontSize + 8;
      });
      if (hitT) {
        pushHistory();
        docRef.current = cloneDoc(docRef.current);
        setSelectedId(hitT.id);
        dragRef.current = { id: hitT.id, kind: "text", ox: pt.x - hitT.x, oy: pt.y - hitT.y };
        drawing.current = true;
        return;
      }
      const hitM = [...docRef.current.numberedMarkers].reverse().find((m) => {
        const dx = pt.x - m.x;
        const dy = pt.y - m.y;
        return dx * dx + dy * dy <= 18 * 18;
      });
      if (hitM) {
        pushHistory();
        docRef.current = cloneDoc(docRef.current);
        setSelectedId(hitM.id);
        dragRef.current = { id: hitM.id, kind: "marker", ox: pt.x - hitM.x, oy: pt.y - hitM.y };
        drawing.current = true;
        return;
      }
      setSelectedId(null);
      return;
    }

    drawing.current = true;
    pushHistory();
    draftPts.current = [pt.x, pt.y];
    paintLive();
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing.current) return;
    e.preventDefault();
    e.stopPropagation();
    const pt = toNative(e);
    if (tool === "select" && dragRef.current) {
      const next = docRef.current;
      if (dragRef.current.kind === "text") {
        const t = next.textLabels.find((x) => x.id === dragRef.current!.id);
        if (t) {
          t.x = pt.x - dragRef.current.ox;
          t.y = pt.y - dragRef.current.oy;
        }
      } else if (dragRef.current.kind === "marker") {
        const m = next.numberedMarkers.find((x) => x.id === dragRef.current!.id);
        if (m) {
          m.x = pt.x - dragRef.current.ox;
          m.y = pt.y - dragRef.current.oy;
        }
      }
      paintCommitted();
      return;
    }
    if (tool === "pen") {
      draftPts.current.push(pt.x, pt.y);
    } else if (tool === "line" || tool === "arrow" || tool === "rect" || tool === "ellipse") {
      if (draftPts.current.length >= 2) {
        draftPts.current = [draftPts.current[0], draftPts.current[1], pt.x, pt.y];
      }
    }
    paintLive();
  };

  const onPointerUp = () => {
    if (!drawing.current) return;
    drawing.current = false;
    if (tool === "select") {
      dragRef.current = null;
      const next = docRef.current;
      setDoc(next);
      notify(next);
      return;
    }
    const pts = draftPts.current;
    draftPts.current = [];
    paintLive();
    if (pts.length < 4 && tool !== "pen") {
      paint();
      return;
    }
    if (tool === "pen" && pts.length < 4) {
      paint();
      return;
    }
    const type: DrawVector["type"] =
      tool === "pen" ? "path" : tool === "line" ? "line" : tool === "arrow" ? "arrow" : tool === "ellipse" ? "ellipse" : "rect";
    const next = cloneDoc(docRef.current);
    next.vectors.push({ id: uid("v"), type, points: pts, stroke: color, width: strokeW });
    commitDoc(next);
  };

  const clear = () => {
    pushHistory();
    commitDoc(emptyDoc());
    setSelectedId(null);
  };

  const undo = () => {
    const prev = undoStack.current.pop();
    if (!prev) return;
    redoStack.current.push(cloneDoc(docRef.current));
    commitDoc(prev);
  };

  const redo = () => {
    const nxt = redoStack.current.pop();
    if (!nxt) return;
    undoStack.current.push(cloneDoc(docRef.current));
    commitDoc(nxt);
  };

  const exportRasterPng = useCallback(async () => {
    if (!naturalWidth || !naturalHeight) return null;
    const d = docRef.current;
    if (!d.vectors.length && !d.textLabels.length && !d.numberedMarkers.length) return null;
    const c = document.createElement("canvas");
    c.width = naturalWidth;
    c.height = naturalHeight;
    const ctx = c.getContext("2d");
    if (!ctx) return null;
    // temporarily paint via cloning current canvas content
    const src = canvasRef.current;
    if (src) ctx.drawImage(src, 0, 0);
    // ensure labels/markers drawn (canvas already has them from paint)
    return c.toDataURL("image/png").replace(/^data:image\/png;base64,/, "");
  }, [naturalHeight, naturalWidth]);

  useImperativeHandle(
    ref,
    () => ({
      clear,
      undo,
      redo,
      canUndo: () => undoStack.current.length > 0,
      canRedo: () => redoStack.current.length > 0,
      getDocument: () => cloneDoc(docRef.current),
      setDocument: (d) => {
        commitDoc(cloneDoc(d));
      },
      hasContent: () => {
        const d = docRef.current;
        return d.vectors.length > 0 || d.textLabels.length > 0 || d.numberedMarkers.length > 0;
      },
      exportRasterPng,
      exportPayload: () => {
        const d = docRef.current;
        return {
          drawingOverlay: {
            rasterPngBase64: null, // filled async by caller via exportRasterPng
            vectors: d.vectors.map((v) => ({
              type: v.type,
              points: v.points,
              stroke: v.stroke,
              width: v.width,
            })),
          },
          textLabels: d.textLabels.map((t) => ({ ...t })),
          numberedMarkers: d.numberedMarkers.map((m) => ({ ...m })),
        };
      },
    }),
    [exportRasterPng],
  );

  // Delete selected
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!interactive || locked) return;
      if ((e.key === "Delete" || e.key === "Backspace") && selectedId) {
        pushHistory();
        const next = cloneDoc(docRef.current);
        next.textLabels = next.textLabels.filter((t) => t.id !== selectedId);
        next.numberedMarkers = next.numberedMarkers.filter((m) => m.id !== selectedId);
        next.numberedMarkers.forEach((m, i) => {
          m.number = i + 1;
        });
        next.vectors = next.vectors.filter((v) => v.id !== selectedId);
        setSelectedId(null);
        commitDoc(next);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [interactive, locked, selectedId, pushHistory]);

  const cursor = useMemo(() => {
    if (!interactive || locked) return "default";
    if (tool === "text") return "text";
    if (tool === "select") return "move";
    if (tool === "marker") return "pointer";
    return "crosshair";
  }, [interactive, locked, tool]);

  const canvasStyle = {
    position: "absolute" as const,
    inset: 0,
    width: "100%",
    height: "100%",
    maxWidth: "100%",
    maxHeight: "100%",
    display: "block",
    pointerEvents: "none" as const,
  };

  return (
    <div
      ref={wrapRef}
      data-testid="ers-drawing-layer"
      data-visible={visible ? "true" : "false"}
      style={{
        position: "absolute",
        inset: 0,
        opacity: visible ? 1 : 0,
        cursor,
        touchAction: "none",
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <canvas
        ref={canvasRef}
        data-testid="ers-drawing-committed"
        style={canvasStyle}
      />
      <canvas
        ref={liveCanvasRef}
        data-testid="ers-drawing-live"
        style={canvasStyle}
      />
    </div>
  );
});

ErsDrawingLayer.displayName = "ErsDrawingLayer";
