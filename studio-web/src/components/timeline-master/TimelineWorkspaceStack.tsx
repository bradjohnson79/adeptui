import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  DEFAULT_LEFT_WIDTH,
  DEFAULT_RIGHT_WIDTH,
  DEFAULT_VIEWER_PRESET,
  TIMELINE_LAYOUT_EVENT,
  clampViewerHeight,
  createTimelineViewerSnapshot,
  getPresetViewerRatio,
  loadProjectPreviewHeightRatio,
  loadTimelineWorkspaceLayout,
  resolveViewerHeight,
  saveProjectPreviewHeightRatio,
  saveTimelineWorkspaceLayout,
  viewerHeightBounds,
  type TimelineWorkspaceLayout,
  type TimelineViewerPreset,
} from "../../timelineMaster/workspaceLayout";
import { TIMELINE_FOCUS_EVENT, type TimelineFocusRequest } from "../../timelineMaster/timelineFocus";
import "../../styles/timeline-master/timeline-workspace.css";

/**
 * Vertically stacked Preview Monitor + Timeline workspace with persisted resize.
 * Preview grows/shrinks via the divider; the track region absorbs height and scrolls.
 */
export function TimelineWorkspaceStack({
  monitor,
  timeline,
  extraControls,
  projectId,
}: {
  monitor: ReactNode;
  timeline: ReactNode;
  extraControls?: ReactNode;
  projectId?: string | null;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const dividerRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState(() => {
    const base = loadTimelineWorkspaceLayout();
    const projectRatio = loadProjectPreviewHeightRatio(projectId);
    if (projectRatio != null) {
      return { ...base, viewerHeight: projectRatio };
    }
    return base;
  });
  const [containerSize, setContainerSize] = useState({ width: 1440, height: 900 });
  const [fullscreenViewer, setFullscreenViewer] = useState(false);
  /** Live height while dragging — avoids persisting every pointermove. */
  const [liveHeightPx, setLiveHeightPx] = useState<number | null>(null);
  const dragRef = useRef<{
    active: boolean;
    pointerId: number | null;
    startY: number;
    startHeight: number;
  }>({ active: false, pointerId: null, startY: 0, startHeight: 0 });
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  useEffect(() => {
    const projectRatio = loadProjectPreviewHeightRatio(projectId);
    if (projectRatio == null) return;
    setLayout((prev) =>
      prev.viewerHeight === projectRatio ? prev : { ...prev, viewerHeight: projectRatio },
    );
  }, [projectId]);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;

    const measure = () => {
      const rect = node.getBoundingClientRect();
      setContainerSize({
        width: Math.max(1, Math.round(rect.width)),
        height: Math.max(1, Math.round(rect.height)),
      });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const bounds = useMemo(
    () => viewerHeightBounds(containerSize.height, containerSize.width),
    [containerSize.height, containerSize.width],
  );

  const resolvedHeightPx = useMemo(
    () => resolveViewerHeight(layout, containerSize.height, containerSize.width),
    [containerSize.height, containerSize.width, layout],
  );

  const viewerHeightPx = liveHeightPx ?? resolvedHeightPx;

  const persistLayout = useCallback((patch: Parameters<typeof saveTimelineWorkspaceLayout>[0]) => {
    const next = saveTimelineWorkspaceLayout(patch);
    setLayout(next);
    return next;
  }, []);

  const commitHeight = useCallback(
    (px: number, options?: { persistProject?: boolean }) => {
      if (fullscreenViewer) return resolvedHeightPx;
      const next = clampViewerHeight(px, containerSize.height, containerSize.width);
      const ratio = Number((next / Math.max(containerSize.height, 1)).toFixed(4));
      persistLayout({ viewerHeight: ratio, monitorHeightPx: next });
      if (options?.persistProject !== false) {
        saveProjectPreviewHeightRatio(projectId, ratio);
      }
      return next;
    },
    [containerSize.height, containerSize.width, fullscreenViewer, persistLayout, projectId, resolvedHeightPx],
  );

  useEffect(() => {
    const onLayout = (event: Event) => {
      const detail = (event as CustomEvent<TimelineWorkspaceLayout>).detail;
      setLayout(detail || loadTimelineWorkspaceLayout());
    };
    window.addEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
    return () => window.removeEventListener(TIMELINE_LAYOUT_EVENT, onLayout as EventListener);
  }, []);

  // Clamp stored height when the workspace shrinks (inspector open, window resize, etc.).
  useEffect(() => {
    if (fullscreenViewer || liveHeightPx != null) return;
    const clamped = clampViewerHeight(resolvedHeightPx, containerSize.height, containerSize.width);
    if (clamped !== resolvedHeightPx) {
      const ratio = Number((clamped / Math.max(containerSize.height, 1)).toFixed(4));
      persistLayout({ viewerHeight: ratio, monitorHeightPx: clamped });
      saveProjectPreviewHeightRatio(projectId, ratio);
    }
  }, [
    containerSize.height,
    containerSize.width,
    fullscreenViewer,
    liveHeightPx,
    persistLayout,
    projectId,
    resolvedHeightPx,
  ]);

  const applyPreset = useCallback(
    (preset: TimelineViewerPreset) => {
      if (fullscreenViewer) {
        setFullscreenViewer(false);
      }
      const targetRatio = Number(getPresetViewerRatio(preset, containerSize.width).toFixed(4));
      const resolved = clampViewerHeight(
        targetRatio * Math.max(containerSize.height, 1),
        containerSize.height,
        containerSize.width,
      );
      const ratio = Number((resolved / Math.max(containerSize.height, 1)).toFixed(4));
      persistLayout({
        viewerPreset: preset,
        viewerHeight: ratio,
        monitorHeightPx: resolved,
      });
      saveProjectPreviewHeightRatio(projectId, ratio);
    },
    [containerSize.height, containerSize.width, fullscreenViewer, persistLayout, projectId],
  );

  const fitToPreset = useCallback(() => {
    const next = resolveViewerHeight(
      {
        ...layoutRef.current,
        viewerHeight: 0,
      },
      containerSize.height,
      containerSize.width,
    );
    commitHeight(next);
  }, [commitHeight, containerSize.height, containerSize.width]);

  const resetLayout = useCallback(() => {
    setFullscreenViewer(false);
    setLiveHeightPx(null);
    const targetRatio = Number(getPresetViewerRatio(DEFAULT_VIEWER_PRESET, containerSize.width).toFixed(4));
    const resolved = clampViewerHeight(
      targetRatio * Math.max(containerSize.height, 1),
      containerSize.height,
      containerSize.width,
    );
    const ratio = Number((resolved / Math.max(containerSize.height, 1)).toFixed(4));
    persistLayout({
      viewerPreset: DEFAULT_VIEWER_PRESET,
      viewerHeight: ratio,
      monitorHeightPx: resolved,
      trackDensity: "compact",
      zoom: 1,
      lastNonFullscreenLayout: undefined,
      leftWidth: DEFAULT_LEFT_WIDTH,
      rightWidth: DEFAULT_RIGHT_WIDTH,
      leftDrawerOpen: true,
      rightDrawerOpen: true,
    });
    saveProjectPreviewHeightRatio(projectId, ratio);
  }, [containerSize.height, containerSize.width, persistLayout, projectId]);

  const exitFullscreen = useCallback(() => {
    const latest = loadTimelineWorkspaceLayout();
    const snapshot = latest.lastNonFullscreenLayout;
    setFullscreenViewer(false);
    setLiveHeightPx(null);
    if (snapshot) {
      persistLayout({
        viewerPreset: snapshot.viewerPreset,
        viewerHeight: snapshot.viewerHeight,
        trackDensity: snapshot.trackDensity,
        zoom: snapshot.zoom,
      });
      saveProjectPreviewHeightRatio(projectId, snapshot.viewerHeight <= 1 ? snapshot.viewerHeight : Number((snapshot.viewerHeight / Math.max(containerSize.height, 1)).toFixed(4)));
      return;
    }
    fitToPreset();
  }, [containerSize.height, fitToPreset, persistLayout, projectId]);

  const enterFullscreen = useCallback(() => {
    persistLayout({ lastNonFullscreenLayout: createTimelineViewerSnapshot(layoutRef.current) });
    setLiveHeightPx(null);
    setFullscreenViewer(true);
  }, [persistLayout]);

  useEffect(() => {
    const onFocus = (event: Event) => {
      const detail = (event as CustomEvent<TimelineFocusRequest>).detail;
      if (!detail) return;
      if (detail.layoutReset) {
        resetLayout();
        return;
      }
      if (detail.fitViewer) {
        fitToPreset();
      }
      if (detail.viewerPreset) {
        applyPreset(detail.viewerPreset);
      }
      if (detail.trackDensity) {
        persistLayout({ trackDensity: detail.trackDensity });
      }
      if (detail.fullscreen === true) {
        if (!fullscreenViewer) enterFullscreen();
      } else if (detail.fullscreen === false) {
        if (fullscreenViewer) exitFullscreen();
      }
    };
    window.addEventListener(TIMELINE_FOCUS_EVENT, onFocus as EventListener);
    return () => window.removeEventListener(TIMELINE_FOCUS_EVENT, onFocus as EventListener);
  }, [applyPreset, enterFullscreen, exitFullscreen, fitToPreset, fullscreenViewer, persistLayout, resetLayout]);

  useEffect(() => {
    if (!fullscreenViewer) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      exitFullscreen();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [exitFullscreen, fullscreenViewer]);

  const endDrag = useCallback(
    (pointerId?: number) => {
      const state = dragRef.current;
      if (!state.active) return;
      state.active = false;
      const el = dividerRef.current;
      if (el && pointerId != null) {
        try {
          el.releasePointerCapture(pointerId);
        } catch {
          /* already released */
        }
      }
      state.pointerId = null;
      setLiveHeightPx((current) => {
        if (current != null) {
          commitHeight(current);
        }
        return null;
      });
    },
    [commitHeight],
  );

  useEffect(() => {
    return () => {
      dragRef.current.active = false;
      dragRef.current.pointerId = null;
    };
  }, []);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (fullscreenViewer || e.button !== 0) return;
    e.preventDefault();
    dragRef.current = {
      active: true,
      pointerId: e.pointerId,
      startY: e.clientY,
      startHeight: viewerHeightPx,
    };
    setLiveHeightPx(viewerHeightPx);
    dividerRef.current?.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const state = dragRef.current;
    if (!state.active || state.pointerId !== e.pointerId) return;
    // Natural top-pane math: pointer down enlarges preview; pointer up shrinks it.
    const next = clampViewerHeight(
      state.startHeight + (e.clientY - state.startY),
      containerSize.height,
      containerSize.width,
    );
    setLiveHeightPx(next);
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== e.pointerId) return;
    endDrag(e.pointerId);
  };

  const onPointerCancel = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current.pointerId !== e.pointerId) return;
    endDrag(e.pointerId);
  };

  const onLostPointerCapture = () => {
    if (!dragRef.current.active) return;
    endDrag();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && fullscreenViewer) {
      e.preventDefault();
      exitFullscreen();
      return;
    }
    if (fullscreenViewer) return;
    const step = e.shiftKey ? 40 : 16;
    // ArrowUp moves the splitter up → smaller preview; ArrowDown enlarges (ARIA window splitter).
    if (e.key === "ArrowUp") {
      e.preventDefault();
      commitHeight(viewerHeightPx - step);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      commitHeight(viewerHeightPx + step);
    } else if (e.key === "Home") {
      e.preventDefault();
      commitHeight(bounds.min);
    } else if (e.key === "End") {
      e.preventDefault();
      commitHeight(bounds.max);
    }
  };

  return (
    <div
      className={`timeline-workspace-stack${fullscreenViewer ? " is-fullscreen-viewer" : ""}`}
      ref={rootRef}
      data-testid="timeline-workspace-stack"
      onKeyDown={onKeyDown}
    >
      <div
        className="timeline-workspace-monitor"
        style={fullscreenViewer ? undefined : { height: viewerHeightPx, flex: `0 0 ${viewerHeightPx}px` }}
        data-testid="timeline-workspace-monitor"
        data-preview-height={Math.round(viewerHeightPx)}
      >
        {extraControls ? (
          <div className="timeline-workspace-monitor__controls" role="toolbar" aria-label="Preview extra controls">
            {extraControls}
          </div>
        ) : null}
        <div className="timeline-workspace-monitor__body">{monitor}</div>
      </div>
      {!fullscreenViewer ? (
        <>
          <div
            ref={dividerRef}
            className={`timeline-workspace-divider${liveHeightPx != null ? " is-active" : ""}`}
            role="separator"
            aria-orientation="horizontal"
            aria-valuenow={Math.round(viewerHeightPx)}
            aria-valuemin={bounds.min}
            aria-valuemax={bounds.max}
            aria-label="Resize Preview Monitor. Use arrow keys to adjust height."
            tabIndex={0}
            data-testid="timeline-monitor-divider"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerCancel}
            onLostPointerCapture={onLostPointerCapture}
            onDoubleClick={fitToPreset}
            onKeyDown={onKeyDown}
          >
            <span className="timeline-workspace-divider__grip" aria-hidden />
          </div>
          <div className="timeline-workspace-tracks" data-testid="timeline-workspace-tracks">
            {timeline}
          </div>
        </>
      ) : null}
    </div>
  );
}
