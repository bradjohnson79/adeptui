import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type {
  BibleAuditEvent,
  BibleDomainSummary,
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

type NavSection =
  | "overview"
  | "story"
  | "characters"
  | "relationships"
  | "locations"
  | "objects"
  | "wardrobe"
  | "visual"
  | "canon"
  | "timeline"
  | "continuity"
  | "decisions"
  | "references"
  | "history";

const NAV_ITEMS: { id: NavSection; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "story", label: "Story" },
  { id: "characters", label: "Characters" },
  { id: "relationships", label: "Relationships" },
  { id: "locations", label: "Locations" },
  { id: "objects", label: "Objects" },
  { id: "wardrobe", label: "Wardrobe" },
  { id: "visual", label: "Visual Language" },
  { id: "canon", label: "Canon" },
  { id: "timeline", label: "Timeline" },
  { id: "continuity", label: "Continuity" },
  { id: "decisions", label: "Decisions" },
  { id: "references", label: "References" },
  { id: "history", label: "History" },
];

function lifecycleBadge(status?: string) {
  if (!status || status === "draft") return null;
  const cls =
    status === "locked"
      ? "pill warn"
      : status === "approved"
        ? "pill ok"
        : status === "in_review"
          ? "pill"
          : "pill muted";
  return <span className={cls}>{status}</span>;
}

function EntityCard({
  entity,
  onSelect,
  selected,
}: {
  entity: CoDirectorBibleEntity;
  onSelect?: () => void;
  selected?: boolean;
}) {
  return (
    <li
      className={`bible-entity-card${selected ? " selected" : ""}`}
      style={{ marginBottom: "0.5rem", cursor: onSelect ? "pointer" : undefined }}
      onClick={onSelect}
      onKeyDown={onSelect ? (e) => e.key === "Enter" && onSelect() : undefined}
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
    >
      <strong>{entity.displayName}</strong>{" "}
      <span className="scene-meta">· {entity.entityType}</span>
      {lifecycleBadge(entity.lifecycleStatus)}
      {entity.readiness && entity.readiness !== "basic" ? (
        <span className="scene-meta"> · {entity.readiness}</span>
      ) : null}
      {typeof entity.data?.description === "string" && entity.data.description ? (
        <p className="muted" style={{ margin: "0.2rem 0 0" }}>
          {String(entity.data.description).slice(0, 200)}
        </p>
      ) : null}
    </li>
  );
}

/**
 * Production Bible workspace (M2.3): domain navigation, lifecycle badges, context retrieval.
 */
