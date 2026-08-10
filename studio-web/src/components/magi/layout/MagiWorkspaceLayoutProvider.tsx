import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  applyPreset,
  clampLeftWidth,
  clampRightWidth,
  clampTimelineHeight,
  DEFAULT_LAYOUT,
  loadMagiLayout,
  saveMagiLayout,
  type MagiPaneId,
  type MagiWorkspaceLayoutV1,
  type MagiWorkspacePreset,
} from "./MagiLayoutPersistence";

type MagiLayoutContextValue = {
  layout: MagiWorkspaceLayoutV1;
  upperWidth: number;
  setAccordion: (id: string, open: boolean) => void;
  setLeftWidth: (n: number) => void;
  setRightWidth: (n: number) => void;
  setTimelineHeight: (n: number) => void;
  toggleLeftDock: () => void;
  toggleRightDock: () => void;
  toggleTimeline: () => void;
  movePane: (pane: MagiPaneId, side: "left" | "right") => void;
  reorderPane: (pane: MagiPaneId, direction: "up" | "down") => void;
  applyWorkspacePreset: (preset: MagiWorkspacePreset) => void;
  resetWorkspace: () => void;
  setRenderQueueOpen: (open: boolean) => void;
  compactNotice: boolean;
};

const MagiLayoutContext = createContext<MagiLayoutContextValue | null>(null);

function persist(next: MagiWorkspaceLayoutV1) {
  saveMagiLayout(next);
  return next;
}

export function MagiWorkspaceLayoutProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<MagiWorkspaceLayoutV1>(() => loadMagiLayout());
  const [upperWidth, setUpperWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 1400
  );
  const [viewportH, setViewportH] = useState(
    typeof window !== "undefined" ? window.innerHeight : 900
  );
  const [userCollapsedLeft, setUserCollapsedLeft] = useState(false);
  const [userCollapsedRight, setUserCollapsedRight] = useState(false);

  useEffect(() => {
    const onResize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      setUpperWidth(w);
      setViewportH(h);
      setLayout((prev) => {
        let next = {
          ...prev,
          leftDockWidth: clampLeftWidth(prev.leftDockWidth, w),
          rightDockWidth: clampRightWidth(prev.rightDockWidth, w),
          timelineHeight: clampTimelineHeight(prev.timelineHeight, h),
        };
        // 900–1099: auto-collapse one dock; prefs recoverable
        if (w < 900) {
          next = { ...next, leftDockCollapsed: true, rightDockCollapsed: true };
        } else if (w < 1100) {
          if (!userCollapsedRight) next = { ...next, rightDockCollapsed: true };
        } else if (w < 1440) {
          next = {
            ...next,
            leftDockWidth: clampLeftWidth(Math.min(next.leftDockWidth, 260), w),
            rightDockWidth: clampRightWidth(Math.min(next.rightDockWidth, 280), w),
          };
        }
        return persist(next);
      });
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [userCollapsedLeft, userCollapsedRight]);

  const update = useCallback((fn: (prev: MagiWorkspaceLayoutV1) => MagiWorkspaceLayoutV1) => {
    setLayout((prev) => persist(fn(prev)));
  }, []);

  const value = useMemo<MagiLayoutContextValue>(
    () => ({
      layout,
      upperWidth,
      compactNotice: upperWidth < 900,
      setAccordion: (id, open) =>
        update((p) => ({
          ...p,
          activePreset: "custom",
          accordionState: { ...p.accordionState, [id]: open },
        })),
      setLeftWidth: (n) =>
        update((p) => ({
          ...p,
          activePreset: "custom",
          leftDockWidth: clampLeftWidth(n, upperWidth),
        })),
      setRightWidth: (n) =>
        update((p) => ({
          ...p,
          activePreset: "custom",
          rightDockWidth: clampRightWidth(n, upperWidth),
        })),
      setTimelineHeight: (n) =>
        update((p) => ({
          ...p,
          activePreset: "custom",
          timelineHeight: clampTimelineHeight(n, viewportH),
        })),
      toggleLeftDock: () => {
        setUserCollapsedLeft(true);
        update((p) => ({ ...p, activePreset: "custom", leftDockCollapsed: !p.leftDockCollapsed }));
      },
      toggleRightDock: () => {
        setUserCollapsedRight(true);
        update((p) => ({ ...p, activePreset: "custom", rightDockCollapsed: !p.rightDockCollapsed }));
      },
      toggleTimeline: () =>
        update((p) => ({ ...p, activePreset: "custom", timelineCollapsed: !p.timelineCollapsed })),
      movePane: (pane, side) =>
        update((p) => {
          const left = p.leftPaneOrder.filter((x) => x !== pane);
          const right = p.rightPaneOrder.filter((x) => x !== pane);
          if (side === "left") left.push(pane);
          else right.push(pane);
          return { ...p, activePreset: "custom", leftPaneOrder: left, rightPaneOrder: right };
        }),
      reorderPane: (pane, direction) =>
        update((p) => {
          const moveIn = (arr: MagiPaneId[]) => {
            const i = arr.indexOf(pane);
            if (i < 0) return arr;
            const j = direction === "up" ? i - 1 : i + 1;
            if (j < 0 || j >= arr.length) return arr;
            const next = [...arr];
            [next[i], next[j]] = [next[j], next[i]];
            return next;
          };
          return {
            ...p,
            activePreset: "custom",
            leftPaneOrder: moveIn(p.leftPaneOrder),
            rightPaneOrder: moveIn(p.rightPaneOrder),
          };
        }),
      applyWorkspacePreset: (preset) => update((p) => applyPreset(preset, p)),
      resetWorkspace: () =>
        update(() => ({ ...DEFAULT_LAYOUT, accordionState: { ...DEFAULT_LAYOUT.accordionState } })),
      setRenderQueueOpen: (open) => update((p) => ({ ...p, renderQueueOpen: open })),
    }),
    [layout, update, upperWidth, viewportH]
  );

  return <MagiLayoutContext.Provider value={value}>{children}</MagiLayoutContext.Provider>;
}

export function useMagiLayout(): MagiLayoutContextValue {
  const ctx = useContext(MagiLayoutContext);
  if (!ctx) throw new Error("useMagiLayout requires MagiWorkspaceLayoutProvider");
  return ctx;
}
