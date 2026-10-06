/** Shared Fit / contain math for preview monitors (Timeline Re-Take, MAGI, etc.). */

export type MediaContainRect = { x: number; y: number; w: number; h: number; scale: number };

export function mediaContainRect(
  containerW: number,
  containerH: number,
  mediaW: number,
  mediaH: number,
): MediaContainRect {
  if (containerW <= 0 || containerH <= 0 || mediaW <= 0 || mediaH <= 0) {
    return { x: 0, y: 0, w: 0, h: 0, scale: 0 };
  }
  const scale = Math.min(containerW / mediaW, containerH / mediaH);
  const w = mediaW * scale;
  const h = mediaH * scale;
  return {
    x: (containerW - w) / 2,
    y: (containerH - h) / 2,
    w,
    h,
    scale,
  };
}
