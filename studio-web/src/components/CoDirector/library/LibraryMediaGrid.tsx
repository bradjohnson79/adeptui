/**
 * Library media grid — the Co-Director Library tab.
 *
 * Replaces the previous raw-JSON dump (ProjectRetrievalPanel + asset.list tool)
 * with a creator-facing media browser: filter chips, thumbnail cards, and a
 * preview modal. Fetches api.library directly and renders friendly labels
 * (no UUIDs, no JSON, no evidence bullets).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import { useCoDirectorSession } from "../CoDirectorSession";
import {
  FILTERS,
  getAssetName,
  getAssetKindText,
  getCardPreviewUrl,
  getDisplayDate,
  getDocumentKind,
  isAudioAsset,
  isImageAsset,
  isVideoAsset,
  matchesFilter,
  type AssetFilterId,
  type LibraryAsset,
} from "./assetModel";
import "./libraryMediaGrid.css";

type Props = {
  projectId: string;
  onGoTab?: (tab: string) => void;
};

function formatDuration(seconds: number | null): string {
  if (seconds == null || !isFinite(seconds) || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function getAssociationLabel(asset: LibraryAsset): string {
  const parts: string[] = [];
  if (asset.characterId) parts.push("Character");
  if (asset.sceneId) parts.push("Scene");
  if (parts.length === 0 && asset.libraryPath) {
    const seg = asset.libraryPath.split("/").filter(Boolean).pop();
    return seg ? seg.replace(/[-_]/g, " ") : "";
  }
  return parts.join(" · ");
}

function CardMeta({ asset, duration }: { asset: LibraryAsset; duration?: string }) {
  const association = getAssociationLabel(asset);
  return (
    <div className="library-media-grid__meta">
      <strong>{getAssetName(asset)}</strong>
      <span>
        {getAssetKindText(asset)}
        {duration ? ` · ${duration}` : ""}
        {asset.created_at ? ` · ${getDisplayDate(asset)}` : ""}
      </span>
      {association ? <span className="library-media-grid__badge">{association}</span> : null}
    </div>
  );
}

function MediaCard({ asset, onOpen }: { asset: LibraryAsset; onOpen: () => void }) {
  const [duration, setDuration] = useState<number | null>(null);
  const previewUrl = getCardPreviewUrl(asset);

  if (isImageAsset(asset) && previewUrl) {
    return (
      <button type="button" className="library-media-grid__card" data-testid="library-card-image" onClick={onOpen}>
        <div className="library-media-grid__thumb">
          <img src={previewUrl} alt={getAssetName(asset)} loading="lazy" />
        </div>
        <CardMeta asset={asset} />
      </button>
    );
  }

  if (isVideoAsset(asset)) {
    return (
      <button type="button" className="library-media-grid__card" data-testid="library-card-video" onClick={onOpen}>
        <div className="library-media-grid__thumb">
          <video
            src={api.assetUrl(asset.id)}
            preload="metadata"
            muted
            playsInline
            onLoadedMetadata={(e) => setDuration((e.target as HTMLVideoElement).duration)}
          />
          <span className="library-media-grid__play-overlay">▶</span>
        </div>
        <CardMeta asset={asset} duration={formatDuration(duration)} />
      </button>
    );
  }

  if (isAudioAsset(asset)) {
    return (
      <button type="button" className="library-media-grid__card" data-testid="library-card-audio" onClick={onOpen}>
        <div className="library-media-grid__thumb">
          <span className="library-media-grid__thumb-icon">♪</span>
        </div>
        <CardMeta asset={asset} duration={formatDuration(duration)} />
      </button>
    );
  }

  return (
    <button type="button" className="library-media-grid__card" data-testid="library-card-document" onClick={onOpen}>
      <div className="library-media-grid__thumb">
        <span className="library-media-grid__thumb-icon">{getDocumentKind(asset.filename)}</span>
      </div>
      <CardMeta asset={asset} />
    </button>
  );
}

function PreviewMedia({ asset }: { asset: LibraryAsset }) {
  if (isImageAsset(asset)) {
    return (
      <div className="library-media-preview__media">
        <img src={api.assetUrl(asset.id)} alt={getAssetName(asset)} />
      </div>
    );
  }
  if (isVideoAsset(asset)) {
    return (
      <div className="library-media-preview__media">
        <video src={api.assetUrl(asset.id)} controls autoPlay playsInline />
      </div>
    );
  }
  if (isAudioAsset(asset)) {
    return (
      <div className="library-media-preview__media">
        <audio src={api.assetUrl(asset.id)} controls autoPlay />
      </div>
    );
  }
  return (
    <div className="library-media-preview__media">
      <div className="library-media-preview__media-doc">
        <div className="doc-glyph">{getDocumentKind(asset.filename)}</div>
        <p>This is a {getAssetKindText(asset)} file. Use a full editor to open it directly.</p>
      </div>
    </div>
  );
}

function PreviewModal({ asset, onClose }: { asset: LibraryAsset; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="library-media-preview" role="dialog" aria-modal="true" aria-label={`${getAssetName(asset)} preview`}>
      <button type="button" className="library-media-preview__backdrop" aria-label="Close preview" onClick={onClose} />
      <div className="library-media-preview__panel">
        <button type="button" className="library-media-preview__close" aria-label="Close" onClick={onClose}>×</button>
        <PreviewMedia asset={asset} />
        <div className="library-media-preview__meta">
          <h3>{getAssetName(asset)}</h3>
          <dl>
            <dt>Type</dt>
            <dd>{getAssetKindText(asset)}</dd>
            {asset.created_at ? (<><dt>Created</dt><dd>{getDisplayDate(asset)}</dd></>) : null}
            {asset.libraryPath ? (<><dt>Folder</dt><dd>{asset.libraryPath}</dd></>) : null}
            {asset.characterId ? (<><dt>Linked Character</dt><dd>{asset.characterId}</dd></>) : null}
            {asset.sceneId ? (<><dt>Linked Scene</dt><dd>{asset.sceneId}</dd></>) : null}
          </dl>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function SkeletonGrid() {
  return (
    <div className="library-media-grid__skeleton" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="library-media-grid__skeleton-card">
          <div className="library-media-grid__skeleton-thumb" />
          <div className="library-media-grid__skeleton-line" />
          <div className="library-media-grid__skeleton-line" />
        </div>
      ))}
    </div>
  );
}

export function LibraryMediaGrid({ projectId, onGoTab }: Props) {
  void onGoTab;
  const { activeExecution } = useCoDirectorSession();
  const [filter, setFilter] = useState<AssetFilterId>("all");
  const [query, setQuery] = useState("");
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewAsset, setPreviewAsset] = useState<LibraryAsset | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await api.library(projectId, { q: query.trim() || undefined });
      setAssets(Array.isArray(payload?.items) ? (payload.items as LibraryAsset[]) : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, query]);

  // Live update: refresh when an execution completes or produces new assets.
  useEffect(() => {
    if (!activeExecution) return;
    // Only refresh if this execution belongs to the current project.
    if (activeExecution.project_id && activeExecution.project_id !== projectId) return;
    // Refresh when execution status changes to completed (new assets in Library).
    if (activeExecution.status === "completed" || activeExecution.result_asset_ids?.length) {
      void refresh();
    }
  }, [activeExecution?.status, activeExecution?.result_asset_ids?.length, activeExecution?.execution_id, projectId, refresh]);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError(null);
    api
      .library(projectId, { q: query.trim() || undefined })
      .then((payload) => {
        if (cancelled) return;
        setAssets(Array.isArray(payload?.items) ? (payload.items as LibraryAsset[]) : []);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, query]);

  const filtered = useMemo(
    () => assets.filter((a) => matchesFilter(a, filter)),
    [assets, filter],
  );

  return (
    <div className="library-media-grid" data-testid="library-media-grid">
      <div className="library-media-grid__toolbar">
        <div className="library-media-grid__search">
          <input
            type="search"
            placeholder="Search assets…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search library assets"
          />
        </div>
        <div className="library-media-grid__filters" role="tablist" aria-label="Asset type filter">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={`library-media-grid__filter${filter === f.id ? " is-active" : ""}`}
              data-testid={`library-filter-${f.id}`}
              onClick={() => setFilter(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {busy ? (
        <SkeletonGrid />
      ) : error ? (
        <div className="library-media-grid__state library-media-grid__state--error" data-testid="library-error">
          <strong>Library could not load</strong>
          <p>{error}</p>
          <button type="button" className="library-media-grid__filter is-active" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      ) : assets.length === 0 ? (
        <div className="library-media-grid__state" data-testid="library-empty">
          <strong>No project assets yet.</strong>
          <p>Generated and uploaded images, videos, audio and documents will appear here.</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="library-media-grid__state" data-testid="library-empty-filter">
          <strong>No {filter} assets</strong>
          <p>Try a different filter or clear your search.</p>
        </div>
      ) : (
        <div className="library-media-grid__grid" role="list">
          {filtered.map((asset) => (
            <MediaCard key={asset.id} asset={asset} onOpen={() => setPreviewAsset(asset)} />
          ))}
        </div>
      )}

      {previewAsset ? <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} /> : null}
    </div>
  );
}
