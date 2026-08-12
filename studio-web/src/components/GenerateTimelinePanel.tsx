import { useState } from "react";
import type { EngineName, Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

type ProposalScene = {
  name: string;
  prompt: string;
  duration_sec: number;
  engine?: EngineName | null;
  camera_note?: string;
};

export function GenerateTimelinePanel({
  project,
  onChange,
  onOpenTimeline,
}: {
  project: Project;
  onChange: () => void;
  onOpenTimeline: () => void;
}) {
  const [brief, setBrief] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [scenes, setScenes] = useState<ProposalScene[] | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const [enqueueRender, setEnqueueRender] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const propose = async () => {
    if (!brief.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.proposeTimeline(project.id, brief.trim());
      setSummary(res.summary || "");
      setWarnings(res.warnings || []);
      setScenes(res.scenes || []);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
      setScenes(null);
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!scenes?.length) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await api.applyTimeline(project.id, {
        scenes,
        replace_existing: replaceExisting,
        enqueue_render: enqueueRender,
      });
      setMsg(
        `Applied ${res.created_scene_ids.length} scene(s)${res.job_id ? " · timeline render queued" : ""}`
      );
      setScenes(null);
      await onChange();
      onOpenTimeline();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setScenes(null);
    setSummary("");
    setWarnings([]);
    setMsg(null);
  };

  return (
    <div className="panel generate-timeline-panel">
      <PanelHeading
        title="Generate Timeline"
        tip="Propose a multi-scene timeline from a brief. Review and Apply before anything is written. Optional enqueue after Apply."
      />
      <p className="scene-meta">
        Paste a script or short brief. Scenes are never overwritten until you click Apply.
      </p>
      <div className="field">
        <label>Brief / script</label>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder="Two characters meet in the rain… then they run to the train…"
          rows={8}
        />
      </div>
      <div className="row-actions">
        <button type="button" className="primary" disabled={busy || !brief.trim()} onClick={propose}>
          {busy && !scenes ? "Proposing…" : "Propose scenes"}
        </button>
      </div>

      {scenes && (
        <div className="timeline-proposal">
          <div className="section-label">Review proposal</div>
          {summary && <p className="scene-meta">{summary}</p>}
          {warnings.map((w) => (
            <div key={w} className="pill warn" style={{ marginBottom: 6 }}>
              {w}
            </div>
          ))}
          <ol className="proposal-list">
            {scenes.map((s, i) => (
              <li key={i}>
                <input
                  value={s.name}
                  onChange={(e) => {
                    const next = [...scenes];
                    next[i] = { ...s, name: e.target.value };
                    setScenes(next);
                  }}
                />
                <textarea
                  value={s.prompt}
                  onChange={(e) => {
                    const next = [...scenes];
                    next[i] = { ...s, prompt: e.target.value };
                    setScenes(next);
                  }}
                  rows={3}
                />
                <div className="row-actions">
                  <label className="scene-meta">
                    Duration
                    <input
                      style={{ width: 64 }}
                      type="number"
                      min={1}
                      max={30}
                      step={0.5}
                      value={s.duration_sec}
                      onChange={(e) => {
                        const next = [...scenes];
                        next[i] = { ...s, duration_sec: Number(e.target.value) || 5 };
                        setScenes(next);
                      }}
                    />
                  </label>
                  <label className="scene-meta">
                    Engine
                    <select
                      value={s.engine || "auto"}
                      onChange={(e) => {
                        const next = [...scenes];
                        next[i] = { ...s, engine: e.target.value as EngineName };
                        setScenes(next);
                      }}
                    >
                      <option value="auto">Auto</option>
                      <option value="minimax-h3">MiniMax H3 (Default)</option>
                      <option value="ltx">LTX 2.5</option>
                      <option value="hunyuan15">HunyuanVideo 1.5</option>
                      <option value="hunyuan13b">HunyuanVideo 13B</option>
                      <option value="wan">WAN (Optional)</option>
                      <option value="fal_seedance">Seedance</option>
                      <option value="fal_kling">Kling</option>
                      <option value="fal_veo">Veo</option>
                      <option value="fal_runway">Runway</option>
                    </select>
                  </label>
                </div>
              </li>
            ))}
          </ol>
          <label className="scene-meta" style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={replaceExisting}
              onChange={(e) => setReplaceExisting(e.target.checked)}
              style={{ width: "auto" }}
            />
            Replace existing scenes
          </label>
          <label className="scene-meta" style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
            <input
              type="checkbox"
              checked={enqueueRender}
              onChange={(e) => setEnqueueRender(e.target.checked)}
              style={{ width: "auto" }}
            />
            Enqueue timeline render after Apply
          </label>
          <div className="row-actions" style={{ marginTop: 12 }}>
            <button type="button" className="primary" disabled={busy} onClick={apply}>
              Apply
            </button>
            <button type="button" disabled={busy} onClick={cancel}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {msg && <div className="scene-meta" style={{ marginTop: 10 }}>{msg}</div>}
    </div>
  );
}
