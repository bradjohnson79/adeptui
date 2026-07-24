import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type {
  CoDirectorBible,
  CoDirectorBibleEntity,
  CoDirectorBibleFact,
  CoDirectorBibleVersion,
} from "../api";
import type { Project } from "../types";
import { PanelHeading } from "./HelpTip";

const ENTITY_TYPES = [
  "project_profile",
  "character",
  "location",
  "visual_style",
  "production_rule",
  "continuity_rule",
  "narrative_thread",
  "scene_fact",
  "prop",
  "organization",
] as const;

/**
 * Production Bible workspace (Co-Director M2.1): versioned project knowledge grounding.
 * The model never writes here directly — manual edits create a new version immediately;
 * model-proposed edits go through the approval cards in the Co-Director conversation panel.
 */
export function ProductionBibleWorkspace({ project }: { project: Project; onChange?: () => Promise<void> }) {
  const [bible, setBible] = useState<CoDirectorBible | null>(null);
  const [versions, setVersions] = useState<CoDirectorBibleVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<CoDirectorBibleVersion | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  // Import preview/confirm flow
  const [preview, setPreview] = useState<{
    entities: CoDirectorBibleEntity[];
    facts: CoDirectorBibleFact[];
    summary: string;
    warnings: string[];
  } | null>(null);

  // New-entity mini form
  const [newEntityType, setNewEntityType] = useState<(typeof ENTITY_TYPES)[number]>("character");
  const [newEntityKey, setNewEntityKey] = useState("");
  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityDesc, setNewEntityDesc] = useState("");

  const load = async () => {
    setLoading(true);
    setNotFound(false);
    try {
      const b = await api.getBible(project.id);
      setBible(b);
      setSelectedVersion(b.currentVersion);
      const v = await api.listBibleVersions(project.id);
      setVersions(v.versions);
    } catch (err) {
      if (err instanceof ApiError && err.code === "BIBLE_NOT_FOUND") {
        setNotFound(true);
        setBible(null);
      } else {
        setMsg(err instanceof Error ? err.message : "Failed to load Production Bible");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const runImportPreview = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await api.previewBibleImport(project.id, { includeScenes: true, includeAssetsAsProps: true });
      setPreview(res);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  const confirmImport = async () => {
    if (!preview) return;
    setBusy(true);
    setMsg("");
    try {
      await api.confirmBibleImport(project.id, {
        entities: preview.entities,
        facts: preview.facts,
        summary: preview.summary,
        changeReason: "initial_import",
      });
      setPreview(null);
      setMsg("Production Bible created as version 1.");
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  };

  const addEntity = async () => {
    if (!newEntityKey.trim()) {
      setMsg("Entity key is required.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      await api.createBibleVersion(project.id, {
        mutations: {
          entityMutations: [
            {
              entityType: newEntityType,
              entityKey: newEntityKey.trim(),
              displayName: newEntityName.trim() || newEntityKey.trim(),
              data: newEntityDesc.trim() ? { description: newEntityDesc.trim() } : {},
            },
          ],
          factMutations: [],
          summary: `Added ${newEntityType} "${newEntityName || newEntityKey}"`,
          changeReason: "manual_edit",
        },
        createdBy: "user",
      });
      setNewEntityKey("");
      setNewEntityName("");
      setNewEntityDesc("");
      setMsg("New Bible version created.");
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed to add entity");
    } finally {
      setBusy(false);
    }
  };

  const viewVersion = async (versionNumber: number) => {
    setBusy(true);
    try {
      const v = await api.getBibleVersion(project.id, versionNumber);
      setSelectedVersion(v);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed to load version");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <PanelHeading title="Production Bible" tip="Versioned project knowledge Co-Director grounds every chat turn in." />
        <p className="muted">Loading…</p>
      </div>
    );
  }

  if (notFound && !preview) {
    return (
      <div className="page">
        <PanelHeading title="Production Bible" tip="Versioned project knowledge Co-Director grounds every chat turn in." />
        <p className="empty">
          This project doesn't have a Production Bible yet. Import a starting point from your
          existing project data (name, style, tagged assets, scene notes), review it, then
          confirm to create version 1.
        </p>
        {msg && <p className="pill">{msg}</p>}
        <div className="row-actions">
          <button type="button" className="primary" disabled={busy} onClick={() => void runImportPreview()}>
            {busy ? "Building preview…" : "Import from project"}
          </button>
        </div>
      </div>
    );
  }

  if (preview) {
    return (
      <div className="page">
        <PanelHeading title="Create Production Bible — Preview" tip="Nothing is saved yet. Review, then confirm to create version 1." />
        <p>{preview.summary}</p>
        {preview.warnings.map((w) => (
          <p key={w} className="muted">
            ⚠ {w}
          </p>
        ))}
        <h4>Entities ({preview.entities.length})</h4>
        <ul className="ms-list">
          {preview.entities.map((e) => (
            <li key={e.entityKey}>
              <strong>{e.displayName}</strong> <span className="scene-meta">· {e.entityType}</span>
            </li>
          ))}
        </ul>
        <h4>Facts ({preview.facts.length})</h4>
        <ul className="ms-list">
          {preview.facts.map((f, i) => (
            <li key={i}>{f.statement}</li>
          ))}
        </ul>
        {msg && <p className="pill">{msg}</p>}
        <div className="row-actions">
          <button type="button" className="ghost" disabled={busy} onClick={() => setPreview(null)}>
            Cancel
          </button>
          <button type="button" className="primary" disabled={busy} onClick={() => void confirmImport()}>
            {busy ? "Creating…" : "Confirm — create version 1"}
          </button>
        </div>
      </div>
    );
  }

  const current = selectedVersion;

  return (
    <div className="page">
      <PanelHeading title="Production Bible" tip="Versioned project knowledge Co-Director grounds every chat turn in. The model never edits this directly — proposals require your approval." />
      {msg && <p className="pill">{msg}</p>}

      <div className="row-actions" style={{ marginBottom: "1rem" }}>
        <span className="scene-meta">
          Version {current?.versionNumber ?? "—"} of {versions.length} · {bible?.versionCount ?? 0} total
        </span>
      </div>

      {versions.length > 1 && (
        <div className="row-actions" style={{ marginBottom: "1rem", flexWrap: "wrap" }}>
          {versions.map((v) => (
            <button
              key={v.id}
              type="button"
              className={current?.versionNumber === v.versionNumber ? "primary" : "ghost"}
              disabled={busy}
              onClick={() => void viewVersion(v.versionNumber)}
            >
              v{v.versionNumber}
            </button>
          ))}
        </div>
      )}

      {current?.summary && <p className="muted">{current.summary}</p>}

      <h4>Entities ({current?.entities.length ?? 0})</h4>
      {!current?.entities.length ? (
        <p className="empty">No entities yet.</p>
      ) : (
        <ul className="ms-list">
          {current.entities.map((e) => (
            <li key={e.entityKey} style={{ marginBottom: "0.5rem" }}>
              <strong>{e.displayName}</strong> <span className="scene-meta">· {e.entityType}</span>
              {typeof e.data?.description === "string" && e.data.description ? (
                <p className="muted" style={{ margin: "0.2rem 0 0" }}>
                  {String(e.data.description)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <h4>Continuity / narrative facts ({current?.facts.length ?? 0})</h4>
      {!current?.facts.length ? (
        <p className="empty">No facts recorded yet.</p>
      ) : (
        <ul className="ms-list">
          {current.facts.map((f, i) => (
            <li key={i}>{f.statement}</li>
          ))}
        </ul>
      )}

      <h4>Add entity manually</h4>
      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
        <select value={newEntityType} onChange={(e) => setNewEntityType(e.target.value as (typeof ENTITY_TYPES)[number])}>
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="key (e.g. ava)"
          value={newEntityKey}
          onChange={(e) => setNewEntityKey(e.target.value)}
          style={{ width: 140 }}
        />
        <input
          type="text"
          placeholder="Display name"
          value={newEntityName}
          onChange={(e) => setNewEntityName(e.target.value)}
          style={{ width: 180 }}
        />
        <input
          type="text"
          placeholder="Description"
          value={newEntityDesc}
          onChange={(e) => setNewEntityDesc(e.target.value)}
          style={{ flex: 1, minWidth: 200 }}
        />
        <button type="button" className="primary" disabled={busy} onClick={() => void addEntity()}>
          Add (new version)
        </button>
      </div>
    </div>
  );
}