export function ProductionBibleWorkspace({ project }: { project: Project; onChange?: () => Promise<void> }) {
  const [bible, setBible] = useState<CoDirectorBible | null>(null);
  const [summary, setSummary] = useState<BibleDomainSummary | null>(null);
  const [versions, setVersions] = useState<CoDirectorBibleVersion[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<CoDirectorBibleVersion | null>(null);
  const [audit, setAudit] = useState<BibleAuditEvent[]>([]);
  const [nav, setNav] = useState<NavSection>("overview");
  const [selectedEntity, setSelectedEntity] = useState<CoDirectorBibleEntity | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [preview, setPreview] = useState<{
    entities: CoDirectorBibleEntity[];
    facts: CoDirectorBibleFact[];
    summary: string;
    warnings: string[];
  } | null>(null);

  const [newEntityType, setNewEntityType] = useState<(typeof ENTITY_TYPES)[number]>("character");
  const [newEntityKey, setNewEntityKey] = useState("");
  const [newEntityName, setNewEntityName] = useState("");
  const [newEntityDesc, setNewEntityDesc] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    try {
      const b = await api.getBible(project.id);
      setBible(b);
      setSelectedVersion(b.currentVersion);
      const v = await api.listBibleVersions(project.id);
      setVersions(v.versions);
      try {
        const s = await api.getBibleSummary(project.id);
        setSummary(s);
      } catch {
        setSummary(null);
      }
      try {
        const a = await api.listBibleAudit(project.id);
        setAudit(a.events);
      } catch {
        setAudit([]);
      }
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
  }, [project.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const entities = selectedVersion?.entities ?? [];

  const filteredEntities = useMemo(() => {
    const map: Record<NavSection, string[]> = {
      overview: [],
      story: ["narrative_thread", "story_arc", "story_beat", "project_profile"],
      characters: ["character"],
      relationships: ["relationship"],
      locations: ["location"],
      objects: ["prop", "production_object"],
      wardrobe: ["wardrobe", "appearance_state"],
      visual: ["visual_style", "visual_language"],
      canon: ["canon_record"],
      timeline: ["timeline_entry"],
      continuity: ["continuity_state", "continuity_rule", "conflict_record"],
      decisions: ["production_decision"],
      references: ["reference_link"],
      history: [],
    };
    const types = map[nav];
    if (!types.length) return entities;
    return entities.filter((e) => types.includes(e.entityType));
  }, [entities, nav]);

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
      if (newEntityType === "character") {
        await api.createBibleCharacter(project.id, {
          entityKey: newEntityKey.trim(),
          displayName: newEntityName.trim() || newEntityKey.trim(),
          data: newEntityDesc.trim() ? { description: newEntityDesc.trim() } : {},
        });
      } else {
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
      }
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

  const approveSelected = async () => {
    if (!selectedEntity?.stableId) return;
    setBusy(true);
    try {
      await api.approveBibleCharacter(project.id, selectedEntity.stableId);
      setMsg("Entity approved.");
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  };

  const lockSelected = async () => {
    if (!selectedEntity?.stableId) return;
    setBusy(true);
    try {
      await api.lockBibleCharacter(project.id, selectedEntity.stableId);
      setMsg("Entity locked.");
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Lock failed");
    } finally {
      setBusy(false);
    }
  };

  const exportBible = async () => {
    setBusy(true);
    try {
      const data = await api.exportBible(project.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `production-bible-${project.id.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg("Bible exported.");
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Export failed");
    } finally {
      setBusy(false);
    }
  };

  const seedDemo = async () => {
    setBusy(true);
    try {
      const res = await api.seedDemoBible(project.id);
      setMsg(res.seeded ? "Demo seed applied." : "Bible already exists.");
      await load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Seed failed");
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
          <button type="button" className="ghost" disabled={busy} onClick={() => void seedDemo()}>
            Load demo seed
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
    <div className="page bible-workspace">
      <PanelHeading
        title="Production Bible"
        tip="Versioned project knowledge Co-Director grounds every chat turn in. The model never edits this directly — proposals require your approval."
      />
      {msg && <p className="pill">{msg}</p>}

      <div className="row-actions" style={{ marginBottom: "1rem" }}>
        <span className="scene-meta">
          Version {current?.versionNumber ?? "—"} of {versions.length} · {bible?.versionCount ?? 0} total
        </span>
        <button type="button" className="ghost" disabled={busy} onClick={() => void exportBible()}>
          Export JSON
        </button>
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

      <nav className="bible-nav row-actions" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "1rem" }}>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={nav === item.id ? "primary" : "ghost"}
            onClick={() => {
              setNav(item.id);
              setSelectedEntity(null);
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {nav === "overview" && summary && (
        <div className="bible-overview" style={{ marginBottom: "1rem" }}>
          <h4>Bible Health</h4>
          <p className="muted">
            {summary.health?.entityCount ?? 0} entities · {summary.conflictCount ?? 0} conflicts ·{" "}
            {summary.health?.lockedCount ?? 0} locked · {summary.health?.incompleteCount ?? 0} incomplete
          </p>
          {(summary.conflicts ?? []).slice(0, 5).map((c, i) => (
            <p key={i} className="pill warn">
              {(c as { description?: string }).description ?? "Conflict detected"}
            </p>
          ))}
        </div>
      )}

      {nav === "history" ? (
        <>
          <h4>Audit trail ({audit.length})</h4>
          {!audit.length ? (
            <p className="empty">No audit events yet.</p>
          ) : (
            <ul className="ms-list">
              {audit.map((e) => (
                <li key={e.id}>
                  <strong>{e.eventType}</strong> — {e.summary}
                  <span className="scene-meta"> · {e.createdAt}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : nav !== "overview" ? (
        <>
          <h4>
            {NAV_ITEMS.find((n) => n.id === nav)?.label} ({filteredEntities.length})
          </h4>
          {!filteredEntities.length ? (
            <p className="empty">No entities in this domain yet.</p>
          ) : (
            <ul className="ms-list">
              {filteredEntities.map((e) => (
                <EntityCard
                  key={e.stableId ?? e.entityKey}
                  entity={e}
                  selected={selectedEntity?.stableId === e.stableId}
                  onSelect={nav === "characters" ? () => setSelectedEntity(e) : undefined}
                />
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <h4>All entities ({entities.length})</h4>
          <ul className="ms-list">
            {entities.map((e) => (
              <EntityCard key={e.stableId ?? e.entityKey} entity={e} />
            ))}
          </ul>
        </>
      )}

      {selectedEntity && nav === "characters" && (
        <div className="bible-character-editor" style={{ marginTop: "1rem", padding: "1rem", border: "1px solid var(--border)" }}>
          <h4>{selectedEntity.displayName}</h4>
          {lifecycleBadge(selectedEntity.lifecycleStatus)}
          <p className="muted">stableId: {selectedEntity.stableId}</p>
          <div className="row-actions" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
            <button type="button" className="ghost" disabled={busy || selectedEntity.lifecycleStatus === "locked"} onClick={() => void approveSelected()}>
              Approve
            </button>
            <button type="button" className="primary" disabled={busy || selectedEntity.lifecycleStatus === "locked"} onClick={() => void lockSelected()}>
              Lock
            </button>
          </div>
          {selectedEntity.lifecycleStatus === "locked" && (
            <p className="pill warn">Locked — direct edits require a proposal.</p>
          )}
        </div>
      )}

      <h4 style={{ marginTop: "1.5rem" }}>Add entity manually</h4>
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
