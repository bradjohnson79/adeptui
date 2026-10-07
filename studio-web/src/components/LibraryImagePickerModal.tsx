/**
 * Generic single-select modal for choosing a Library image as a key frame
 * (First Frame / Middle / Last). Parent owns persistence; this component
 * only reports the selection via onPick.
 *
 * Uses the project image assets already loaded client-side (the `images` prop)
 * — no extra API fetch — and renders real thumbnails via api.assetUrl.
 *
 * Replaces the old @-tag dropdown on the 1 Frame / 3 Frame surfaces with a
 * visual Library browser (creator-first: see the pictures, then pick one).
 */
import { useEffect, useId, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { Asset } from "../types";
import { api } from "../api";
import "./LibraryImagePickerModal.css";

type Props = {
  /** Project image assets to browse (already filtered to kind === "image"). */
  images: Asset[];
  /** Currently selected asset id (highlighted in the grid). */
  currentAssetId?: string | null;
  /** Dialog title, e.g. "Choose a First Frame". */
  title?: string;
  /** Confirm button label, e.g. "Use this frame". */
  confirmLabel?: string;
  open: boolean;
  busy?: boolean;
  onCancel: () => void;
  /** Reports the chosen asset id (or null to clear). */
  onPick: (id: string | null) => void;
};

export function LibraryImagePickerModal({
  images,
  currentAssetId,
  title = "Choose a Library image",
  confirmLabel = "Use this frame",
  open,
  busy,
  onCancel,
  onPick,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const titleId = useId();

  // Reset transient state whenever the modal (re)opens.
  useEffect(() => {
    if (!open) {
      setSelectedId(null);
      setQuery("");
      return;
    }
    setSelectedId(currentAssetId ?? null);
  }, [open, currentAssetId]);

  // Escape to cancel.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return images;
    return images.filter((a) => {
      const name = (a.tag || a.filename || "").toLowerCase();
      return name.includes(q);
    });
  }, [images, query]);

  if (!open) return null;

  return createPortal(
    <div
      className="lib-img-picker"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onCancel}
    >
      <div className="lib-img-picker__body" onClick={(e) => e.stopPropagation()}>
        <div className="lib-img-picker__header">
          <strong id={titleId}>{title}</strong>
          <button
            type="button"
            className="lib-img-picker__close"
            aria-label="Close library picker"
            onClick={onCancel}
          >
            ×
          </button>
        </div>

        <div className="lib-img-picker__search">
          <input
            type="search"
            placeholder="Search your Library…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search library images"
            autoFocus
          />
        </div>

        <div className="lib-img-picker__grid" role="listbox" aria-label="Library images">
          {filtered.length === 0 ? (
            <p className="lib-img-picker__empty">
              {images.length === 0
                ? "No images in your Library yet. Upload one to get started."
                : "No images match your search."}
            </p>
          ) : (
            filtered.map((a) => {
              const isSelected = selectedId === a.id;
              const name = a.tag || a.filename || "Untitled";
              return (
                <button
                  key={a.id}
                  type="button"
                  className={`lib-img-picker__asset${isSelected ? " is-selected" : ""}`}
                  onClick={() => setSelectedId(a.id)}
                  aria-label={`Select ${name}${isSelected ? " (currently selected)" : ""}`}
                  role="option"
                  aria-selected={isSelected}
                >
                  <img src={api.assetUrl(a.id)} alt={name} loading="lazy" />
                  <span className="lib-img-picker__asset-name">{name}</span>
                  {isSelected ? <span className="lib-img-picker__asset-check" aria-hidden="true">✓</span> : null}
                </button>
              );
            })
          )}
        </div>

        <div className="lib-img-picker__footer">
          <button
            type="button"
            className="lib-img-picker__btn"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="lib-img-picker__btn primary"
            data-testid="library-image-picker-confirm"
            disabled={!selectedId || busy}
            onClick={() => {
              if (selectedId) onPick(selectedId);
            }}
          >
            {busy ? "Attaching…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
