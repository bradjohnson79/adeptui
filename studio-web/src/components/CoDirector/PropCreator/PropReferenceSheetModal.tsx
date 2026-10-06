import { useEffect } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import "../../library/libraryQuickPreview.css";

type Props = {
  open: boolean;
  assetId: string;
  projectId: string;
  title?: string;
  onClose: () => void;
};

/** Adept lightbox for Prop Reference Sheet — X corner close, Esc, backdrop. */
export function PropReferenceSheetModal({ open, assetId, projectId, title, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !assetId) return null;

  const src = api.assetUrl(assetId, assetId, projectId);
  const label = title || "Prop Reference Sheet";

  return createPortal(
    <div
      className="library-quick-preview"
      role="dialog"
      aria-modal="true"
      aria-label={label}
      data-testid="prop-prs-modal"
    >
      <button
        type="button"
        className="library-quick-preview__backdrop"
        aria-label="Close Prop Reference Sheet"
        data-testid="prop-prs-modal-backdrop"
        onClick={onClose}
      />
      <div
        className="library-quick-preview__panel"
        data-testid="prop-prs-modal-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="library-quick-preview__close"
          aria-label="Close Prop Reference Sheet"
          data-testid="prop-prs-modal-close"
          onClick={onClose}
        >
          ×
        </button>
        <div className="library-quick-preview__media">
          {src ? (
            <img src={src} alt={label} data-testid="prop-prs-modal-image" />
          ) : (
            <p className="muted">Prop Reference Sheet unavailable.</p>
          )}
        </div>
        <p className="library-quick-preview__meta" data-testid="prop-prs-modal-title">
          {label}
        </p>
      </div>
    </div>,
    document.body,
  );
}
