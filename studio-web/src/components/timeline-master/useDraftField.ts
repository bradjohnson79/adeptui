import { useEffect, useRef, useState } from "react";

export type ExternalDraftSync = {
  focused: boolean;
  dirty: boolean;
  latest: string;
  persisted: string;
  externalSeen: string;
  externalValue: string;
};

/**
 * Keep a flushed prompt when the parent snapshot is still the pre-edit text.
 * Blur-then-OK otherwise rewinds the textarea before the save round-trips.
 */
export function shouldAdoptExternalDraft(state: ExternalDraftSync): boolean {
  if (state.focused || state.dirty) return false;
  if (state.externalValue === state.latest) return false;
  if (
    state.latest === state.persisted &&
    state.persisted !== state.externalSeen &&
    state.externalValue === state.externalSeen
  ) {
    return false;
  }
  return true;
}

/**
 * Stable draft field for Timeline Inspector / Prompt editors.
 * Local value while focused; syncs from props when not focused; persists on blur, idle, or unmount.
 */
export function useDraftField(
  externalValue: string,
  persist: (value: string) => void | Promise<void>,
  opts?: { idleMs?: number; identity?: string },
) {
  const idleMs = opts?.idleMs ?? 400;
  const identity = opts?.identity ?? "";
  const [value, setValue] = useState(externalValue);
  const [isDirty, setIsDirty] = useState(false);
  const focusedRef = useRef(false);
  const dirtyRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const latestRef = useRef(externalValue);
  const persistedRef = useRef(externalValue);
  const externalSeenRef = useRef(externalValue);
  const persistRef = useRef(persist);
  persistRef.current = persist;

  useEffect(() => {
    // Reset draft when selection/identity changes. Do not persist the empty
    // first paint that can land before the shared Timed Prompt snapshot hydrates.
    focusedRef.current = false;
    dirtyRef.current = false;
    setIsDirty(false);
    setValue(externalValue);
    latestRef.current = externalValue;
    persistedRef.current = externalValue;
    externalSeenRef.current = externalValue;
  }, [identity]);

  useEffect(() => {
    const adopt = shouldAdoptExternalDraft({
      focused: focusedRef.current,
      dirty: dirtyRef.current,
      latest: latestRef.current,
      persisted: persistedRef.current,
      externalSeen: externalSeenRef.current,
      externalValue,
    });
    if (!adopt) {
      if (!focusedRef.current && !dirtyRef.current && externalValue === latestRef.current) {
        externalSeenRef.current = externalValue;
        persistedRef.current = externalValue;
      }
      return;
    }
    externalSeenRef.current = externalValue;
    setValue(externalValue);
    latestRef.current = externalValue;
    persistedRef.current = externalValue;
    dirtyRef.current = false;
    setIsDirty(false);
  }, [externalValue]);

  const flush = () => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (!dirtyRef.current) return;
    const next = latestRef.current;
    if (next === persistedRef.current) {
      dirtyRef.current = false;
      setIsDirty(false);
      return;
    }
    persistedRef.current = next;
    dirtyRef.current = false;
    setIsDirty(false);
    void persistRef.current(next);
  };

  const flushRef = useRef(flush);
  flushRef.current = flush;

  useEffect(
    () => () => {
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
      // Persist pending Timed Prompt / Inspector edits if the editor unmounts
      // before blur/idle (modal close, selection change).
      flushRef.current();
    },
    [],
  );

  const onChange = (next: string) => {
    focusedRef.current = true;
    dirtyRef.current = true;
    setIsDirty(true);
    latestRef.current = next;
    setValue(next);
    if (timerRef.current != null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      flush();
    }, idleMs);
  };

  const onFocus = () => {
    focusedRef.current = true;
  };

  const onBlur = () => {
    focusedRef.current = false;
    flush();
  };

  return { value, onChange, onFocus, onBlur, flush, isDirty };
}
