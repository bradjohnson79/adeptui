import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";
import {
  FILTERS,
  getAssetIcon,
  getAssetKindText,
  getAssetName,
  getCardPreviewUrl,
  matchesFilter,
  type AssetFilterId,
  type LibraryAsset,
} from "./library/assetModel";
import "./codirector-library-browser.css";

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="codirector-library-browser__empty">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

export function CoDirectorAssetPicker() {
  const { assetPickerOpen, setAssetPickerOpen, uiContext, addLibraryAssets } = useCoDirectorSession();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<AssetFilterId>("all");
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [selectedById, setSelectedById] = useState<Record<string, LibraryAsset>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const searchRef = useRef<HTMLInputElement>(null);

  const projectId = uiContext.projectId;

  const closePicker = useCallback(() => {
    setAssetPickerOpen(false);
  }, [setAssetPickerOpen]);

  useEffect(() => {
    if (!assetPickerOpen) {
      setQuery("");
      setFilter("all");
      setAssets([]);
      setSelectedById({});
      setBusy(false);
      setError(null);
      return;
    }

    searchRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closePicker();
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
    };
  }, [assetPickerOpen, closePicker]);

  useEffect(() => {
    if (!assetPickerOpen) return;
    if (!projectId) {
      setAssets([]);
      setBusy(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setBusy(true);
    setError(null);

    api
      .library(projectId, { q: query.trim() || undefined })
      .then((payload) => {
        if (cancelled) return;
        setAssets(Array.isArray(payload?.items) ? payload.items : []);
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
  }, [assetPickerOpen, projectId, query]);

  useEffect(() => {
    if (!assets.length) return;
    setSelectedById((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const asset of assets) {
        if (!next[asset.id]) continue;
        next[asset.id] = asset;
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [assets]);

  const filteredAssets = useMemo(() => assets.filter((asset) => matchesFilter(asset, filter)), [assets, filter]);

  const selectedAssets = useMemo(() => Object.values(selectedById), [selectedById]);
  const selectedCount = selectedAssets.length;
  const selectedCountLabel =
    selectedCount === 0 ? "No assets selected yet" : selectedCount === 1 ? "1 asset selected" : `${selectedCount} assets selected`;

  const toggleAsset = (asset: LibraryAsset) => {
    setSelectedById((prev) => {
      if (prev[asset.id]) {
        const next = { ...prev };
        delete next[asset.id];
        return next;
      }
      return { ...prev, [asset.id]: asset };
    });
  };

  const addSelectedAssets = () => {
    if (!selectedAssets.length) return;
    addLibraryAssets(
      selectedAssets.map((asset) => ({
        id: asset.id,
        name: getAssetName(asset),
        mimeType: asset.mime_type,
        previewUrl: getCardPreviewUrl(asset),
      })),
    );
  };

  const renderBody = () => {
    if (!projectId) {
      return (
        <EmptyState
          title="Open a project first"
          body="Choose a project to browse its Library and attach the pieces you want Co-Director to use."
        />
      );
    }

    if (busy) {
      return (
        <div className="codirector-library-browser__status">
          <p>Loading your project library...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="codirector-library-browser__status codirector-library-browser__status--error">
          <strong>We could not open the Library right now.</strong>
          <p>{error}</p>
        </div>
      );
    }

    if (!assets.length && !query.trim()) {
      return (
        <EmptyState
          title="No library items yet"
          body="Add images, video, audio, or documents to this project and they will show up here."
        />
      );
    }

    if (!filteredAssets.length && query.trim()) {
      return (
        <EmptyState
          title="No matches yet"
          body={`Nothing matched "${query.trim()}". Try a different search or switch filters.`}
        />
      );
    }

    if (!filteredAssets.length) {
      const activeFilter = FILTERS.find((item) => item.id === filter)?.label || "items";
      return (
        <EmptyState
          title={`No ${activeFilter.toLowerCase()} here yet`}
          body="Try another filter or search for something else in your project library."
        />
      );
    }

    return (
      <div className="codirector-library-browser__grid">
        {filteredAssets.map((asset) => {
          const previewUrl = getCardPreviewUrl(asset);
          const selected = Boolean(selectedById[asset.id]);
          const assetName = getAssetName(asset);

          return (
            <button
              key={asset.id}
              type="button"
              className={`codirector-library-browser__card${selected ? " is-selected" : ""}`}
              onClick={() => toggleAsset(asset)}
              aria-pressed={selected}
              data-testid={`codirector-library-asset-${asset.id}`}
            >
              <div className="codirector-library-browser__thumb">
                {previewUrl ? (
                  <img src={previewUrl} alt="" loading="lazy" />
                ) : (
                  <span className="codirector-library-browser__icon" aria-hidden>
                    {getAssetIcon(asset)}
                  </span>
                )}
                {selected ? <span className="codirector-library-browser__selected-badge">Selected</span> : null}
              </div>
              <div className="codirector-library-browser__meta">
                <strong title={assetName}>{assetName}</strong>
                <span>{getAssetKindText(asset)}</span>
              </div>
            </button>
          );
        })}
      </div>
    );
  };

  if (!assetPickerOpen || typeof document === "undefined") return null;

  return createPortal(
    <div className="codirector-library-browser" data-testid="codirector-library-browser">
      <button
        type="button"
        className="codirector-library-browser__backdrop"
        aria-label="Close project library browser"
        onClick={closePicker}
      />
      <div
        className="codirector-library-browser__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="codirector-library-browser__header">
          <div className="codirector-library-browser__title-row">
            <div>
              <p className="codirector-library-browser__eyebrow">Project Library</p>
              <h2 id={titleId}>Select from Project Library</h2>
            </div>
            <button
              type="button"
              className="codirector-library-browser__close"
              aria-label="Close project library browser"
              onClick={closePicker}
            >
              X
            </button>
          </div>
          <div className="codirector-library-browser__toolbar">
            <label className="codirector-library-browser__search">
              <span className="sr-only">Search project library</span>
              <input
                ref={searchRef}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search your project library"
                aria-label="Search project library"
              />
            </label>
            <div className="codirector-library-browser__filters" role="group" aria-label="Library filters">
              {FILTERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`codirector-library-browser__filter${filter === item.id ? " is-active" : ""}`}
                  onClick={() => setFilter(item.id)}
                  data-testid={`codirector-library-filter-${item.id}`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="codirector-library-browser__body">{renderBody()}</div>

        <div className="codirector-library-browser__footer">
          <p className="codirector-library-browser__selected-count" data-testid="codirector-library-selected-count">
            {selectedCountLabel}
          </p>
          <div className="codirector-library-browser__actions">
            <button type="button" className="ghost" onClick={closePicker} data-testid="codirector-library-cancel">
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              disabled={selectedCount === 0}
              onClick={addSelectedAssets}
              data-testid="codirector-library-add"
            >
              Add selected
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
