/**
 * SpatialGrid — two independent layers on one rectangular production surface.
 *
 *   RECTANGULAR WORKSPACE / VIEWPORT
 *     + Spatial Map image layer (native aspect, Freehand, Resize)
 *     + Canonical placement-grid layer (square world, circle-in-square cells)
 *
 * Circular viewport / picture clip is retired. Circle-in-square cell display
 * is required. Alignment moves only the Atlas. Placements stay in world coords.
 * Workspace zoom sizes the production rectangle; it is not map calibration.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CameraFovCone } from "./CameraFovCone";
import { CameraMarker } from "./CameraMarker";
import {
  CARDINAL_LABELS,
  cellCenterNormalized,
  clientToSlicedSquareViewBox,
  viewBoxToLocalCss,
  densityForScale,
  isValidCell,
  normalizedToPixel,
  pointerToCell,
  type GridScale,
} from "./gridGeometry";
import {
  attachedBadgeFor,
  formatCharacterAttachmentTooltip,
  isAttachedProp,
  visibleAttachedPropsForCharacter,
  type AttachedBadge,
} from "./attachmentUi";
import {
  alignmentFromOppositeAnchorResize,
  alignmentFromPixelPair,
  containRect,
  hydrateAlignment,
  imageCorners,
  pixelsFromAlignment,
  sourceAspect,
  transformPoint,
  transformedImageBounds,
  type BackgroundAlignment,
  type ResizeCorner,
} from "./backgroundAlignment";
import {
  displayedAtlasRect,
  viewBoxToSourcePixel,
} from "./correctArea";
import { SLOT_COLORS } from "./types";
import type { CameraMovementArrow } from "./cameraMovementPath";
import { cameraFollowSubjectId, resolveCameraAttachMode, resolvePovCameraScrubPosition } from "./cameraMovementPath";
import { worldMetersToNormalized } from "./spinCameraGeometry";
import type { MovementArrow, SpatialCamera, SpatialCharacterPlacement, SpatialPropPlacement, SlotColorKey, SpinCameraPlacement } from "./types";

export type GridPlacement = {
  id: string;
  tag: string;
  colorKey: SlotColorKey;
  gridRow: number;
  gridColumn: number;
  normalizedX?: number | null;
  normalizedY?: number | null;
  slotIndex: number;
  kind: "character" | "prop";
  label?: string;
  visible?: boolean;
  attachedBadge?: AttachedBadge | null;
  tooltip?: string;
};

type Props = {
  backgroundAssetId: string;
  imageUrl: string;
  placements: GridPlacement[];
  cameras: SpatialCamera[];
  widthMeters?: number;
  depthMeters?: number;
  movementArrows?: MovementArrow[];
  cameraMovementArrows?: CameraMovementArrow[];
  /** Active movement alias (M1/M2/…) — camera glyph: free uses saved pose; POV attaches to character. */
  activeMovementAlias?: string | null;
  spinCamera?: SpinCameraPlacement | null;
  selectedSpinCamera?: boolean;
  selectedPlacementId: string | null;
  selectedCameraId: string | null;
  occupiedMessage: string | null;
  gridScale: GridScale;
  placementActive: boolean;
  showGrid?: boolean;
  showCircles?: boolean;
  showLabels?: boolean;
  zoom?: number;
  ghostColor?: string;
  alignment?: BackgroundAlignment;
  handActive?: boolean;
  resizeActive?: boolean;
  onAlignmentChange?: (next: BackgroundAlignment) => void;
  onAlignmentCommit?: (next: BackgroundAlignment) => void;
  onSourceMeasured?: (width: number, height: number) => void;
  onCellClick: (column: number, row: number) => void;
  onSelectPlacement: (placementId: string | null) => void;
  onSelectCamera: (cameraId: string | null) => void;
  onSelectSpinCamera?: () => void;
  /**
   * Correct Area / Inpaint overlay. When present, SpatialGrid renders the SAME
   * atlas image + transform (single viewport authority) and paints a
   * source-pixel-resolution mask directly on the displayed atlas rect. The
   * parent (CorrectAreaPanel) supplies tool state + callbacks; SpatialGrid owns
   * the canvas and the viewBox→source-pixel mapping so parity is structural.
   */
  maskEditor?: MaskEditorOverlayProps;
};

export type MaskEditorTool = "brush" | "erase" | "rect";

export type MaskEditorOverlayProps = {
  active: boolean;
  tool: MaskEditorTool;
  brushSize: number;
  /** 0..1 overlay opacity of the painted mask over the atlas. */
  overlayOpacity?: number;
  /** Register an imperative handle so the parent can export/clear/restore. */
  registerHandle?: (handle: SpatialMaskHandle | null) => void;
  onChange?: (hasMask: boolean) => void;
};

export type SpatialMaskHandle = {
  /** Mask PNG (base64, no data: prefix) at SOURCE natural resolution. */
  exportPng: () => Promise<string>;
  clear: () => void;
  /** Restore a source-resolution mask PNG (base64 or data URL). */
  restorePng: (pngBase64: string) => Promise<void>;
  /** Natural source pixel size the mask is authored at. */
  getSourceSize: () => { width: number; height: number };
  measureCoverage: () => number;
};

export function toGridPlacements(
  characters: SpatialCharacterPlacement[],
  props: SpatialPropPlacement[],
): GridPlacement[] {
  const independentProps = props.filter((p) => !isAttachedProp(p));
  return [
    ...characters.map((c) => {
      const visibleAttached = visibleAttachedPropsForCharacter(c, props);
      return {
        id: c.id,
        tag: c.tag || c.label,
        colorKey: (c.colorKey as SlotColorKey) || "red",
        gridRow: c.gridRow,
        gridColumn: c.gridColumn,
        normalizedX: c.normalizedX,
        normalizedY: c.normalizedY,
        slotIndex: c.slotIndex,
        kind: "character" as const,
        label: c.label || c.tag,
        visible: c.visible,
        attachedBadge: attachedBadgeFor(visibleAttached),
        tooltip: formatCharacterAttachmentTooltip(c, visibleAttached),
      };
    }),
    ...independentProps.map((p) => ({
      id: p.id,
      tag: p.tag || p.label,
      colorKey: (p.colorKey as SlotColorKey) || "purple",
      gridRow: p.gridRow,
      gridColumn: p.gridColumn,
      normalizedX: p.normalizedX,
      normalizedY: p.normalizedY,
      slotIndex: p.slotIndex,
      kind: "prop" as const,
      label: p.label || p.tag,
      visible: p.visible,
    })),
  ];
}

