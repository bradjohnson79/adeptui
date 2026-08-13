/**
 * Single-select modal for choosing a Library image as a Character Reference.
 * Parent owns attachment/persistence; this component only reports selection.
 */
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import {
  getCardPreviewUrl,
  isImageAsset,
  type LibraryAsset,
} from "../library/assetModel";
import "./characterCompact.css";

type Props = {
  projectId: string;
  currentAssetId?: string | null;
  open: boolean;
  onCancel: () => void;
  onConfirm: (asset: LibraryAsset) => void;
  busy?: boolean;
  error?: string | null;
};

export function CharacterReferenceAssetPicker({
  projectId,
  currentAssetId,
  open,
  onCancel,
  onConfirm,
  busy,
  error,
}: Props) {
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setSelectedAssetId(currentAssetId ?? null);
    setLoadError(null);
    setLoading(true);
    void api
      .library(projectId, { q: "" })
      .then((res) => {
        const items = Array.isArray(res?.items) ? (res.items as LibraryAsset[]) : [];
        setAssets(items.filter(isImageAsset));
      })
      .catch((e) => {
        setLoadError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [open, projectId, currentAssetId]);

  const imageAssets = useMemo(() => assets, [assets]);

  const selectedAsset = useMemo(
    () => imageAssets.find((a) => a.id === selectedAssetId) ?? null,
    [imageAssets, selectedAssetId],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const displayError = error ?? loadError;

  return createPortal(
    <div
      className="character-compact__preview"
      role="dialog"
      aria-modal="true"
      aria-label="Choose a Reference Image"
      onClick={onCancel}
    >
      <div
        className="character-compact__picker-body"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="character-compact__picker-header">
          <strong>Choose a Reference Image</strong>
        </div>
        <div className="character-compact__picker-grid">
          {loading ? (
            <p className="character-compact__bio-text">Loading your Library…</p>
          ) : imageAssets.length === 0 ? (
            <p className="character-compact__bio-text">No images in your Library yet.</p>
          ) : (
            <div className="character-compact__assets-grid" role="listbox" aria-label="Library images">
              {imageAssets.map((a) => {
                const isSelected = selectedAssetId === a.id;
                const name = a.tag || a.filename || "Untitled";
                return (
                  <button
                    key={a.id}
                    type="button"
                    className={`character-compact__asset is-media${isSelected ? " is-selected" : ""}`}
                    onClick={() => setSelectedAssetId(a.id)}
                    aria-label={`Select ${name}${isSelected ? " (currently selected)" : ""}`}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <img src={getCardPreviewUrl(a) || api.assetUrl(a.id)} alt={name} loading="lazy" />
                    <strong>{name}</strong>
                    {isSelected ? <span className="character-compact__asset-check">✓</span> : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {displayError ? (
          <p className="character-compact__hint" style={{ color: "#f08787" }} data-testid="character-compact-picker-error">
            {displayError}
          </p>
        ) : null}
        <div className="character-compact__picker-footer">
          <div className="character-compact__picker-footer-inner">
            <button
              type="button"
              className="character-compact__actions-button"
              onClick={onCancel}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="button"
              className="character-compact__actions-button primary"
              data-testid="character-compact-picker-select"
              disabled={!selectedAssetId || busy}
              onClick={() => {
                if (selectedAsset) {
                  onConfirm(selectedAsset);
                }
              }}
            >
              {busy ? "Attaching…" : "Select"}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
