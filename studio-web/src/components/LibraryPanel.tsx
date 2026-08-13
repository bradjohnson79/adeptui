import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";

const DIR_STATUS = ["draft", "generating", "variations", "approved", "used_in_editor"] as const;
const ED_STATUS = ["animatic", "rough_cut", "scene_cut", "alternate", "approved", "master"] as const;
const MODEL_FAMILIES = ["all", "zimage", "flux", "qwen", "imagen", "krea2"] as const;

function favoritesKey(projectId: string) {
  return `adept-library-favorites:${projectId}`;
}

function loadFavorites(projectId: string): Set<string> {
  try {
    const raw = localStorage.getItem(favoritesKey(projectId));
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

function saveFavorites(projectId: string, ids: Set<string>) {
  localStorage.setItem(favoritesKey(projectId), JSON.stringify([...ids]));
}

function parsePromptMeta(item: any): Record<string, unknown> {
  try {
    return JSON.parse(item?.prompt_meta_json || "{}");
  } catch {
    return {};
  }
}

function assetThumbUrl(item: any): string {
  const meta = parsePromptMeta(item);
  const gate = (meta.gate || {}) as Record<string, unknown>;
  const thumb = (gate.thumbnailPath || gate.previewPath || meta.previewPath) as string | undefined;
  if (thumb) return api.mediaUrl(thumb);
  return item.kind === "image" ? api.assetUrl(item.id) : "";
}

function assetModelFamily(item: any): string | null {
  const meta = parsePromptMeta(item);
  const prov = (meta.provenance || {}) as Record<string, unknown>;
  const settings = (prov.settings || {}) as Record<string, unknown>;
  const rec = (meta.recommendation || {}) as Record<string, unknown>;
  const model = String(settings.model || meta.model || "");
  if (rec.executionFamily) return String(rec.executionFamily);
  if (/krea/i.test(model)) return "krea2";
  if (/zimage|z-image/i.test(model)) return "zimage";
  if (/flux/i.test(model)) return "flux";
  if (/qwen/i.test(model)) return "qwen";
  if (/imagen/i.test(model)) return "imagen";
  return model ? model.split("/")[0].toLowerCase() : null;
}

function assetHasReferences(item: any): boolean {
  const meta = parsePromptMeta(item);
  const prov = (meta.provenance || {}) as Record<string, unknown>;
  const refs = (prov.references || []) as unknown[];
  const parents = (prov.parentImages || []) as unknown[];
  return refs.length > 0 || parents.length > 0;
}

function ImageProvenanceBlock({ item }: { item: any }) {
  const meta = parsePromptMeta(item);
  const prov = (meta.provenance || null) as Record<string, unknown> | null;
  if (!prov) {
    return <p className="empty">No ImageProvenance on this asset.</p>;
  }
  const fields: [string, unknown][] = [
    ["workflow", prov.workflow],
    ["workflowVersion", prov.workflowVersion],
    ["runtime", prov.runtime],
    ["provider", prov.provider],
    ["prompt", prov.prompt],
    ["seed", prov.seed],
    ["intentId", prov.intentId],
    ["generationTime", prov.generationTime],
  ];
  return (
    <div data-testid="library-provenance" style={{ fontSize: "0.82rem" }}>
      {fields.map(([k, v]) =>
        v != null && v !== "" ? (
          <p key={k} style={{ margin: "0.15rem 0" }}>
            <strong>{k}</strong>: {String(v).slice(0, 120)}
            {String(v).length > 120 ? "…" : ""}
          </p>
        ) : null,
      )}
      {(prov.references as unknown[])?.length ? (
        <p className="muted">References: {(prov.references as unknown[]).length}</p>
      ) : null}
      {(prov.parentImages as unknown[])?.length ? (
        <p className="muted">Parent images: {(prov.parentImages as string[]).join(", ")}</p>
      ) : null}
    </div>
  );
}

function ReferencesUsedBlock({ projectId, assetId }: { projectId: string; assetId: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api.assetReferencesUsed(projectId, assetId).then(setData).catch(() => setData(null));
  }, [projectId, assetId]);
  const refs = data?.references || {};
  const has =
    Boolean(refs.sheet_id || refs.reference_sheet_asset_id || (refs.source_asset_ids || []).length);
  if (!has) {
    return <p className="empty">No IC-LoRA / reference provenance on this asset.</p>;
  }
  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <p className="muted" style={{ fontSize: "0.8rem" }}>
        Model: {refs.ic_lora_model_id || "—"} · Workflow: {refs.workflow_id || "—"} v{refs.workflow_version || "?"}
      </p>
      <div className="row" style={{ gap: "0.4rem", flexWrap: "wrap" }}>
        {refs.reference_sheet_asset_id && (
          <a className="linkish" href={api.assetUrl(refs.reference_sheet_asset_id)}>
            Open Reference Sheet
          </a>
        )}
        {refs.sheet_id && <span className="pill">Sheet {String(refs.sheet_id).slice(0, 8)}</span>}
        {(refs.source_asset_ids || []).length > 0 && (
          <span className="pill">{(refs.source_asset_ids || []).length} source refs</span>
        )}
      </div>
    </div>
  );
}

