/** Project-agnostic Standard Scene Creator pane widths. Not a dock framework. */

export const PANE_STORAGE_KEY = "adept.sceneCreator.paneWidths";

export const DEFAULT_PANE_WIDTHS = { left: 220, right: 280 } as const;

export const PANE_LIMITS = {
  leftMin: 160,
  leftMax: 380,
  rightMin: 220,
  rightMax: 440,
} as const;

export type PaneWidths = { left: number; right: number };

export function clampPaneWidths(next: PaneWidths): PaneWidths {
  const left = Number.isFinite(next.left) ? next.left : DEFAULT_PANE_WIDTHS.left;
  const right = Number.isFinite(next.right) ? next.right : DEFAULT_PANE_WIDTHS.right;
  return {
    left: Math.min(PANE_LIMITS.leftMax, Math.max(PANE_LIMITS.leftMin, Math.round(left))),
    right: Math.min(PANE_LIMITS.rightMax, Math.max(PANE_LIMITS.rightMin, Math.round(right))),
  };
}

export function readPaneWidths(): PaneWidths {
  if (typeof window === "undefined") return { ...DEFAULT_PANE_WIDTHS };
  try {
    const raw = window.localStorage.getItem(PANE_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PANE_WIDTHS };
    const parsed = JSON.parse(raw) as Partial<PaneWidths>;
    return clampPaneWidths({
      left: Number(parsed.left) || DEFAULT_PANE_WIDTHS.left,
      right: Number(parsed.right) || DEFAULT_PANE_WIDTHS.right,
    });
  } catch {
    return { ...DEFAULT_PANE_WIDTHS };
  }
}

export function writePaneWidths(widths: PaneWidths): PaneWidths {
  const next = clampPaneWidths(widths);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(PANE_STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

export function resetPaneWidths(): PaneWidths {
  return writePaneWidths({ ...DEFAULT_PANE_WIDTHS });
}
