/** Floating Re-Take menu geometry. Clamped to the Preview Monitor stage. */

export type OverlayFrame = { x: number; y: number; w: number; h: number };
export type OverlayBounds = { w: number; h: number };
export type ResizeEdge = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export const RETAKE_OVERLAY_PAD = 6;
export const RETAKE_OVERLAY_MIN_W = 196;
export const RETAKE_OVERLAY_MIN_H = 80;
export const RETAKE_OVERLAY_DEFAULT_W = 252;

export function overlayMaxSize(parent: OverlayBounds): OverlayBounds {
  return {
    w: Math.max(96, parent.w - RETAKE_OVERLAY_PAD * 2),
    h: Math.max(72, parent.h - RETAKE_OVERLAY_PAD * 2),
  };
}

export function clampOverlayFrame(frame: OverlayFrame, parent: OverlayBounds): OverlayFrame {
  const max = overlayMaxSize(parent);
  const minW = Math.min(RETAKE_OVERLAY_MIN_W, max.w);
  const minH = Math.min(RETAKE_OVERLAY_MIN_H, max.h);
  const w = Math.min(Math.max(frame.w, minW), max.w);
  const h = Math.min(Math.max(frame.h, minH), max.h);
  const maxX = Math.max(RETAKE_OVERLAY_PAD, parent.w - w - RETAKE_OVERLAY_PAD);
  const maxY = Math.max(RETAKE_OVERLAY_PAD, parent.h - h - RETAKE_OVERLAY_PAD);
  return {
    x: Math.min(Math.max(frame.x, RETAKE_OVERLAY_PAD), maxX),
    y: Math.min(Math.max(frame.y, RETAKE_OVERLAY_PAD), maxY),
    w,
    h,
  };
}

export function defaultRetakeOverlayFrame(parent: OverlayBounds, height = RETAKE_OVERLAY_MIN_H): OverlayFrame {
  const max = overlayMaxSize(parent);
  const w = Math.min(RETAKE_OVERLAY_DEFAULT_W, max.w);
  const h = Math.min(Math.max(height, Math.min(RETAKE_OVERLAY_MIN_H, max.h)), max.h);
  return clampOverlayFrame(
    {
      x: Math.round((parent.w - w) / 2),
      y: RETAKE_OVERLAY_PAD,
      w,
      h,
    },
    parent,
  );
}

export function moveOverlayFrame(frame: OverlayFrame, dx: number, dy: number, parent: OverlayBounds): OverlayFrame {
  return clampOverlayFrame({ ...frame, x: frame.x + dx, y: frame.y + dy }, parent);
}

export function resizeOverlayFrame(
  frame: OverlayFrame,
  edge: ResizeEdge,
  dx: number,
  dy: number,
  parent: OverlayBounds,
): OverlayFrame {
  const max = overlayMaxSize(parent);
  const minW = Math.min(RETAKE_OVERLAY_MIN_W, max.w);
  const minH = Math.min(RETAKE_OVERLAY_MIN_H, max.h);
  let { x, y, w, h } = frame;

  if (edge.includes("e")) {
    w = Math.min(Math.max(frame.w + dx, minW), max.w);
  }
  if (edge.includes("w")) {
    const nextW = Math.min(Math.max(frame.w - dx, minW), max.w);
    x = frame.x + (frame.w - nextW);
    w = nextW;
  }
  if (edge.includes("s")) {
    h = Math.min(Math.max(frame.h + dy, minH), max.h);
  }
  if (edge.includes("n")) {
    const nextH = Math.min(Math.max(frame.h - dy, minH), max.h);
    y = frame.y + (frame.h - nextH);
    h = nextH;
  }

  return clampOverlayFrame({ x, y, w, h }, parent);
}

export function parentBoundsFromElement(el: HTMLElement | null): OverlayBounds | null {
  const parent = el?.offsetParent as HTMLElement | null;
  if (!parent) return null;
  return { w: parent.clientWidth, h: parent.clientHeight };
}
