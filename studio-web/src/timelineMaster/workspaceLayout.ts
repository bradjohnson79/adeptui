/** Timeline workspace layout prefs — local only, not project media. */

import { clampTimelineZoom } from "./timelineZoom";

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
  leftDrawerOpen: boolean;
  rightDrawerOpen: boolean;
  /** Preview Monitor publish/MAGI action bar. Timeline workspace only. */
  previewPublishBarVisible: boolean;
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
export const DRAWER_HANDLE_WIDTH = 14;
export const DRAWER_SPLITTER_WIDTH = 8;

export type DrawerSide = "left" | "right";

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
  leftDrawerOpen: false,
  rightDrawerOpen: false,
  previewPublishBarVisible: true,
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
        ? clampTimelineZoom(snapshot.zoom)
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
    typeof parsed.zoom === "number" && Number.isFinite(parsed.zoom) ? clampTimelineZoom(parsed.zoom) : 1;

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
    leftDrawerOpen: parsed.leftDrawerOpen === true,
    rightDrawerOpen: parsed.rightDrawerOpen === true,
    previewPublishBarVisible: parsed.previewPublishBarVisible !== false,
    ...clampSidebarWidths(
      typeof parsed.leftWidth === "number" ? parsed.leftWidth : DEFAULT_LEFT_WIDTH,
      typeof parsed.rightWidth === "number" ? parsed.rightWidth : DEFAULT_RIGHT_WIDTH,
    ),
  };
}

export function clampSidebarWidths(
  left: number,
  right: number,
  _containerWidth?: number,
): { leftWidth: number; rightWidth: number } {
  return {
    leftWidth: clamp(
      Math.round(Number.isFinite(left) ? left : DEFAULT_LEFT_WIDTH),
      LEFT_PANE_MIN,
      LEFT_PANE_MAX,
    ),
    rightWidth: clamp(
      Math.round(Number.isFinite(right) ? right : DEFAULT_RIGHT_WIDTH),
      RIGHT_PANE_MIN,
      RIGHT_PANE_MAX,
    ),
  };
}

export function clampDrawerWidth(side: DrawerSide, proposed: number): number {
  const paneMin = side === "left" ? LEFT_PANE_MIN : RIGHT_PANE_MIN;
  const paneMax = side === "left" ? LEFT_PANE_MAX : RIGHT_PANE_MAX;
  const fallback = side === "left" ? DEFAULT_LEFT_WIDTH : DEFAULT_RIGHT_WIDTH;
  return clamp(Math.round(Number.isFinite(proposed) ? proposed : fallback), paneMin, paneMax);
}

/** Track canvas inset so clips never paint under an open drawer. Closed = 0.
 *  CSS must use margin (not padding): overflow clips to the padding box. */
export function timelineWorkspaceInsets(layout: Pick<TimelineWorkspaceLayout, "leftDrawerOpen" | "rightDrawerOpen" | "leftWidth" | "rightWidth">): {
  left: number;
  right: number;
} {
  return {
    left: layout.leftDrawerOpen ? layout.leftWidth : 0,
    right: layout.rightDrawerOpen ? layout.rightWidth : 0,
  };
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
    zoom: clampTimelineZoom(layout.zoom),
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
    // Defer so a persist during TimelineWorkspaceStack render cannot setState
    // on TimelineEditorShell in the same render pass.
    queueMicrotask(() => {
      window.dispatchEvent(new CustomEvent(TIMELINE_LAYOUT_EVENT, { detail: next }));
    });
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

/** MAGI finishing stack — isolated from Timeline Generator Large Viewer. */
export const MAGI_CENTER_SPLIT_KEY = "adept_magi_center_split_v1";
export const MAGI_LAYOUT_EVENT = "adept-magi-center-split";
export const MAGI_SPLIT_MIGRATED_KEY = "adept_magi_center_split_v1_migrated";
/** Resting Preview Monitor share of the MAGI center stack. The splitter sits in the 60–70% band. */
export const MAGI_DEFAULT_VIEWER_RATIO = 0.62;
export const MAGI_VIEWER_MIN_PX = 240;
/**
 * Shortest region under the preview splitter.
 * Leaves the timeline toolbar, zoom, and a scrollable track stack
 * so a 60–70% preview cannot collapse the lanes.
 */
export const MAGI_REGION_MIN_PX = 280;
/** One-time adoption of the 75% rest. Later drags stay where the creator put them. */
export const MAGI_RATIO75_MIGRATED_KEY = "adept_magi_center_split_v1_ratio75";
/** One-time move onto the 60–70% preview band. Later drags stay where the creator put them. */
export const MAGI_PREVIEW_BAND_KEY = "adept_magi_center_split_v1_ratio65";
/** Ratios saved while the old 268px timeline floor clamped the resting split. */
const MAGI_LEGACY_RATIO_CEILING = 0.72;

function magiRatio75Pending(): boolean {
  try {
    return localStorage.getItem(MAGI_RATIO75_MIGRATED_KEY) !== "1";
  } catch {
    return false;
  }
}

function previewBandPending(): boolean {
  try {
    return localStorage.getItem(MAGI_PREVIEW_BAND_KEY) !== "1";
  } catch {
    return false;
  }
}

function inPreviewBand(value: number): boolean {
  return value >= 0.6 && value <= 0.7;
}

/** First read after the 60–70% rest: pull a saved ratio into that band. Does not mark the migration finished. */
function takePreviewBand(value: number): number {
  if (!previewBandPending() || inPreviewBand(value)) return value;
  return MAGI_DEFAULT_VIEWER_RATIO;
}

function finishPreviewBand(): void {
  try {
    localStorage.setItem(MAGI_PREVIEW_BAND_KEY, "1");
  } catch {
    /* ignore */
  }
}

export function magiPreviewHeightStorageKey(projectId?: string | null): string {
  const id = (projectId || "").trim() || "global";
  return `adept-ui.magi.preview-height.${id}`;
}

export function loadMagiProjectPreviewHeightRatio(projectId?: string | null): number | null {
  try {
    const key = magiPreviewHeightStorageKey(projectId);
    const raw = localStorage.getItem(key);
    if (!raw) {
      if (magiRatio75Pending()) localStorage.setItem(MAGI_RATIO75_MIGRATED_KEY, "1");
      finishPreviewBand();
      return null;
    }
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) return null;
    let next = value;
    if (magiRatio75Pending() && value < MAGI_LEGACY_RATIO_CEILING) {
      next = MAGI_DEFAULT_VIEWER_RATIO;
      const centerRaw = localStorage.getItem(MAGI_CENTER_SPLIT_KEY);
      const center = centerRaw ? (JSON.parse(centerRaw) as { viewerHeight?: number }) : null;
      if (typeof center?.viewerHeight !== "number" || center.viewerHeight < MAGI_LEGACY_RATIO_CEILING) {
        localStorage.setItem(MAGI_CENTER_SPLIT_KEY, JSON.stringify({ viewerHeight: MAGI_DEFAULT_VIEWER_RATIO }));
      }
      localStorage.setItem(MAGI_RATIO75_MIGRATED_KEY, "1");
    } else if (magiRatio75Pending()) {
      localStorage.setItem(MAGI_RATIO75_MIGRATED_KEY, "1");
    }
    next = takePreviewBand(next);
    if (next !== value) localStorage.setItem(key, String(next));
    finishPreviewBand();
    return next;
  } catch {
    return null;
  }
}