function markerPosition(
  gridColumn: number,
  gridRow: number,
  normalizedX: number | null | undefined,
  normalizedY: number | null | undefined,
  density: number,
  size: number,
): { px: number; py: number } | null {
  if (typeof normalizedX === "number" && typeof normalizedY === "number") {
    return normalizedToPixel(normalizedX, normalizedY, size);
  }
  if (gridColumn >= 0 && gridRow >= 0 && isValidCell(gridColumn, gridRow, density)) {
    const center = cellCenterNormalized(gridColumn, gridRow, density);
    return normalizedToPixel(center.x, center.y, size);
  }
  return null;
}

function markerModifier(kind: "character" | "prop", slotIndex: number): string {
  if (kind === "prop") return " spatial-map__marker--prop";
  const n = Math.min(4, Math.max(1, slotIndex + 1));
  return ` spatial-map__marker--c${n}`;
}

function spinCameraPixelPosition(
  spinCamera: SpinCameraPlacement | null | undefined,
  widthMeters: number,
  depthMeters: number,
  size: number,
): { px: number; py: number } | null {
  if (!spinCamera) return null;
  const norm = worldMetersToNormalized(spinCamera.x, spinCamera.z, widthMeters, depthMeters);
  return normalizedToPixel(norm.normalizedX, norm.normalizedY, size);
}

