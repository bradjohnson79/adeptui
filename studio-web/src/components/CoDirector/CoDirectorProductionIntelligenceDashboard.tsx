import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";

type DashboardPayload = {
  projectId?: string;
  specialists?: { count?: number; inventory?: Array<{ id?: string; name?: string; role?: string }> };
  stage?: string;
  pendingApprovals?: unknown[];
  health?: Record<string, unknown>;
  blockers?: unknown[];
  timelineStatus?: Record<string, unknown>;
  providerHealthNote?: string;
  reasoningModel?: string;
  executionHistory?: unknown[];
  reviewLoops?: unknown[];
  platform?: Record<string, unknown>;
};

export function CoDirectorProductionIntelligenceDashboard({
  projectId,
  enabled,
  sceneId,
}: {
  projectId: string;
  enabled: boolean;
  sceneId?: string;
}) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [m212Pending, setM212Pending] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled || !projectId) return;
    setError(null);
    setBusy(true);
    try {
      const res = (await api.m211Dashboard(projectId)) as DashboardPayload;
      setData(res);
      try {
        const m212 = await api.m212Dashboard(projectId);
        setM212Pending(Array.isArray(m212?.pendingApprovals) ? m212.pendingApprovals.length : 0);
      } catch {
        setM212Pending(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Production Intelligence");
    } finally {
      setBusy(false);
    }
  }, [enabled, projectId]);

  useEffect(() => {
    if (!enabled || !open) return;
    void refresh();
  }, [enabled, open, refresh, sceneId]);

  if (!enabled) return null;

  const inventory = data?.specialists?.inventory || [];
  const pending = data?.pendingApprovals || [];
  const blockers = data?.blockers || [];
  const history = data?.executionHistory || [];

  return (
    <div className="codirector-executive" data-testid="codirector-m211-dashboard">
      <div className="codirector-executive-header">
        <div>
          <p className="scene-meta">Production Intelligence</p>
          <p className="muted">Advise-only orchestration — no silent bible/timeline mutation.</p>
        </div>
        <button
          type="button"
          className="ghost"
          data-testid="toggle-m211-dashboard"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide" : "Open"} dashboard
        </button>
      </div>

      {open && (
        <div className="codirector-executive-body" data-testid="m211-dashboard-body">
          <div className="row-actions">
            <button type="button" className="ghost" disabled={busy} onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {!error && !data && busy && <p className="muted">Loading…</p>}
          {data && (
            <>
              <section data-testid="m211-active-specialists">
                <p className="scene-meta">Active specialists</p>
                <p className="muted">{data.specialists?.count ?? inventory.length} registered</p>
                <ul className="assistant-setup-list">
                  {inventory.slice(0, 12).map((s) => (
                    <li key={s.id || s.name}>{s.name || s.id}</li>
                  ))}
                </ul>
              </section>
              <section data-testid="m211-stage">
                <p className="scene-meta">Stage</p>
                <p>{data.stage || "idle"}</p>
              </section>
              <section data-testid="m211-pending-approvals">
                {m212Pending != null && (
                  <p className="scene-meta" data-testid="m212-pending-hook">
                    Learning Evolution pending: {m212Pending}
                  </p>
                )}

                <p className="scene-meta">Pending approvals</p>
                <p>{pending.length}</p>
              </section>
              <section data-testid="m211-health">
                <p className="scene-meta">Health</p>
                <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(data.health || {}, null, 2)}
                </pre>
              </section>
              <section data-testid="m211-blockers">
                <p className="scene-meta">Blockers</p>
                <p>{blockers.length}</p>
              </section>
              <section data-testid="m211-timeline-status">
                <p className="scene-meta">Timeline status</p>
                <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(data.timelineStatus || {}, null, 2)}
                </pre>
              </section>
              <section data-testid="m211-provider-health">
                <p className="scene-meta">Provider health</p>
                <p className="muted">{data.providerHealthNote || "No new providers; manifest unchanged."}</p>
              </section>
              <section data-testid="m211-reasoning-model">
                <p className="scene-meta">Reasoning model</p>
                <p>{data.reasoningModel || "gemma"}</p>
              </section>
              <section data-testid="m211-execution-history">
                <p className="scene-meta">Execution history</p>
                <p>{history.length} traces</p>
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
