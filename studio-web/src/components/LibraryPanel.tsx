import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";
import { HelpTip } from "./HelpTip";

const DIR_STATUS = ["draft", "generating", "variations", "approved", "used_in_editor"] as const;
const ED_STATUS = ["animatic", "rough_cut", "scene_cut", "alternate", "approved", "master"] as const;
const MODEL_FAMILIES = ["all", "zimage", "flux", "qwen", "imagen", "krea2"] as const;

type TypeNav =
  | "all"
  | "images"
  | "video"
  | "audio"
  | "characters"
  | "props"
  | "scenes"
  | "environments"
  | "storyboards"
  | "scripts"
  | "presets"
  | "posecraft"
  | "scene_image";

const TYPE_NAV: { id: TypeNav; label: string; testId?: string }[] = [
  { id: "all", label: "All" },
  { id: "images", label: "Images", testId: "library-filter-images" },
  { id: "video", label: "Video", testId: "library-filter-video" },
  { id: "audio", label: "Audio", testId: "library-filter-audio" },
  { id: "characters", label: "Characters" },
  { id: "props", label: "Props" },
  { id: "scenes", label: "Scenes" },
  { id: "environments", label: "Environments" },
  { id: "storyboards", label: "Storyboards" },
  { id: "scripts", label: "Scripts" },
  { id: "presets", label: "Presets/Templates" },
  { id: "scene_image", label: "Scene Images" },
];

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

