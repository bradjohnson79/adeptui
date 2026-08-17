/**
 * Shared Timeline focus bus for Co-Director ↔ TimelineEditorShell (SA52).
 * One selection/focus model — no parallel fiction state.
 */

export type TimelineFocusTarget =
  | "scenePrompt"
  | "batch"
  | "trackItem"
  | "preflightFinding"
  | "viewer"
  | "playhead"
  | "inspectorField"
  | "queueJob";

export type TimelineFocusRequest = {
  target: TimelineFocusTarget;
  sceneId?: string;
  selectionKind?: string;
  selectionId?: string;
  fieldId?: string;
  playheadSec?: number;
  findingCode?: string;
  jobId?: string;
  openRightTab?: "inspector" | "codirector" | "hotkeys";
  viewerPreset?: "large" | "balanced" | "timeline_focus";
  fullscreen?: boolean;
  zoom?: number;
  zoomDelta?: number;
  trackDensity?: "compact" | "comfortable" | "expanded";
  layoutReset?: boolean;
  fitViewer?: boolean;
  openInpaint?: boolean;
};

export const TIMELINE_FOCUS_EVENT = "adept-timeline-focus";

export function requestTimelineFocus(request: TimelineFocusRequest): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(TIMELINE_FOCUS_EVENT, { detail: request }));
}

export function focusDomId(id: string): void {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  if (el instanceof HTMLElement) {
    try {
      el.focus({ preventScroll: true });
    } catch {
      /* ignore */
    }
  }
}

export const TIMELINE_FOCUS_IDS = {
  scenePrompt: "timeline-focus-scene-prompt",
  viewer: "timeline-focus-viewer",
  playhead: "timeline-playhead",
  inspector: "timeline-inspector",
  queue: "timeline-render-queue",
  toolbar: "timeline-toolbar",
  batchLane: "timeline-batch-lane",
} as const;
