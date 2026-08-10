import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

type FolderRow = {
  id: string;
  path: string;
  label?: string;
  category?: string;
  runtimeType?: string;
  validationStatus?: string;
  imported?: boolean;
  importDestination?: string | null;
};

const ROOT_LABELS: { id: string; label: string; tip: string }[] = [
  { id: "default", label: "Default models folder", tip: "Preferred root for new model work (e.g. D:\\01_Models)." },
  { id: "llm", label: "LLM models", tip: "Where language models live for Co-Director and chat." },
  { id: "ollama", label: "Ollama models", tip: "Optional Ollama models directory if different from default." },
  { id: "image", label: "Image models", tip: "Image generation weights." },
  { id: "video", label: "Video models", tip: "Video generation weights." },
  { id: "audio", label: "Audio models", tip: "Music and sound models." },
  { id: "voice", label: "Voice models", tip: "Voice and speech models." },
  { id: "3d", label: "3D models", tip: "3D assets and weights." },
  { id: "temp_cache", label: "Temp cache", tip: "Temporary download or conversion cache." },
];

export function ModelStoragePanel({ onMessage }: { onMessage?: (msg: string) => void }) {
  const [roots, setRoots] = useState<Record<string, string>>({});
  const [folders, setFolders] = useState<FolderRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [manualPath, setManualPath] = useState("");
  const [importCopy, setImportCopy] = useState(false);
  const [showAdvancedRoots, setShowAdvancedRoots] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.modelStorageGet();
      setRoots(data.roots || {});
      setFolders(data.registeredFolders || []);
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Could not load Model Storage.");
    }
  }, [onMessage]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveRoot = async (category: string, path: string) => {
    setBusy(true);
    try {
      await api.modelStoragePutRoot(category, path);
      onMessage?.(`Saved ${category} model folder.`);
      await refresh();
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Could not save folder.");
    } finally {
      setBusy(false);
    }
  };

  const browseRoot = async (category: string) => {
    setBusy(true);
    try {
      const picked = await api.setupBrowsePath({
        mode: "directory",
        start_dir: roots[category] || roots.default,
        title: `Choose ${category} models folder`,
      });
      if (picked.cancelled || !picked.path) {
        onMessage?.("No folder selected.");
        return;
      }
      await saveRoot(category, picked.path);
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Browse failed.");
    } finally {
      setBusy(false);
    }
  };

  const registerPath = async (path: string) => {
    if (!path.trim()) return;
    setBusy(true);
    try {
      const result = await api.modelStorageRegisterFolder({
        path: path.trim(),
        category: "llm",
        importIntoLibrary: importCopy,
      });
      if (result.copied) {
        onMessage?.("Imported into Adept library (original left in place).");
      } else {
        onMessage?.("Registered folder path only — nothing was copied.");
      }
      setManualPath("");
      await refresh();
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Register failed.");
    } finally {
      setBusy(false);
    }
  };

  const browseRegister = async () => {
    setBusy(true);
    try {
      const picked = await api.setupBrowsePath({
        mode: "directory",
        start_dir: roots.llm || roots.default,
        title: "Add local model folder",
      });
      if (picked.cancelled || !picked.path) return;
      await registerPath(picked.path);
    } catch (e) {
      onMessage?.(e instanceof Error ? e.message : "Browse failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" data-testid="model-storage-panel" aria-labelledby="model-storage-heading">
      <h2 id="model-storage-heading">Model Storage</h2>
      <p>
        Point Adept at model folders on any drive. Register keeps paths only — Adept never copies unless you choose
        Import.
      </p>

      <div className="model-storage-root" style={{ marginBottom: "1rem" }}>
        <label>
          Default models folder
          <span title={ROOT_LABELS[0].tip}> (?)</span>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.35rem" }}>
            <input
              data-testid="model-storage-root-default"
              value={roots.default || ""}
              onChange={(e) => setRoots((r) => ({ ...r, default: e.target.value }))}
              style={{ flex: "1 1 220px" }}
              aria-label="Default models folder path"
            />
            <button type="button" disabled={busy} onClick={() => void browseRoot("default")} data-testid="model-storage-browse-default">
              Browse Drives…
            </button>
            <button type="button" disabled={busy} onClick={() => void saveRoot("default", roots.default || "")}>
              Save
            </button>
          </div>
        </label>
      </div>

      <button
        type="button"
        className="linkish"
        onClick={() => setShowAdvancedRoots((v) => !v)}
        data-testid="model-storage-more-roots"
      >
        {showAdvancedRoots ? "Hide category folders" : "More category folders"}
      </button>
      {showAdvancedRoots && (
        <div data-testid="model-storage-advanced-roots" style={{ marginTop: "0.75rem" }}>
          {ROOT_LABELS.filter((r) => r.id !== "default").map((row) => (
            <label key={row.id} style={{ display: "block", marginBottom: "0.65rem" }}>
              {row.label}
              <span title={row.tip}> (?)</span>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.25rem" }}>
                <input
                  value={roots[row.id] || ""}
                  onChange={(e) => setRoots((r) => ({ ...r, [row.id]: e.target.value }))}
                  style={{ flex: "1 1 220px" }}
                  aria-label={`${row.label} path`}
                />
                <button type="button" disabled={busy} onClick={() => void browseRoot(row.id)}>
                  Browse…
                </button>
                <button type="button" disabled={busy} onClick={() => void saveRoot(row.id, roots[row.id] || "")}>
                  Save
                </button>
              </div>
            </label>
          ))}
        </div>
      )}

      <h3 style={{ marginTop: "1.25rem" }}>Local model folders</h3>
      <p>Register an existing folder (path only) or Import a copy into the Adept library.</p>
      <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <input
          type="checkbox"
          checked={importCopy}
          onChange={(e) => setImportCopy(e.target.checked)}
          data-testid="model-storage-import-toggle"
        />
        Import into Adept library (copy — original stays put)
      </label>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
        <input
          data-testid="model-storage-manual-path"
          placeholder="Paste folder path…"
          value={manualPath}
          onChange={(e) => setManualPath(e.target.value)}
          style={{ flex: "1 1 240px" }}
          aria-label="Folder path to register"
        />
        <button
          type="button"
          disabled={busy}
          data-testid="model-storage-register"
          onClick={() => void registerPath(manualPath)}
        >
          {importCopy ? "Import Folder" : "Register Folder"}
        </button>
        <button type="button" disabled={busy} data-testid="model-storage-browse-register" onClick={() => void browseRegister()}>
          Browse Drives…
        </button>
      </div>

      <ul data-testid="model-storage-folder-list" style={{ listStyle: "none", padding: 0 }}>
        {folders.length === 0 && <li>No registered folders yet.</li>}
        {folders.map((f) => (
          <li
            key={f.id}
            data-testid={`model-storage-folder-${f.id}`}
            style={{
              border: "1px solid var(--border, #333)",
              borderRadius: 8,
              padding: "0.65rem 0.75rem",
              marginBottom: "0.5rem",
            }}
          >
            <strong>{f.label || f.path}</strong>
            <div style={{ fontSize: "0.9rem", opacity: 0.85 }}>{f.path}</div>
            <div>
              {f.runtimeType || "unknown"} · {f.validationStatus || "Unknown"}
              {f.imported ? " · Imported copy" : " · Path only (not copied)"}
            </div>
            {f.validationStatus === "Drive Unavailable" && (
              <p data-testid="model-storage-drive-unavailable">
                Drive unavailable. Registration kept. Retry Discovery, Locate Folder, or choose another model — Adept
                will not silently switch or re-download to C:\.
              </p>
            )}
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
              <button
                type="button"
                disabled={busy}
                data-testid={`model-storage-retry-${f.id}`}
                onClick={() => void api.modelStorageRefreshFolder(f.id).then(refresh)}
              >
                Retry Discovery
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void api.modelStorageUnregisterFolder(f.id).then(refresh)}
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