export function SpatialGrid({
  imageUrl,
  placements,
  cameras,
  widthMeters = 10,
  depthMeters = 10,
  movementArrows = [],
  cameraMovementArrows = [],
  activeMovementAlias = null,
  spinCamera = null,
  selectedSpinCamera = false,
  selectedPlacementId,
  selectedCameraId,
  occupiedMessage,
  gridScale,
  placementActive,
  showGrid = true,
  showCircles = true,
  showLabels = true,
  zoom = 1,
  ghostColor,
  alignment,
  handActive = false,
  resizeActive = false,
  onAlignmentChange,
  onAlignmentCommit,
  onSourceMeasured,
  onCellClick,
  onSelectPlacement,
  onSelectCamera,
  onSelectSpinCamera,
  maskEditor,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [viewportBox, setViewportBox] = useState({ w: 512, h: 512 });
  const size = Math.max(1, Math.min(viewportBox.w, viewportBox.h));
  const [hover, setHover] = useState<{ column: number; row: number } | null>(null);
  const [handDragging, setHandDragging] = useState(false);
  const [resizeDragging, setResizeDragging] = useState(false);
  const [mapSelected, setMapSelected] = useState(false);
  const liveAlignment = hydrateAlignment(alignment);
  const alignmentRef = useRef(liveAlignment);
  alignmentRef.current = liveAlignment;
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    originScale: number;
    moved: boolean;
  } | null>(null);
  const resizeDragRef = useRef<{
    pointerId: number;
    corner: ResizeCorner;
    origin: BackgroundAlignment;
  } | null>(null);
  const unbindWindowDragRef = useRef<(() => void) | null>(null);
  const offsetPx = pixelsFromAlignment(liveAlignment.offsetX, size);
  const offsetPy = pixelsFromAlignment(liveAlignment.offsetY, size);
  const scale = liveAlignment.scale;
  const cx = size / 2;
  const cy = size / 2;
  const [measuredSource, setMeasuredSource] = useState<{ w: number; h: number } | null>(null);
  const sourceWidth = measuredSource?.w || liveAlignment.sourceWidth;
  const sourceHeight = measuredSource?.h || liveAlignment.sourceHeight;
  const aspect = sourceWidth > 0 && sourceHeight > 0
    ? sourceAspect(sourceWidth, sourceHeight)
    : liveAlignment.sourceAspectRatio || 1;
  const imageBox = containRect(size, aspect);

  /* —— Correct Area / Inpaint shared-viewport mask overlay ————————————————
   * The mask canvas is authored at SOURCE natural resolution and painted via
   * the SAME viewBox→source transform the atlas <image> uses, so parity is
   * structural (no separate zoom/pan/fit). We never re-render the map. */
  const maskActive = !!maskEditor?.active && sourceWidth > 0 && sourceHeight > 0;
  const maskCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const maskDrawingRef = useRef(false);
  const maskRectStartRef = useRef<{ x: number; y: number } | null>(null);
  const maskHasPaintRef = useRef(false);
  const maskOnChangeRef = useRef(maskEditor?.onChange);
  const maskOverlayOpacityRef = useRef(maskEditor?.overlayOpacity ?? 0.45);
  const maskToolRef = useRef<MaskEditorTool>(maskEditor?.tool ?? "brush");
  const maskBrushRef = useRef(maskEditor?.brushSize ?? 28);
  const maskRegisterRef = useRef(maskEditor?.registerHandle);
  const maskSourceRef = useRef({ w: sourceWidth, h: sourceHeight });
  const [maskCompositeTick, setMaskCompositeTick] = useState(0);
  useEffect(() => { maskOnChangeRef.current = maskEditor?.onChange; }, [maskEditor?.onChange]);
  useEffect(() => { maskOverlayOpacityRef.current = maskEditor?.overlayOpacity ?? 0.45; }, [maskEditor?.overlayOpacity]);
  useEffect(() => { maskToolRef.current = maskEditor?.tool ?? "brush"; }, [maskEditor?.tool]);
  useEffect(() => { maskBrushRef.current = maskEditor?.brushSize ?? 28; }, [maskEditor?.brushSize]);
  useEffect(() => { maskRegisterRef.current = maskEditor?.registerHandle; }, [maskEditor?.registerHandle]);
  useEffect(() => {
    if (sourceWidth > 0 && sourceHeight > 0) maskSourceRef.current = { w: sourceWidth, h: sourceHeight };
  }, [sourceWidth, sourceHeight]);

  useEffect(() => {
    if (handActive || resizeActive) setMapSelected(true);
  }, [handActive, resizeActive]);

  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        const h = entry.contentRect.height;
        if (w > 0 && h > 0) setViewportBox({ w, h });
      }
    });
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  /* Allocate the source-resolution mask canvas once source dims are known.
   * Black = preserve, white = edit. Never rescaled by zoom/pan. */
  useEffect(() => {
    if (!maskActive) return;
    const canvas = maskCanvasRef.current;
    const { w, h } = maskSourceRef.current;
    if (!canvas || !(w > 0) || !(h > 0)) return;
    if (canvas.width === w && canvas.height === h) return;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, w, h);
    }
    maskHasPaintRef.current = false;
    setMaskCompositeTick((t) => t + 1);
  }, [maskActive, sourceWidth, sourceHeight]);

  const maskPaint = useCallback((srcX: number, srcY: number, erase: boolean) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    const { w } = maskSourceRef.current;
    // Brush radius is specified in source px relative to a 512-px reference
    // viewport; scale by source width so strokes feel identical at any source res.
    const radius = Math.max(1, (maskBrushRef.current / 2) * (w / 512));
    ctx.fillStyle = erase ? "#000" : "#fff";
    ctx.beginPath();
    ctx.arc(srcX, srcY, radius, 0, Math.PI * 2);
    ctx.fill();
    maskHasPaintRef.current = true;
    setMaskCompositeTick((t) => t + 1);
    maskOnChangeRef.current?.(true);
  }, []);

  const maskDrawRect = useCallback((x0: number, y0: number, x1: number, y1: number, erase: boolean) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = erase ? "#000" : "#fff";
    const x = Math.min(x0, x1);
    const y = Math.min(y0, y1);
    ctx.fillRect(x, y, Math.abs(x1 - x0), Math.abs(y1 - y0));
    maskHasPaintRef.current = true;
    setMaskCompositeTick((t) => t + 1);
    maskOnChangeRef.current?.(true);
  }, []);

  const maskClear = useCallback(() => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas) return;
    const ctx = maskCanvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
    maskHasPaintRef.current = false;
    setMaskCompositeTick((t) => t + 1);
    maskOnChangeRef.current?.(false);
  }, []);

  const maskExportPng = useCallback(async (): Promise<string> => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas || !maskCanvas.width) return "";
    const dataUrl = maskCanvas.toDataURL("image/png");
    return dataUrl.replace(/^data:image\/png;base64,/, "");
  }, []);

  const maskRestorePng = useCallback(async (pngBase64: string) => {
    const maskCanvas = maskCanvasRef.current;
    if (!maskCanvas || !maskCanvas.width) return;
    const raw = (pngBase64 || "").trim();
    if (!raw) return;
    const src = raw.startsWith("data:") ? raw : `data:image/png;base64,${raw}`;
    await new Promise<void>((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const ctx = maskCanvas.getContext("2d");
        if (!ctx) { reject(new Error("mask ctx missing")); return; }
        ctx.imageSmoothingEnabled = false;
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
        ctx.drawImage(img, 0, 0, maskCanvas.width, maskCanvas.height);
        maskHasPaintRef.current = true;
        setMaskCompositeTick((t) => t + 1);
        maskOnChangeRef.current?.(true);
        resolve();
      };
      img.onerror = () => reject(new Error("Failed to restore mask PNG"));
      img.src = src;
    });
  }, []);

  const maskMeasureCoverage = useCallback(() => {
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
  }, []);

  /* Register the imperative handle for CorrectAreaPanel. */
  useEffect(() => {
    if (!maskActive) {
      maskRegisterRef.current?.(null);
      return;
    }
    maskRegisterRef.current?.({
      exportPng: maskExportPng,
      clear: maskClear,
      restorePng: maskRestorePng,
      getSourceSize: () => ({ width: maskSourceRef.current.w, height: maskSourceRef.current.h }),
      measureCoverage: maskMeasureCoverage,
    });
    return () => maskRegisterRef.current?.(null);
  }, [maskActive, maskExportPng, maskClear, maskRestorePng, maskMeasureCoverage, maskCompositeTick]);

  useEffect(() => {
    setMeasuredSource(null);
    if (!imageUrl) return;
    let cancelled = false;
    const probe = new Image();
    probe.onload = () => {
      if (cancelled) return;
      const w = probe.naturalWidth;
      const h = probe.naturalHeight;
      if (w <= 0 || h <= 0) return;
      setMeasuredSource({ w, h });
      onSourceMeasured?.(w, h);
    };
    probe.src = imageUrl;
    return () => {
      cancelled = true;
    };
  }, [imageUrl, onSourceMeasured]);

  const density = densityForScale(gridScale);
  const cellPx = size / density;
  const cellCircleR = cellPx * 0.4;
  const markerR = cellCircleR * 0.72;
  const cameraSize = Math.max(10, Math.round(markerR * 2 * 0.68));

  const gridPath = useMemo(() => {
    const parts: string[] = [];
    for (let i = 0; i <= density; i += 1) {
      const pos = (i / density) * size;
      parts.push(`M 0 ${pos} H ${size}`);
      parts.push(`M ${pos} 0 V ${size}`);
    }
    return parts.join(" ");
  }, [density, size]);

  const validCells = useMemo(() => {
    const cells: Array<{ column: number; row: number; px: number; py: number }> = [];
    for (let row = 0; row < density; row += 1) {
      for (let column = 0; column < density; column += 1) {
        if (!isValidCell(column, row, density)) continue;
        const mid = cellCenterNormalized(column, row, density);
        const pix = normalizedToPixel(mid.x, mid.y, size);
        cells.push({ column, row, px: pix.px, py: pix.py });
      }
    }
    return cells;
  }, [density, size]);

  const pointerToViewBox = useCallback(
    (clientX: number, clientY: number) => {
      const el = viewportRef.current || containerRef.current;
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return clientToSlicedSquareViewBox(clientX, clientY, rect, size);
    },
    [size],
  );

  const handlePointer = useCallback(
    (clientX: number, clientY: number) => {
      const point = pointerToViewBox(clientX, clientY);
      if (!point) return null;
      return pointerToCell(point.x, point.y, size, density);
    },
    [density, pointerToViewBox, size],
  );

  const isImageHit = useCallback(
    (clientX: number, clientY: number) => {
      const point = pointerToViewBox(clientX, clientY);
      if (!point) return false;
      const bounds = transformedImageBounds(imageBox, size, alignmentRef.current);
      const pad = 4;
      return (
        point.x >= bounds.x - pad
        && point.x <= bounds.x + bounds.w + pad
        && point.y >= bounds.y - pad
        && point.y <= bounds.y + bounds.h + pad
      );
    },
    [imageBox, pointerToViewBox, size],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (maskActive) return; // Correct Area: clicks paint, never place/select.
      if (handActive || resizeActive || resizeDragRef.current || dragRef.current) return;
      // Placement is the grid-layer command. Creators click the picture to place.
      // Image-hit may select the Atlas only when placement is not armed.
      if (placementActive) {
        const cell = handlePointer(e.clientX, e.clientY);
        if (!cell) return;
        onCellClick(cell.column, cell.row);
        return;
      }
      const target = e.target as Element | null;
      const onTransform = !!(
        target?.closest?.("[data-atlas-hit='true']")
        || target?.closest?.("[data-testid='spatial-map-transform-overlay']")
        || isImageHit(e.clientX, e.clientY)
      );
      if (!onTransform) setMapSelected(false);
    },
    [handActive, handlePointer, isImageHit, onCellClick, placementActive, resizeActive, maskActive],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      if (handActive || resizeActive || !placementActive) {
        setHover(null);
        return;
      }
      setHover(handlePointer(e.clientX, e.clientY));
    },
    [handActive, handlePointer, placementActive, resizeActive],
  );

  const applyHandDelta = useCallback(
    (clientX: number, clientY: number) => {
      const drag = dragRef.current;
      const point = pointerToViewBox(clientX, clientY);
      if (!drag || !point) return;
      const travel = Math.hypot(point.x - drag.startX, point.y - drag.startY);
      if (!drag.moved && travel < 3) return;
      drag.moved = true;
      const current = alignmentRef.current;
      const next = alignmentFromPixelPair(
        drag.originX + (point.x - drag.startX),
        drag.originY + (point.y - drag.startY),
        size,
        drag.originScale,
        current,
      );
      onAlignmentChange?.(next);
      alignmentRef.current = next;
    },
    [onAlignmentChange, pointerToViewBox, size],
  );

  const applyResizeDelta = useCallback(
    (clientX: number, clientY: number) => {
      const drag = resizeDragRef.current;
      const point = pointerToViewBox(clientX, clientY);
      if (!drag || !point) return;
      const next = alignmentFromOppositeAnchorResize(drag.origin, imageBox, size, drag.corner, point);
      onAlignmentChange?.(next);
      alignmentRef.current = next;
    },
    [imageBox, onAlignmentChange, pointerToViewBox, size],
  );

  const bindWindowDrag = useCallback(() => {
    unbindWindowDragRef.current?.();
    const onMove = (ev: Event) => {
      const pev = ev as PointerEvent;
      if (resizeDragRef.current) {
        applyResizeDelta(pev.clientX, pev.clientY);
        return;
      }
      if (dragRef.current) applyHandDelta(pev.clientX, pev.clientY);
    };
    const onUp = (ev: Event) => {
      const pev = ev as PointerEvent;
      unbindWindowDragRef.current?.();
      unbindWindowDragRef.current = null;
      if (resizeDragRef.current) {
        applyResizeDelta(pev.clientX, pev.clientY);
        resizeDragRef.current = null;
        setResizeDragging(false);
        onAlignmentCommit?.(alignmentRef.current);
        return;
      }
      if (!dragRef.current) return;
      applyHandDelta(pev.clientX, pev.clientY);
      const moved = dragRef.current.moved;
      dragRef.current = null;
      setHandDragging(false);
      if (moved) onAlignmentCommit?.(alignmentRef.current);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("pointercancel", onUp);
    unbindWindowDragRef.current = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [applyHandDelta, applyResizeDelta, onAlignmentCommit]);

  useEffect(() => () => unbindWindowDragRef.current?.(), []);

  /* —— Mask pointer handlers — paint in source pixels via the shared transform. */
  const maskPointerToSource = useCallback(
    (clientX: number, clientY: number) => {
      const point = pointerToViewBox(clientX, clientY);
      if (!point) return null;
      return viewBoxToSourcePixel(
        point.x,
        point.y,
        size,
        maskSourceRef.current.w,
        maskSourceRef.current.h,
        alignmentRef.current,
      );
    },
    [pointerToViewBox, size],
  );

  const handleMaskPointerDown = useCallback(
    (e: React.PointerEvent<Element>) => {
      if (!maskActive) return;
      e.preventDefault();
      e.stopPropagation();
      try { (e.currentTarget as Element).setPointerCapture?.(e.pointerId); } catch { /* noop */ }
      maskDrawingRef.current = true;
      const src = maskPointerToSource(e.clientX, e.clientY);
      if (!src) return;
      if (maskToolRef.current === "rect") {
        maskRectStartRef.current = src;
      } else {
        maskPaint(src.x, src.y, maskToolRef.current === "erase");
      }
    },
    [maskActive, maskPointerToSource, maskPaint],
  );

  const handleMaskPointerMove = useCallback(
    (e: React.PointerEvent<Element>) => {
      if (!maskActive || !maskDrawingRef.current) return;
      const src = maskPointerToSource(e.clientX, e.clientY);
      if (!src) return;
      if (maskToolRef.current === "rect") {
        // Rect commits on pointerup; no live preview canvas (keeps parity simple).
        return;
      }
      maskPaint(src.x, src.y, maskToolRef.current === "erase");
    },
    [maskActive, maskPointerToSource, maskPaint],
  );

  const handleMaskPointerUp = useCallback(
    (e: React.PointerEvent<Element>) => {
      if (!maskActive || !maskDrawingRef.current) return;
      maskDrawingRef.current = false;
      try { (e.currentTarget as Element).releasePointerCapture?.(e.pointerId); } catch { /* noop */ }
      if (maskToolRef.current === "rect" && maskRectStartRef.current) {
        const src = maskPointerToSource(e.clientX, e.clientY);
        const start = maskRectStartRef.current;
        maskRectStartRef.current = null;
        if (src) maskDrawRect(start.x, start.y, src.x, src.y, false);
      }
    },
    [maskActive, maskPointerToSource, maskDrawRect],
  );

  const beginMove = useCallback(
    (e: React.PointerEvent<Element>, svg: SVGSVGElement | null) => {
      const point = pointerToViewBox(e.clientX, e.clientY);
      if (!point || !svg) return;
      e.preventDefault();
      e.stopPropagation();
      svg.setPointerCapture(e.pointerId);
      const current = alignmentRef.current;
      dragRef.current = {
        pointerId: e.pointerId,
        startX: point.x,
        startY: point.y,
        originX: pixelsFromAlignment(current.offsetX, size),
        originY: pixelsFromAlignment(current.offsetY, size),
        originScale: current.scale,
        moved: false,
      };
      setHandDragging(true);
      setMapSelected(true);
      bindWindowDrag();
    },
    [bindWindowDrag, pointerToViewBox, size],
  );

  const handleHandPointerDown = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (maskActive) return; // Mask overlay owns the pointer during Correct Area.
      if (placementActive) return;
      const target = e.target as Element | null;
      if (target?.closest?.("[data-resize-handle='true']")) return;
      if (target?.closest?.("[data-testid^='placement-marker-']") || target?.closest?.("[data-testid^='camera-marker-']")) {
        return;
      }
      if (handActive) {
        beginMove(e, e.currentTarget);
        return;
      }
      if (isImageHit(e.clientX, e.clientY)) {
        setMapSelected(true);
        beginMove(e, e.currentTarget);
      }
    },
    [beginMove, handActive, isImageHit, placementActive, maskActive],
  );

  const handleAtlasPointerDown = useCallback(
    (e: React.PointerEvent<SVGGElement>) => {
      if (maskActive) return; // Correct Area paints; it does not freehand-drag the atlas.
      if (placementActive) return;
      const svg = e.currentTarget.ownerSVGElement;
      setMapSelected(true);
      beginMove(e, svg);
    },
    [beginMove, placementActive, maskActive],
  );

  const handleResizePointerDown = useCallback(
    (e: React.PointerEvent<Element>, corner: ResizeCorner) => {
      e.preventDefault();
      e.stopPropagation();
      const point = pointerToViewBox(e.clientX, e.clientY);
      if (!point) return;
      setMapSelected(true);
      setResizeDragging(true);
      resizeDragRef.current = {
        pointerId: e.pointerId,
        corner,
        origin: alignmentRef.current,
      };
      bindWindowDrag();
      try {
        const captureEl = e.currentTarget as Element | null;
        captureEl?.setPointerCapture?.(e.pointerId);
      } catch {
        /* Window listeners own the drag if capture is unavailable. */
      }
    },
    [bindWindowDrag, pointerToViewBox],
  );

  const handleHandPointerMove = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (resizeDragRef.current) {
        applyResizeDelta(e.clientX, e.clientY);
        return;
      }
      if (!dragRef.current) return;
      applyHandDelta(e.clientX, e.clientY);
    },
    [applyHandDelta, applyResizeDelta],
  );

  const endHandDrag = useCallback(
    (e: React.PointerEvent<SVGSVGElement>) => {
      if (unbindWindowDragRef.current) return;
      if (resizeDragRef.current) {
        if (e.currentTarget.hasPointerCapture(e.pointerId)) {
          e.currentTarget.releasePointerCapture(e.pointerId);
        }
        applyResizeDelta(e.clientX, e.clientY);
        resizeDragRef.current = null;
        setResizeDragging(false);
        onAlignmentCommit?.(alignmentRef.current);
        return;
      }
      if (!dragRef.current) return;
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
      applyHandDelta(e.clientX, e.clientY);
      const moved = dragRef.current.moved;
      dragRef.current = null;
      setHandDragging(false);
      if (moved) onAlignmentCommit?.(alignmentRef.current);
    },
    [applyHandDelta, applyResizeDelta, onAlignmentCommit],
  );

  const handleHandKeyDown = useCallback(
    (e: React.KeyboardEvent<SVGSVGElement>) => {
      if (!handActive) return;
      const step = e.shiftKey ? 4 : 1;
      let dx = 0;
      let dy = 0;
      if (e.key === "ArrowLeft") dx = -step;
      else if (e.key === "ArrowRight") dx = step;
      else if (e.key === "ArrowUp") dy = -step;
      else if (e.key === "ArrowDown") dy = step;
      else return;
      e.preventDefault();
      const current = alignmentRef.current;
      const next = alignmentFromPixelPair(
        pixelsFromAlignment(current.offsetX, size) + dx,
        pixelsFromAlignment(current.offsetY, size) + dy,
        size,
        current.scale,
        current,
      );
      alignmentRef.current = next;
      onAlignmentChange?.(next);
      onAlignmentCommit?.(next);
    },
    [handActive, onAlignmentChange, onAlignmentCommit, size],
  );

  const hasNormalized = (x: number | null | undefined, y: number | null | undefined) =>
    typeof x === "number" && typeof y === "number";
  const placedPlacements = placements.filter(
    (p) => hasNormalized(p.normalizedX, p.normalizedY) || (p.gridRow >= 0 && p.gridColumn >= 0),
  );
  const placedCameras = cameras.filter(
    (c) => hasNormalized(c.normalizedX, c.normalizedY) || (c.gridRow >= 0 && c.gridColumn >= 0),
  );

  /**
   * Camera glyph:
   * - free (default): hydrated/saved pose -- never auto-rides the character
   * - pov (Shot Size = POV): attaches to live Primary Subject marker
   */
  const cameraMarkerCoords = (c: SpatialCamera) => {
    const mode = resolveCameraAttachMode(c);
    if (mode === "pov") {
      const subjectId = cameraFollowSubjectId(c);
      const subject =
        subjectId
          ? placements.find((p) => p.kind === "character" && p.id === subjectId) || null
          : null;
      const scrub = resolvePovCameraScrubPosition(subject, activeMovementAlias, density);
      if (scrub) {
        return {
          gridColumn: -1,
          gridRow: -1,
          normalizedX: scrub.normalizedX,
          normalizedY: scrub.normalizedY,
          scrubAlias: scrub.alias,
          attachMode: scrub.attachMode,
        };
      }
    }
    return {
      gridColumn: c.gridColumn,
      gridRow: c.gridRow,
      normalizedX: c.normalizedX,
      normalizedY: c.normalizedY,
      scrubAlias: null as string | null,
      attachMode: mode,
    };
  };

  const wrapClass = [
    "spatial-map__grid-wrap",
    "spatial-map__grid-wrap--rect",
    showGrid ? "" : "spatial-map__grid-wrap--hide-grid",
    showCircles ? "" : "spatial-map__grid-wrap--hide-circles",
    showLabels ? "" : "spatial-map__grid-wrap--hide-labels",
    mapSelected || resizeActive || handActive ? "spatial-map__grid-wrap--map-selected" : "",
  ].filter(Boolean).join(" ");
  const aspectCss = aspect > 0 ? String(aspect) : "1.7777777777777777";
  const handlesVisible = (mapSelected || resizeActive || handActive) && !placementActive;
  const liveBounds = transformedImageBounds(imageBox, size, liveAlignment);
  const htmlHandlePx = 16;
  const cornerLocals = imageCorners(imageBox);

  return (
    <div
      className={wrapClass}
      ref={containerRef}
      style={{
        ["--spatial-map-aspect" as string]: aspectCss,
        ["--spatial-map-zoom" as string]: String(zoom),
      }}
      data-viewport="rect"
      data-clip="none"
      data-circles={showCircles ? "on" : "off"}
      data-zoom={zoom}
      data-zoom-domain="view"
      data-testid="spatial-map-viewport-frame"
    >
      <div
        className="spatial-map__viewport"
        ref={viewportRef}
        data-testid="spatial-map-viewport"
        data-zoom={zoom}
        data-zoom-domain="view"
      >
        <svg
          className="spatial-map__grid-svg"
          viewBox={`0 0 ${size} ${size}`}
          preserveAspectRatio="xMidYMid slice"
          tabIndex={handActive || mapSelected ? 0 : undefined}
          onClick={handleClick}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHover(null)}
          onPointerDown={maskActive ? handleMaskPointerDown : handleHandPointerDown}
          onPointerMove={maskActive ? handleMaskPointerMove : handleHandPointerMove}
          onPointerUp={maskActive ? handleMaskPointerUp : endHandDrag}
          onPointerCancel={maskActive ? handleMaskPointerUp : endHandDrag}
          onKeyDown={handleHandKeyDown}
          role="img"
          aria-label={maskActive
            ? "Correct Area. Paint a mask over the Spatial Map to select the region to correct."
            : resizeActive
            ? "Resize the Spatial Map image. The placement grid stays still."
            : handActive
              ? "Freehand align. Drag the Spatial Map image. The placement grid stays still."
              : placementActive
                ? "Rectangular spatial map. Click a cell to place the selected object."
                : "Rectangular spatial map with square placement grid. Click a cell to place the selected object."}
          data-testid="spatial-map-grid"
          data-viewport="rect"
          data-clip="none"
          data-mask-active={maskActive ? "true" : "false"}
          data-hand-active={handActive ? "true" : "false"}
          data-hand-dragging={handDragging ? "true" : "false"}
          data-resize-active={resizeActive ? "true" : "false"}
          data-resize-dragging={resizeDragging ? "true" : "false"}
          data-map-selected={handlesVisible ? "true" : "false"}
          data-grid-detail={gridScale}
          data-grid-size={density}
          data-grid-kind="cartesian"
        >
          <g data-testid="spatial-map-workspace-layer">
            <g
              className="spatial-map-atlas-layer"
              data-testid="spatial-map-atlas-layer"
              transform={`translate(${offsetPx} ${offsetPy}) translate(${cx} ${cy}) scale(${scale}) translate(${-cx} ${-cy})`}
              data-offset-x={String(liveAlignment.offsetX)}
              data-offset-y={String(liveAlignment.offsetY)}
              data-scale={String(scale)}
              data-fit="contain"
              data-source-width={String(sourceWidth || "")}
              data-source-height={String(sourceHeight || "")}
              data-aspect={String(aspect)}
              data-image-x={String(imageBox.x)}
              data-image-y={String(imageBox.y)}
              data-image-width={String(imageBox.w)}
              data-image-height={String(imageBox.h)}
              data-atlas-hit="true"
              onPointerDown={handleAtlasPointerDown}
            >
              <image
                href={imageUrl}
                x={imageBox.x}
                y={imageBox.y}
                width={imageBox.w}
                height={imageBox.h}
                preserveAspectRatio="xMidYMid meet"
                style={{ pointerEvents: "all", cursor: handlesVisible ? "grab" : "pointer" }}
              />
            </g>
            {maskActive ? (
              /* Mask canvas is composited in the HTML overlay (below), positioned
                  over the displayed atlas rect via the shared viewBoxToLocalCss
                  mapping — identical to the resize handles. */
              <g className="spatial-map-mask-layer" data-testid="spatial-map-mask-layer" pointerEvents="none" />
            ) : null}
            <g className="spatial-map-placement-grid-layer" data-testid="spatial-map-placement-grid-layer">
            <path d={gridPath} className="spatial-map__grid-lines" data-testid="spatial-map-grid-lines" />

            {validCells.map((cell) => {
              const isTarget = !!(placementActive && hover && hover.column === cell.column && hover.row === cell.row);
              return (
                <circle
                  key={`cell-${cell.column}-${cell.row}`}
                  className={`spatial-map__cell-circle${isTarget ? " is-place-target" : ""}`}
                  cx={cell.px}
                  cy={cell.py}
                  r={cellCircleR}
                  data-column={cell.column}
                  data-row={cell.row}
                  data-testid={`cell-circle-${cell.column}-${cell.row}`}
                />
              );
            })}

            {placementActive && !handActive && !resizeActive && hover && ghostColor ? (
              (() => {
                const mid = cellCenterNormalized(hover.column, hover.row, density);
                const pix = normalizedToPixel(mid.x, mid.y, size);
                return (
                  <circle
                    className="spatial-map__ghost-cursor"
                    cx={pix.px}
                    cy={pix.py}
                    r={cellCircleR}
                    fill={ghostColor}
                    fillOpacity={0.35}
                    stroke={ghostColor}
                    strokeOpacity={0.85}
                    strokeWidth={2}
                    pointerEvents="none"
                    aria-hidden="true"
                    data-testid="spatial-map-ghost-cursor"
                  />
                );
              })()
            ) : null}

            <defs>
              <marker
                id="spatial-map-movement-arrowhead"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L6,3 L0,6 Z" fill="rgba(196, 181, 253, 0.95)" />
              </marker>
            </defs>
            <g className="spatial-map__movement-arrows" data-testid="spatial-map-movement-arrows" pointerEvents="none">
              {movementArrows.map((arrow) => {
                const from = markerPosition(
                  arrow.from.gridColumn ?? -1,
                  arrow.from.gridRow ?? -1,
                  arrow.from.normalizedX,
                  arrow.from.normalizedY,
                  density,
                  size,
                );
                const to = markerPosition(
                  arrow.to.gridColumn ?? -1,
                  arrow.to.gridRow ?? -1,
                  arrow.to.normalizedX,
                  arrow.to.normalizedY,
                  density,
                  size,
                );
                if (!from || !to) return null;
                const key = `${arrow.characterId}-${arrow.fromAlias}-${arrow.toAlias}`;
                return (
                  <g
                    key={key}
                    className="spatial-map__movement-arrow"
                    data-testid={`movement-arrow-${arrow.characterId}-${arrow.fromAlias}-${arrow.toAlias}`}
                    data-character-id={arrow.characterId}
                    data-from-alias={arrow.fromAlias}
                    data-to-alias={arrow.toAlias}
                  >
                    <line
                      x1={from.px}
                      y1={from.py}
                      x2={to.px}
                      y2={to.py}
                      stroke="rgba(196, 181, 253, 0.9)"
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      markerEnd="url(#spatial-map-movement-arrowhead)"
                    />
                    <title>{`${arrow.label || arrow.characterId}: ${arrow.fromAlias} -> ${arrow.toAlias}`}</title>
                  </g>
                );
              })}
            </g>

            <defs>
              <marker
                id="spatial-map-camera-movement-arrowhead"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L6,3 L0,6 Z" fill="rgba(74, 222, 128, 0.95)" />
              </marker>
            </defs>
            <g className="spatial-map__camera-movement-arrows" data-testid="spatial-map-camera-movement-arrows" pointerEvents="none">
              {cameraMovementArrows.map((arrow) => {
                const from = markerPosition(
                  -1,
                  -1,
                  arrow.from.normalizedX,
                  arrow.from.normalizedY,
                  density,
                  size,
                );
                const to = markerPosition(
                  -1,
                  -1,
                  arrow.to.normalizedX,
                  arrow.to.normalizedY,
                  density,
                  size,
                );
                if (!from || !to) return null;
                const key = `${arrow.cameraId}-${arrow.subjectCharacterId}-${arrow.fromAlias}-${arrow.toAlias}`;
                return (
                  <g
                    key={key}
                    className="spatial-map__camera-movement-arrow"
                    data-testid={`camera-movement-arrow-${arrow.cameraId}-${arrow.fromAlias}-${arrow.toAlias}`}
                    data-camera-id={arrow.cameraId}
                    data-subject-character-id={arrow.subjectCharacterId}
                    data-from-alias={arrow.fromAlias}
                    data-to-alias={arrow.toAlias}
                  >
                    <line
                      x1={from.px}
                      y1={from.py}
                      x2={to.px}
                      y2={to.py}
                      stroke="rgba(74, 222, 128, 0.92)"
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      markerEnd="url(#spatial-map-camera-movement-arrowhead)"
                    />
                    <title>{`${arrow.label}: ${arrow.fromAlias} -> ${arrow.toAlias}`}</title>
                  </g>
                );
              })}
            </g>

            {placedCameras.map((c) => {
              const coords = cameraMarkerCoords(c);
              const px = markerPosition(coords.gridColumn, coords.gridRow, coords.normalizedX, coords.normalizedY, density, size);
              if (!px) return null;
              const isSelected = selectedCameraId === c.id;
              const hidden = c.visible === false;
              return (
                <g
                  key={`fov-${c.id}`}
                  transform={`translate(${px.px}, ${px.py})`}
                  className={`spatial-map__fov-layer${hidden ? " spatial-map__camera--hidden" : ""}`}
                  data-visible={hidden ? "false" : "true"}
                  data-scrub-alias={coords.scrubAlias || undefined}
                  data-attach-mode={coords.attachMode || undefined}
                >
                  <CameraFovCone
                    orientation={c.orientation || "N"}
                    fovPreset={c.fovPreset || "medium"}
                    radius={Math.max(cameraSize * 2.6, cellPx * 1.6)}
                    selected={isSelected}
                  />
                </g>
              );
            })}

            {placedPlacements.map((p) => {
              const px = markerPosition(p.gridColumn, p.gridRow, p.normalizedX, p.normalizedY, density, size);
              if (!px) return null;
              const isSelected = selectedPlacementId === p.id;
              const hidden = p.visible === false;
              const slot = Math.min(4, Math.max(1, p.slotIndex + 1));
              return (
                <g
                  key={p.id}
                  className={`spatial-map__marker${markerModifier(p.kind, p.slotIndex)}${isSelected ? " is-selected" : ""}${hidden ? " spatial-map__marker--hidden" : ""}`}
                  transform={`translate(${px.px}, ${px.py})`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (handActive || resizeActive) return;
                    onSelectPlacement(isSelected ? null : p.id);
                  }}
                  style={{ cursor: "pointer" }}
                  data-testid={`placement-marker-${p.id}`}
                  data-kind={p.kind}
                  data-slot={String(slot)}
                  data-visible={hidden ? "false" : "true"}
                >
                  <title>{p.tooltip || p.label || p.tag}</title>
                  <circle
                    className="spatial-map__marker-circle"
                    r={markerR}
                    fill={SLOT_COLORS[p.colorKey] || "#fff"}
                    stroke="rgba(255,255,255,0.85)"
                    strokeWidth={2}
                  />
                  {p.kind === "character" && p.attachedBadge ? (
                    <g
                      className="spatial-map__prop-badge"
                      transform={`translate(${markerR * 0.78}, ${-markerR * 0.78})`}
                      data-testid={`character-prop-badge-${p.id}`}
                      data-badge={p.attachedBadge.type === "single" ? p.attachedBadge.slotLabel : `+${p.attachedBadge.count}`}
                    >
                      <circle
                        className="spatial-map__prop-badge-circle"
                        r={Math.max(6, markerR * 0.38)}
                        fill="#1b1230"
                        stroke="rgba(255,255,255,0.9)"
                        strokeWidth={1.2}
                      />
                      <text
                        className="spatial-map__prop-badge-label"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={Math.max(7, markerR * 0.36)}
                        fill="#fff"
                      >
                        {p.attachedBadge.type === "single" ? p.attachedBadge.slotLabel : `+${p.attachedBadge.count}`}
                      </text>
                    </g>
                  ) : null}
                </g>
              );
            })}

            {placedCameras.map((c) => {
              const coords = cameraMarkerCoords(c);
              const px = markerPosition(coords.gridColumn, coords.gridRow, coords.normalizedX, coords.normalizedY, density, size);
              if (!px) return null;
              const isSelected = selectedCameraId === c.id;
              const hidden = c.visible === false;
              return (
                <g
                  key={c.id}
                  className={`spatial-map__camera${isSelected ? " is-selected" : ""}${hidden ? " spatial-map__camera--hidden" : ""}`}
                  transform={`translate(${px.px}, ${px.py})`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (handActive || resizeActive) return;
                    onSelectCamera(isSelected ? null : c.id);
                  }}
                  style={{ cursor: "pointer" }}
                  data-testid={`camera-marker-${c.id}`}
                  data-visible={hidden ? "false" : "true"}
                  data-scrub-alias={coords.scrubAlias || undefined}
                  data-attach-mode={coords.attachMode || undefined}
                >
                  <CameraMarker
                    size={cameraSize}
                    label={c.cameraSlot >= 0 ? `C${c.cameraSlot + 1}` : c.label}
                    orientation={c.orientation || "N"}
                  />
                  <rect
                    className="spatial-map__camera-hitbox"
                    x={-cameraSize / 2}
                    y={-cameraSize / 2}
                    width={cameraSize}
                    height={cameraSize}
                    fill="transparent"
                    pointerEvents="all"
                  />
                </g>
              );
            })}

            {(() => {
              const px = spinCameraPixelPosition(spinCamera, widthMeters, depthMeters, size);
              if (!px) return null;
              const r = Math.max(8, cameraSize * 0.75);
              const isSelected = selectedSpinCamera;
              return (
                <g
                  key="spin-camera-marker"
                  className={`spatial-map__spin-camera${isSelected ? " is-selected" : ""}`}
                  transform={`translate(${px.px}, ${px.py})`}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (handActive || resizeActive) return;
                    onSelectSpinCamera?.();
                  }}
                  style={{ cursor: "pointer" }}
                  data-testid="spin-camera-marker"
                >
                  <circle
                    className="spatial-map__spin-camera-ring"
                    r={r}
                    fill="none"
                    stroke="#22d3ee"
                    strokeWidth={2}
                  />
                  <line x1={-r} y1={0} x2={r} y2={0} stroke="#22d3ee" strokeWidth={2} />
                  <line x1={0} y1={-r} x2={0} y2={r} stroke="#22d3ee" strokeWidth={2} />
                  <circle r={2.5} fill="#22d3ee" />
                  {isSelected ? (
                    <g className="spatial-map__spin-compass" data-testid="spin-camera-compass" pointerEvents="none">
                      <text y={-r - 6} className="spatial-map__spin-compass-label" textAnchor="middle">
                        N
                      </text>
                      <text x={r + 8} className="spatial-map__spin-compass-label" textAnchor="start" dominantBaseline="middle">
                        E
                      </text>
                      <text y={r + 14} className="spatial-map__spin-compass-label" textAnchor="middle">
                        S
                      </text>
                      <text x={-r - 8} className="spatial-map__spin-compass-label" textAnchor="end" dominantBaseline="middle">
                        W
                      </text>
                    </g>
                  ) : null}
                </g>
              );
            })()}
            </g>
          </g>

          {CARDINAL_LABELS.map((label, index) => {
            const radius = size / 2 - 1;
            const angle = (index / 8) * Math.PI * 2 - Math.PI / 2;
            const lx = cx + (radius - 16) * Math.cos(angle);
            const ly = cy + (radius - 16) * Math.sin(angle);
            return (
              <text key={label} x={lx} y={ly} className="spatial-map__grid-label" textAnchor="middle" dominantBaseline="middle">
                {label}
              </text>
            );
          })}

          {handlesVisible ? (
            <g
              className="spatial-map__transform-overlay"
              data-testid="spatial-map-transform-overlay"
              data-selected="true"
            >
              <rect
                className="spatial-map__transform-box"
                data-testid="spatial-map-transform-box"
                x={liveBounds.x}
                y={liveBounds.y}
                width={liveBounds.w}
                height={liveBounds.h}
                pointerEvents="none"
              />
              <g className="spatial-map__resize-handles" data-testid="spatial-map-resize-handles" pointerEvents="none" />
            </g>
          ) : null}
        </svg>
        {maskActive ? (
          /* Correct Area mask overlay — positioned over the DISPLAYED atlas rect
             via the same viewBoxToLocalCss mapping the resize handles use, so the
             source-resolution mask lands pixel-for-pixel on the displayed image.
             pointerEvents:none — painting is routed through the grid svg. */
          (() => {
            const sw = sourceWidth;
            const sh = sourceHeight;
            const rect = displayedAtlasRect(size, sw, sh, liveAlignment);
            const topLeft = viewBoxToLocalCss(rect.x, rect.y, viewportBox.w, viewportBox.h, size);
            const botRight = viewBoxToLocalCss(rect.x + rect.width, rect.y + rect.height, viewportBox.w, viewportBox.h, size);
            const w = Math.max(1, botRight.x - topLeft.x);
            const h = Math.max(1, botRight.y - topLeft.y);
            return (
              <canvas
                ref={maskCanvasRef}
                className="spatial-map__mask-canvas"
                data-testid="spatial-map-mask-canvas"
                data-source-width={sw}
                data-source-height={sh}
                data-display-left={topLeft.x}
                data-display-top={topLeft.y}
                data-display-width={w}
                data-display-height={h}
                style={{
                  position: "absolute",
                  left: topLeft.x,
                  top: topLeft.y,
                  width: w,
                  height: h,
                  opacity: maskOverlayOpacityRef.current,
                  pointerEvents: "none",
                  zIndex: 3,
                }}
              />
            );
          })()
        ) : null}
        {handlesVisible ? (
          <div className="spatial-map__html-handles" data-testid="spatial-map-html-handles">
            {(["nw", "ne", "sw", "se"] as const).map((corner) => {
              const local = cornerLocals[corner];
              const world = transformPoint(local.x, local.y, size, liveAlignment);
              const css = viewBoxToLocalCss(world.x, world.y, viewportBox.w, viewportBox.h, size);
              return (
                <div
                  key={corner}
                  role="button"
                  tabIndex={0}
                  aria-label={`Resize ${corner}`}
                  className={`spatial-map__resize-handle spatial-map__resize-handle--${corner}`}
                  data-testid={`spatial-map-resize-handle-${corner}`}
                  data-resize-handle="true"
                  data-corner={corner}
                  style={{
                    left: css.x,
                    top: css.y,
                    width: htmlHandlePx,
                    height: htmlHandlePx,
                  }}
                  onPointerDown={(e) => handleResizePointerDown(e, corner)}
                  onClick={(e) => e.stopPropagation()}
                />
              );
            })}
          </div>
        ) : null}
      </div>

      {occupiedMessage ? <p className="spatial-map__occupied-message">{occupiedMessage}</p> : null}
    </div>
  );
}