export function LibraryPanel({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange: () => Promise<void>;
  onGo?: (tab: EditorTab) => void;
}) {
  const [scope, setScope] = useState<"project" | "global">("project");
  const [q, setQ] = useState("");
  const [folderFilter, setFolderFilter] = useState<{ folderId?: string; systemKey?: string; label?: string } | null>(
    null
  );
  const [treeFolders, setTreeFolders] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [graph, setGraph] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [sheets, setSheets] = useState<any[]>([]);
  const [avatars, setAvatars] = useState<any[]>([]);
  const [dirSeqs, setDirSeqs] = useState<any[]>([]);
  const [editor, setEditor] = useState<any>(null);
  const [dirFilter, setDirFilter] = useState<string>("all");
  const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites(project.id));
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [modelFamilyFilter, setModelFamilyFilter] = useState<string>("all");
  const [refsFilter, setRefsFilter] = useState<"all" | "has" | "none">("all");
  const [collectionFilter, setCollectionFilter] = useState<string>("");
  const [collections, setCollections] = useState<any[]>([]);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [genHistory, setGenHistory] = useState<any[]>([]);

  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<"single" | "bulk" | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteResults, setDeleteResults] = useState<string | null>(null);

  useEffect(() => {
    setFavorites(loadFavorites(project.id));
  }, [project.id]);

  useEffect(() => {
    api.imageProductCollections(project.id).then((r) => setCollections(r.collections || [])).catch(() => setCollections([]));
    api.imageProductHistory(project.id, 20).then((r) => setGenHistory(r.entries || [])).catch(() => setGenHistory([]));
  }, [project.id, project.assets.length]);

  const refresh = () =>
    api
      .library(project.id, {
        q,
        scope,
        folder: folderFilter?.folderId,
        system_key: folderFilter?.systemKey,
      })
      .then((payload) => {
        setItems(payload.items || []);
        setTreeFolders(payload.tree?.folders || []);
      })
      .catch(console.error);

  useEffect(() => {
    refresh();
  }, [project.id, q, scope, folderFilter, project.assets.length]);

  useEffect(() => {
    api.listMasterSheets(project.id).then(setSheets).catch(() => setSheets([]));
    api.listAvatarSessions(project.id).then(setAvatars).catch(() => setAvatars([]));
    api.listDirectorSequences(project.id).then(setDirSeqs).catch(() => setDirSeqs([]));
    api.getEditor(project.id).then(setEditor).catch(() => setEditor(null));
  }, [project.id, project.updated_at]);

  useEffect(() => {
    if (!selected) {
      setGraph(null);
      return;
    }
    api.assetGraph(selected).then(setGraph).catch(console.error);
  }, [selected]);

  const suggestLabel = async (id: string) => {
    const guess = prompt("Confirm AI categorize label (required confirm):", "character");
    if (!guess) return;
    await api.patchAssetMeta(id, { labels_json: JSON.stringify([guess]), tag: guess });
    setMsg(`Labeled ${guess}`);
    await onChange();
    refresh();
  };

  const toggleFavorite = (assetId: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      saveFavorites(project.id, next);
      return next;
    });
  };

  const createCollection = async () => {
    const name = newCollectionName.trim();
    if (!name) return;
    const col = await api.imageProductCreateCollection(project.id, { name });
    setCollections((prev) => [...prev, col]);
    setNewCollectionName("");
    setMsg(`Collection “${name}” created`);
  };

  const addSelectedToCollection = async (collectionId: string) => {
    if (!selected) return;
    await api.imageProductAddCollectionAssets(project.id, collectionId, [selected]);
    const r = await api.imageProductCollections(project.id);
    setCollections(r.collections || []);
    setMsg("Added to collection");
  };

  const filteredItems = useMemo(() => {
    let rows = items;
    if (showFavoritesOnly) rows = rows.filter((a) => favorites.has(a.id));
    if (modelFamilyFilter !== "all") {
      rows = rows.filter((a) => assetModelFamily(a) === modelFamilyFilter);
    }
    if (refsFilter === "has") rows = rows.filter((a) => assetHasReferences(a));
    if (refsFilter === "none") rows = rows.filter((a) => !assetHasReferences(a));
    if (collectionFilter) {
      const col = collections.find((c) => c.collectionId === collectionFilter);
      const ids = new Set(col?.assetIds || []);
      rows = rows.filter((a) => ids.has(a.id));
    }
    return rows;
  }, [items, showFavoritesOnly, favorites, modelFamilyFilter, refsFilter, collectionFilter, collections]);

  const selectedItem = useMemo(() => items.find((a) => a.id === selected) || null, [items, selected]);

  const enterSelect = useCallback(() => {
    setSelectMode(true);
    setSelectedIds(new Set());
  }, []);

  const exitSelect = useCallback(() => {
    setSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  const toggleSelect = useCallback((assetId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(filteredItems.filter((a) => a.kind === "image").map((a) => a.id)));
  }, [filteredItems]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (deleteConfirm !== "bulk") return;
    setDeleteBusy(true);
    try {
      const ids = [...selectedIds];
      const res = await api.sceneReferences.bulkDeleteAssets(project.id, ids, false);
      const results = res?.results ?? [];
      const failed = results.filter((r: { assetId: string; status: string; name?: string }) => r.status !== "deleted" && r.status !== "ok");
      if (failed.length > 0) {
        const names = failed.map((r: { assetId: string; status: string; name?: string }) => r.name || r.assetId).join(", ");
        setDeleteResults(`Some assets could not be deleted: ${names}`);
      } else {
        setDeleteResults(`${ids.length} asset${ids.length !== 1 ? "s" : ""} deleted.`);
      }
      setDeleteConfirm(null);
      setSelectMode(false);
      setSelectedIds(new Set());
      await refresh();
    } catch (err) {
      setDeleteResults(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleteBusy(false);
    }
  }, [deleteConfirm, selectedIds, project.id, refresh]);

  const filteredDir = dirFilter === "all" ? dirSeqs : dirSeqs.filter((s) => s.status === dirFilter);
  const clipCount = editor
    ? Object.values(editor.tracks || {}).reduce(
        (n: number, clips) => n + ((clips as any[])?.length || 0),
        0
      )
    : 0;

  return (
    <div className="page library-page">
      <h1>Libraries</h1>
      <p className="muted">Project and Global scopes · smart search · version lineage · Asset Graph</p>
      {msg && <p className="pill">{msg}</p>}

      <div className="row" style={{ gap: "0.5rem", alignItems: "center" }}>
        <button type="button" className={scope === "project" ? "primary" : ""} onClick={() => setScope("project")}>
          Project Library
        </button>
        <button type="button" className={scope === "global" ? "primary" : ""} onClick={() => setScope("global")}>
          Global Library
        </button>
        <input
          style={{ flex: 1 }}
          placeholder="Search filename, tags, prompt, labels…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <section className="dash-card" style={{ margin: "1rem 0" }}>
        <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
          Timeline Sequences
        </h2>
        <p className="muted">Prompt Timeline packages — draft through approved / used in Editor.</p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.5rem" }}>
          <button type="button" className={dirFilter === "all" ? "primary" : ""} onClick={() => setDirFilter("all")}>
            All
          </button>
          {DIR_STATUS.map((s) => (
            <button
              key={s}
              type="button"
              className={dirFilter === s ? "primary" : ""}
              onClick={() => setDirFilter(s)}
            >
              {s === "used_in_editor" ? "Used in Editor" : s}
            </button>
          ))}
        </div>
        {!filteredDir.length ? (
          <p className="empty">No Timeline sequences yet. Send from Timeline Prompt.</p>
        ) : (
          <ul className="ms-list">
            {filteredDir.map((s) => (
              <li key={s.id}>
                <strong>{s.name || "Sequence"}</strong>
                <span className="scene-meta">
                  {" "}
                  · v{s.version} · {s.status}
                  {s.scene_id ? ` · scene ${String(s.scene_id).slice(0, 8)}` : ""}
                </span>
                {onGo && (
                  <button type="button" style={{ marginLeft: 8 }} onClick={() => onGo("timeline")}>
                    Open Timeline
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="dash-card" style={{ margin: "1rem 0" }}>
        <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
          Editor Sequences
        </h2>
        <p className="muted">
          Assembly timeline status — Animatics / Rough Cuts / Scene Cuts / Alternate / Approved / Master.
        </p>
        <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.5rem" }}>
          {ED_STATUS.map((s) => (
            <span key={s} className={`pill ${editor?.status === s ? "warn" : ""}`}>
              {s.replace(/_/g, " ")}
              {editor?.status === s ? " ✓" : ""}
            </span>
          ))}
        </div>
        {!editor ? (
          <p className="empty">No Editor project yet.</p>
        ) : (
          <p>
            <strong>{editor.name || "Editor"}</strong>
            <span className="scene-meta">
              {" "}
              · {String(editor.status || "").replace(/_/g, " ")} · {clipCount} clip
              {clipCount === 1 ? "" : "s"}
            </span>
            {onGo && (
              <button type="button" style={{ marginLeft: 8 }} onClick={() => onGo("magi")}>
                Open MAGI Editor
              </button>
            )}
          </p>
        )}
      </section>

      <section className="dash-card" style={{ margin: "1rem 0" }}>
        <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
          Scene Master Sheets
        </h2>
        <p className="muted">Whole-Scene Packages — structured what-exists data (not collage boards).</p>
        {!sheets.length ? (
          <p className="empty">No master sheets saved yet. Open Scene Master Sheet from the hamburger menu.</p>
        ) : (
          <ul className="ms-list">
            {sheets.map((s) => (
              <li key={s.id}>
                <strong>{s.title || "Master Sheet"}</strong> · {s.version}
                {s.approved_authority ? " · Authority ✓" : ""} · scene {s.scene_id?.slice(0, 8)}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="dash-card" style={{ margin: "1rem 0" }}>
        <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
          Avatars
        </h2>
        <p className="muted">Avatar Sessions — Looks, Voice, takes, and lip-sync checkpoints.</p>
        {!avatars.length ? (
          <p className="empty">No avatar sessions yet. Open Avatar Studio from Generation.</p>
        ) : (
          <ul className="ms-list">
            {avatars.map((a) => (
              <li key={a.id}>
                <strong>{a.name || a.character_name || a.id}</strong>
                <span className="scene-meta">
                  {" "}
                  · {a.mode || "talking_portrait"} · {(a.takes || []).length} take
                  {(a.takes || []).length === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="dash-card" style={{ margin: "1rem 0" }} data-testid="library-collections">
        <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
          Production Collections
        </h2>
        <p className="muted">Image-product collections — group assets for production handoff.</p>
        <div className="row" style={{ gap: "0.4rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
          <input
            value={newCollectionName}
            onChange={(e) => setNewCollectionName(e.target.value)}
            placeholder="New collection name"
            data-testid="library-new-collection"
          />
          <button type="button" onClick={() => void createCollection()} disabled={!newCollectionName.trim()}>
            Create
          </button>
        </div>
        {!collections.length ? (
          <p className="empty">No collections yet.</p>
        ) : (
          <ul className="ms-list">
            {collections.map((c) => (
              <li key={c.collectionId}>
                <button
                  type="button"
                  className={collectionFilter === c.collectionId ? "primary" : "linkish"}
                  onClick={() =>
                    setCollectionFilter((prev) => (prev === c.collectionId ? "" : c.collectionId))
                  }
                >
                  {c.name}
                </button>
                <span className="scene-meta"> · {(c.assetIds || []).length} assets</span>
                {selected && (
                  <button
                    type="button"
                    style={{ marginLeft: 8 }}
                    onClick={() => void addSelectedToCollection(c.collectionId)}
                  >
                    + selected
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="row" style={{ gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.75rem" }} data-testid="library-filters">
        <button
          type="button"
          className={showFavoritesOnly ? "primary" : ""}
          onClick={() => setShowFavoritesOnly((v) => !v)}
        >
          ★ Favorites{favorites.size ? ` (${favorites.size})` : ""}
        </button>
        {MODEL_FAMILIES.map((f) => (
          <button
            key={f}
            type="button"
            className={modelFamilyFilter === f ? "primary" : ""}
            onClick={() => setModelFamilyFilter(f)}
          >
            {f === "all" ? "All models" : f === "krea2" ? "Krea 2" : f}
          </button>
        ))}
        {(["all", "has", "none"] as const).map((r) => (
          <button
            key={r}
            type="button"
            className={refsFilter === r ? "primary" : ""}
            onClick={() => setRefsFilter(r)}
          >
            {r === "all" ? "Any refs" : r === "has" ? "Has refs" : "No refs"}
          </button>
        ))}
        {collectionFilter && (
          <button type="button" className="ghost" onClick={() => setCollectionFilter("")}>
            Clear collection filter
          </button>
        )}
        {selectMode ? (
          <div className="library-select-actions">
            <button
              type="button"
              onClick={() => {
                const imageIds = filteredItems.filter((a) => a.kind === "image").map((a) => a.id);
                if (imageIds.length > 0 && imageIds.every((id) => selectedIds.has(id))) {
                  clearSelection();
                } else {
                  selectAll();
                }
              }}
              disabled={filteredItems.filter((a) => a.kind === "image").length === 0}
            >
              {filteredItems.filter((a) => a.kind === "image").length > 0 &&
              filteredItems.filter((a) => a.kind === "image").every((a) => selectedIds.has(a.id))
                ? "Clear"
                : "Select All"}
            </button>
            <button
              type="button"
              className="library-delete-btn"
              disabled={selectedIds.size === 0}
              onClick={() => setDeleteConfirm("bulk")}
            >
              Delete Selected ({selectedIds.size})
            </button>
            <button type="button" className="primary" onClick={exitSelect}>
              Done
            </button>
          </div>
        ) : (
          <button type="button" onClick={enterSelect}>
            Select
          </button>
        )}
      </div>

      {deleteResults && <p className="pill warn">{deleteResults}</p>}

      <div className="library-layout">
        <aside className="library-inspector" style={{ maxWidth: 220 }}>
          <h2>Folders</h2>
          <button
            type="button"
            className={!folderFilter ? "primary" : ""}
            style={{ display: "block", marginBottom: "0.35rem", width: "100%", textAlign: "left" }}
            onClick={() => setFolderFilter(null)}
          >
            All assets
          </button>
          {!treeFolders.length ? (
            <p className="empty">No folder tree.</p>
          ) : (
            <ul className="home-list" style={{ fontSize: "0.85rem" }}>
              {treeFolders.map((f) => (
                <li key={f.folderId || f.systemKey}>
                  <button
                    type="button"
                    className={
                      folderFilter?.systemKey === f.systemKey || folderFilter?.folderId === f.folderId
                        ? "linkish primary"
                        : "linkish"
                    }
                    onClick={() =>
                      setFolderFilter({
                        folderId: f.folderId,
                        systemKey: f.systemKey,
                        label: f.displayName,
                      })
                    }
                  >
                    {f.displayName}
                  </button>
                  {(f.children || []).slice(0, 6).map((child: any) => (
                    <button
                      key={child.folderId || child.systemKey}
                      type="button"
                      className={
                        folderFilter?.systemKey === child.systemKey ? "linkish primary" : "linkish"
                      }
                      style={{ display: "block", marginLeft: "0.75rem", fontSize: "0.8rem" }}
                      onClick={() =>
                        setFolderFilter({
                          folderId: child.folderId,
                          systemKey: child.systemKey,
                          label: child.displayName,
                        })
                      }
                    >
                      {child.displayName}
                    </button>
                  ))}
                </li>
              ))}
            </ul>
          )}
          {folderFilter?.label && (
            <p className="muted" style={{ fontSize: "0.75rem" }}>
              Filter: {folderFilter.label}
            </p>
          )}
        </aside>
        <div className="library-grid">
          {!filteredItems.length ? (
            <p className="empty">No assets match filters.</p>
          ) : (
            filteredItems.map((a) => {
              const isImage = a.kind === "image";
              const showSelect = selectMode && isImage;
              const isSelected = selectedIds.has(a.id);
              return (
                <button
                  key={a.id}
                  type="button"
                  className={`library-card${selected === a.id ? " selected" : ""}${isSelected ? " is-library-selected" : ""}${showSelect ? " is-selectable" : ""}`}
                  onClick={() => {
                    if (showSelect) {
                      toggleSelect(a.id);
                      return;
                    }
                    setSelected(a.id);
                  }}
                >
                  {showSelect && (
                    <label
                      className={`library-checkbox${isSelected ? " is-checked" : ""}`}
                      onClick={(e) => { e.stopPropagation(); }}
                    >
                      <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(a.id)} />
                    </label>
                  )}
                  {isImage ? (
                    <img src={assetThumbUrl(a)} alt={a.filename} loading="lazy" />
                  ) : (
                    <div className="library-card-fallback">{a.kind}</div>
                  )}
                  <span>
                    {favorites.has(a.id) ? "★ " : ""}
                    {a.tag || a.filename}
                  </span>
                  {assetModelFamily(a) && (
                    <span className="pill" style={{ fontSize: "0.65rem" }}>
                      {assetModelFamily(a)}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        <aside className="library-inspector">
          <h2>Asset Graph</h2>
          {!selected || !graph ? (
            <p className="empty">Select an asset.</p>
          ) : (
            <>
              <p>
                <strong>{graph.asset.tag || graph.asset.filename}</strong> · {graph.asset.kind}
              </p>
              <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
                <button type="button" onClick={() => suggestLabel(selected)}>
                  AI categorize (confirm)
                </button>
                <button type="button" onClick={() => toggleFavorite(selected)}>
                  {favorites.has(selected) ? "Unfavorite" : "Favorite"}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    api.promoteGlobal(selected).then(() => {
                      setMsg("Promoted to global");
                      refresh();
                    })
                  }
                >
                  Promote to Global
                </button>
              </div>
              <h3>ImageProvenance</h3>
              {selectedItem ? <ImageProvenanceBlock item={selectedItem} /> : null}
              <h3>Generation history</h3>
              {!genHistory.length ? (
                <p className="empty">No image-product history yet.</p>
              ) : (
                <ul className="home-list" style={{ fontSize: "0.8rem" }}>
                  {genHistory.slice(0, 8).map((h, i) => (
                    <li key={h.jobId || i}>
                      {String(h.purpose || "generate")} · {String(h.prompt || "").slice(0, 48)}
                      {h.jobId ? ` · ${String(h.jobId).slice(0, 8)}` : ""}
                    </li>
                  ))}
                </ul>
              )}
              <h3>References used</h3>
              <ReferencesUsedBlock projectId={project.id} assetId={selected} />
              <h3>Related / lineage</h3>
              <p className="muted" style={{ fontSize: "0.8rem" }}>
                Edges: storyboard_of · spatial_of · camera_of · derived_from · used_in_director
              </p>
              {!graph.related?.length ? (
                <p className="empty">No edges yet.</p>
              ) : (
                <ul className="home-list">
                  {graph.related.map((r: any) => (
                    <li key={r.id}>
                      <button type="button" className="linkish" onClick={() => setSelected(r.id)}>
                        {r.relation}: {r.tag || r.filename}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <h3>Versions</h3>
              {!graph.versions?.length ? (
                <p className="empty">No version timeline.</p>
              ) : (
                <ul className="home-list">
                  {graph.versions.map((v: any) => (
                    <li key={v.id}>
                      v{v.version} · {v.op} · seed {v.seed} · {v.model}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </aside>
      </div>

      {deleteConfirm &&
        createPortal(
          <div className="library-confirm">
            <div className="library-confirm__panel">
              <h3>Delete {selectedIds.size} asset{selectedIds.size !== 1 ? "s" : ""}?</h3>
              <p className="library-confirm__hint">
                This action cannot be undone. Assets used in scenes may block deletion.
              </p>
              <div className="library-confirm__actions">
                <button type="button" onClick={() => setDeleteConfirm(null)} disabled={deleteBusy}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="library-confirm__confirm"
                  onClick={handleDeleteConfirm}
                  disabled={deleteBusy}
                >
                  {deleteBusy ? "Deleting…" : "Delete"}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
