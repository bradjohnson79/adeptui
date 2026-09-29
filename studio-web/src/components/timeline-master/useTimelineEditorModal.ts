import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from "react";

/** Focus trap + Escape=Cancel + stop Timeline hotkeys from seeing modal keystrokes. */
export function useTimelineEditorModal(open: boolean, onCancel: () => void, initialSelector = "textarea, input, select, button") {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;
  const wasOpenRef = useRef(false);

  useEffect(() => {
    if (!open) {
      wasOpenRef.current = false;
      return;
    }
    const root = dialogRef.current;
    if (!root) return;

    // Focus the initial field only when the modal newly opens, or when focus is
    // outside the dialog. Never steal focus from Prompt Name / other fields after
    // an autosave rerender that recreates an unstable onCancel identity.
    const active = document.activeElement;
    const alreadyInside = Boolean(active && root.contains(active));
    const justOpened = !wasOpenRef.current;
    wasOpenRef.current = true;
    if (justOpened || !alreadyInside) {
      const initial = root.querySelector<HTMLElement>(initialSelector);
      if (initial && document.activeElement !== initial) {
        initial.focus();
      }
    }

    const focusables = () =>
      Array.from(
        root.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);

    const onKeyDown = (event: KeyboardEvent) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    root.addEventListener("keydown", onKeyDown);
    return () => root.removeEventListener("keydown", onKeyDown);
  }, [initialSelector, open]);

  const stopHotkeys = (event: ReactKeyboardEvent) => {
    event.stopPropagation();
  };

  return { dialogRef, stopHotkeys };
}
