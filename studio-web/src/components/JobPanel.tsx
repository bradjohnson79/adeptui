import { useEffect, useState } from "react";
import type { Job, Project } from "../types";
import { api } from "../api";
import { HelpTip, PanelHeading } from "./HelpTip";

export function JobPanel({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const list = await api.listJobs(projectId);
        if (!alive) return;
        setJobs(list);
        if (list.some((j) => j.status === "done")) onDone();
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [projectId, onDone]);

  return (
    <div className="panel">
      <PanelHeading
        title="Render queue"
        tip="Live jobs for scene renders, timeline stitches, lip sync, and image tools. Cancel running work here."
      />
      {jobs.length === 0 && <div className="empty">No jobs yet</div>}
      {jobs.slice(0, 8).map((j) => (
        <div className="job-item" key={j.id}>
          <div className="scene-head">
            <strong>{j.kind}</strong>
            <span className="scene-meta">{j.status}</span>
          </div>
          <div className="scene-meta">{j.message}</div>
          <div className="bar">
            <i style={{ width: `${Math.round((j.progress || 0) * 100)}%` }} />
          </div>
          {(j.status === "queued" || j.status === "running") && (
            <button style={{ marginTop: 8 }} onClick={() => api.cancelJob(j.id)}>
              Cancel
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export function PreviewPlayer({ project }: { project: Project }) {
  const latest =
    project.scenes
      .flatMap((s) => [s.lipsync_output_path, s.output_path])
      .find((p) => !!p) || null;

  // Prefer newest scene output with path
  const sceneOut = [...project.scenes].reverse().find((s) => s.lipsync_output_path || s.output_path);
  const path = sceneOut?.lipsync_output_path || sceneOut?.output_path || latest;

  return (
    <div className="panel preview">
      <PanelHeading
        title="Preview"
        tip="Plays the latest rendered scene or lip-synced output so you can review motion before exporting."
      />
      {path ? (
        <video key={path} src={api.mediaUrl(path)} controls />
      ) : (
        <div className="empty">Render a scene to preview</div>
      )}
    </div>
  );
}

export function AdvancedPanel({ project, onChange }: { project: Project; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [falKeyInput, setFalKeyInput] = useState("");
  const [falStatus, setFalStatus] = useState<{ configured: boolean; hint?: string | null } | null>(null);
  const [falMsg, setFalMsg] = useState<string | null>(null);
  const [busyFal, setBusyFal] = useState(false);
  const [falUsage, setFalUsage] = useState<Awaited<ReturnType<typeof api.falUsage>> | null>(null);
  const [busyUsage, setBusyUsage] = useState(false);

  const refreshFalUsage = async () => {
    setBusyUsage(true);
    try {
      const u = await api.falUsage(30);
      setFalUsage(u);
    } catch {
      setFalUsage(null);
    } finally {
      setBusyUsage(false);
    }
  };

  useEffect(() => {
    api.falKeyStatus()
      .then((st) => {
        setFalStatus(st);
        if (st.configured) refreshFalUsage();
      })
      .catch(() => setFalStatus({ configured: false }));
  }, []);

  const saveFalKey = async () => {
    const key = falKeyInput.trim();
    if (!key) return;
    setBusyFal(true);
    setFalMsg(null);
    try {
      const st = await api.falKeySet(key);
      setFalStatus(st);
      setFalKeyInput("");
      setFalMsg("API key saved securely on this machine.");
      await refreshFalUsage();
    } catch (err) {
      setFalMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyFal(false);
    }
  };

  const clearFalKey = async () => {
    setBusyFal(true);
    setFalMsg(null);
    try {
      const st = await api.falKeyClear();
      setFalStatus(st);
      setFalUsage(null);
      setFalMsg("API key cleared.");
    } catch (err) {
      setFalMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyFal(false);
    }
  };

  return (
    <div className="panel">
      <details className="advanced" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>
          <span className="summary-with-help">
            Advanced (Prompts, Preset, Seed, Default Engine)
            <HelpTip text="Project prompts, draft/quality preset, seed, local or fal.ai engines, and encrypted fal API key with usage." />
          </span>
        </summary>
        <div className="field">
          <label>Project name</label>
          <input
            value={project.name}
            onChange={(e) => api.updateProject(project.id, { name: e.target.value }).then(onChange)}
          />
        </div>
        <div className="field">
          <label>Global prompt</label>
          <textarea
            value={project.global_prompt}
            onChange={(e) => api.updateProject(project.id, { global_prompt: e.target.value }).then(onChange)}
          />
        </div>
        <div className="field">
          <label>Negative prompt</label>
          <textarea
            value={project.negative_prompt}
            onChange={(e) => api.updateProject(project.id, { negative_prompt: e.target.value }).then(onChange)}
          />
        </div>
        <div className="field">
          <label>Preset</label>
          <select
            value={project.preset}
            onChange={(e) =>
              api.updateProject(project.id, { preset: e.target.value as "draft" | "quality" }).then(onChange)
            }
          >
            <option value="draft">Draft (faster)</option>
            <option value="quality">Quality</option>
          </select>
        </div>
        <div className="field">
          <label>Seed (-1 = random/hash)</label>
          <input
            type="number"
            value={project.seed}
            onChange={(e) => api.updateProject(project.id, { seed: Number(e.target.value) }).then(onChange)}
          />
        </div>
        <div className="field">
          <label>Default engine</label>
          <select
            value={project.engine_default}
            onChange={(e) =>
              api
                .updateProject(project.id, { engine_default: e.target.value as Project["engine_default"] })
                .then(onChange)
            }
          >
            <optgroup label="Local (ComfyUI)">
              <option value="ltx">LTX 2.3</option>
              <option value="wan">WAN 2.2</option>
            </optgroup>
            <optgroup label="Cloud API (fal.ai)">
              <option value="fal_seedance">Seedance 2.0</option>
              <option value="fal_kling">Kling 2.5 Turbo Pro</option>
              <option value="fal_veo">Veo 3.1</option>
              <option value="fal_runway">Runway Gen-3 Turbo</option>
            </optgroup>
          </select>
          {String(project.engine_default).startsWith("fal_") && (
            <p className="scene-meta" style={{ marginTop: 6 }}>
              Cloud engines bill through your fal.ai account. Add a start image for best I2V results.
            </p>
          )}
        </div>
        <div className="field">
          <label>fal.ai API key</label>
          <p className="scene-meta" style={{ marginTop: 0 }}>
            Stored encrypted on this machine only (never sent to the browser after save). Get a key at{" "}
            <a href="https://fal.ai/dashboard/keys" target="_blank" rel="noreferrer">
              fal.ai/dashboard/keys
            </a>
            .
          </p>
          {falStatus?.configured ? (
            <div className="scene-meta" style={{ marginBottom: 6 }}>
              Saved key: <code>{falStatus.hint}</code>
            </div>
          ) : (
            <div className="scene-meta" style={{ marginBottom: 6 }}>
              No fal.ai key saved yet.
            </div>
          )}
          <input
            type="password"
            autoComplete="off"
            placeholder={falStatus?.configured ? "Paste to replace key…" : "Paste fal.ai API key…"}
            value={falKeyInput}
            onChange={(e) => setFalKeyInput(e.target.value)}
            disabled={busyFal}
          />
          <div className="row-actions" style={{ marginTop: 8 }}>
            <button type="button" className="primary" disabled={busyFal || !falKeyInput.trim()} onClick={saveFalKey}>
              {busyFal ? "Saving…" : "Save key"}
            </button>
            {falStatus?.configured && (
              <button type="button" disabled={busyFal} onClick={clearFalKey}>
                Clear key
              </button>
            )}
          </div>
          {falMsg && <div className="scene-meta" style={{ marginTop: 6 }}>{falMsg}</div>}
          {(falStatus?.configured || falUsage) && (
            <div className="fal-usage-card">
              <div className="fal-usage-head">
                <strong>fal.ai usage</strong>
                <button type="button" className="ghost" disabled={busyUsage} onClick={refreshFalUsage}>
                  {busyUsage ? "Refreshing…" : "Refresh"}
                </button>
              </div>
              {falUsage?.ok ? (
                <>
                  <div className="fal-usage-grid">
                    <div>
                      <div className="scene-meta">Credit balance</div>
                      <div className="fal-usage-value">
                        {falUsage.balance == null
                          ? "—"
                          : `${falUsage.currency} ${falUsage.balance.toFixed(2)}`}
                      </div>
                    </div>
                    <div>
                      <div className="scene-meta">Spent (last {falUsage.period_days}d)</div>
                      <div className="fal-usage-value">
                        {falUsage.currency} {falUsage.spend.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div className="scene-meta">Usage</div>
                      <div className="fal-usage-value">
                        {falUsage.usage_units} {falUsage.usage_unit_label}
                      </div>
                    </div>
                  </div>
                  {falUsage.username && (
                    <div className="scene-meta" style={{ marginTop: 6 }}>
                      Account: {falUsage.username}
                    </div>
                  )}
                  {falUsage.top_endpoints?.length > 0 && (
                    <ul className="fal-usage-endpoints">
                      {falUsage.top_endpoints.slice(0, 3).map((e) => (
                        <li key={e.endpoint_id}>
                          <span>{e.endpoint_id.split("/").slice(-2).join("/")}</span>
                          <span>
                            {e.currency} {e.cost.toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : (
                <div className="scene-meta">{falUsage?.message || "Loading usage…"}</div>
              )}
              <div className="fal-usage-links">
                <a href={falUsage?.login_url || "https://fal.ai/login"} target="_blank" rel="noreferrer">
                  Log in to fal.ai
                </a>
                <a href={falUsage?.manage_url || "https://fal.ai/dashboard/usage"} target="_blank" rel="noreferrer">
                  Usage dashboard
                </a>
                <a href={falUsage?.billing_url || "https://fal.ai/dashboard/billing"} target="_blank" rel="noreferrer">
                  Billing
                </a>
                <a href={falUsage?.keys_url || "https://fal.ai/dashboard/keys"} target="_blank" rel="noreferrer">
                  Manage keys
                </a>
              </div>
              {falUsage?.needs_admin_key && (
                <div className="scene-meta" style={{ marginTop: 6 }}>
                  Tip: create an <strong>ADMIN</strong> scope key on fal for live balance/spend (API-scope keys can
                  still run generations).
                </div>
              )}
            </div>
          )}
        </div>
        <div className="row-actions">
          <button onClick={() => api.exportPack(project.id).then(onChange)}>Export pack</button>
        </div>
      </details>
    </div>
  );
}
