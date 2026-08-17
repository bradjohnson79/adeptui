/**
 * Library media grid — the Co-Director Library tab.
 *
 * Replaces the previous raw-JSON dump (ProjectRetrievalPanel + asset.list tool)
 * with a creator-facing media browser: filter chips, thumbnail cards, and a
 * preview modal. Fetches api.library directly and renders friendly labels
 * (no UUIDs, no JSON, no evidence bullets).
 *
 * Phase 6 parity with the Standard LibraryPanel:
 *  - CDX-017: Approved badge for approved props / approved takes /
 *    production_approval=approved assets.
 *  - CDX-071: entity associations resolve to names from the payload tree
 *    (never raw UUIDs in the preview dialog).
 *  - CDX-074: consumes payload.tree/folderMap for folder-chip navigation and
 *    a Project/Global scope toggle, matching the canonical library behavior.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { createPortal } from "react-dom";
import { api } from "../../../api";
import { useCoDirectorSession } from "../CoDirectorSession";
import {
  FILTERS,
  getApprovalBadge,
  getAssetAssociationLabel,
  getAssetKindText,
  getAssetName,
  getCardPreviewUrl,
  getDisplayDate,
  getDocumentKind,
  isAudioAsset,
  isImageAsset,
  isVideoAsset,
  matchesFilter,
  resolveLinkedEntityName,
  type AssetFilterId,
  type LibraryAsset,
  type LibraryFolderMapEntry,
  type LibraryFolderNode,
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

type FolderFilter = { folderId?: string; systemKey?: string; label?: string };

function CardMeta({
  asset,
  duration,
  folders,
}: {
  asset: LibraryAsset;
  duration?: string;
  folders: LibraryFolderNode[] | null;
}) {
  const association = getAssetAssociationLabel(asset, folders);
  const approval = getApprovalBadge(asset);
  return (
    <div className="library-media-grid__meta">
      <strong>{getAssetName(asset)}</strong>
      <span>
        {getAssetKindText(asset)}
        {duration ? ` · ${duration}` : ""}
        {asset.created_at ? ` · ${getDisplayDate(asset)}` : ""}
      </span>
      {approval ? (
        <span
          className="library-media-grid__badge library-media-grid__badge--approved"
          data-testid="library-approval-badge"
        >
          ✓ {approval.label}
        </span>
      ) : null}
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
  folders,
}: {
  asset: LibraryAsset;
  onOpen: () => void;
  selectMode: boolean;
  selected: boolean;
  onToggleSelect: () => void;
  folders: LibraryFolderNode[] | null;
}) {
  const previewUrl = getCardPreviewUrl(asset);

  const handleClick = () => {
    if (selectMode) {
      onToggleSelect();
      return;
    }
    onOpen();
  };

  const cardClass = `library-media-grid__card${selectMode ? " is-selectable" : ""}${selected ? " is-selected" : ""}`;

  const showCheckbox = selectMode;

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
      <CardMeta asset={asset} folders={folders} />
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
            <video src={api.assetUrl(asset.id)} preload="metadata" muted playsInline />
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

function PreviewModal({
  asset,
  onClose,
  folders,
}: {
  asset: LibraryAsset;
  onClose: () => void;
  folders: LibraryFolderNode[] | null;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // CDX-071: resolve entity ids to names from the payload tree — never UUIDs.
  const characterName = resolveLinkedEntityName(asset, folders, "character");
  const propName = resolveLinkedEntityName(asset, folders, "prop");
  const sceneName = resolveLinkedEntityName(asset, folders, "scene");
  const approval = getApprovalBadge(asset);

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
            {approval ? (<><dt>Approval</dt><dd>✓ {approval.label}</dd></>) : null}
            {asset.created_at ? (<><dt>Created</dt><dd>{getDisplayDate(asset)}</dd></>) : null}
            {asset.libraryPath ? (<><dt>Folder</dt><dd>{asset.libraryPath}</dd></>) : null}
            {characterName ? (<><dt>Linked Character</dt><dd>{characterName}</dd></>) : null}
            {propName ? (<><dt>Linked Prop</dt><dd>{propName}</dd></>) : null}
            {sceneName ? (<><dt>Linked Scene</dt><dd>{sceneName}</dd></>) : null}
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
    const label = n === 1 ? "Delete 1 asset?" : `Delete ${n} assets?`;
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
              ? "This will remove the asset from this project's library."
              : `This will remove ${n} assets from this project's library.`}
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
              {n === 1 ? "Delete" : `Delete ${n} Assets`}
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
      <div className="library-media-confirm" role="alertdialog" aria-modal="true" aria-label="Some assets are in use">
        <button
          type="button"
          className="library-media-preview__backdrop"
          aria-label="Cancel"
          onClick={onCancel}
          disabled={busy}
        />
        <div className="library-media-confirm__panel">
          <h3>{n === 1 ? "1 asset is in use" : `${n} assets are in use`}</h3>
          <p className="library-media-confirm__hint">
            These assets are referenced by other parts of this project. Force delete removes them anyway.
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
  const { t } = useTranslation(["library", "common"]);
  const { activeExecution } = useCoDirectorSession();
  const [filter, setFilter] = useState<AssetFilterId>("all");
  const [query, setQuery] = useState("");
  // CDX-074: project/global scope parity with the Standard LibraryPanel.
  const [scope, setScope] = useState<"project" | "global">("project");
  const [folderFilter, setFolderFilter] = useState<FolderFilter | null>(null);
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [treeFolders, setTreeFolders] = useState<LibraryFolderNode[]>([]);
  const [folderMap, setFolderMap] = useState<Record<string, LibraryFolderMapEntry>>({});
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewAsset, setPreviewAsset] = useState<LibraryAsset | null>(null);

  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [deleting, setDeleting] = useState(false);

  const libraryParams = useMemo(
    () => ({
      q: query.trim() || undefined,
      scope,
      folder: folderFilter?.folderId || undefined,
      system_key: folderFilter?.systemKey || undefined,
    }),
    [query, scope, folderFilter],
  );

  const applyPayload = useCallback((payload: Awaited<ReturnType<typeof api.library>>) => {
    setAssets(Array.isArray(payload?.items) ? (payload.items as LibraryAsset[]) : []);
    setTreeFolders(Array.isArray(payload?.tree?.folders) ? payload.tree.folders : []);
    setFolderMap(payload?.folderMap || {});
  }, []);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = await api.library(projectId, libraryParams);
      applyPayload(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [projectId, libraryParams, applyPayload]);

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
      .library(projectId, libraryParams)
      .then((payload) => {
        if (cancelled) return;
        applyPayload(payload);
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
  }, [projectId, libraryParams, applyPayload]);

  const filtered = useMemo(
    () => assets.filter((a) => matchesFilter(a, filter)),
    [assets, filter],
  );

  const selectableIds = useMemo(() => filtered.map((a) => a.id), [filtered]);

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

  // CDX-074: folder navigation derived from the payload taxonomy tree.
  const activeFolder = useMemo(() => {
    if (!folderFilter) return null;
    return (
      treeFolders.find(
        (f) =>
          (f.folderId && f.folderId === folderFilter.folderId) ||
          (f.systemKey && f.systemKey === folderFilter.systemKey),
      ) || null
    );
  }, [treeFolders, folderFilter]);

  const isFolderActive = useCallback(
    (folder: LibraryFolderNode) =>
      Boolean(folder.systemKey && folder.systemKey === folderFilter?.systemKey) ||
      Boolean(folder.folderId && folder.folderId === folderFilter?.folderId),
    [folderFilter],
  );

  const selectFolder = useCallback((folder: LibraryFolderNode | null) => {
    if (!folder) {
      setFolderFilter(null);
      return;
    }
    if (!folder.folderId && !folder.systemKey) return;
    setFolderFilter({
      folderId: folder.folderId,
      systemKey: folder.systemKey,
      label: folder.displayName,
    });
  }, []);

  const activeFolderPath = useMemo(() => {
    if (!folderFilter) return undefined;
    if (folderFilter.folderId && folderMap[folderFilter.folderId]?.displayPath) {
      return folderMap[folderFilter.folderId].displayPath;
    }
    return folderFilter.label;
  }, [folderFilter, folderMap]);

  return (
    <div className="library-media-grid" data-testid="library-media-grid">
      <div className="library-media-grid__toolbar">
        <div className="library-media-grid__scope" role="group" aria-label="Library scope">
          <button
            type="button"
            className={`library-media-grid__filter${scope === "project" ? " is-active" : ""}`}
            onClick={() => setScope("project")}
            data-testid="library-scope-project"
          >
            {t("library:project")}
          </button>
          <button
            type="button"
            className={`library-media-grid__filter${scope === "global" ? " is-active" : ""}`}
            onClick={() => setScope("global")}
            data-testid="library-scope-global"
          >
            {t("library:global")}
          </button>
        </div>
        <div className="library-media-grid__search">
          <input
            type="search"
            placeholder={t("library:searchPlaceholder")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t("library:searchAria")}
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
              {t(`library:${f.id}`)}
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

      {treeFolders.length > 0 ? (
        <div className="library-media-grid__nav" role="navigation" aria-label="Library folders" data-testid="library-folder-nav">
          <button
            type="button"
            className={`library-media-grid__filter${!folderFilter ? " is-active" : ""}`}
            onClick={() => selectFolder(null)}
            data-testid="library-folder-all"
          >
            All folders
          </button>
          {treeFolders.map((folder) => (
            <button
              key={folder.folderId || folder.systemKey || folder.displayName || "folder"}
              type="button"
              className={`library-media-grid__filter${isFolderActive(folder) ? " is-active" : ""}`}
              onClick={() => selectFolder(folder)}
              data-testid="library-folder-chip"
            >
              {folder.displayName || "Folder"}
            </button>
          ))}
        </div>
      ) : null}
      {activeFolder?.children?.length ? (
        <div
          className="library-media-grid__nav library-media-grid__nav--children"
          role="navigation"
          aria-label="Library subfolders"
          data-testid="library-folder-subnav"
        >
          {activeFolder.children.map((child) => (
            <button
              key={child.folderId || child.systemKey || child.displayName || "child"}
              type="button"
              className={`library-media-grid__filter library-media-grid__filter--sub${isFolderActive(child) ? " is-active" : ""}`}
              onClick={() => selectFolder(child)}
              data-testid="library-folder-subchip"
            >
              {child.displayName || "Folder"}
            </button>
          ))}
        </div>
      ) : null}
      {folderFilter ? (
        <div className="library-media-grid__breadcrumb" data-testid="library-folder-breadcrumb">
          <span className="library-media-grid__breadcrumb-path">📁 {activeFolderPath || folderFilter.label || "Folder"}</span>
          <button
            type="button"
            className="library-media-grid__filter"
            onClick={() => selectFolder(null)}
            data-testid="library-folder-clear"
          >
            Clear folder
          </button>
        </div>
      ) : null}

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
          <strong>{scope === "global" ? "No global assets yet." : "No project assets yet."}</strong>
          <p>
            {scope === "global"
              ? "Assets promoted to the global library will appear here."
              : "Generated and uploaded images, videos, audio and documents will appear here."}
          </p>
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
              folders={treeFolders}
            />
          ))}
        </div>
      )}

      {previewAsset ? <PreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} folders={treeFolders} /> : null}
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
