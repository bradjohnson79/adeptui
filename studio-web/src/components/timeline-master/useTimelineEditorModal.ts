import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from "react";

/** Focus trap + Escape=Cancel + stop Timeline hotkeys from seeing modal keystrokes. */
export function useTimelineEditorModal(open: boolean, onCancel: () => void, initialSelector = "textarea, input, select, button") {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const root = dialogRef.current;
    if (!root) return;
    const initial = root.querySelector<HTMLElement>(initialSelector);
    initial?.focus();

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
        onCancel();
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
  }, [initialSelector, onCancel, open]);

  const stopHotkeys = (event: ReactKeyboardEvent) => {
    event.stopPropagation();
  };

  return { dialogRef, stopHotkeys };
}
