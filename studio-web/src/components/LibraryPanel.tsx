import { useEffect, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";

const DIR_STATUS = ["draft", "generating", "variations", "approved", "used_in_editor"] as const;
const ED_STATUS = ["animatic", "rough_cut", "scene_cut", "alternate", "approved", "master"] as const;

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
  const [items, setItems] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [graph, setGraph] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [sheets, setSheets] = useState<any[]>([]);
  const [avatars, setAvatars] = useState<any[]>([]);
  const [dirSeqs, setDirSeqs] = useState<any[]>([]);
  const [editor, setEditor] = useState<any>(null);
  const [dirFilter, setDirFilter] = useState<string>("all");

  const refresh = () =>
    api.library(project.id, { q, scope }).then(setItems).catch(console.error);

  useEffect(() => {
    refresh();
  }, [project.id, q, scope, project.assets.length]);

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
          Director Sequences
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
          <p className="empty">No Director sequences yet. Send from Director Prompt Timeline.</p>
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
                  <button type="button" style={{ marginLeft: 8 }} onClick={() => onGo("director")}>
                    Open Director
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
              <button type="button" style={{ marginLeft: 8 }} onClick={() => onGo("editor")}>
                Open Editor
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

      <div className="library-layout">
        <div className="library-grid">
          {!items.length ? (
            <p className="empty">No assets in this scope.</p>
          ) : (
            items.map((a) => (
              <button
                key={a.id}
                type="button"
                className={`library-card ${selected === a.id ? "selected" : ""}`}
                onClick={() => setSelected(a.id)}
              >
                {a.kind === "image" ? (
                  <img src={api.assetUrl(a.id)} alt={a.filename} />
                ) : (
                  <div className="library-card-fallback">{a.kind}</div>
                )}
                <span>{a.tag || a.filename}</span>
              </button>
            ))
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
    </div>
  );
}
