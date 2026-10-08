import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { isQuickPreviewKind, type QuickPreviewKind } from "./libraryQuickPreview";
import "./libraryQuickPreview.css";

export type LibraryQuickPreviewAsset = {
  id: string;
  kind: string;
  filename?: string;
  tag?: string;
  name?: string;
  model?: string;
  /** Direct picture URL for an in-progress frame that is not a Library asset yet. */
  previewSrc?: string;
};

function kindLabel(kind: QuickPreviewKind, t: (key: string) => string) {
  if (kind === "image") return t("images");
  if (kind === "video") return t("video");
  return t("audio");
}

export function LibraryQuickPreviewModal({
  asset,
  onClose,
  projectId,
}: {
  asset: LibraryQuickPreviewAsset | null;
  onClose: () => void;
  projectId?: string | null;
}) {
  const { t } = useTranslation("library");
  const [meta, setMeta] = useState({ width: 0, height: 0, duration: 0 });
  const [failed, setFailed] = useState(false);
  const kind = asset && isQuickPreviewKind(asset.kind) ? asset.kind : null;

  useEffect(() => {
    if (!asset) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [asset, onClose]);

  useEffect(() => {
    setMeta({ width: 0, height: 0, duration: 0 });
    setFailed(false);
  }, [asset?.id]);

  if (!asset || !kind) return null;

  const title = asset.name || asset.tag || asset.filename || t("quickPreview");
  const src = String(asset.previewSrc || "").trim() || api.assetUrl(asset.id, null, projectId);

  return createPortal(
    <div className="library-quick-preview" role="dialog" aria-modal="true" aria-label={t("quickPreview")} data-testid="library-quick-preview">
      <button
        type="button"
        className="library-quick-preview__backdrop"
        aria-label={t("closePreview")}
        data-testid="library-quick-preview-backdrop"
        onClick={onClose}
      />
      <div className="library-quick-preview__panel" data-testid={`library-quick-preview-${kind}`} onClick={(event) => event.stopPropagation()}>
        <header className="library-quick-preview__header">
          <h3 className="library-quick-preview__title">{title}</h3>
          <button
            type="button"
            className="library-quick-preview__close"
            aria-label={t("closePreview")}
            data-testid="library-quick-preview-close"
            onClick={onClose}
          >
            X
          </button>
        </header>
        <div className="library-quick-preview__media">
          {failed ? (
            <p className="library-quick-preview__unavailable" data-testid="library-quick-preview-error">
              Unable to preview this asset.
            </p>
          ) : null}
          {!failed && kind === "image" ? (
            <img
              key={asset.id}
              src={src}
              alt={title}
              onLoad={(event) => {
                const el = event.currentTarget;
                setMeta((current) => ({ ...current, width: el.naturalWidth, height: el.naturalHeight }));
              }}
              onError={() => setFailed(true)}
            />
          ) : null}
          {!failed && kind === "video" ? (
            <video
              key={asset.id}
              src={src}
              controls
              playsInline
              preload="metadata"
              data-testid="library-quick-preview-player"
              onLoadedMetadata={(event) => {
                const el = event.currentTarget;
                setMeta({
                  width: el.videoWidth,
                  height: el.videoHeight,
                  duration: Number.isFinite(el.duration) ? el.duration : 0,
                });
              }}
              onError={() => setFailed(true)}
            />
          ) : null}
          {!failed && kind === "audio" ? (
            <audio
              key={asset.id}
              src={src}
              controls
              preload="metadata"
              data-testid="library-quick-preview-player"
              onLoadedMetadata={(event) => {
                const el = event.currentTarget;
                setMeta((current) => ({
                  ...current,
                  duration: Number.isFinite(el.duration) ? el.duration : 0,
                }));
              }}
              onError={() => setFailed(true)}
            />
          ) : null}
        </div>
        <div className="library-quick-preview__meta">
          <span>{t("previewKind")}: {kindLabel(kind, t)}</span>
          {asset.filename ? <span>{t("previewFilename")}: {asset.filename}</span> : null}
          {meta.width > 0 && meta.height > 0 ? (
            <span>{t("previewDimensions")}: {meta.width}×{meta.height}</span>
          ) : null}
          {meta.duration > 0 ? <span>{t("previewDuration")}: {meta.duration.toFixed(1)}s</span> : null}
          {asset.model ? <span>Model: {asset.model}</span> : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
