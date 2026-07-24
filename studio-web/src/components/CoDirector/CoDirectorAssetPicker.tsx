import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { useCoDirectorSession } from "./CoDirectorSession";

type LibraryAsset = {
  id: string;
  tag?: string;
  filename?: string;
  kind?: string;
  mime_type?: string;
  url?: string;
  thumb_url?: string;
};

export function CoDirectorAssetPicker() {
  const { assetPickerOpen, setAssetPickerOpen, uiContext, addLibraryAssets } = useCoDirectorSession();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "image" | "video">("all");
  const [assets, setAssets] = useState<LibraryAsset[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!assetPickerOpen) return;
    const projectId = uiContext.projectId;
    if (!projectId) {
      setAssets([]);
      setError("Open a project to browse Library assets.");
      return;
    }
    setBusy(true);
    setError(null);
    api
      .library(projectId, { q: query || undefined })
      .then((rows) => setAssets(rows || []))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false));
  }, [assetPickerOpen, query, uiContext.projectId]);

  const filtered = useMemo(() => {
    return assets.filter((a) => {
      const kind = `${a.kind || ""} ${a.mime_type || ""}`.toLowerCase();
      if (filter === "image") return kind.includes("image");
      if (filter === "video") return kind.includes("video");
      return true;
    });
  }, [assets, filter]);

  if (!assetPickerOpen) return null;

  const selectedAssets = filtered.filter((a) => selected[a.id]);

  return (
    <div
      className="codirector-modal-backdrop"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) setAssetPickerOpen(false);
      }}
    >
      <div
        className="codirector-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="codirector-asset-picker-title"
      >
        <div className="codirector-modal-head">
          <h3 id="codirector-asset-picker-title">Select Library assets</h3>
          <button type="button" className="ghost" onClick={() => setAssetPickerOpen(false)}>
            Close
          </button>
        </div>
        <div className="codirector-picker-toolbar">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search assets…"
            aria-label="Search assets"
          />
          <div className="codirector-filter-chips" role="group" aria-label="Asset type">
            {(["all", "image", "video"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={filter === id ? "primary" : ""}
                onClick={() => setFilter(id)}
              >
                {id}
              </button>
            ))}
          </div>
        </div>
        {error && <p className="muted">{error}</p>}
        {busy ? (
          <p className="muted">Loading assets…</p>
        ) : (
          <div className="codirector-picker-grid">
            {!filtered.length && <p className="muted">No assets found.</p>}
            {filtered.map((asset) => {
              const name = asset.tag || asset.filename || asset.id;
              const preview = asset.thumb_url || asset.url;
              return (
                <label key={asset.id} className={`codirector-picker-card ${selected[asset.id] ? "selected" : ""}`}>
                  <input
                    type="checkbox"
                    checked={!!selected[asset.id]}
                    onChange={(e) => setSelected((prev) => ({ ...prev, [asset.id]: e.target.checked }))}
                  />
                  {preview ? <img src={preview} alt="" /> : <span className="codirector-attachment-icon">Asset</span>}
                  <span title={name}>{name}</span>
                </label>
              );
            })}
          </div>
        )}
        <div className="codirector-modal-actions">
          <button type="button" className="ghost" onClick={() => setAssetPickerOpen(false)}>
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            disabled={!selectedAssets.length}
            onClick={() =>
              addLibraryAssets(
                selectedAssets.map((a) => ({
                  id: a.id,
                  name: a.tag || a.filename || a.id,
                  mimeType: a.mime_type,
                  previewUrl: a.thumb_url || a.url,
                })),
              )
            }
          >
            Add {selectedAssets.length || ""} selected
          </button>
        </div>
      </div>
    </div>
  );
}
