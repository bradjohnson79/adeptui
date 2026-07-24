import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import { PanelHeading } from "./HelpTip";

type Segment = {
  id: string;
  segment_number: number;
  segment_type: string;
  speaker: string;
  text: string;
  action: string;
  dialogue: string;
  emotion: string;
  location: string;
  duration_est: number;
  status: string;
  revision: number;
  characters: string[];
  scene_id?: string | null;
};

type Panel = {
  id: string;
  segment_id: string;
  panel_index: number;
  label: string;
  asset_id?: string | null;
  style: string;
  notes: string;
  prompt: string;
  approval: string;
  script_sync_status: string;
  status: string;
  duration_est: number;
  shot_size: string;
  lens: string;
};

const STYLES = [
  "Pencil storyboard",
  "Ink storyboard",
  "Grayscale cinematic",
  "Color concept frame",
  "Anime storyboard",
  "Photoreal previs",
  "Production still",
];

const SEG_TYPES = [
  "scene_heading",
  "action",
  "dialogue",
  "reaction",
  "insert",
  "transition",
  "camera_beat",
  "story_beat",
];

export function ScriptStoryboardWorkspace({
  project,
  onChange,
  onGoDirector,
  shotListOnly = false,
}: {
  project: Project;
  onChange: () => Promise<void> | void;
  onGoDirector?: () => void;
  shotListOnly?: boolean;
}) {
  const [view, setView] = useState<"split" | "script" | "storyboard" | "shotlist">(
    shotListOnly ? "shotlist" : "split"
  );
  const [docId, setDocId] = useState<string>("");
  const [segments, setSegments] = useState<Segment[]>([]);
  const [panels, setPanels] = useState<Panel[]>([]);
  const [selectedSeg, setSelectedSeg] = useState<string | null>(null);
  const [selectedPanel, setSelectedPanel] = useState<string | null>(null);
  const [importText, setImportText] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [style, setStyle] = useState(() => {
    try {
      const d = project.defaults_json ? JSON.parse(project.defaults_json) : {};
      return d.storyboard_style || "Pencil storyboard";
    } catch {
      return "Pencil storyboard";
    }
  });

  const load = useCallback(async () => {
    const r = await api.getScript(project.id);
    setDocId(r.doc.id);
    setSegments(r.segments || []);
    setPanels(r.panels || []);
    if (!selectedSeg && r.segments?.[0]) setSelectedSeg(r.segments[0].id);
  }, [project.id, selectedSeg]);

  useEffect(() => {
    load().catch(console.error);
  }, [project.id]);

  const seg = useMemo(() => segments.find((s) => s.id === selectedSeg) || null, [segments, selectedSeg]);
  const segPanels = useMemo(
    () => panels.filter((p) => p.segment_id === selectedSeg).sort((a, b) => a.panel_index - b.panel_index),
    [panels, selectedSeg]
  );
  const panel = useMemo(
    () => panels.find((p) => p.id === selectedPanel) || segPanels[0] || null,
    [panels, selectedPanel, segPanels]
  );

  const saveSeg = async (patch: Partial<Segment>) => {
    if (!seg) return;
    const r = await api.patchSegment(project.id, seg.id, patch);
    setMsg(r.visual_change ? "Visual change — linked storyboards marked script_changed" : "Saved (dialogue/meta)");
    await load();
  };

  const addSegment = async () => {
    const s = await api.createSegment(project.id, {
      segment_type: "action",
      text: "",
      action: "New action beat.",
    });
    setSelectedSeg(s.id);
    await load();
  };

  const ensurePanel = async () => {
    if (!seg) return null;
    if (panel) return panel;
    const p = await api.createPanel(project.id, { segment_id: seg.id, style });
    setSelectedPanel(p.id);
    await load();
    return p;
  };

  const generatePanel = async () => {
    if (!seg) return;
    setBusy(true);
    setMsg(null);
    try {
      let p = panel;
      if (!p) {
        p = await api.createPanel(project.id, { segment_id: seg.id, style });
        setSelectedPanel(p.id);
      }
      const r = await api.storyboardGenerate(project.id, {
        panel_id: p!.id,
        segment_id: seg.id,
        style,
      });
      setMsg(`Storyboard job ${r.job_id}`);
      const poll = setInterval(() => {
        api.getJob(r.job_id).then(async (j) => {
          if (j.status === "done" || j.status === "failed") {
            clearInterval(poll);
            setMsg(j.status === "done" ? "Panel generated" : j.message);
            await load();
            await onChange();
          }
        });
      }, 1500);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const resolveSync = async (mode: string) => {
    if (!panel) return;
    if (mode === "keep") {
      await api.patchPanel(project.id, panel.id, { script_sync_status: "ok", status: panel.asset_id ? "complete" : "draft" });
    } else if (mode === "non_visual") {
      await api.patchPanel(project.id, panel.id, { script_sync_status: "non_visual", status: panel.asset_id ? "complete" : "draft" });
    } else if (mode === "regen") {
      await generatePanel();
      return;
    } else if (mode === "duplicate") {
      const p = await api.createPanel(project.id, {
        segment_id: panel.segment_id,
        style: panel.style,
        label: `${panel.label} (alt)`,
      });
      setSelectedPanel(p.id);
      await api.storyboardGenerate(project.id, { panel_id: p.id, style: panel.style });
    }
    await load();
  };

  const sendDirector = async (approvedOnly: boolean) => {
    const ids = approvedOnly
      ? panels.filter((p) => p.approval === "approved").map((p) => p.id)
      : panel
        ? [panel.id]
        : segPanels.map((p) => p.id);
    const r = await api.storyboardSendDirector(project.id, {
      panel_ids: ids,
      approved_only: approvedOnly,
    });
    setMsg(`Created ${r.created_scene_ids.length} Director scene(s)`);
    await onChange();
    onGoDirector?.();
  };

  const doImport = async () => {
    if (!importText.trim()) return;
    const r = await api.importScript(project.id, importText);
    setMsg(`Imported ${r.count} segments`);
    setImportText("");
    await load();
  };

  return (
    <div className={`page script-board-workspace ${shotListOnly ? "shotlist-only" : ""}`}>
      <header className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
        <PanelHeading
          title="Script / Storyboard"
          tip="Structured script segments linked to storyboard panels, Spatial Maps, and Director — no silent overwrites."
        />
        {!shotListOnly && (
          <div className="workspace-tabs">
            {(
              [
                ["split", "Split"],
                ["script", "Script"],
                ["storyboard", "Storyboard"],
                ["shotlist", "Shot List"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={view === id ? "primary" : ""}
                onClick={() => setView(id)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </header>
      {msg && <p className="pill warn">{msg}</p>}

      {(view === "script" || view === "split") && (
        <div className={`script-split ${view === "script" ? "script-only" : ""}`}>
          <aside className="script-seg-list">
            <div className="row" style={{ marginBottom: "0.5rem" }}>
              <button type="button" className="primary" onClick={() => void addSegment()}>
                + Segment
              </button>
            </div>
            <ul className="home-list">
              {segments.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className={selectedSeg === s.id ? "primary" : "linkish"}
                    onClick={() => {
                      setSelectedSeg(s.id);
                      setSelectedPanel(null);
                    }}
                  >
                    #{s.segment_number} {s.segment_type}
                    {s.speaker ? ` · ${s.speaker}` : ""}
                  </button>
                </li>
              ))}
            </ul>
            <details style={{ marginTop: "1rem" }}>
              <summary>Import plain text / markdown</summary>
              <textarea rows={6} value={importText} onChange={(e) => setImportText(e.target.value)} />
              <button type="button" onClick={() => void doImport()}>
                Import → segments
              </button>
            </details>
          </aside>

          <section className="script-editor">
            {!seg ? (
              <p className="empty">No segment selected.</p>
            ) : (
              <>
                <div className="gen-grid">
                  <div className="field">
                    <label>Type</label>
                    <select
                      value={seg.segment_type}
                      onChange={(e) => void saveSeg({ segment_type: e.target.value })}
                    >
                      {SEG_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field">
                    <label>Speaker</label>
                    <input value={seg.speaker} onChange={(e) => setSegments((xs) => xs.map((x) => (x.id === seg.id ? { ...x, speaker: e.target.value } : x)))} onBlur={(e) => void saveSeg({ speaker: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>Duration est (s)</label>
                    <input
                      type="number"
                      value={seg.duration_est}
                      onChange={(e) => void saveSeg({ duration_est: Number(e.target.value) })}
                    />
                  </div>
                </div>
                <div className="field">
                  <label>Action</label>
                  <textarea
                    rows={3}
                    value={seg.action}
                    onChange={(e) =>
                      setSegments((xs) => xs.map((x) => (x.id === seg.id ? { ...x, action: e.target.value } : x)))
                    }
                    onBlur={(e) => void saveSeg({ action: e.target.value, text: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label>Dialogue</label>
                  <textarea
                    rows={3}
                    value={seg.dialogue || seg.text}
                    onChange={(e) =>
                      setSegments((xs) =>
                        xs.map((x) => (x.id === seg.id ? { ...x, dialogue: e.target.value, text: e.target.value } : x))
                      )
                    }
                    onBlur={(e) => void saveSeg({ dialogue: e.target.value, text: e.target.value })}
                  />
                </div>
                <p className="scene-meta">Revision {seg.revision} · edits never silently regenerate panels</p>
              </>
            )}
          </section>

          {view === "split" && (
            <section className="storyboard-panel-view">
              <h3>Storyboard Panel</h3>
              <div className="field">
                <label>Style</label>
                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                  {STYLES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              {panel?.asset_id ? (
                <img src={api.assetUrl(panel.asset_id)} alt={panel.label} style={{ width: "100%", borderRadius: 12 }} />
              ) : (
                <div className="empty">No frame yet</div>
              )}
              {panel && (
                <p className="scene-meta">
                  {panel.label} · {panel.status} · sync {panel.script_sync_status} · {panel.shot_size} {panel.lens}
                </p>
              )}
              {panel?.script_sync_status === "script_changed" && (
                <div className="card" style={{ marginTop: "0.5rem" }}>
                  <strong>Script changed</strong>
                  <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginTop: 8 }}>
                    <button type="button" onClick={() => void resolveSync("keep")}>
                      Keep panel
                    </button>
                    <button type="button" onClick={() => void resolveSync("non_visual")}>
                      Not visually relevant
                    </button>
                    <button type="button" onClick={() => void resolveSync("regen")}>
                      Regenerate
                    </button>
                    <button type="button" onClick={() => void resolveSync("duplicate")}>
                      Duplicate & regen
                    </button>
                  </div>
                </div>
              )}
              <div className="row" style={{ marginTop: "0.75rem", flexWrap: "wrap", gap: "0.4rem" }}>
                <button type="button" onClick={() => void ensurePanel()}>
                  + Panel
                </button>
                <button type="button" className="primary" disabled={busy || !seg} onClick={() => void generatePanel()}>
                  Generate Storyboard
                </button>
                <button
                  type="button"
                  disabled={!panel}
                  onClick={() => panel && api.patchPanel(project.id, panel.id, { approval: "approved", status: "approved" }).then(load)}
                >
                  Approve
                </button>
                <button type="button" onClick={() => void sendDirector(false)}>
                  Send to Director
                </button>
                <button type="button" onClick={() => void sendDirector(true)}>
                  Approved only → Director
                </button>
              </div>
            </section>
          )}
        </div>
      )}

      {(view === "storyboard" || view === "shotlist" || view === "split") && (
        <div className="storyboard-strip">
          <h3>{view === "shotlist" ? "Shot List" : "Storyboard Strip"}</h3>
          <div className="strip-row">
            {panels.length === 0 && <p className="empty">No panels yet.</p>}
            {panels.map((p) => {
              const s = segments.find((x) => x.id === p.segment_id);
              return (
                <button
                  key={p.id}
                  type="button"
                  className={`strip-card ${selectedPanel === p.id ? "selected" : ""}`}
                  onClick={() => {
                    setSelectedPanel(p.id);
                    setSelectedSeg(p.segment_id);
                    if (view === "shotlist") setView("split");
                  }}
                >
                  {p.asset_id ? (
                    <img src={api.assetUrl(p.asset_id)} alt={p.label} />
                  ) : (
                    <div className="library-card-fallback">{p.status}</div>
                  )}
                  <span>
                    Seg {s?.segment_number ?? "?"} · {p.label}
                  </span>
                  <span className={`pill ${p.script_sync_status === "script_changed" ? "warn" : ""}`}>
                    {p.status}
                  </span>
                </button>
              );
            })}
          </div>
          {view === "shotlist" && (
            <table className="shot-table">
              <thead>
                <tr>
                  <th>Seg</th>
                  <th>Panel</th>
                  <th>Status</th>
                  <th>Sync</th>
                  <th>Dur</th>
                  <th>Style</th>
                </tr>
              </thead>
              <tbody>
                {panels.map((p) => {
                  const s = segments.find((x) => x.id === p.segment_id);
                  return (
                    <tr key={p.id}>
                      <td>{s?.segment_number}</td>
                      <td>{p.label}</td>
                      <td>{p.status}</td>
                      <td>{p.script_sync_status}</td>
                      <td>{p.duration_est}s</td>
                      <td>{p.style}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
      <p className="scene-meta">Doc {docId.slice(0, 8)} · Library auto-tags storyboard assets</p>
    </div>
  );
}
