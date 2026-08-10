import { useEffect, useId, useRef, type ReactNode, type RefObject } from "react";
import "./button.css";
import "./drawer.css";

export type DrawerProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Element that opened the drawer — focus returns here on close. */
  returnFocusRef?: RefObject<HTMLElement | null>;
  side?: "left" | "right";
  testId?: string;
  panelClassName?: string;
  bodyClassName?: string;
};

function getFocusable(root: HTMLElement): HTMLElement[] {
  const nodes = root.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  return Array.from(nodes).filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  returnFocusRef,
  side = "left",
  testId = "ui-drawer",
  panelClassName,
  bodyClassName,
}: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = getFocusable(panel);
    (focusable[0] || panel).focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const items = getFocusable(panelRef.current);
      if (!items.length) {
        e.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      returnFocusRef?.current?.focus?.();
    };
  }, [open, onClose, returnFocusRef]);

  if (!open) return null;

  return (
    <div className="ui-drawer-root" data-testid={testId}>
      <button
        type="button"
        className="ui-drawer-backdrop"
        aria-label="Close menu"
        data-testid={`${testId}-backdrop`}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        className={["ui-drawer-panel", `side-${side}`, panelClassName].filter(Boolean).join(" ")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid={`${testId}-panel`}
      >
        <div className="ui-drawer-header">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="ui-btn ui-btn--icon" aria-label="Close navigation" onClick={onClose}>
            ×
          </button>
        </div>
        <div className={["ui-drawer-body", bodyClassName].filter(Boolean).join(" ")}>{children}</div>
      </div>
    </div>
  );
}
