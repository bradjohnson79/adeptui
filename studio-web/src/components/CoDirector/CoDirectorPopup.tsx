import { useEffect, useRef } from "react";
import { CoDirectorShell } from "./CoDirectorShell";
import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorPopup() {
  const { open, displayMode, closeSession, draft, attachments, busy } = useCoDirectorSession();
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open || displayMode !== "popup") return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => {
      panelRef.current?.querySelector<HTMLTextAreaElement>("textarea")?.focus();
    }, 0);
    return () => {
      window.clearTimeout(timer);
      previouslyFocused.current?.focus?.();
    };
  }, [open, displayMode]);

  useEffect(() => {
    if (!open || displayMode !== "popup") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (busy) return;
      if ((draft.trim() || attachments.length) && !window.confirm("Close Co-Director? Your draft will be kept.")) {
        return;
      }
      closeSession();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [attachments.length, busy, closeSession, displayMode, draft, open]);

  if (!open || displayMode !== "popup") return null;

  return (
    <div
      ref={panelRef}
      className="codirector-popup"
      role="dialog"
      aria-modal="false"
      aria-label="Co-Director"
      data-testid="codirector-popup"
    >
      <CoDirectorShell mode="popup" onClose={closeSession} />
    </div>
  );
}
