import { useEffect, useId, useRef, type RefObject } from "react";
import { createPortal } from "react-dom";
import { NewProductionCard, type NewProductionOpts } from "../dashboard/NewProductionCard";
import "./HomeCreateProjectModal.css";

type HomeCreateProjectModalProps = {
  open: boolean;
  busy: boolean;
  error?: string | null;
  initialName?: string;
  formKey: number;
  onClose: () => void;
  onCreate: (opts: NewProductionOpts) => void;
  onSelectTemplate: (templateId: string) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
};

function getFocusable(root: HTMLElement): HTMLElement[] {
  const nodes = root.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
  );
  return Array.from(nodes).filter((el) => !el.hasAttribute("disabled") && el.tabIndex !== -1);
}

export function HomeCreateProjectModal({
  open,
  busy,
  error,
  initialName,
  formKey,
  onClose,
  onCreate,
  onSelectTemplate,
  returnFocusRef,
}: HomeCreateProjectModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = getFocusable(panel);
    (focusable[0] || panel).focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      const items = getFocusable(panelRef.current);
      if (!items.length) {
        event.preventDefault();
        panelRef.current.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    const prevOverscroll = document.documentElement.style.overscrollBehavior;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overscrollBehavior = "none";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
      document.documentElement.style.overscrollBehavior = prevOverscroll;
      returnFocusRef?.current?.focus?.();
    };
  }, [onClose, open, returnFocusRef]);

  if (!open) return null;

  return createPortal(
    <div className="home-create-project-modal" data-testid="create-project-modal">
      <button
        type="button"
        className="home-create-project-modal__backdrop"
        aria-label="Close create project dialog"
        data-testid="create-project-modal-backdrop"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        className="home-create-project-modal__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="create-project-modal-panel"
      >
        <div className="home-create-project-modal__header">
          <div>
            <p className="eyebrow home-create-project-modal__eyebrow">Create project</p>
            <h2 id={titleId}>Create a Project</h2>
          </div>
          <button
            type="button"
            className="ui-btn ui-btn--icon home-create-project-modal__close"
            aria-label="Close create project dialog"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="home-create-project-modal__content">
          <NewProductionCard
            key={formKey}
            busy={busy}
            error={error}
            initialName={initialName}
            onCancel={onClose}
            onSelectTemplate={onSelectTemplate}
            onCreate={onCreate}
          />
        </div>
      </div>
    </div>,
    document.body,
  );
}
