import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import EnvironmentViewport from "./EnvironmentViewport";

type Dashboard = {
  categories?: Record<string, string>;
  readiness?: string;
  currentStage?: string;
  blockers?: unknown[];
};

const css = `
.m213-page { min-height: 100vh; background: linear-gradient(160deg,#12151a 0%,#1c2430 45%,#152028 100%); color:#e8eef5; font-family: "Segoe UI", sans-serif; }
.m213-hero { padding: 1.25rem 1.5rem; border-bottom: 1px solid rgba(255,255,255,0.08); }
.m213-hero h1 { margin: 0; font-size: 1.55rem; letter-spacing: 0.02em; }
.m213-hero p { margin: 0.35rem 0 0; opacity: 0.8; max-width: 52rem; }
.m213-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 1rem; padding: 1rem 1.5rem 2rem; }
.m213-panel { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0.9rem; }
.m213-panel h2 { margin: 0 0 0.6rem; font-size: 1rem; }
.m213-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-bottom: 0.6rem; }
.m213-row button, .m213-bookmarks button { background:#2b3644; color:#e8eef5; border:1px solid #3b4a5c; border-radius:6px; padding:0.35rem 0.65rem; cursor:pointer; }
.m213-row button:disabled { opacity: 0.45; cursor: not-allowed; }
.m213-viewport { display:flex; flex-direction:column; gap:0.4rem; min-height: 360px; }
.m213-viewport-canvas { flex:1; min-height: 320px; border-radius:8px; overflow:hidden; border:1px solid rgba(255,255,255,0.08); }
.m213-viewport-toolbar, .m213-bookmarks { display:flex; flex-wrap:wrap; gap:0.4rem; align-items:center; font-size:0.85rem; }
.m213-badge { background:#5a3d12; color:#ffd79a; padding:0.15rem 0.45rem; border-radius:4px; font-size:0.75rem; }
.m213-log { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 0.78rem; max-height: 240px; overflow:auto; background:#0d1116; padding:0.6rem; border-radius:6px; }
.m213-cats { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:0.35rem; font-size:0.85rem; }
.m213-cat { padding:0.35rem 0.45rem; border-radius:6px; background:rgba(0,0,0,0.25); }
@media (max-width: 960px) { .m213-grid { grid-template-columns: 1fr; } }
`;

export default function EnvironmentStudioWorkspace() {
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [projectId, setProjectId] = useState("m213-demo");
  const [environmentId, setEnvironmentId] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [log, setLog] = useState("Ready.");
  const [busy, setBusy] = useState(false);
  const honesty = useMemo(() => {
    const adapters = (status?.adapters as Array<Record<string, unknown>> | undefined) || [];
    return adapters.map((a) => `${a.name}: available=${a.available} fixture=${a.fixture}`).join(" | ");
  }, [status]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await api.m213Status();
        if (cancelled) return;
        setStatus(s);
        setEnabled(Boolean(s.enabled));
        setLog((prev) => prev + `\nStatus flag=${s.flag} enabled=${s.enabled}`);
      } catch (err) {
        if (!cancelled) setLog(`Status error: ${err}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      const out = await fn();
      setLog((prev) => prev + `\n[${label}] ` + JSON.stringify(out, null, 2).slice(0, 2500));
      return out as Record<string, unknown>;
    } catch (err) {
      setLog((prev) => prev + `\n[${label} ERROR] ${err}`);
      return null;
    } finally {
      setBusy(false);
    }
  };

  const createSpin = async () => {
    const out = await run("camera-spin", () =>
      api.m213CameraSpin({ projectId, title: "UI Spin Env", fixture: true, level: "C1_panorama" }),
    );
    if (out?.environmentId) setEnvironmentId(String(out.environmentId));
  };

  const approveEnv = async () => {
    if (!environmentId) return;
    await run("approve-env", () => api.m213ApproveEnv(environmentId, { note: "ui approve" }));
  };

  const runE2E = async () => {
    const out = await run("e2e-guided", () => api.m213E2EGuided({ projectId, fixture: true }));
    if (out?.environmentId) setEnvironmentId(String(out.environmentId));
    if ((out?.plan as { id?: string } | undefined)?.id) {
      const pid = String((out!.plan as { id: string }).id);
      setPlanId(pid);
      const dash = await run("dashboard", () => api.m213PlanDashboard(pid));
      if (dash) setDashboard(dash as Dashboard);
    }
  };

  return (
    <div className="m213-page" data-testid="environment-studio">
      <style>{css}</style>
      <header className="m213-hero">
        <div className="m213-row">
          <Link to="/">Home</Link>
          <span className="m213-badge">{enabled ? "FLAG ON" : "FLAG DEFAULT OFF"}</span>
          <span className="m213-badge">M2.13</span>
        </div>
        <h1>3D &amp; Virtual Environment Studio</h1>
        <p>
          Native Adept UI destination for import, camera-spin, reconstruction adapters, theme,
          blocking, camera/lighting, VPC A–Z protocol, and concept-to-timeline — with persisted
          approvals and honest fixture/mock labels.
        </p>
      </header>
      <div className="m213-grid">
        <section className="m213-panel">
          <h2>Viewport</h2>
          <EnvironmentViewport fixture />
          <div className="m213-row" style={{ marginTop: "0.75rem" }}>
            <label>
              Project{" "}
              <input value={projectId} onChange={(e) => setProjectId(e.target.value)} />
            </label>
            <button type="button" disabled={!enabled || busy} onClick={createSpin}>
              Route C: Camera-spin
            </button>
            <button type="button" disabled={!enabled || busy || !environmentId} onClick={approveEnv}>
              Approve Environment
            </button>
            <button type="button" disabled={!enabled || busy} onClick={runE2E}>
              Guided E2E (fixture)
            </button>
          </div>
          <p style={{ fontSize: "0.85rem", opacity: 0.75 }}>
            Env: {environmentId || "—"} · Plan: {planId || "—"}
          </p>
          <p style={{ fontSize: "0.8rem", opacity: 0.7 }}>Adapters: {honesty || "—"}</p>
        </section>
        <section className="m213-panel">
          <h2>VPC Coordination</h2>
          <div className="m213-cats">
            {Object.entries(dashboard?.categories || {}).map(([k, v]) => (
              <div key={k} className="m213-cat">
                <strong>{k}</strong>: {v}
              </div>
            ))}
          </div>
          <p style={{ marginTop: "0.75rem" }}>
            Stage: {dashboard?.currentStage || "—"} · Readiness: {dashboard?.readiness || "—"}
          </p>
          <h2 style={{ marginTop: "1rem" }}>Activity</h2>
          <div className="m213-log">{log}</div>
        </section>
      </div>
    </div>
  );
}
