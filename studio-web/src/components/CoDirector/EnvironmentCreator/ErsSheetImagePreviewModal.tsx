import { useEffect } from "react";
import { createPortal } from "react-dom";
import "../../library/libraryQuickPreview.css";

export type ErsSheetImagePreview = {
  assetId: string;
  title: string;
  src: string;
  kind: "original" | "snapshot";
};

/**
 * Adept in-app full-size ERS image preview (original master or baked snapshot).
 * Reuses Library quick-preview chrome; Escape / backdrop / Close dismiss.
 */
export function ErsSheetImagePreviewModal({
  preview,
  onClose,
}: {
  preview: ErsSheetImagePreview | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!preview) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [preview, onClose]);

  if (!preview) return null;

  return createPortal(
    <div
      className="library-quick-preview"
      role="dialog"
      aria-modal="true"
      aria-label={preview.title}
      data-testid="ers-sheet-image-preview"
      data-preview-kind={preview.kind}
    >
      <button
        type="button"
        className="library-quick-preview__backdrop"
        aria-label="Close preview"
        data-testid="ers-sheet-image-preview-backdrop"
        onClick={onClose}
      />
      <div
        className="library-quick-preview__panel"
        data-testid="ers-sheet-image-preview-panel"
        onClick={(event) => event.stopPropagation()}
        style={{ maxHeight: "92vh", overflow: "auto" }}
      >
        <button
          type="button"
          className="library-quick-preview__close"
          aria-label="Close preview"
          data-testid="ers-sheet-image-preview-close-x"
          onClick={onClose}
        >
          ×
        </button>
        <div
          className="library-quick-preview__media"
          style={{ maxHeight: "none", overflow: "auto" }}
        >
          <img
            src={preview.src}
            alt={preview.title}
            data-testid="ers-sheet-image-preview-img"
            data-asset-id={preview.assetId}
            style={{
              maxWidth: "min(92vw, 1200px)",
              maxHeight: "78vh",
              width: "auto",
              height: "auto",
              objectFit: "contain",
            }}
          />
        </div>
        <div className="library-quick-preview__meta">
          <h3 className="library-quick-preview__title">{preview.title}</h3>
          <span data-testid="ers-sheet-image-preview-kind">
            {preview.kind === "snapshot" ? "Snapshot (baked)" : "Original"}
          </span>
          <button
            type="button"
            className="secondary"
            data-testid="ers-sheet-image-preview-close"
            onClick={onClose}
            style={{ marginLeft: "auto" }}
          >
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
