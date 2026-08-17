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
};

function kindLabel(kind: QuickPreviewKind, t: (key: string) => string) {
  if (kind === "image") return t("images");
  if (kind === "video") return t("video");
  return t("audio");
}

export function LibraryQuickPreviewModal({
  asset,
  onClose,
}: {
  asset: LibraryQuickPreviewAsset | null;
  onClose: () => void;
}) {
  const { t } = useTranslation("library");
  const [meta, setMeta] = useState({ width: 0, height: 0, duration: 0 });
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
  }, [asset?.id]);

  if (!asset || !kind) return null;

  const title = asset.tag || asset.name || asset.filename || t("quickPreview");
  const src = api.assetUrl(asset.id);

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
        <button
          type="button"
          className="library-quick-preview__close"
          aria-label={t("closePreview")}
          data-testid="library-quick-preview-close"
          onClick={onClose}
        >
          ×
        </button>
        <div className="library-quick-preview__media">
          {kind === "image" ? (
            <img
              src={src}
              alt={title}
              onLoad={(event) => {
                const el = event.currentTarget;
                setMeta((current) => ({ ...current, width: el.naturalWidth, height: el.naturalHeight }));
              }}
            />
          ) : null}
          {kind === "video" ? (
            <video
              src={src}
              controls
              playsInline
              onLoadedMetadata={(event) => {
                const el = event.currentTarget;
                setMeta({
                  width: el.videoWidth,
                  height: el.videoHeight,
                  duration: Number.isFinite(el.duration) ? el.duration : 0,
                });
              }}
            />
          ) : null}
          {kind === "audio" ? (
            <audio
              src={src}
              controls
              onLoadedMetadata={(event) => {
                const el = event.currentTarget;
                setMeta((current) => ({
                  ...current,
                  duration: Number.isFinite(el.duration) ? el.duration : 0,
                }));
              }}
            />
          ) : null}
        </div>
        <div className="library-quick-preview__meta">
          <h3 className="library-quick-preview__title">{title}</h3>
          <span>{t("previewKind")}: {kindLabel(kind, t)}</span>
          {asset.filename ? <span>{t("previewFilename")}: {asset.filename}</span> : null}
          {meta.width > 0 && meta.height > 0 ? (
            <span>{t("previewDimensions")}: {meta.width}×{meta.height}</span>
          ) : null}
          {meta.duration > 0 ? <span>{t("previewDuration")}: {meta.duration.toFixed(1)}s</span> : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