export function saveMagiProjectPreviewHeightRatio(projectId: string | null | undefined, ratio: number): void {
  try {
    localStorage.setItem(magiPreviewHeightStorageKey(projectId), String(ratio));
  } catch {
    /* ignore */
  }
}

export function magiViewerHeightBounds(containerHeight: number): { min: number; max: number } {
  const usable = Math.max(containerHeight || 0, 1);
  if (usable >= MAGI_VIEWER_MIN_PX + MAGI_REGION_MIN_PX + 8) {
    return { min: MAGI_VIEWER_MIN_PX, max: usable - MAGI_REGION_MIN_PX };
  }
  const min = Math.max(80, Math.round(usable * 0.35));
  return { min, max: Math.max(min, usable - min) };
}

export function clampMagiViewerHeight(px: number, containerHeight: number): number {
  const { min, max } = magiViewerHeightBounds(containerHeight);
  return clamp(Math.round(px), min, max);
}

export function resolveMagiViewerHeight(viewerHeight: number, containerHeight: number): number {
  const raw = typeof viewerHeight === "number" && viewerHeight > 0 ? viewerHeight : MAGI_DEFAULT_VIEWER_RATIO;
  const px = raw <= 1 ? (containerHeight || 0) * raw : raw;
  return clampMagiViewerHeight(px || containerHeight * MAGI_DEFAULT_VIEWER_RATIO, containerHeight);
}

export function loadMagiCenterSplit(): { viewerHeight: number } {
  try {
    const raw = localStorage.getItem(MAGI_CENTER_SPLIT_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as { viewerHeight?: number };
      if (typeof parsed.viewerHeight === "number" && parsed.viewerHeight > 0) {
        let viewerHeight = parsed.viewerHeight;
        if (magiRatio75Pending() && parsed.viewerHeight < MAGI_LEGACY_RATIO_CEILING) {
          viewerHeight = MAGI_DEFAULT_VIEWER_RATIO;
          localStorage.setItem(MAGI_RATIO75_MIGRATED_KEY, "1");
        }
        viewerHeight = takePreviewBand(viewerHeight);
        if (viewerHeight !== parsed.viewerHeight) {
          localStorage.setItem(MAGI_CENTER_SPLIT_KEY, JSON.stringify({ viewerHeight }));
        }
        return { viewerHeight };
      }
    }
  } catch {
    /* fall through */
  }
  try {
    if (!localStorage.getItem(MAGI_SPLIT_MIGRATED_KEY)) {
      localStorage.setItem(MAGI_SPLIT_MIGRATED_KEY, "1");
    }
  } catch {
    /* ignore */
  }
  return { viewerHeight: MAGI_DEFAULT_VIEWER_RATIO };
}

export function saveMagiCenterSplit(patch: { viewerHeight?: number; monitorHeightPx?: number }): {
  viewerHeight: number;
} {
  const current = loadMagiCenterSplit();
  const next = {
    viewerHeight:
      typeof patch.viewerHeight === "number" && patch.viewerHeight > 0
        ? patch.viewerHeight
        : current.viewerHeight,
  };
  try {
    localStorage.setItem(MAGI_CENTER_SPLIT_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") {
    queueMicrotask(() => {
      window.dispatchEvent(new CustomEvent(MAGI_LAYOUT_EVENT, { detail: next }));
    });
  }
  return next;
}

export function resetMagiCenterSplit(projectId?: string | null): { viewerHeight: number } {
  const next = { viewerHeight: MAGI_DEFAULT_VIEWER_RATIO };
  try {
    localStorage.setItem(MAGI_CENTER_SPLIT_KEY, JSON.stringify(next));
    localStorage.removeItem(magiPreviewHeightStorageKey(projectId));
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined") {
    queueMicrotask(() => {
      window.dispatchEvent(new CustomEvent(MAGI_LAYOUT_EVENT, { detail: next }));
    });
  }
  return next;
}
