/**
 * Canonical Adept composition-guide geometry.
 *
 * One master rectangle. Everything else is derived from it.
 *
 *   VIEWPORT + SELECTED ASPECT → master composition rect
 *     ├── Action Safe  (inset)
 *     ├── Title Safe   (inset)
 *     ├── Center vertical   (clipped to master)
 *     └── Center horizontal (clipped to master)
 */

import {
  DEFAULT_PRODUCTION_ASPECT,
  PRODUCTION_ASPECTS,
  normalizeProductionAspect,
  type ProductionAspectRatio,
} from "../workspacePrefs";

export type CompositionRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export const EMPTY_COMPOSITION_RECT: CompositionRect = { x: 0, y: 0, width: 0, height: 0 };

/** Percentage inset for Action Safe from the composition frame edge. */
export const ACTION_SAFE_INSET = 0.05;

/** Percentage inset for Title Safe from the composition frame edge. */
export const TITLE_SAFE_INSET = 0.1;

export type AspectPair = { w: number; h: number };

export function parseAspectPair(aspectRatio: string | null | undefined): AspectPair {
  const normalized = normalizeProductionAspect(aspectRatio);
  const [w, h] = normalized.split(":").map(Number);
  if (!w || !h || w <= 0 || h <= 0) return { w: 16, h: 9 };
  return { w, h };
}

/**
 * Classify pixel dimensions onto the Timeline production-aspect catalog.
 * MAGI uses this so published-master width/height become a composition class
 * (16:9, 9:16, …) instead of a megapixel-tier string like "1920:1088".
 */
export function aspectFromDimensions(width: number, height: number): ProductionAspectRatio {
  if (width <= 0 || height <= 0) return DEFAULT_PRODUCTION_ASPECT;
  const ratio = width / height;
  let best: ProductionAspectRatio = DEFAULT_PRODUCTION_ASPECT;
  let bestErr = Number.POSITIVE_INFINITY;
  for (const label of PRODUCTION_ASPECTS) {
    const [aw, ah] = label.split(":").map(Number);
    const err = Math.abs(ratio - aw / ah);
    if (err < bestErr) {
      bestErr = err;
      best = label;
    }
  }
  return best;
}

/**
 * Largest centered rectangle of `aspectWidth:aspectHeight` that fits inside
 * the viewport. This is the ONLY master composition rectangle.
 */
export function fitAspectRect(
  viewportWidth: number,
  viewportHeight: number,
  aspectWidth: number,
  aspectHeight: number,
): CompositionRect {
  if (viewportWidth <= 0 || viewportHeight <= 0 || aspectWidth <= 0 || aspectHeight <= 0) {
    return { ...EMPTY_COMPOSITION_RECT };
  }
  const viewportAspect = viewportWidth / viewportHeight;
  const targetAspect = aspectWidth / aspectHeight;
  if (viewportAspect > targetAspect) {
    const height = viewportHeight;
    const width = height * targetAspect;
    return {
      x: (viewportWidth - width) / 2,
      y: 0,
      width,
      height,
    };
  }
  const width = viewportWidth;
  const height = width / targetAspect;
  return {
    x: 0,
    y: (viewportHeight - height) / 2,
    width,
    height,
  };
}

/**
 * Timeline/MAGI entry point: viewport + selected composition aspect.
 */
export function getCompositionRect(
  viewportWidth: number,
  viewportHeight: number,
  aspectRatio: string | null | undefined,
): CompositionRect {
  const { w, h } = parseAspectPair(aspectRatio);
  return fitAspectRect(viewportWidth, viewportHeight, w, h);
}

export function insetRect(rect: CompositionRect, percent: number): CompositionRect {
  const ix = rect.width * percent;
  const iy = rect.height * percent;
  return {
    x: rect.x + ix,
    y: rect.y + iy,
    width: Math.max(0, rect.width - ix * 2),
    height: Math.max(0, rect.height - iy * 2),
  };
}

export type SafeAreaRects = {
  actionSafe: CompositionRect;
  titleSafe: CompositionRect;
};

export function getSafeAreaRects(comp: CompositionRect): SafeAreaRects {
  return {
    actionSafe: insetRect(comp, ACTION_SAFE_INSET),
    titleSafe: insetRect(comp, TITLE_SAFE_INSET),
  };
}

export function getCenterLines(comp: CompositionRect) {
  return {
    centerX: comp.x + comp.width / 2,
    centerY: comp.y + comp.height / 2,
  };
}

/** Center segments clipped exactly to the master composition boundary. */
export function getCenterLineSegments(comp: CompositionRect) {
  return {
    horizontal: {
      x1: comp.x,
      x2: comp.x + comp.width,
      y: comp.y + comp.height / 2,
    },
    vertical: {
      x: comp.x + comp.width / 2,
      y1: comp.y,
      y2: comp.y + comp.height,
    },
  };
}
