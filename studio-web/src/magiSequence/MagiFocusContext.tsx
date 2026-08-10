import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type FocusEvent,
  type ReactNode,
} from "react";
import { MAGI_FOCUS_ATTR, isTypingTarget, resolveEffectiveFocusRegion } from "./focus";
import type { MagiFocusRegion } from "./types";

type MagiFocusContextValue = {
  focusRegion: MagiFocusRegion;
  effectiveRegion: MagiFocusRegion;
  setFocusRegion: (region: MagiFocusRegion) => void;
  bindRegionProps: (region: MagiFocusRegion) => {
    [MAGI_FOCUS_ATTR]: MagiFocusRegion;
    tabIndex: number;
    onMouseDown: () => void;
    onFocusCapture: (event: FocusEvent) => void;
  };
};

const MagiFocusContext = createContext<MagiFocusContextValue | null>(null);

function blurTypingTarget() {
  if (isTypingTarget(document.activeElement) && document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }
}

export function MagiFocusProvider({ children }: { children: ReactNode }) {
  const [focusRegion, setFocusRegionState] = useState<MagiFocusRegion>("timeline");
  const [lastSurface, setLastSurface] = useState<MagiFocusRegion>("timeline");
  const [, setFocusVersion] = useState(0);

  const setFocusRegion = useCallback((region: MagiFocusRegion) => {
    setFocusRegionState(region);
    setFocusVersion((value) => value + 1);
    if (region !== "text_input" && region !== "modal" && region !== "none") {
      setLastSurface(region);
    }
  }, []);

  const bindRegionProps = useCallback(
    (region: MagiFocusRegion) => ({
      [MAGI_FOCUS_ATTR]: region,
      tabIndex: 0 as const,
      onMouseDown: () => {
        if (region !== "text_input") {
          blurTypingTarget();
        }
        setFocusRegion(region);
      },
      onFocusCapture: (event: FocusEvent) => {
        if (isTypingTarget(event.target)) {
          setFocusRegion("text_input");
          return;
        }
        setFocusRegion(region);
      },
    }),
    [setFocusRegion],
  );

  const effectiveRegion = resolveEffectiveFocusRegion(focusRegion);

  const value = useMemo(
    () => ({
      focusRegion: effectiveRegion === "text_input" || effectiveRegion === "modal"
        ? effectiveRegion
        : focusRegion || lastSurface,
      effectiveRegion,
      setFocusRegion,
      bindRegionProps,
    }),
    [bindRegionProps, effectiveRegion, focusRegion, lastSurface, setFocusRegion],
  );

  return (
    <MagiFocusContext.Provider value={value}>
      <div data-magi-focus-region={value.effectiveRegion} data-testid="magi-focus-root">
        {children}
      </div>
    </MagiFocusContext.Provider>
  );
}

export function useMagiFocus(): MagiFocusContextValue {
  const ctx = useContext(MagiFocusContext);
  if (!ctx) {
    throw new Error("useMagiFocus must be used within MagiFocusProvider");
  }
  return ctx;
}