function parseLabels(item: any): string[] {
  try {
    const raw = item?.labels_json;
    if (Array.isArray(raw)) return raw.map(String);
    const parsed = JSON.parse(raw || "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function assetThumbUrl(item: any): string {
  const meta = parsePromptMeta(item);
  const gate = (meta.gate || {}) as Record<string, unknown>;
  const thumb = (gate.thumbnailPath || gate.previewPath || meta.previewPath) as string | undefined;
  if (thumb) return api.mediaUrl(thumb);
  if (item.thumb_url) return String(item.thumb_url);
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

function modelFamilyLabel(family: string | null | undefined): string {
  if (!family) return "";
  if (family === "zimage") return "Z-Image";
  if (family === "krea2") return "Krea 2";
  if (family === "flux") return "Flux";
  if (family === "qwen") return "Qwen";
  if (family === "imagen") return "Imagen";
  if (family === "all") return "All";
  return family;
}

function assetHasReferences(item: any): boolean {
  const meta = parsePromptMeta(item);
  const prov = (meta.provenance || {}) as Record<string, unknown>;
  const refs = (prov.references || []) as unknown[];
  const parents = (prov.parentImages || []) as unknown[];
  return refs.length > 0 || parents.length > 0;
}

function folderKeyOf(item: any): string {
  return String(item?.folderSystemKey || item?.systemKey || item?.classification?.targetFolder || "").toLowerCase();
}

function typeHaystack(item: any): string {
  return [item?.kind, item?.filename, item?.tag, item?.libraryPath, folderKeyOf(item), parseLabels(item).join(" ")]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function matchesTypeNav(item: any, type: TypeNav): boolean {
  if (type === "all") return true;
  const kind = String(item?.kind || "").toLowerCase();
  const key = folderKeyOf(item);
  const hay = typeHaystack(item);
  if (type === "images") return kind === "image";
  if (type === "video") return kind === "video" || key.startsWith("video");
  if (type === "audio") return kind === "audio" || key.startsWith("audio");
  if (type === "characters") {
    return key.startsWith("characters") || Boolean(item?.characterId) || /\bcharacter/.test(hay);
  }
  if (type === "props") {
    return key.startsWith("props") || Boolean(item?.propId) || /\bprop/.test(hay);
  }
  if (type === "scenes") {
    return key.startsWith("scenes") || Boolean(item?.sceneId) || /\bscene/.test(hay);
  }
  if (type === "environments") {
    return key.startsWith("environments") || key.includes("environment") || /environment/.test(hay);
  }
  if (type === "storyboards") {
    return key.startsWith("storyboards") || /storyboard/.test(hay);
  }
  if (type === "scripts") {
    return kind === "script" || key.startsWith("scripts") || /\bscript/.test(hay);
  }
  if (type === "presets") {
    return key.startsWith("templates_presets") || key.includes("preset") || /preset|template/.test(hay);
  }
  if (type === "posecraft") {
    return key.includes("posecraft") || /posecraft|pose\s*craft|\bpose\b/.test(hay);
  }
  if (type === "scene_image") {
    return (
      key.includes("scene_image") ||
      /scene_image|approved_scene_image|scene_shot|approved_take/.test(hay) ||
      String(item?.assetType || item?.label || "").toLowerCase().includes("scene")
    );
  }
  return true;
}

function kindLabel(kind: string | undefined): string {
  const k = String(kind || "").toLowerCase();
  if (k === "image") return "Image";
  if (k === "video") return "Video";
  if (k === "audio") return "Audio";
  if (k === "script") return "Script";
  return kind ? String(kind) : "File";
}

function formatWhen(value: unknown): string | null {
  if (!value) return null;
  const d = new Date(String(value));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString();
}

function collectionModified(col: any): string | null {
  const meta = (col?.metadata || {}) as Record<string, unknown>;
  return (
    formatWhen(col?.updatedAt) ||
    formatWhen(col?.updated_at) ||
    formatWhen(col?.lastModified) ||
    formatWhen(meta.updatedAt) ||
    formatWhen(meta.lastModified) ||
    formatWhen(meta.updated_at)
  );
}

function TypeGlyph({ kind }: { kind: string }) {
  const k = String(kind || "").toLowerCase();
  const glyph = k === "video" ? "â–¶" : k === "audio" ? "â™ª" : k === "script" ? "â‰¡" : "â–£";
  return (
    <span className={`library-type-glyph library-type-glyph--${k || "file"}`} aria-hidden>
      {glyph}
    </span>
  );
}

function ImageProvenanceBlock({ item }: { item: any }) {
  const meta = parsePromptMeta(item);
  const prov = (meta.provenance || null) as Record<string, unknown> | null;
  if (!prov) {
    return <p className="library-empty-compact">No generation notes on this item.</p>;
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
    <div data-testid="library-provenance" className="library-details-block">
      {fields.map(([k, v]) =>
        v != null && v !== "" ? (
          <p key={k}>
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
    return <p className="library-empty-compact">No reference notes on this item.</p>;
  }
  return (
    <div className="library-details-block">
      <p className="muted">
        Model: {refs.ic_lora_model_id || "—"} · Workflow: {refs.workflow_id || "—"} v{refs.workflow_version || "?"}
      </p>
      <div className="row library-inline-row">
        {refs.reference_sheet_asset_id && (
          <a className="linkish" href={api.assetUrl(refs.reference_sheet_asset_id)}>
            Open reference sheet
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

function LibraryPack({
  title,
  count,
  open,
  onToggle,
  children,
  testId,
}: {
  title: string;
  count: number;
  open: boolean;
  onToggle: (next: boolean) => void;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <details
      className="library-pack"
      open={open}
      data-testid={testId}
      onToggle={(e) => {
        const next = (e.currentTarget as HTMLDetailsElement).open;
        if (next !== open) onToggle(next);
      }}
    >
      <summary className="library-pack-summary">
        <span>{title}</span>
        <span className="library-pack-count">{count}</span>
      </summary>
      <div className="library-pack-body">{children}</div>
    </details>
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
    null,
  );
  const [typeNav, setTypeNav] = useState<TypeNav>(() => {
    try {
      const raw = String(new URLSearchParams(window.location.search).get("assetType") || "").toLowerCase();
      if (raw === "posecraft") return "posecraft";
      if (raw === "scene_image" || raw === "approved_scene_image") return "scene_image";
      if ((TYPE_NAV as { id: string }[]).some((t) => t.id === raw)) return raw as TypeNav;
    } catch {
      /* ignore */
    }
    return "all";
  });
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
  const [packOpen, setPackOpen] = useState<Record<string, boolean>>({});

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
    if (typeNav !== "all") rows = rows.filter((a) => matchesTypeNav(a, typeNav));
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
  }, [items, typeNav, showFavoritesOnly, favorites, modelFamilyFilter, refsFilter, collectionFilter, collections]);

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
        0,
      )
    : 0;

  const isPackOpen = (key: string, hasItems: boolean) => packOpen[key] ?? hasItems;
  const setPack = (key: string, next: boolean) => setPackOpen((prev) => ({ ...prev, [key]: next }));

  const imageItems = filteredItems.filter((a) => a.kind === "image");
  const allImagesSelected = imageItems.length > 0 && imageItems.every((a) => selectedIds.has(a.id));

  const collectionThumb = (col: any): string => {
    const ids = (col?.assetIds || []) as string[];
    const hit = items.find((a) => ids.includes(a.id) && a.kind === "image");
    return hit ? assetThumbUrl(hit) : "";
  };

  return (
    <div className="page library-page">
      <h1>Libraries</h1>
      <p className="muted library-lede">Find pictures, video, audio, and other files for this project.</p>
      {msg && <p className="pill">{msg}</p>}

      <section className="library-section-assets" data-testid="library-section-assets">
        <div className="library-asset-bar">
          <button
            type="button"
            className={scope === "project" ? "primary" : ""}
            data-testid="library-scope-project"
            onClick={() => setScope("project")}
          >
            Project Library
          </button>
          <button
            type="button"
            className={scope === "global" ? "primary" : ""}
            data-testid="library-scope-global"
            onClick={() => setScope("global")}
          >
            Global Library
          </button>
          <input
            className="library-search"
            data-testid="library-search"
            placeholder="Search names, tags, or prompts"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <div className="library-type-nav" data-testid="library-type-nav">
          <span className="library-filter-legend">
            Type
            <HelpTip text="Show only pictures, video, audio, or a folder kind. All clears this filter." />
          </span>
          {TYPE_NAV.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={typeNav === chip.id ? "primary" : ""}
              data-testid={chip.testId}
              onClick={() => setTypeNav(chip.id)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        <div className="library-filter-groups" data-testid="library-filters">
          <div className="library-filter-group">
            <span className="library-filter-legend">
              Model
              <HelpTip text="Show items made with this look. All shows every model." />
            </span>
            {MODEL_FAMILIES.map((f) => (
              <button
                key={f}
                type="button"
                className={modelFamilyFilter === f ? "primary" : ""}
                data-testid={`library-filter-model-${f}`}
                onClick={() => setModelFamilyFilter(f)}
              >
                {modelFamilyLabel(f)}
              </button>
            ))}
          </div>
          <div className="library-filter-group">
            <span className="library-filter-legend">
              References
              <HelpTip text="Has refs means this item used other pictures as a guide." />
            </span>
            {(["all", "has", "none"] as const).map((r) => (
              <button
                key={r}
                type="button"
                className={refsFilter === r ? "primary" : ""}
                onClick={() => setRefsFilter(r)}
              >
                {r === "all" ? "Any" : r === "has" ? "Has refs" : "No refs"}
              </button>
            ))}
          </div>
          <div className="library-filter-group">
            <button
              type="button"
              className={showFavoritesOnly ? "primary" : ""}
              onClick={() => setShowFavoritesOnly((v) => !v)}
            >
              â˜… Favorites{favorites.size ? ` (${favorites.size})` : ""}
            </button>
            {collectionFilter && (
              <button type="button" className="ghost" onClick={() => setCollectionFilter("")}>
                Clear collection
              </button>
            )}
            {selectMode ? (
              <div className="library-select-actions">
                <button
                  type="button"
                  onClick={() => {
                    if (allImagesSelected) clearSelection();
                    else selectAll();
                  }}
                  disabled={imageItems.length === 0}
                >
                  {allImagesSelected ? "Clear" : "Select All"}
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
                Selection mode
              </button>
            )}
          </div>
        </div>

        {deleteResults && <p className="pill warn">{deleteResults}</p>}

        <div className={`library-layout${selected ? " has-selection" : ""}`}>
          <aside className="library-sidebar library-inspector">
            <h2>Folders</h2>
            <button
              type="button"
              className={!folderFilter && !collectionFilter ? "primary" : ""}
              onClick={() => {
                setFolderFilter(null);
                setCollectionFilter("");
                setTypeNav("all");
              }}
            >
              All assets
            </button>
            {!treeFolders.length ? (
              <p className="library-empty-compact">No folders yet.</p>
            ) : (
              <ul className="library-folder-list">
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
            {folderFilter?.label && <p className="muted library-folder-hint">Folder: {folderFilter.label}</p>}
          </aside>

          <div className="library-grid">
            {!filteredItems.length ? (
              <p className="library-empty-compact" data-testid="library-empty-compact">
                Nothing matches these filters.
              </p>
            ) : (
              filteredItems.map((a) => {
                const isImage = a.kind === "image";
                const showSelect = selectMode && isImage;
                const isSelected = selectedIds.has(a.id);
                const family = assetModelFamily(a);
                const hasRefs = assetHasReferences(a);
                const title = a.tag || a.filename || "Untitled";
                return (
                  <button
                    key={a.id}
                    type="button"
                    data-testid="library-asset-card"
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
                        onClick={(e) => {
                          e.stopPropagation();
                        }}
                      >
                        <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(a.id)} />
                      </label>
                    )}
                    {isImage ? (
                      <img src={assetThumbUrl(a)} alt={title} loading="lazy" />
                    ) : (
                      <div className={`library-card-media library-card-media--${a.kind || "file"}`}>
                        <TypeGlyph kind={a.kind} />
                        <span className="library-card-media-kind">{kindLabel(a.kind)}</span>
                        <span className="library-card-media-name">{a.filename || a.tag || "—"}</span>
                      </div>
                    )}
                    <span className="library-card-kicker">
                      <TypeGlyph kind={a.kind} />
                      {kindLabel(a.kind)}
                    </span>
                    <span className="library-card-title">
                      {favorites.has(a.id) ? "â˜… " : ""}
                      {title}
                    </span>
                    <span className="library-card-tags">
                      {family ? <span className="library-model-tag">{modelFamilyLabel(family)}</span> : null}
                      {hasRefs ? <span className="library-ref-tag">Has refs</span> : null}
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <aside className="library-inspector library-graph">
            <div className="library-inspector-head">
              <h2>Asset Graph</h2>
              <HelpTip text="Shows how this item connects to other files you have selected." />
            </div>
            {!selected ? (
              <p className="library-empty-compact">Select an item to see how it connects.</p>
            ) : (
              <>
                <p className="library-graph-title">
                  <strong>{graph?.asset?.tag || graph?.asset?.filename || selectedItem?.tag || selectedItem?.filename}</strong>
                  <span className="muted"> · {kindLabel(graph?.asset?.kind || selectedItem?.kind)}</span>
                </p>
                <div className="row library-inline-row">
                  <button type="button" onClick={() => toggleFavorite(selected)}>
                    {favorites.has(selected) ? "Unfavorite" : "Favorite"}
                  </button>
                </div>
                {graph?.related?.length ? (
                  <ul className="library-related-list">
                    {graph.related.slice(0, 6).map((r: any) => (
                      <li key={r.id}>
                        <button type="button" className="linkish" onClick={() => setSelected(r.id)}>
                          {r.tag || r.filename}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="library-empty-compact">
                    {graph ? "No connected items yet." : "Loading connections…"}
                  </p>
                )}
                <details className="library-details">
                  <summary>Details</summary>
                  <div className="library-inline-row">
                    <button type="button" onClick={() => suggestLabel(selected)}>
                      AI categorize (confirm)
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
                  <h3>Generation notes</h3>
                  {selectedItem ? <ImageProvenanceBlock item={selectedItem} /> : null}
                  <h3>Recent generations</h3>
                  {!genHistory.length ? (
                    <p className="library-empty-compact">No recent generations yet.</p>
                  ) : (
                    <ul className="library-mini-list">
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
                  <h3>Connections</h3>
                  <p className="muted library-edge-names">
                    Edges: storyboard_of · spatial_of · camera_of · derived_from · used_in_director
                  </p>
                  {!graph?.related?.length ? (
                    <p className="library-empty-compact">No connections yet.</p>
                  ) : (
                    <ul className="library-mini-list">
                      {graph.related.map((r: any) => (
                        <li key={`edge-${r.id}`}>
                          <button type="button" className="linkish" onClick={() => setSelected(r.id)}>
                            {r.relation}: {r.tag || r.filename}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <h3>Versions</h3>
                  {!graph?.versions?.length ? (
                    <p className="library-empty-compact">No versions yet.</p>
                  ) : (
                    <ul className="library-mini-list">
                      {graph.versions.map((v: any) => (
                        <li key={v.id}>
                          v{v.version} · {v.op} · seed {v.seed} · {v.model}
                        </li>
                      ))}
                    </ul>
                  )}
                </details>
              </>
            )}
          </aside>
        </div>
      </section>

      <LibraryPack
        title="Timeline Sequences"
        count={filteredDir.length}
        open={isPackOpen("timeline", dirSeqs.length > 0)}
        onToggle={(next) => setPack("timeline", next)}
      >
        <p className="muted library-pack-lede">Sequences you sent from Timeline.</p>
        <div className="row library-inline-row">
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
          <p className="library-empty-compact">
            Make a sequence in Timeline
            {onGo && (
              <button type="button" className="library-empty-action" onClick={() => onGo("timeline")}>
                Open Timeline
              </button>
            )}
          </p>
        ) : (
          <ul className="library-mini-list">
            {filteredDir.map((s) => (
              <li key={s.id}>
                <strong>{s.name || "Sequence"}</strong>
                <span className="scene-meta">
                  {" "}
                  · v{s.version} · {s.status}
                  {s.scene_id ? ` · scene ${String(s.scene_id).slice(0, 8)}` : ""}
                </span>
                {onGo && (
                  <button type="button" className="library-row-action" onClick={() => onGo("timeline")}>
                    Open Timeline
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </LibraryPack>

      <LibraryPack
        title="Editor Sequences"
        count={editor ? 1 : 0}
        open={isPackOpen("editor", Boolean(editor))}
        onToggle={(next) => setPack("editor", next)}
      >
        <p className="muted library-pack-lede">Assembly status in the Editor.</p>
        <div className="row library-inline-row">
          {ED_STATUS.map((s) => (
            <span key={s} className={`pill ${editor?.status === s ? "warn" : ""}`}>
              {s.replace(/_/g, " ")}
              {editor?.status === s ? " âœ“" : ""}
            </span>
          ))}
        </div>
        {!editor ? (
          <p className="library-empty-compact">
            No Editor sequence yet.
            {onGo && (
              <button type="button" className="library-empty-action" onClick={() => onGo("magi")}>
                Open MAGI Editor
              </button>
            )}
          </p>
        ) : (
          <p className="library-pack-line">
            <strong>{editor.authority === "magi-sequence" ? "MAGI Sequence" : editor.name || "Editor"}</strong>
            <span className="scene-meta">
              {" "}
              · {editor.authority === "magi-sequence" ? "sole editorial authority" : String(editor.status || "").replace(/_/g, " ")} · {clipCount} clip
              {clipCount === 1 ? "" : "s"}
            </span>
            {onGo && (
              <button type="button" className="library-row-action" onClick={() => onGo("magi")}>
                Open MAGI Editor
              </button>
            )}
          </p>
        )}
      </LibraryPack>

      <LibraryPack
        title="Scene Master Sheets"
        count={sheets.length}
        open={isPackOpen("sheets", sheets.length > 0)}
        onToggle={(next) => setPack("sheets", next)}
      >
        <p className="muted library-pack-lede">Whole-scene packages — what exists in the scene.</p>
        {!sheets.length ? (
          <p className="library-empty-compact">
            No master sheets yet.
          </p>
        ) : (
          <ul className="library-mini-list">
            {sheets.map((s) => (
              <li key={s.id}>
                <strong>{s.title || "Master Sheet"}</strong> · {s.version}
                {s.approved_authority ? " · Authority âœ“" : ""} · scene {s.scene_id?.slice(0, 8)}
              </li>
            ))}
          </ul>
        )}
      </LibraryPack>

      <LibraryPack
        title="Avatars"
        count={avatars.length}
        open={isPackOpen("avatars", avatars.length > 0)}
        onToggle={(next) => setPack("avatars", next)}
      >
        <p className="muted library-pack-lede">Looks, voice, takes, and lip-sync checkpoints.</p>
        {!avatars.length ? (
          <p className="library-empty-compact">No avatar sessions in this project. Avatar Studio is not available in this version; existing historical outputs still appear here when present.</p>
        ) : (
          <ul className="library-mini-list">
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
      </LibraryPack>

      <LibraryPack
        title="Production Collections"
        count={collections.length}
        open={isPackOpen("collections", collections.length > 0)}
        onToggle={(next) => setPack("collections", next)}
        testId="library-collections"
      >
        <p className="muted library-pack-lede">Group items you want to keep together.</p>
        <div className="library-collection-create">
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
          <p className="library-empty-compact">No collections yet.</p>
        ) : (
          <ul className="library-collection-list">
            {collections.map((c) => {
              const count = (c.assetIds || []).length;
              const modified = collectionModified(c);
              const thumb = collectionThumb(c);
              return (
                <li key={c.collectionId}>
                  <button
                    type="button"
                    className={`library-collection-row${collectionFilter === c.collectionId ? " is-active" : ""}`}
                    onClick={() =>
                      setCollectionFilter((prev) => (prev === c.collectionId ? "" : c.collectionId))
                    }
                  >
                    <span className={`library-collection-thumb${thumb ? "" : " is-empty"}`}>
                      {thumb ? <img src={thumb} alt="" /> : <TypeGlyph kind="image" />}
                    </span>
                    <span className="library-collection-copy">
                      <strong>{c.name}</strong>
                      <span className="muted">
                        {count} asset{count === 1 ? "" : "s"}
                        {modified ? ` · ${modified}` : ""}
                      </span>
                    </span>
                  </button>
                  {selected && (
                    <button
                      type="button"
                      className="library-row-action"
                      onClick={() => void addSelectedToCollection(c.collectionId)}
                    >
                      + selected
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </LibraryPack>

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
