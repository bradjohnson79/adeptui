import { useEffect, useRef, useState } from "react";

/**
 * Stable draft field for Timeline Inspector / Prompt editors.
 * Local value while focused; syncs from props when not focused; persists on blur or idle.
 */
export function useDraftField(
  externalValue: string,
  persist: (value: string) => void | Promise<void>,
  opts?: { idleMs?: number; identity?: string },
) {
  const idleMs = opts?.idleMs ?? 400;
  const identity = opts?.identity ?? "";
  const [value, setValue] = useState(externalValue);
  const focusedRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const latestRef = useRef(externalValue);
  const persistRef = useRef(persist);
  persistRef.current = persist;

  useEffect(() => {
    // Reset draft when selection/identity changes
    focusedRef.current = false;
    setValue(externalValue);
    latestRef.current = externalValue;
  }, [identity]);

  useEffect(() => {
    if (focusedRef.current) return;
    setValue(externalValue);
    latestRef.current = externalValue;
  }, [externalValue]);

  useEffect(
    () => () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const flush = () => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const next = latestRef.current;
    void persistRef.current(next);
  };

  const onChange = (next: string) => {
    focusedRef.current = true;
    latestRef.current = next;
    setValue(next);
    if (timerRef.current != null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      void persistRef.current(latestRef.current);
    }, idleMs);
  };

  const onFocus = () => {
    focusedRef.current = true;
  };

  const onBlur = () => {
    focusedRef.current = false;
    flush();
  };

  return { value, onChange, onFocus, onBlur };
}
