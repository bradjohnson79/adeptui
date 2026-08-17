/** Timeline workspace layout prefs — local only, not project media. */

export const TIMELINE_WORKSPACE_KEY = "adept_timeline_workspace_layout_v1";
export const TIMELINE_LAYOUT_EVENT = "adept-timeline-layout";

export type TimelineViewerPreset = "large" | "balanced" | "timeline_focus";
export type TimelineTrackDensity = "compact" | "comfortable" | "expanded";
export type TimelineViewerLayoutSnapshot = {
  viewerPreset: TimelineViewerPreset;
  viewerHeight: number;
  trackDensity: TimelineTrackDensity;
  zoom: number;
};

export type TimelineWorkspaceLayout = {
  /** Legacy px value kept for migration and older consumers. */
  monitorHeightPx: number;
  viewerPreset: TimelineViewerPreset;
  /** Ratio when <= 1, px when > 1. */
  viewerHeight: number;
  showEmptyHelp: boolean;
  trackDensity: TimelineTrackDensity;
  displayMode: "seconds" | "frames" | "timecode";
  showFilenames: boolean;
  showThumbnails: boolean;
  snapEnabled: boolean;
  playheadFollow: boolean;
  guidancePriority: "visual_first" | "prompt_first" | "balanced" | "custom";
  customPriorityOrder?: string[];
  lastNonFullscreenLayout?: TimelineViewerLayoutSnapshot;
  zoom: number;
  leftWidth: number;
  rightWidth: number;
};

export const DEFAULT_VIEWER_PRESET: TimelineViewerPreset = "large";
export const DEFAULT_VIEWER_HEIGHT = 0.48;
export const DEFAULT_MONITOR_HEIGHT = 360;
export const MIN_MONITOR_HEIGHT = 260;
export const COLLAPSED_MONITOR_HEIGHT = 96;
/** Reserved for toolbar + compact track viewport under the divider. */
export const TIMELINE_REGION_MIN_PX = 140;

export const DEFAULT_LEFT_WIDTH = 280;
export const DEFAULT_RIGHT_WIDTH = 320;
export const LEFT_PANE_MIN = 220;
export const LEFT_PANE_MAX = 440;
export const RIGHT_PANE_MIN = 260;
export const RIGHT_PANE_MAX = 500;
export const CENTER_PANE_MIN = 520;
export const SIDEBAR_GAP_PX = 16;

const VIEWER_PRESET_TARGETS: Record<TimelineViewerPreset, { at1280: number; at1920: number; min: number; max: number }> = {
  large: { at1280: 0.48, at1920: 0.52, min: 0.4, max: 0.58 },
  balanced: { at1280: 0.42, at1920: 0.46, min: 0.36, max: 0.52 },
  timeline_focus: { at1280: 0.34, at1920: 0.38, min: 0.28, max: 0.44 },
};

export function previewHeightStorageKey(projectId?: string | null): string {
  const id = (projectId || "").trim() || "global";
  return `adept-ui.timeline.preview-height.${id}`;
}

