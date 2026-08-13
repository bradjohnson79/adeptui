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

type BulkDeleteResult = { assetId: string; status: string; name?: string };

type ConfirmState =
  | { kind: "delete"; ids: string[] }
  | { kind: "blocked"; blocked: BulkDeleteResult[] }
  | null;

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

function SelectCheckbox({
  checked,
  onClick,
  label,
}: {
  checked: boolean;
  onClick: (e: React.MouseEvent) => void;
  label: string;
}) {
  return (
    <label
      className={`library-media-grid__select-checkbox${checked ? " is-checked" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick(e);
      }}
      title={label}
      aria-label={label}
    >
      <input type="checkbox" checked={checked} onChange={() => {}} />
    </label>
  );
}

function MediaCard({
  asset,
  onOpen,
  selectMode,
  selected,
  onToggleSelect,
}: {
  asset: LibraryAsset;
  onOpen: () => void;
  selectMode: boolean;
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const [duration, setDuration] = useState<number | null>(null);
  const previewUrl = getCardPreviewUrl(asset);

  const handleClick = () => {
    if (selectMode && isImageAsset(asset)) {
      onToggleSelect();
      return;
    }
    onOpen();
  };

  const cardClass = `library-media-grid__card${selectMode && isImageAsset(asset) ? " is-selectable" : ""}${
    selected ? " is-selected" : ""
  }`;

  const showCheckbox = selectMode && isImageAsset(asset);

  const cardContent = (preview: React.ReactNode) => (
    <>
      {showCheckbox ? (
        <SelectCheckbox
          checked={selected}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSelect();
          }}
          label={`Select ${getAssetName(asset)}`}
        />
      ) : null}
      <div className="library-media-grid__thumb">{preview}</div>
      <CardMeta asset={asset} />
    </>
  );

  if (isImageAsset(asset) && previewUrl) {
    return (
      <button
        type="button"
        className={cardClass}
        data-testid="library-card-image"
        onClick={handleClick}
        aria-pressed={showCheckbox ? selected : undefined}
      >
        {cardContent(<img src={previewUrl} alt={getAssetName(asset)} loading="lazy" />)}
      </button>
    );
  }

  if (isVideoAsset(asset)) {
    return (
      <button
        type="button"
        className={cardClass}
        data-testid="library-card-video"
        onClick={handleClick}
        aria-pressed={showCheckbox ? selected : undefined}
      >
        {cardContent(
          <>
            <video
              src={api.assetUrl(asset.id)}
              preload="metadata"
              muted
              playsInline
              onLoadedMetadata={(e) => setDuration((e.target as HTMLVideoElement).duration)}
            />
            <span className="library-media-grid__play-overlay">▶</span>
          </>,
        )}
      </button>
    );
  }

  if (isAudioAsset(asset)) {
    return (
      <button
        type="button"
        className={cardClass}
        data-testid="library-card-audio"
        onClick={handleClick}
        aria-pressed={showCheckbox ? selected : undefined}
      >
        {cardContent(<span className="library-media-grid__thumb-icon">♪</span>)}
        <CardMeta asset={asset} duration={formatDuration(duration)} />
      </button>
    );
  }

  return (
    <button
      type="button"
      className={cardClass}
      data-testid="library-card-document"
      onClick={handleClick}
      aria-pressed={showCheckbox ? selected : undefined}
    >
      {cardContent(<span className="library-media-grid__thumb-icon">{getDocumentKind(asset.filename)}</span>)}
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

function ConfirmDialog({
  state,
  onCancel,
  onConfirm,
  busy,
}: {
  state: ConfirmState;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);

  if (state?.kind === "delete") {
    const n = state.ids.length;
    const label = n === 1 ? "Delete 1 image?" : `Delete ${n} images?`;
    return createPortal(
      <div className="library-media-confirm" role="alertdialog" aria-modal="true" aria-label={label}>
        <button
          type="button"
          className="library-media-preview__backdrop"
          aria-label="Cancel"
          onClick={onCancel}
          disabled={busy}
        />
        <div className="library-media-confirm__panel">
          <h3>{label}</h3>
          <p className="library-media-confirm__hint">
            {n === 1
              ? "This will remove the image from this project's library."
              : `This will remove ${n} images from this project's library.`}
          </p>
          <div className="library-media-confirm__actions">
            <button
              type="button"
              className="library-media-grid__filter"
              onClick={onCancel}
              disabled={busy}
              data-testid="library-bulk-delete-cancel"
            >
              Cancel
            </button>
            <button
              type="button"
              className="library-media-confirm__confirm"
              onClick={onConfirm}
              disabled={busy}
              data-testid="library-bulk-delete-confirm"
            >
              {n === 1 ? "Delete" : `Delete ${n} Images`}
            </button>
          </div>
        </div>
      </div>,
      document.body,
    );
  }

  if (state?.kind === "blocked") {
    const blocked = state.blocked;
    const n = blocked.length;
    return createPortal(
      <div className="library-media-confirm" role="alertdialog" aria-modal="true" aria-label="Some images are in use">
        <button
          type="button"
          className="library-media-preview__backdrop"
          aria-label="Cancel"
          onClick={onCancel}
          disabled={busy}
        />
        <div className="library-media-confirm__panel">
          <h3>{n === 1 ? "1 image is in use" : `${n} images are in use`}</h3>
          <p className="library-media-confirm__hint">
            These images are referenced by other parts of this project. Force delete removes them anyway.
          </p>
          <ul className="library-media-confirm__list" data-testid="library-bulk-delete-blocked-list">
            {blocked.map((b) => (
              <li key={b.assetId}>{b.name || b.assetId}</li>
            ))}
          </ul>
          <div className="library-media-confirm__actions">
            <button
              type="button"
              className="library-media-grid__filter"
              onClick={onCancel}
              disabled={busy}
              data-testid="library-bulk-delete-blocked-cancel"
            >
              Cancel
            </button>
            <button
              type="button"
              className="library-media-confirm__confirm library-media-confirm__confirm--danger"
              onClick={onConfirm}
              disabled={busy}
              data-testid="library-bulk-delete-force"
            >
              Force Delete
            </button>
          </div>
        </div>
      </div>,
      document.body,
    );
  }

  return null;
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

  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [deleting, setDeleting] = useState(false);

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
    if (activeExecution.project_id && activeExecution.project_id !== projectId) return;
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

  const selectableIds = useMemo(
    () => filtered.filter((a) => isImageAsset(a)).map((a) => a.id),
    [filtered],
  );

  const toggleSelect = useCallback((assetId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(selectableIds));
  }, [selectableIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const enterSelect = useCallback(() => {
    setSelectMode(true);
    setSelectedIds(new Set());
  }, []);

  const exitSelect = useCallback(() => {
    setSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  const onDelete = () => {
    setConfirmState({ kind: "delete", ids: [...selectedIds] });
  };

  const runDelete = async (assetIds: string[], force: boolean) => {
    setDeleting(true);
    try {
      const res = await api.sceneReferences.bulkDeleteAssets(projectId, assetIds, force);
      const results = res?.results ?? [];
      if (!force) {
        const blocked = results.filter((r: { assetId: string; status: string; name?: string }) => r.status !== "deleted" && r.status !== "ok");
        if (blocked.length > 0) {
          setConfirmState({ kind: "blocked", blocked });
          return;
        }
      }
      setConfirmState(null);
      setSelectedIds(new Set());
      setSelectMode(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConfirmState(null);
    } finally {
      setDeleting(false);
    }
  };

  const onConfirmDelete = () => {
    if (confirmState?.kind !== "delete") return;
    void runDelete(confirmState.ids, false);
  };

  const onConfirmForce = () => {
    if (confirmState?.kind !== "blocked") return;
    const blockedIds = confirmState.blocked.map((b) => b.assetId);
    void runDelete(blockedIds, true);
  };

  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));

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
        <div className="library-media-grid__select-actions">
          {selectMode ? (
            <>
              <button
                type="button"
                className="library-media-grid__filter"
                onClick={allSelected ? clearSelection : selectAll}
                disabled={selectableIds.length === 0}
                data-testid="library-select-all"
              >
                {allSelected ? "Clear Selection" : "Select All"}
              </button>
              <button
                type="button"
                className="library-media-grid__filter library-media-grid__filter--danger"
                onClick={onDelete}
                disabled={selectedIds.size === 0}
                data-testid="library-delete-selected"
              >
                Delete Selected{selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}
              </button>
              <button
                type="button"
                className="library-media-grid__filter"
                onClick={exitSelect}
                data-testid="library-exit-select"
              >
                Done
              </button>
            </>
          ) : (
            <button
              type="button"
              className="library-media-grid__filter"
              onClick={enterSelect}
              data-testid="library-enter-select"
            >
              Select
            </button>
          )}
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
            <MediaCard
              key={asset.id}
              asset={asset}
              onOpen={() => setPreviewAsset(asset)}
              selectMode={selectMode}
              selected={selectedIds.has(asset.id)}
              onToggleSelect={() => toggleSelect(asset.id)}
            />
          ))}
        </div>
      )}

      {previewAsset ? <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} /> : null}
      {confirmState ? (
        <ConfirmDialog
          state={confirmState}
          onCancel={() => !deleting && setConfirmState(null)}
          onConfirm={confirmState.kind === "delete" ? onConfirmDelete : onConfirmForce}
          busy={deleting}
        />
      ) : null}
    </div>
  );
}