export function loadProjectPreviewHeightRatio(projectId?: string | null): number | null {
  try {
    const raw = localStorage.getItem(previewHeightStorageKey(projectId));
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

export function saveProjectPreviewHeightRatio(projectId: string | null | undefined, ratio: number): void {
  try {
    localStorage.setItem(previewHeightStorageKey(projectId), String(ratio));
  } catch {
    /* ignore */
  }
}

export const DEFAULT_TIMELINE_WORKSPACE: TimelineWorkspaceLayout = {
  monitorHeightPx: DEFAULT_MONITOR_HEIGHT,
  viewerPreset: DEFAULT_VIEWER_PRESET,
  viewerHeight: DEFAULT_VIEWER_HEIGHT,
  showEmptyHelp: true,
  trackDensity: "compact",
  displayMode: "seconds",
  showFilenames: true,
  showThumbnails: true,
  snapEnabled: true,
  playheadFollow: true,
  guidancePriority: "visual_first",
  zoom: 1,
  leftWidth: DEFAULT_LEFT_WIDTH,
  rightWidth: DEFAULT_RIGHT_WIDTH,
};

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function currentViewportWidth() {
  return typeof window !== "undefined" ? window.innerWidth : 1920;
}

function normalizeSnapshot(
  snapshot: Partial<TimelineViewerLayoutSnapshot> | undefined,
): TimelineViewerLayoutSnapshot | undefined {
  if (!snapshot) return undefined;
  return {
    viewerPreset: snapshot.viewerPreset || DEFAULT_VIEWER_PRESET,
    viewerHeight:
      typeof snapshot.viewerHeight === "number" && snapshot.viewerHeight > 0
        ? snapshot.viewerHeight
        : DEFAULT_VIEWER_HEIGHT,
    trackDensity: snapshot.trackDensity || "compact",
    zoom:
      typeof snapshot.zoom === "number" && Number.isFinite(snapshot.zoom)
        ? clamp(snapshot.zoom, 0.5, 3)
        : 1,
  };
}

function normalizeWorkspaceLayout(parsed: Partial<TimelineWorkspaceLayout>): TimelineWorkspaceLayout {
  const preset = parsed.viewerPreset || DEFAULT_VIEWER_PRESET;
  const viewerHeight =
    typeof parsed.viewerHeight === "number" && parsed.viewerHeight > 0
      ? parsed.viewerHeight
      : typeof parsed.monitorHeightPx === "number" && parsed.monitorHeightPx > 0
        ? parsed.monitorHeightPx
        : getPresetViewerRatio(preset, currentViewportWidth());
  const zoom =
    typeof parsed.zoom === "number" && Number.isFinite(parsed.zoom) ? clamp(parsed.zoom, 0.5, 3) : 1;

  return {
    ...DEFAULT_TIMELINE_WORKSPACE,
    ...parsed,
    viewerPreset: preset,
    viewerHeight,
    monitorHeightPx:
      typeof parsed.monitorHeightPx === "number" && parsed.monitorHeightPx > 0
        ? parsed.monitorHeightPx
        : viewerHeight > 1
          ? Math.round(viewerHeight)
          : DEFAULT_MONITOR_HEIGHT,
    trackDensity: parsed.trackDensity || "compact",
    lastNonFullscreenLayout: normalizeSnapshot(parsed.lastNonFullscreenLayout),
    zoom,
    ...clampSidebarWidths(
      typeof parsed.leftWidth === "number" ? parsed.leftWidth : DEFAULT_LEFT_WIDTH,
      typeof parsed.rightWidth === "number" ? parsed.rightWidth : DEFAULT_RIGHT_WIDTH,
    ),
  };
}

export function clampSidebarWidths(
  left: number,
  right: number,
  containerWidth?: number,
): { leftWidth: number; rightWidth: number } {
  let leftWidth = clamp(
    Math.round(Number.isFinite(left) ? left : DEFAULT_LEFT_WIDTH),
    LEFT_PANE_MIN,
    LEFT_PANE_MAX,
  );
  let rightWidth = clamp(
    Math.round(Number.isFinite(right) ? right : DEFAULT_RIGHT_WIDTH),
    RIGHT_PANE_MIN,
    RIGHT_PANE_MAX,
  );
  if (typeof containerWidth === "number" && containerWidth > 0) {
    const maxSides = Math.max(LEFT_PANE_MIN + RIGHT_PANE_MIN, containerWidth - CENTER_PANE_MIN - SIDEBAR_GAP_PX);
    if (leftWidth + rightWidth > maxSides) {
      const overflow = leftWidth + rightWidth - maxSides;
      const shrinkLeft = Math.min(overflow, Math.max(0, leftWidth - LEFT_PANE_MIN));
      leftWidth -= shrinkLeft;
      rightWidth -= Math.min(overflow - shrinkLeft, Math.max(0, rightWidth - RIGHT_PANE_MIN));
    }
  }
  return { leftWidth, rightWidth };
}

export function resetTimelineWorkspaceLayout(): TimelineWorkspaceLayout {
  return saveTimelineWorkspaceLayout({
    ...DEFAULT_TIMELINE_WORKSPACE,
    viewerHeight: getPresetViewerRatio(DEFAULT_VIEWER_PRESET, currentViewportWidth()),
    lastNonFullscreenLayout: undefined,
  });
}

export function getPresetViewerRatio(preset: TimelineViewerPreset, viewportWidth: number): number {
  const config = VIEWER_PRESET_TARGETS[preset];
  const width = clamp(viewportWidth || 1920, 1280, 1920);
  const t = (width - 1280) / (1920 - 1280);
  return clamp(lerp(config.at1280, config.at1920, t), config.min, config.max);
}

export function createTimelineViewerSnapshot(
  layout: Pick<TimelineWorkspaceLayout, "viewerPreset" | "viewerHeight" | "trackDensity" | "zoom">,
): TimelineViewerLayoutSnapshot {
  return {
    viewerPreset: layout.viewerPreset,
    viewerHeight: layout.viewerHeight,
    trackDensity: layout.trackDensity,
    zoom: clamp(layout.zoom, 0.5, 3),
  };
}

export function loadTimelineWorkspaceLayout(): TimelineWorkspaceLayout {
  try {
    const raw = localStorage.getItem(TIMELINE_WORKSPACE_KEY);
    if (!raw) {
      return normalizeWorkspaceLayout({
        ...DEFAULT_TIMELINE_WORKSPACE,
        viewerHeight: getPresetViewerRatio(DEFAULT_VIEWER_PRESET, currentViewportWidth()),
      });
    }
    const parsed = JSON.parse(raw) as Partial<TimelineWorkspaceLayout>;
    return normalizeWorkspaceLayout(parsed);
  } catch {
    return normalizeWorkspaceLayout({
      ...DEFAULT_TIMELINE_WORKSPACE,
      viewerHeight: getPresetViewerRatio(DEFAULT_VIEWER_PRESET, currentViewportWidth()),
    });
  }
}

export function saveTimelineWorkspaceLayout(patch: Partial<TimelineWorkspaceLayout>): TimelineWorkspaceLayout {
  const next = normalizeWorkspaceLayout({ ...loadTimelineWorkspaceLayout(), ...patch });
  try {
    localStorage.setItem(TIMELINE_WORKSPACE_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(TIMELINE_LAYOUT_EVENT, { detail: next }));
  }
  return next;
}

export function viewerHeightBounds(containerHeight: number, viewportWidth: number): { min: number; max: number } {
  const usableHeight = Math.max(containerHeight || 0, 1);
  const floor = usableHeight < 600 ? 220 : MIN_MONITOR_HEIGHT;
  const ratioMin = Math.round(usableHeight * (viewportWidth <= 1280 ? 0.28 : 0.3));
  const min = clamp(ratioMin, floor, Math.max(floor, Math.round(usableHeight * 0.45)));
  const maxByRatio = Math.round(usableHeight * (viewportWidth <= 1280 ? 0.72 : viewportWidth >= 1920 ? 0.78 : 0.75));
  const maxByTracks = Math.max(min, usableHeight - TIMELINE_REGION_MIN_PX);
  const max = Math.max(min, Math.min(maxByRatio, maxByTracks));
  return { min, max };
}

export function clampViewerHeight(px: number, containerHeight: number, viewportWidth: number): number {
  const { min, max } = viewerHeightBounds(containerHeight, viewportWidth);
  return clamp(Math.round(px), min, max);
}

export function resolveViewerHeight(layout: TimelineWorkspaceLayout, containerHeight: number, viewportWidth: number): number {
  const fallbackRatio = getPresetViewerRatio(layout.viewerPreset, viewportWidth);
  const raw = typeof layout.viewerHeight === "number" && layout.viewerHeight > 0 ? layout.viewerHeight : fallbackRatio;
  const px = raw <= 1 ? (containerHeight || 0) * raw : raw;
  return clampViewerHeight(px || DEFAULT_MONITOR_HEIGHT, containerHeight, viewportWidth);
}

export function clampMonitorHeight(px: number, viewportHeight: number, dockSafe = 72): number {
  const containerHeight = Math.max(520, Math.floor(viewportHeight - dockSafe));
  return clampViewerHeight(px, containerHeight, typeof window !== "undefined" ? window.innerWidth : 1440);
}
